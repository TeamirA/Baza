from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Product, SavedProduct


class WishlistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("sam", "sam@example.com", "a-Strong-test-pass-91")
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=3)
        cls.tote = Product.objects.create(name="Tote", price=Decimal("5.00"), stock=0)

    def toggle(self, product, json=False, **extra):
        headers = {"HTTP_ACCEPT": "application/json"} if json else {}
        return self.client.post(reverse("products:wishlist_toggle", args=[product.pk]), extra, **headers)

    def test_guests_get_a_login_link_that_returns_them(self):
        html = self.client.get(self.mug.get_absolute_url()).content.decode()
        self.assertIn('href="/accounts/login/?next=%2Fproducts%2Fmug%2F&amp;reason=save"', html)
        self.assertNotIn("data-wishlist ", html)
        response = self.toggle(self.mug)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))
        self.assertFalse(SavedProduct.objects.exists())

    def test_toggle_on_and_off_with_safe_redirect(self):
        self.client.force_login(self.user)
        response = self.toggle(self.mug, next="/products/mug/")
        self.assertRedirects(response, "/products/mug/")
        self.assertTrue(SavedProduct.objects.filter(user=self.user, product=self.mug).exists())
        page = self.client.get("/products/mug/").content.decode()
        self.assertIn('aria-pressed="true"', page)
        self.assertIn('data-wishlist-count>1<', page)
        self.toggle(self.mug, next="https://evil.example/")
        self.assertFalse(SavedProduct.objects.exists())

    def test_json_toggle_for_the_heart_script(self):
        self.client.force_login(self.user)
        self.assertEqual(self.toggle(self.mug, json=True).json(), {"saved": True, "count": 1})
        self.assertEqual(self.toggle(self.tote, json=True).json(), {"saved": True, "count": 2})
        self.assertEqual(self.toggle(self.mug, json=True).json(), {"saved": False, "count": 1})
        missing = self.client.post(reverse("products:wishlist_toggle", args=[999]), HTTP_ACCEPT="application/json")
        self.assertEqual(missing.status_code, 404)

    def test_saved_page_lists_items_and_hides_inactive(self):
        self.client.force_login(self.user)
        self.toggle(self.mug)
        self.toggle(self.tote)
        hidden = Product.objects.create(name="Gone", price=Decimal("1.00"), stock=1)
        self.toggle(hidden)
        Product.objects.filter(pk=hidden.pk).update(is_active=False)
        response = self.client.get(reverse("products:wishlist"))
        self.assertEqual([p.name for p in response.context["items"]], ["Tote", "Mug"])
        self.assertContains(response, "Move to cart", count=1)  # the tote is sold out

    def test_move_to_cart(self):
        self.client.force_login(self.user)
        self.toggle(self.mug)
        response = self.client.post(reverse("products:wishlist_move_to_cart", args=[self.mug.pk]), follow=True)
        self.assertContains(response, "Moved Mug to your cart.")
        self.assertEqual(self.user.cart_items.get().product, self.mug)
        self.assertFalse(SavedProduct.objects.exists())

    def test_move_to_cart_of_sold_out_item_explains(self):
        self.client.force_login(self.user)
        self.toggle(self.tote)
        response = self.client.post(reverse("products:wishlist_move_to_cart", args=[self.tote.pk]), follow=True)
        self.assertContains(response, "Tote is sold out.")
        self.assertTrue(SavedProduct.objects.exists())
