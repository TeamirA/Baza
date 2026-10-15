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

    def test_login_keeps_cart_and_logout_works(self):
        User.objects.create_user("sam", "sam@example.com", PASSWORD)
        mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        self.client.post(reverse("orders:cart_add", args=[mug.pk]), {"quantity": 2})

        response = self.client.post(reverse("login"), {"username": "sam", "password": PASSWORD})
        self.assertRedirects(response, reverse("products:list"))
        self.assertEqual(self.client.session["cart"], {str(mug.pk): 2})

        response = self.client.get(reverse("orders:cart"))
        self.assertContains(response, "Log out")
        self.assertNotContains(response, "Log in to check out")

        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
