from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from products.models import Product

PASSWORD = "a-Strong-test-pass-91"


class AuthTests(TestCase):
    def register(self, **overrides):
        data = {"username": "sam", "email": "sam@example.com", "password1": PASSWORD, "password2": PASSWORD}
        data.update(overrides)
        return self.client.post(reverse("register"), data)

    def test_register_creates_user_and_logs_in(self):
        response = self.register()
        self.assertRedirects(response, reverse("products:list"))
        user = User.objects.get(username="sam")
        self.assertEqual(user.email, "sam@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_register_validation_errors_are_shown(self):
        User.objects.create_user("taken", "dup@example.com", PASSWORD)
        response = self.register(email="DUP@example.com", password2="mismatch")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertContains(response, "field--invalid")
        self.assertFalse(User.objects.filter(username="sam").exists())

    def test_login_failure_shows_error_card(self):
        response = self.client.post(reverse("login"), {"username": "nobody", "password": "wrong"})
        self.assertContains(response, "error-card")

    def cart_quantities(self):
        return {line.product.name: line.quantity for line in self.client.get(reverse("orders:cart")).context["cart"].lines}

    def test_guest_cart_moves_into_account_and_survives_logout(self):
        user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        self.client.post(reverse("orders:cart_add", args=[mug.pk]), {"quantity": 2})

        response = self.client.post(reverse("login"), {"username": "sam", "password": PASSWORD})
        self.assertRedirects(response, reverse("products:list"))
        self.assertEqual(self.client.session.get("cart"), {})  # moved out of the session...
        self.assertEqual(list(user.cart_items.values_list("product__name", "quantity")), [("Mug", 2)])  # ...into the account

        response = self.client.get(reverse("orders:cart"))
        self.assertContains(response, "Log out")
        self.assertNotContains(response, "Log in to check out")

        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.cart_quantities(), {})  # guests don't see the account cart

        self.client.post(reverse("login"), {"username": "sam", "password": PASSWORD})
        self.assertEqual(self.cart_quantities(), {"Mug": 2})  # still there after logging back in

    def test_login_adds_guest_items_to_existing_account_cart(self):
        user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=9)
        tote = Product.objects.create(name="Tote", price=Decimal("2.50"), stock=9)
        user.cart_items.create(product=mug, quantity=1)

        self.client.post(reverse("orders:cart_add", args=[mug.pk]), {"quantity": 2})
        self.client.post(reverse("orders:cart_add", args=[tote.pk]), {"quantity": 1})
        self.client.post(reverse("login"), {"username": "sam", "password": PASSWORD})

        self.assertEqual(self.cart_quantities(), {"Mug": 3, "Tote": 1})

    def test_signed_in_cart_changes_are_saved_to_the_account(self):
        user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=9)
        self.client.force_login(user)
        self.client.post(reverse("orders:cart_add", args=[mug.pk]), {"quantity": 2})
        self.client.post(reverse("orders:cart_update", args=[mug.pk]), {"quantity": 5})
        self.assertEqual(user.cart_items.get().quantity, 5)
        self.assertContains(self.client.get(reverse("products:list")), 'cart-link__count">5<')
        self.client.post(reverse("orders:cart_remove", args=[mug.pk]))
        self.assertFalse(user.cart_items.exists())
