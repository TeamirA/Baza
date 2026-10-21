"""Fills the store with a real product catalog for demos.

The catalog lives in products/data/catalog.json: about 180 products with
brands, prices, stock, warranty/shipping/returns details and up to three
photos each, taken from DummyJSON (https://dummyjson.com), a free product
dataset for demo stores. Photos are downloaded from its CDN, put on a white
background and saved through the normal upload path (WebP sizes, stored in
Vercel Blob in production). Each product also gets the dataset's sample
reviews, which the site labels "Sample review" (not "Verified purchase").

The first run creates the categories and products in one go and retires the
old drawn sample products (hidden, not deleted, so past orders still show
them). Later runs only fill what's still missing (empty photo slots, products
without sample reviews), so products deleted in the admin don't come back.
"""

import io
import json
import time
import urllib.request
from collections import OrderedDict
from datetime import datetime, time as day_time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image

from products.images import ImageProcessingError
from products.models import Category, Product, ProductImage, Review
from products.repositories import ProductImageRepository
from products.services import ImageUploadError, ProductImageService

CATALOG_FILE = Path(__file__).resolve().parents[2] / "data" / "catalog.json"

# The drawn products from the first version of the store.
LEGACY_SAMPLE_SLUGS = [
    "classic-cotton-tee", "everyday-hoodie", "canvas-cap", "ceramic-mug", "linen-throw-pillow",
    "soy-candle", "leather-card-holder", "canvas-tote-bag", "steel-water-bottle",
]

DOWNLOAD_TIMEOUT = 25  # seconds per attempt
DOWNLOAD_ATTEMPTS = 4
RETRY_PAUSE = 2  # seconds, growing with each attempt
MAX_PHOTO_BYTES = 8 * 1024 * 1024


