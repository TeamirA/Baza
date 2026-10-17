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
        self.assertContains(response, "3 in stock")

    def test_missing_or_inactive_product_returns_404_with_error_card(self):
        for slug in ["does-not-exist", self.hidden.slug]:
            response = self.client.get(reverse("products:detail", args=[slug]))
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, "error-card", status_code=404)


class LayoutTests(TestCase):
    def test_every_page_has_skip_link_and_theme_toggle(self):
        for url in [reverse("products:list"), reverse("orders:cart"), reverse("login")]:
            response = self.client.get(url)
            self.assertContains(response, 'href="#main"')
            self.assertContains(response, 'id="main"')
            self.assertContains(response, "data-theme-toggle")
            # The saved theme is applied in <head>, before first paint.
            self.assertLess(response.content.index(b'localStorage.getItem("theme")'), response.content.index(b"<body>"))
