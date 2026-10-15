from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from products.models import Product


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        cls.tote = Product.objects.create(name="Tote", price=Decimal("2.50"), stock=10)

    def add(self, product, quantity=1, **extra):
        return self.client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": quantity, **extra})

    def test_add_and_view_cart_totals(self):
        self.add(self.mug, 2)
        self.add(self.tote, 3)
        self.add(self.mug, 1)  # merges with the existing line
        response = self.client.get(reverse("orders:cart"))
        cart = response.context["cart"]
        self.assertEqual(cart.item_count, 6)
        self.assertEqual(cart.total, Decimal("37.50"))
        self.assertContains(response, "$37.50")
        self.assertContains(response, "cart-link__count")

    def test_cannot_exceed_stock(self):
        response = self.add(self.mug, 6)
        self.assertEqual(self.client.session.get("cart", {}), {})
        response = self.client.get(response.url)
        self.assertContains(response, "Only 5 of Mug available.")
        self.assertContains(response, "error-card")

    def test_sold_out_and_unknown_products_are_rejected(self):
        sold_out = Product.objects.create(name="Gone", price=Decimal("1.00"), stock=0)
        self.client.get(self.add(sold_out).url)
        self.assertNotIn(str(sold_out.pk), self.client.session.get("cart", {}))
        response = self.client.post(reverse("orders:cart_add", args=[999999]), follow=True)
        self.assertContains(response, "no longer available")

    def test_update_and_remove(self):
        self.add(self.mug, 2)
        self.client.post(reverse("orders:cart_update", args=[self.mug.pk]), {"quantity": 4})
        self.assertEqual(self.client.session["cart"], {str(self.mug.pk): 4})
        self.client.post(reverse("orders:cart_update", args=[self.mug.pk]), {"quantity": 0})
        self.assertEqual(self.client.session["cart"], {})
        self.add(self.tote)
        self.client.post(reverse("orders:cart_remove", args=[self.tote.pk]))
        self.assertEqual(self.client.session["cart"], {})

    def test_invalid_quantity_shows_error(self):
        response = self.add(self.mug, "abc")
        response = self.client.get(response.url)
        self.assertContains(response, "Quantity must be a whole number.")

    def test_deactivated_product_drops_out_of_cart(self):
        self.add(self.tote)
        Product.objects.filter(pk=self.tote.pk).update(is_active=False)
        response = self.client.get(reverse("orders:cart"))
        self.assertTrue(response.context["cart"].is_empty)

    def test_add_redirects_back_to_safe_next_only(self):
        detail = self.mug.get_absolute_url()
        self.assertRedirects(self.add(self.mug, next=detail), detail)
        response = self.add(self.mug, next="https://evil.example.com/")
        self.assertEqual(response.url, reverse("orders:cart"))

    def test_cart_mutations_require_post(self):
        response = self.client.get(reverse("orders:cart_add", args=[self.mug.pk]))
        self.assertEqual(response.status_code, 405)
