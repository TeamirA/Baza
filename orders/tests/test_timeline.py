from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Product

from ..models import Order, OrderItem
from ..services import OrderService

PASSWORD = "a-Strong-test-pass-91"


class TimelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)

    def setUp(self):
        self.client.force_login(self.user)
        self.order = Order.objects.create(user=self.user, full_name="Sam", email="sam@example.com", address="1 St")
        OrderItem.objects.create(order=self.order, product=self.mug, quantity=2, price=self.mug.price)

    def steps(self):
        return [(s.label, s.done) for s in OrderService().get_order(self.order.pk).timeline]

    def test_pending_then_paid(self):
        self.assertEqual(self.steps(), [("Order placed", True), ("Payment received", False), ("Shipped", False)])
        page = self.client.get(reverse("orders:detail", args=[self.order.pk]))
        self.assertContains(page, 'aria-current="step"')
        OrderService().mark_as_paid(self.order.pk)
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.paid_at)
        self.assertEqual(self.steps(), [("Order placed", True), ("Payment received", True), ("Shipped", False)])

    def test_cancelled(self):
        OrderService().cancel(self.order.pk)
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.cancelled_at)
        self.assertEqual(self.steps(), [("Order placed", True), ("Cancelled", True)])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_shipping_in_admin_records_time_and_tracking(self):
        OrderService().mark_as_paid(self.order.pk)
        admin_user = User.objects.create_superuser("boss", "boss@example.com", PASSWORD)
        self.client.force_login(admin_user)
        item = self.order.items.get()
        self.client.post(reverse("admin:orders_order_change", args=[self.order.pk]), {
            "status": "shipped", "full_name": "Sam", "email": "sam@example.com", "address": "1 St",
            "stripe_session_id": "", "amount_paid": "", "stock_reserved": "on", "tracking_number": "1Z999AA10123456784",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1", "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-id": item.pk, "items-0-order": self.order.pk,
        })
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "shipped")
        self.assertIsNotNone(self.order.shipped_at)
        self.assertIn("Tracking number: 1Z999AA10123456784", mail.outbox[-1].body)
        self.client.force_login(self.user)
        page = self.client.get(reverse("orders:detail", args=[self.order.pk]))
        self.assertContains(page, "Tracking number: 1Z999AA10123456784")
        self.assertContains(page, 'class="timeline__step timeline__step--done"', count=3)


class BuyAgainTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)
        cls.tote = Product.objects.create(name="Tote", price=Decimal("5.00"), stock=1)
        cls.gone = Product.objects.create(name="Gone", price=Decimal("1.00"), stock=0)

    def setUp(self):
        self.client.force_login(self.user)
        self.order = Order.objects.create(user=self.user, status=Order.Status.PAID)
        for product, qty in [(self.mug, 2), (self.tote, 3), (self.gone, 1)]:
            OrderItem.objects.create(order=self.order, product=product, quantity=qty, price=product.price)

    def test_adds_what_it_can_and_explains_the_rest(self):
        response = self.client.post(reverse("orders:buy_again", args=[self.order.access_token]), follow=True)
        self.assertRedirects(response, reverse("orders:cart"))
        self.assertEqual(dict(self.user.cart_items.values_list("product__name", "quantity")), {"Mug": 2, "Tote": 1})
        self.assertContains(response, f"Added 3 items from order #{self.order.pk} to your cart.")
        self.assertContains(response, "Tote: only 1 of 3 added (limited stock).")
        self.assertContains(response, "Gone: sold out.")

    def test_button_only_on_finished_orders(self):
        page = self.client.get(reverse("orders:detail", args=[self.order.pk]))
        self.assertContains(page, "Buy again")
        pending = Order.objects.create(user=self.user)
        self.assertNotContains(self.client.get(reverse("orders:detail", args=[pending.pk])), "Buy again")

    def test_requires_post(self):
        self.assertEqual(self.client.get(reverse("orders:buy_again", args=[self.order.access_token])).status_code, 405)