def load_catalog(path=CATALOG_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["products"]


def interleave(items, key):
    """Round-robin across groups, so the first page of "Newest" shows a mix of
    categories instead of 12 kitchen items in a row."""
    groups = OrderedDict()
    for item in items:
        groups.setdefault(key(item), []).append(item)
    queues = list(groups.values())
    mixed = []
    while any(queues):
        for queue in queues:
            if queue:
                mixed.append(queue.pop(0))
    return mixed


def product_details(item):
    rows = [("SKU", item.get("sku")), ("Warranty", item.get("warranty")),
            ("Shipping", item.get("shipping")), ("Returns", item.get("returns"))]
    return [[label, value] for label, value in rows if value]


def download(url, attempts=DOWNLOAD_ATTEMPTS):
    """Fetches a photo, retrying: the catalog's CDN sometimes times out (HTTP 522)
    and then serves the same file fine a moment later."""
    request = urllib.request.Request(url, headers={"User-Agent": "Baza catalog seeder"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
                data = response.read(MAX_PHOTO_BYTES + 1)
            break
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(RETRY_PAUSE * attempt)
    if len(data) > MAX_PHOTO_BYTES:
        raise ImageUploadError("photo is too large")
    return data


def on_white(data):
    """Catalog photos have transparent backgrounds; shops show products on white,
    and transparent PNGs would vanish into the dark theme's card colour."""
    image = Image.open(io.BytesIO(data))
    image.load()
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "PNG")
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Create the demo catalog (real products and photos). Safe to run again: only fills what's missing."

    def add_arguments(self, parser):
        parser.add_argument("--no-photos", action="store_true", help="Create products without downloading photos.")
        parser.add_argument("--workers", type=int, default=10, help="Products processed in parallel (default 10).")

    def handle(self, *args, no_photos=False, workers=10, **options):
        catalog = load_catalog()
        skus = [item["sku"] for item in catalog]
        if Product.objects.filter(sku__in=skus).exists():
            self.stdout.write("Catalog already seeded; filling in anything missing.")
        else:
            self.create_catalog(catalog)
        self.add_sample_reviews(catalog)
        if not no_photos:
            self.add_missing_photos(catalog, max(1, workers))

    @transaction.atomic
    def add_sample_reviews(self, catalog):
        """Adds the dataset's reviews to catalog products that have no sample reviews yet."""
        reviews_by_sku = {item["sku"]: item.get("reviews", []) for item in catalog}
        reviewed = set(Review.objects.filter(is_sample=True).values_list("product_id", flat=True))
        pending = []  # (review, date) pairs
        for product in Product.objects.filter(sku__in=reviews_by_sku).exclude(pk__in=reviewed).only("id", "sku"):
            for r in reviews_by_sku[product.sku]:
                review = Review(product=product, author_name=r["name"], rating=r["rating"], title=r["comment"], is_sample=True)
                pending.append((review, r.get("date")))
        if not pending:
            return
        Review.objects.bulk_create([review for review, _ in pending])
        # created_at is auto-set on insert; put back the dataset's dates so they read naturally.
        for review, date in pending:
            if date:
                when = timezone.make_aware(datetime.combine(datetime.strptime(date, "%Y-%m-%d").date(), day_time(12)))
                Review.objects.filter(pk=review.pk).update(created_at=when, updated_at=when)
        self.stdout.write(self.style.SUCCESS(f"Added {len(pending)} sample review(s)."))

    @transaction.atomic
    def create_catalog(self, catalog):
        categories = {}
        for name in sorted({item["category"] for item in catalog}):
            categories[name], _ = Category.objects.get_or_create(name=name)

        taken = set(Product.objects.values_list("slug", flat=True))
        # Newest first is the default sort, so create the mix in reverse.
        for item in reversed(interleave(catalog, key=lambda i: i["category"])):
            slug = base = slugify(item["name"])[:200]
            n = 2
            while slug in taken:
                slug, n = f"{base}-{n}", n + 1
            taken.add(slug)
            Product.objects.create(
                name=item["name"],
                slug=slug,
                brand=item.get("brand", ""),
                sku=item["sku"],
                category=categories[item["category"]],
                description=item["description"],
                price=Decimal(item["price"]),
                stock=item["stock"],
                details=product_details(item),
            )
        retired = Product.objects.filter(slug__in=LEGACY_SAMPLE_SLUGS, is_active=True).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(
            f"Created {len(catalog)} products in {len(categories)} categories; retired {retired} drawn sample product(s)."
        ))

    def add_missing_photos(self, catalog, workers):
        photos_by_sku = {item["sku"]: item.get("images", []) for item in catalog}
        # Each catalog photo has a fixed slot (its position); fill the empty slots,
        # so a product that got 1 of 3 photos last time gets the other 2 now.
        filled = {}
        for product_id, position in ProductImage.objects.filter(product__sku__in=photos_by_sku).values_list(
            "product_id", "position"
        ):
            filled.setdefault(product_id, set()).add(position)
        todo = []
        for product in Product.objects.filter(sku__in=photos_by_sku).values("id", "slug", "name", "sku"):
            missing = [
                (position, url) for position, url in enumerate(photos_by_sku[product["sku"]])
                if position not in filled.get(product["id"], set())
            ]
            if missing:
                todo.append((product, missing))
        if not todo:
            self.stdout.write("Every catalog product has all its photos.")
            return
        self.stdout.write(f"Adding photos to {len(todo)} product(s) with {workers} workers...")

        service = ProductImageService()
        records = ProductImageRepository()

        def prepare_product(product, missing):
            """Download, flatten, resize and upload one product's photos (no database work)."""
            done, problems = [], []
            for position, url in missing:
                try:
                    processed = service.prepare(on_white(download(url)))
                    variants = service.upload(product["slug"], processed)
                    done.append((position, variants, processed.width, processed.height))
                except (OSError, ImageUploadError, ImageProcessingError, ValueError) as e:
                    problems.append(f"{product['name']}: {url} ({e})")
            return product, done, problems

        added = finished = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(prepare_product, p, missing) for p, missing in todo]):
                product, done, problems = future.result()
                for position, variants, width, height in done:
                    alt = product["name"] if position == 0 else f"{product['name']}, view {position + 1}"
                    records.create(product["id"], variants, width, height, alt, position)
                    added += 1
                for problem in problems:
                    self.stderr.write(self.style.WARNING(f"Skipped a photo for {problem}"))
                finished += 1
                if finished % 25 == 0:
                    self.stdout.write(f"  {finished}/{len(todo)} products done")
        self.stdout.write(self.style.SUCCESS(f"Added {added} photo(s)."))
