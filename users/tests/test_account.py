from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order
from products.models import Product

from ..models import Address
from ..services import MAX_ADDRESSES

PASSWORD = "a-Strong-test-pass-91"


class AccountTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        cls.other = User.objects.create_user("alex", "alex@example.com", PASSWORD)

    def setUp(self):
        self.client.force_login(self.user)

    def add(self, **overrides):
        data = {"label": "Home", "full_name": "Sam Doe", "address": "1 Main St\nTown"}
        data.update(overrides)
        return self.client.post(reverse("address_add"), data)


class ProfilePageTests(AccountTestCase):
    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("profile"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('profile')}")

    def test_shows_details_and_header_link(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "sam@example.com")
        self.assertContains(response, f'href="{reverse("profile")}">Account</a>')
        self.assertContains(response, "No saved addresses yet")


class AddressTests(AccountTestCase):
    def test_first_address_becomes_default(self):
        self.assertRedirects(self.add(), reverse("profile"))
        address = self.user.addresses.get()
        self.assertTrue(address.is_default)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "1 Main St<br>Town")
        self.assertContains(response, "Default")

    def test_new_default_replaces_old(self):
        self.add(label="Home")
        self.add(label="Work", make_default="on")
        self.assertEqual(list(self.user.addresses.filter(is_default=True).values_list("label", flat=True)), ["Work"])
        self.add(label="Cabin")  # not default
        self.assertEqual(self.user.addresses.filter(is_default=True).count(), 1)

    def test_make_default(self):
        self.add(label="Home")
        self.add(label="Work")
        work = self.user.addresses.get(label="Work")
        self.client.post(reverse("address_default", args=[work.pk]))
        self.assertEqual(list(self.user.addresses.filter(is_default=True)), [work])

    def test_deleting_default_promotes_newest(self):
        self.add(label="Home")
        self.add(label="Work")
        self.add(label="Cabin")
        home = self.user.addresses.get(label="Home")
        self.client.post(reverse("address_delete", args=[home.pk]))
        self.assertFalse(Address.objects.filter(pk=home.pk).exists())
        self.assertEqual(self.user.addresses.get(is_default=True).label, "Cabin")

    def test_cannot_touch_someone_elses_address(self):
        theirs = Address.objects.create(user=self.other, full_name="Alex", address="2 Elm", is_default=True)
        response = self.client.post(reverse("address_delete", args=[theirs.pk]), follow=True)
        self.assertContains(response, "That address doesn&#x27;t exist anymore.")
        self.client.post(reverse("address_default", args=[theirs.pk]))
        self.assertTrue(Address.objects.filter(pk=theirs.pk, is_default=True).exists())

    def test_invalid_address_shows_errors(self):
        response = self.add(full_name="", address="")
        self.assertContains(response, "field--invalid", status_code=400)
        self.assertFalse(self.user.addresses.exists())

    def test_address_limit(self):
        for i in range(MAX_ADDRESSES):
            Address.objects.create(user=self.user, full_name="Sam", address=f"{i} Main St")
        response = self.client.post(
            reverse("address_add"), {"full_name": "Sam", "address": "Extra"}, follow=True
        )
        self.assertContains(response, f"You can save up to {MAX_ADDRESSES} addresses")
        self.assertEqual(self.user.addresses.count(), MAX_ADDRESSES)

    def test_actions_need_post(self):
        self.add()
        address = self.user.addresses.get()
        self.assertEqual(self.client.get(reverse("address_delete", args=[address.pk])).status_code, 405)


class EmailChangeTests(AccountTestCase):
    def change(self, email, password=PASSWORD):
        return self.client.post(reverse("email_change"), {"email": email, "password": password})

    def test_changes_email(self):
        self.assertRedirects(self.change(" New@Example.com "), reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")

    def test_needs_current_password(self):
        response = self.change("new@example.com", password="wrong")
        self.assertContains(response, "That password isn&#x27;t right.", status_code=400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "sam@example.com")

    def test_rejects_taken_email(self):
        response = self.change("ALEX@example.com")
        self.assertContains(response, "An account with this email already exists.", status_code=400)


class PasswordChangeTests(AccountTestCase):
    def test_change_password_keeps_session(self):
        self.client.login(username="sam", password=PASSWORD)
        page = self.client.get(reverse("password_change"))
        self.assertContains(page, "Change password")
        new = "an0ther-Strong-pass"
        response = self.client.post(
            reverse("password_change"), {"old_password": PASSWORD, "new_password1": new, "new_password2": new}
        )
        self.assertRedirects(response, reverse("password_change_done"))
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)  # still signed in
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new))

    def test_wrong_old_password(self):
        response = self.client.post(
            reverse("password_change"), {"old_password": "nope", "new_password1": "x", "new_password2": "x"}
        )
        self.assertContains(response, "field--invalid")


@override_settings(DEBUG=True, STRIPE_SECRET_KEY="")
class CheckoutAddressTests(AccountTestCase):
    SHIPPING = {"full_name": "Sam Doe", "email": "sam@example.com", "address": "1 Main St\nTown"}

    def setUp(self):
        super().setUp()
        self.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=50)
        self.client.post(reverse("orders:cart_add", args=[self.mug.pk]), {"quantity": 1})

    def checkout(self, **extra):
        return self.client.post(reverse("orders:checkout"), {**self.SHIPPING, **extra})

    def test_default_address_prefills_checkout(self):
        Address.objects.create(user=self.user, label="Work", full_name="Sam at Work", address="9 Office Rd", is_default=True)
        response = self.client.get(reverse("orders:checkout"))
        form = response.context["form"]
        self.assertEqual(form["full_name"].value(), "Sam at Work")
        self.assertEqual(form["address"].value(), "9 Office Rd")
        self.assertFalse(form["save_address"].value())
        self.assertContains(response, "Ship to a saved address")
        self.assertContains(response, 'data-address="9 Office Rd"')

    def test_first_checkout_offers_and_saves_address(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertTrue(response.context["form"]["save_address"].value())
        self.assertNotContains(response, "Ship to a saved address")

        self.checkout(save_address="on")
        self.assertEqual(Order.objects.count(), 1)
        address = self.user.addresses.get()
        self.assertEqual((address.full_name, address.address, address.is_default), ("Sam Doe", "1 Main St\nTown", True))

    def test_same_address_is_not_saved_twice(self):
        self.checkout(save_address="on")
        self.client.post(reverse("orders:cart_add", args=[self.mug.pk]), {"quantity": 1})
        self.checkout(save_address="on")
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(self.user.addresses.count(), 1)

    def test_unticked_box_saves_nothing(self):
        self.checkout()
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(self.user.addresses.exists())

    def test_guests_never_save_addresses(self):
        self.client.logout()
        self.client.post(reverse("orders:cart_add", args=[self.mug.pk]), {"quantity": 1})
        response = self.client.get(reverse("orders:checkout"))
        self.assertNotContains(response, "Save this address")
        self.checkout(save_address="on")
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(Address.objects.exists())
