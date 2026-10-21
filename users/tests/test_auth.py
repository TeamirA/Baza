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


from django.core import mail
from django.test import override_settings


@override_settings(EMAIL_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    def test_full_reset_flow(self):
        User.objects.create_user("sam", "sam@example.com", PASSWORD)
        self.assertContains(self.client.get(reverse("login")), "Forgot password?")

        response = self.client.post(reverse("password_reset"), {"email": "sam@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Reset your Baza password")
        link = next(line for line in mail.outbox[0].body.splitlines() if "/accounts/reset/" in line)

        response = self.client.get(link, follow=True)  # Django swaps the token for a session marker
        self.assertContains(response, "Choose a new password")
        new_password = "an0ther-Strong-pass"
        response = self.client.post(response.redirect_chain[-1][0], {"new_password1": new_password, "new_password2": new_password})
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.assertTrue(self.client.login(username="sam", password=new_password))

    def test_unknown_email_gets_same_response_and_no_mail(self):
        response = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(mail.outbox, [])

    def test_bad_link_explains_and_offers_a_new_one(self):
        response = self.client.get(reverse("password_reset_confirm", args=["MQ", "bad-token"]))
        self.assertContains(response, "Link expired")


@override_settings(EMAIL_ENABLED=False, DEBUG=False)
class PasswordResetWithoutEmailTests(TestCase):
    def test_link_hidden_and_form_explains(self):
        self.assertNotContains(self.client.get(reverse("login")), "Forgot password?")
        response = self.client.get(reverse("password_reset"))
        self.assertContains(response, "Password reset isn&#x27;t available yet")
        self.assertNotContains(response, 'name="email"')
