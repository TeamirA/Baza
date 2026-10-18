from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.home = Category.objects.create(name="Home")
        cls.mug = Product.objects.create(name="Ceramic Mug", price=Decimal("14.50"), stock=3, category=cls.home)
        cls.hidden = Product.objects.create(name="Hidden Thing", price=Decimal("1.00"), is_active=False)

    def test_list_shows_only_active_products(self):
        response = self.client.get(reverse("products:list"))
        self.assertContains(response, "Ceramic Mug")
        self.assertNotContains(response, "Hidden Thing")

    def test_list_filters_by_category_and_search(self):
        Product.objects.create(name="Tote Bag", price=Decimal("24.00"))
        response = self.client.get(reverse("products:list"), {"category": "home"})
        self.assertContains(response, "Ceramic Mug")
        self.assertNotContains(response, "Tote Bag")
        response = self.client.get(reverse("products:list"), {"q": "tote"})
        self.assertContains(response, "Tote Bag")
        self.assertNotContains(response, "Ceramic Mug")

    def test_unknown_category_shows_error_card(self):
        response = self.client.get(reverse("products:list"), {"category": "nope"})
        self.assertContains(response, "error-card")

    def test_detail_page(self):
        response = self.client.get(self.mug.get_absolute_url())
        self.assertContains(response, "$14.50")
        self.assertContains(response, "Only 3 left")
        self.assertContains(response, "data-qty-stepper")
        self.assertContains(response, 'max="3"')

    def test_missing_or_inactive_product_returns_404_with_error_card(self):
        for slug in ["does-not-exist", self.hidden.slug]:
            response = self.client.get(reverse("products:detail", args=[slug]))
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, "error-card", status_code=404)


class StockBadgeTests(TestCase):
    def test_badges_reflect_stock_level(self):
        Product.objects.create(name="Plenty", price=Decimal("1.00"), stock=50)
        Product.objects.create(name="Few", price=Decimal("1.00"), stock=5)
        Product.objects.create(name="None", price=Decimal("1.00"), stock=0)
        html = self.client.get(reverse("products:list")).content.decode()
        self.assertIn("In stock", html)
        self.assertIn("Only 5 left", html)
        self.assertIn("Sold out", html)


class LayoutTests(TestCase):
    def test_every_page_has_skip_link_and_theme_toggle(self):
        for url in [reverse("products:list"), reverse("orders:cart"), reverse("login")]:
            response = self.client.get(url)
            self.assertContains(response, 'href="#main"')
            self.assertContains(response, 'id="main"')
            self.assertContains(response, "data-theme-toggle")
            # The saved theme is applied in <head>, before first paint.
            self.assertLess(response.content.index(b'localStorage.getItem("theme")'), response.content.index(b"<body>"))


class RelatedProductsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.home = Category.objects.create(name="Home")
        cls.apparel = Category.objects.create(name="Apparel")
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5, category=cls.home)
        cls.candle = Product.objects.create(name="Candle", price=Decimal("8.00"), stock=5, category=cls.home)
        cls.pillow = Product.objects.create(name="Pillow", price=Decimal("30.00"), stock=0, category=cls.home)
        cls.tee = Product.objects.create(name="Tee", price=Decimal("19.00"), stock=9, category=cls.apparel)
        Product.objects.create(name="Hidden Lamp", price=Decimal("5.00"), stock=5, category=cls.home, is_active=False)

    def related_names(self, product):
        response = self.client.get(product.get_absolute_url())
        return response, [p.name for p in response.context["related"]]

    def test_same_category_first_in_stock_first_then_others(self):
        response, names = self.related_names(self.mug)
        self.assertEqual(names, ["Candle", "Pillow", "Tee"])  # home (in stock, then sold out), then other
        self.assertNotIn("Mug", names)
        self.assertNotIn("Hidden Lamp", names)
        self.assertContains(response, "You might also like")  # mixed categories

    def test_heading_names_category_when_all_suggestions_match(self):
        for i in range(4):
            Product.objects.create(name=f"Bowl {i}", price=Decimal("3.00"), stock=2, category=self.home)
        response, names = self.related_names(self.mug)
        self.assertEqual(len(names), 4)
        self.assertContains(response, "More in Home")
