import io
import json
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from ..management.commands import seed_products
from ..models import Category, Product, ProductImage
from .test_images import FakeStore


def transparent_png(size=900):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.paste((200, 30, 30, 255), (300, 300, 600, 600))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def run(**options):
    call_command("seed_products", stdout=io.StringIO(), stderr=io.StringIO(), **options)


class CatalogFileTests(TestCase):
    def test_catalog_is_real_and_complete(self):
        catalog = seed_products.load_catalog()
        self.assertGreaterEqual(len(catalog), 150)
        self.assertEqual(len({p["sku"] for p in catalog}), len(catalog))
        self.assertEqual(len({p["name"] for p in catalog}), len(catalog))
        for item in catalog:
            self.assertTrue(item["images"], item["name"])
            self.assertTrue(all(url.startswith("https://") for url in item["images"]))
            self.assertGreater(Decimal(item["price"]), 0)


class SeedCatalogTests(TestCase):
    def test_creates_catalog_mixed_and_retires_drawn_samples(self):
        drawn = Product.objects.create(name="Ceramic Mug", slug="ceramic-mug", price=Decimal("14.50"), stock=3)
        run(no_photos=True)

        catalog = seed_products.load_catalog()
        self.assertEqual(Product.objects.filter(is_active=True).count(), len(catalog))
        self.assertEqual(Category.objects.count(), len({p["category"] for p in catalog}))
        drawn.refresh_from_db()
        self.assertFalse(drawn.is_active)  # hidden, but old orders can still show it

        first_page = list(Product.objects.filter(is_active=True).order_by("-created_at", "-pk")[:12])
        self.assertGreater(len({p.category_id for p in first_page}), 5)  # a mix, not one category

        phone = Product.objects.get(sku=catalog[0]["sku"])
        self.assertEqual(phone.brand, catalog[0]["brand"])
        self.assertIn(["SKU", catalog[0]["sku"]], phone.details)

    def test_second_run_adds_nothing_and_keeps_deletions(self):
        run(no_photos=True)
        Product.objects.filter(sku=seed_products.load_catalog()[0]["sku"]).delete()
        count = Product.objects.count()
        run(no_photos=True)
        self.assertEqual(Product.objects.count(), count)

    def test_product_page_shows_brand_and_details(self):
        run(no_photos=True)
        product = Product.objects.exclude(brand="").first()
        response = self.client.get(product.get_absolute_url())
        self.assertContains(response, "product-specs")
        self.assertContains(response, product.brand)


@override_settings(MAX_IMAGE_UPLOAD_BYTES=10 * 1024 * 1024)
class SeedPhotoTests(TestCase):
    def setUp(self):
        catalog = [
            {"sku": "T-1", "name": "Test Phone", "brand": "Acme", "category": "Electronics", "description": "A phone.",
             "price": "99.00", "stock": 5, "images": ["https://cdn.example/1.png", "https://cdn.example/2.png"]},
            {"sku": "T-2", "name": "Test Pan", "brand": "", "category": "Kitchen", "description": "A pan.",
             "price": "19.00", "stock": 0, "images": ["https://cdn.example/broken.png"]},
        ]
        patcher = mock.patch.object(seed_products, "load_catalog", return_value=catalog)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.store = FakeStore()
        patcher = mock.patch("products.services.get_media_store", return_value=self.store)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_download(self, url):
        if "broken" in url:
            raise OSError("404")
        return transparent_png()

    def test_photos_are_flattened_resized_and_recorded(self):
        with mock.patch.object(seed_products, "download", side_effect=self.fake_download):
            run(workers=2)
        phone = Product.objects.get(sku="T-1")
        self.assertEqual(list(phone.images.values_list("alt_text", flat=True)), ["Test Phone", "Test Phone, view 2"])
        cover = phone.images.first()
        self.assertEqual(sorted(cover.variants, key=int), ["400", "800", "900"])
        corner = Image.open(io.BytesIO(self.store.files[cover.variants["400"]])).convert("RGB").getpixel((2, 2))
        self.assertGreater(min(corner), 245)  # transparent background became white

        # The broken photo is skipped; a later run retries only what's missing.
        self.assertFalse(Product.objects.get(sku="T-2").images.exists())
        with mock.patch.object(seed_products, "download", return_value=transparent_png()) as download:
            run()
        self.assertEqual(download.call_count, 1)
        self.assertEqual(ProductImage.objects.count(), 3)

    def test_partly_photographed_products_get_their_missing_photos(self):
        with mock.patch.object(seed_products, "download", side_effect=self.fake_download):
            run(workers=2)
        phone = Product.objects.get(sku="T-1")
        phone.images.filter(position=1).delete()
        with mock.patch.object(seed_products, "download", return_value=transparent_png()) as download:
            run()
        self.assertEqual(sorted(phone.images.values_list("position", flat=True)), [0, 1])
        self.assertEqual(download.call_count, 2)  # phone's 2nd photo and the pan's broken one


