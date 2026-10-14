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
    help = "Create sample categories and products (idempotent)."

    def handle(self, *args, **options):
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
