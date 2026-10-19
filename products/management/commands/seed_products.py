from decimal import Decimal

from django.core.management.base import BaseCommand

from products.models import Category, Product

SEED = {
    "Apparel": [
        ("Classic Cotton Tee", "19.00", 40, "Heavyweight 100% cotton tee with a relaxed fit."),
        ("Everyday Hoodie", "48.00", 15, "Brushed fleece hoodie with a kangaroo pocket."),
        ("Canvas Cap", "22.00", 0, "Six-panel washed canvas cap with an adjustable strap."),
    ],
    "Home": [
        ("Ceramic Mug", "14.50", 60, "Stoneware mug, 350 ml, dishwasher safe."),
        ("Linen Throw Pillow", "32.00", 12, "Stonewashed linen cover with a feather insert."),
        ("Soy Candle", "18.00", 25, "Hand-poured soy wax candle, roughly 40 hours of burn time."),
    ],
    "Accessories": [
        ("Leather Card Holder", "35.00", 20, "Vegetable-tanned leather, holds up to six cards."),
        ("Canvas Tote Bag", "24.00", 30, "Sturdy 12 oz canvas tote with an inner pocket."),
        ("Steel Water Bottle", "29.00", 8, "Double-walled, keeps drinks cold for 24 hours."),
    ],
}


class Command(BaseCommand):
    help = "Create sample categories and products (idempotent). Optionally give them sample photos."

    def add_arguments(self, parser):
        parser.add_argument("--with-photos", action="store_true", help="Also add sample photos to products without any.")
        parser.add_argument("--photos-only", action="store_true", help="Only add sample photos; don't create products.")

    def handle(self, *args, with_photos=False, photos_only=False, **options):
        if not photos_only:
            self.seed_products()
        if with_photos or photos_only:
            self.seed_photos()

    def seed_products(self):
        created = 0
        for category_name, products in SEED.items():
            category, _ = Category.objects.get_or_create(name=category_name)
            for name, price, stock, description in products:
                _, was_created = Product.objects.get_or_create(
                    name=name,
                    defaults={
                        "category": category,
                        "price": Decimal(price),
                        "stock": stock,
                        "description": description,
                    },
                )
                created += was_created
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new product(s)."))

    def seed_photos(self):
        """Adds drawn sample photos to sample products that have no photos yet.
        Uses the real upload path, so on Vercel the files go to Blob."""
        from products.sample_photos import sample_photos
        from products.services import ImageUploadError, ProductImageService

        service = ProductImageService()
        added = 0
        for product in Product.objects.filter(images__isnull=True):
            for position, (data, view) in enumerate(sample_photos(product.slug)):
                try:
                    service.add_image(product.pk, data, alt_text=f"{product.name}, {view}", position=position)
                    added += 1
                except ImageUploadError as e:
                    self.stderr.write(self.style.WARNING(f"Couldn't add a photo to {product.name}: {e}"))
                    return
        self.stdout.write(self.style.SUCCESS(f"Added {added} sample photo(s)."))