class DownloadRetryTests(TestCase):
    def test_retries_flaky_cdn_then_gives_up(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"photo"
        with mock.patch.object(seed_products.time, "sleep"), mock.patch.object(
            seed_products.urllib.request, "urlopen", side_effect=[OSError("522"), response]
        ) as urlopen:
            self.assertEqual(seed_products.download("https://cdn.example/1.webp"), b"photo")
        self.assertEqual(urlopen.call_count, 2)

        with mock.patch.object(seed_products.time, "sleep"), mock.patch.object(
            seed_products.urllib.request, "urlopen", side_effect=OSError("522")
        ) as urlopen:
            with self.assertRaises(OSError):
                seed_products.download("https://cdn.example/1.webp")
        self.assertEqual(urlopen.call_count, seed_products.DOWNLOAD_ATTEMPTS)


class SampleReviewTests(TestCase):
    def test_sample_reviews_are_added_once_dated_and_labelled(self):
        from django.contrib.auth.models import User

        from orders.models import Order, OrderItem

        from ..models import Review

        run(no_photos=True)
        catalog = seed_products.load_catalog()
        expected = sum(len(item.get("reviews", [])) for item in catalog)
        self.assertGreater(expected, 300)
        self.assertEqual(Review.objects.filter(is_sample=True).count(), expected)
        run(no_photos=True)  # nothing doubles
        self.assertEqual(Review.objects.filter(is_sample=True).count(), expected)

        item = catalog[0]
        product = Product.objects.get(sku=item["sku"])
        review = product.reviews.order_by("created_at").first()
        self.assertIsNone(review.user)
        self.assertEqual(review.created_at.year, int(min(r["date"] for r in item["reviews"])[:4]))

        page = self.client.get(product.get_absolute_url())
        self.assertContains(page, "Sample review")
        self.assertContains(page, item["reviews"][0]["name"])
        self.assertNotContains(page, "Verified purchase")

        # A real buyer can still review alongside the samples, labelled as verified.
        buyer = User.objects.create_user("sam", "sam@example.com", "a-Strong-test-pass-91")
        order = Order.objects.create(user=buyer, full_name="Sam", email="sam@example.com", address="1 St", status="paid")
        OrderItem.objects.create(order=order, product=product, quantity=1, price=product.price)
        self.client.force_login(buyer)
        self.client.post(reverse("products:review", args=[product.slug]), {"rating": 5, "title": "Mine"})
        page = self.client.get(product.get_absolute_url())
        self.assertContains(page, "Verified purchase")
        self.assertEqual(page.context["product"].rating_count, len(item["reviews"]) + 1)


class DemoNoticeTests(TestCase):
    def test_notice_shows_test_card_and_can_be_turned_off(self):
        self.assertContains(self.client.get(reverse("products:list")), "Stripe test mode")
        with override_settings(DEMO_NOTICE=False):
            self.assertNotContains(self.client.get(reverse("products:list")), "Stripe test mode")
