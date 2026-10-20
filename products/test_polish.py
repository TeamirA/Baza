"""Fixes from the Phase 10 browser and phone testing."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order, OrderItem
from products.models import Product

PASSWORD = "a-Strong-test-pass-91"


class NotFoundPageTests(TestCase):
    @override_settings(DEBUG=False)
    def test_unknown_url_gets_branded_404(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "We can't find that page", status_code=404)
        self.assertContains(response, 'class="brand"', status_code=404)

    def test_missing_product_offers_search_not_an_error(self):
        response = self.client.get(reverse("products:detail", args=["blue-steel-mug"]))
        self.assertContains(response, "This product isn't available", status_code=404)
        self.assertContains(response, 'value="blue steel mug"', status_code=404)
        self.assertNotContains(response, "Something went wrong", status_code=404)


class ProductPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)

    def test_add_to_cart_returns_to_the_buy_box(self):
        url = reverse("products:detail", args=[self.mug.slug])
        page = self.client.get(url)
        self.assertContains(page, f'name="next" value="{url}#buy"')
        response = self.client.post(reverse("orders:cart_add", args=[self.mug.pk]), {"quantity": 1, "next": f"{url}#buy"})
        self.assertRedirects(response, f"{url}#buy", fetch_redirect_response=False)

    def test_guest_save_link_explains_and_keeps_filters(self):
        response = self.client.get(reverse("products:list") + "?q=mug&sort=price_asc")
        self.assertContains(response, "next=%2F%3Fq%3Dmug%26sort%3Dprice_asc&amp;reason=save")
        login = self.client.get(reverse("login") + "?next=/&reason=save")
        self.assertContains(login, "Log in to save items for later")

    def test_star_picker_runs_one_to_five(self):
        user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        order = Order.objects.create(user=user, full_name="Sam", email="sam@example.com", address="1 St", status="paid")
        OrderItem.objects.create(order=order, product=self.mug, quantity=1, price=self.mug.price)
        self.client.force_login(user)
        html = self.client.get(reverse("products:detail", args=[self.mug.slug])).content.decode()
        values = [html.index(f'name="rating" value="{n}"') for n in range(1, 6)]
        self.assertEqual(values, sorted(values))  # 1 star first, so arrow keys match what you see

    def test_paid_order_links_to_reviews(self):
        user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        order = Order.objects.create(user=user, full_name="Sam", email="sam@example.com", address="1 St", status="paid")
        OrderItem.objects.create(order=order, product=self.mug, quantity=1, price=self.mug.price)
        self.client.force_login(user)
        response = self.client.get(reverse("orders:detail", args=[order.pk]))
        self.assertContains(response, f'{reverse("products:detail", args=[self.mug.slug])}#reviews">Rate &amp; review')


class AutofillTests(TestCase):
    def test_checkout_fields_have_autocomplete_hints(self):
        mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        self.client.post(reverse("orders:cart_add", args=[mug.pk]), {"quantity": 1})
        response = self.client.get(reverse("orders:checkout"))
        for hint in ("shipping name", "email", "shipping street-address"):
            self.assertContains(response, f'autocomplete="{hint}"')
