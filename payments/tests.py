import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order, OrderItem
from orders.services import OrderService
from products.models import Product

from .gateways import PaymentError, get_payment_gateway
from .gateways.dev_gateway import DevGateway
from .gateways.stripe_gateway import StripeGateway

PASSWORD = "a-Strong-test-pass-91"
SHIPPING = {"full_name": "Sam Doe", "email": "sam@example.com", "address": "1 Main St\nTown"}
WEBHOOK_SECRET = "whsec_test_secret"


class CheckoutTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("sam", "sam@example.com", PASSWORD)
        cls.other = User.objects.create_user("alex", "alex@example.com", PASSWORD)
        cls.mug = Product.objects.create(name="Mug", price=Decimal("10.00"), stock=5)

    def setUp(self):
        self.client.force_login(self.user)

    def fill_cart(self, quantity=2):
        self.client.post(reverse("orders:cart_add", args=[self.mug.pk]), {"quantity": quantity})

    def make_order(self, user=None, quantity=2):
        order = Order.objects.create(user=user or self.user, **SHIPPING)
        OrderItem.objects.create(order=order, product=self.mug, quantity=quantity, price=self.mug.price)
        return order


@override_settings(DEBUG=True, STRIPE_SECRET_KEY="")
class DevCheckoutFlowTests(CheckoutTestCase):
    def test_full_checkout_marks_paid_decrements_stock_and_clears_cart(self):
        self.fill_cart(2)
        response = self.client.post(reverse("orders:checkout"), SHIPPING)
        self.assertTrue(response.url.startswith("http://testserver/payments/success/?session_id="))
        self.assertFalse(self.user.cart_items.exists())  # cart emptied once the order exists

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.items.get().price, Decimal("10.00"))

        response = self.client.get(response.url, follow=True)
        self.assertRedirects(response, reverse("orders:detail", args=[order.pk]))
        self.assertContains(response, "Payment received")
        order.refresh_from_db()
        self.mug.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self.mug.stock, 3)

    def test_confirming_twice_does_not_double_count_stock(self):
        self.fill_cart(2)
        success_url = self.client.post(reverse("orders:checkout"), SHIPPING).url
        self.client.get(success_url)
        self.client.get(success_url)
        self.mug.refresh_from_db()
        self.assertEqual(self.mug.stock, 3)

    def test_tampered_session_id_is_rejected(self):
        order = self.make_order()
        response = self.client.get(reverse("payments:success"), {"session_id": f"forged-{order.pk}"}, follow=True)
        self.assertContains(response, "not valid")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_price_snapshot_survives_price_change(self):
        self.fill_cart(1)
        self.client.post(reverse("orders:checkout"), SHIPPING)
        Product.objects.filter(pk=self.mug.pk).update(price=Decimal("99.00"))
        order = OrderService().list_orders(self.user)[0]
        self.assertEqual(order.total, Decimal("10.00"))


class CheckoutRulesTests(CheckoutTestCase):
    def test_guest_sees_checkout_with_login_option(self):
        self.client.logout()
        self.fill_cart()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checking out as a guest")

    def test_empty_cart_redirects_back_to_cart(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("orders:cart"))

    def test_invalid_shipping_form_shows_errors(self):
        self.fill_cart()
        response = self.client.post(reverse("orders:checkout"), {"full_name": "", "email": "nope", "address": ""})
        self.assertContains(response, "field--invalid")
        self.assertFalse(Order.objects.exists())

    def test_stock_change_after_adding_to_cart_blocks_order(self):
        self.fill_cart(4)
        Product.objects.filter(pk=self.mug.pk).update(stock=1)
        response = self.client.post(reverse("orders:checkout"), SHIPPING)
        self.assertContains(response, "Only 1 of Mug left")
        self.assertFalse(Order.objects.exists())

    @override_settings(DEBUG=False, STRIPE_SECRET_KEY="")
    def test_unconfigured_payments_keep_order_and_show_error(self):
        self.fill_cart()
        response = self.client.post(reverse("orders:checkout"), SHIPPING, follow=True)
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:detail", args=[order.pk]))
        self.assertContains(response, "Payments aren&#x27;t set up yet")
        self.assertContains(response, "Pay $20.00")

    def test_order_pages_are_private(self):
        mine = self.make_order()
        theirs = self.make_order(user=self.other)
        response = self.client.get(reverse("orders:list"))
        self.assertContains(response, f"Order #{mine.pk}")
        self.assertNotContains(response, f"Order #{theirs.pk}")
        response = self.client.get(reverse("orders:detail", args=[theirs.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "error-card", status_code=404)

    def test_cannot_pay_for_paid_order(self):
        order = self.make_order()
        OrderService().mark_as_paid(order.pk)
        response = self.client.post(reverse("payments:pay", args=[order.access_token]), follow=True)
        self.assertContains(response, "already paid")


@override_settings(DEBUG=True, STRIPE_SECRET_KEY="")
class GuestCheckoutTests(CheckoutTestCase):
    def setUp(self):
        pass  # stay signed out

    def test_guest_can_order_and_pay_and_return_via_private_link(self):
        self.fill_cart(2)
        success_url = self.client.post(reverse("orders:checkout"), SHIPPING).url
        order = Order.objects.get()
        self.assertIsNone(order.user)
        self.assertEqual(order.email, "sam@example.com")
        self.assertEqual(self.client.session["cart"], {})

        response = self.client.get(success_url, follow=True)
        track_url = reverse("orders:track", args=[order.access_token])
        self.assertRedirects(response, track_url)
        self.assertContains(response, "Payment received")
        self.assertContains(response, "Keep this page")
        self.assertContains(response, "Create an account")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        # The private link works later, from another browser, without signing in.
        other_browser = self.client_class()
        self.assertContains(other_browser.get(track_url), f"Order #{order.pk}")

    def test_unknown_link_is_a_404_with_error_card(self):
        import uuid

        response = self.client.get(reverse("orders:track", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "error-card", status_code=404)

    def test_guest_can_retry_payment_from_the_link(self):
        order = Order.objects.create(user=None, **SHIPPING)
        OrderItem.objects.create(order=order, product=self.mug, quantity=1, price=self.mug.price)
        response = self.client.post(reverse("payments:pay", args=[order.access_token]))
        self.assertTrue(response.url.startswith("http://testserver/payments/success/?session_id="))

    def test_cancel_returns_guest_to_their_order(self):
        order = Order.objects.create(user=None, **SHIPPING)
        response = self.client.get(reverse("payments:cancel", args=[order.access_token]), follow=True)
        self.assertRedirects(response, reverse("orders:track", args=[order.access_token]))
        self.assertContains(response, "Payment was cancelled")

    def test_members_orders_are_not_listed_as_guest_orders(self):
        self.client.force_login(self.user)
        self.fill_cart(1)
        self.client.get(self.client.post(reverse("orders:checkout"), SHIPPING).url)
        order = Order.objects.get()
        self.assertEqual(order.user, self.user)
        response = self.client.get(reverse("orders:detail", args=[order.pk]))
        self.assertNotContains(response, "Keep this page")


class GatewaySelectionTests(TestCase):
    @override_settings(STRIPE_SECRET_KEY="sk_test_x")
    def test_stripe_when_key_set(self):
        self.assertIsInstance(get_payment_gateway(), StripeGateway)

    @override_settings(STRIPE_SECRET_KEY="", DEBUG=True)
    def test_dev_gateway_only_in_debug(self):
        self.assertIsInstance(get_payment_gateway(), DevGateway)

    @override_settings(STRIPE_SECRET_KEY="", DEBUG=False)
    def test_no_gateway_in_production_without_key(self):
        with self.assertRaises(PaymentError):
            get_payment_gateway()


class StripeGatewayTests(CheckoutTestCase):
    def test_checkout_session_params(self):
        order = OrderService().get_order(self.make_order(quantity=3).pk)
        gateway = StripeGateway("sk_test_x")
        fake_session = mock.Mock(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1")
        with mock.patch.object(gateway.client.v1.checkout.sessions, "create", return_value=fake_session) as create:
            session = gateway.create_checkout_session(order, "https://s/?session_id={CHECKOUT_SESSION_ID}", "https://c/")
        params = create.call_args.kwargs["params"]
        self.assertEqual(session.url, fake_session.url)
        self.assertEqual(params["client_reference_id"], str(order.id))
        self.assertEqual(params["customer_email"], "sam@example.com")
        self.assertEqual(params["line_items"][0]["quantity"], 3)
        self.assertEqual(params["line_items"][0]["price_data"]["unit_amount"], 1000)
        self.assertIn("{CHECKOUT_SESSION_ID}", params["success_url"])
        self.assertTrue(params["allow_promotion_codes"])

    def test_session_result_from_real_stripe_object(self):
        import stripe

        gateway = StripeGateway("sk_test_x")
        session = stripe.checkout.Session.construct_from(
            {"id": "cs_test_2", "client_reference_id": "42", "payment_status": "paid"}, "sk_test_x"
        )
        with mock.patch.object(gateway.client.v1.checkout.sessions, "retrieve", return_value=session):
            result = gateway.get_session_result("cs_test_2")
        self.assertEqual((result.order_id, result.paid, result.session_id), (42, True, "cs_test_2"))


@override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class StripeWebhookTests(CheckoutTestCase):
    def send(self, event, secret=WEBHOOK_SECRET):
        payload = json.dumps(event)
        timestamp = int(time.time())
        signature = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
        return self.client.post(
            reverse("payments:webhook"),
            payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
        )

    def completed_event(self, order_id):
        return {
            "id": "evt_1",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_1", "object": "checkout.session",
                                "client_reference_id": str(order_id), "payment_status": "paid"}},
        }

    def test_valid_webhook_marks_order_paid_once(self):
        order = self.make_order(quantity=2)
        self.assertEqual(self.send(self.completed_event(order.pk)).status_code, 200)
        self.assertEqual(self.send(self.completed_event(order.pk)).status_code, 200)  # Stripe retry
        order.refresh_from_db()
        self.mug.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.stripe_session_id, "cs_test_1")
        self.assertEqual(self.mug.stock, 3)

    def test_discounted_payment_records_amount_paid(self):
        order = self.make_order(quantity=2)  # 2 x $10.00
        event = self.completed_event(order.pk)
        event["data"]["object"]["amount_total"] = 1500  # $15.00 after a promo code
        self.assertEqual(self.send(event).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.amount_paid, Decimal("15.00"))
        response = self.client.get(reverse("orders:detail", args=[order.pk]))
        self.assertContains(response, "Promo discount")
        self.assertContains(response, "−$5.00")
        self.assertContains(response, "$15.00")
        self.assertContains(self.client.get(reverse("orders:list")), "$15.00")

    def test_bad_signature_is_rejected(self):
        order = self.make_order()
        self.assertEqual(self.send(self.completed_event(order.pk), secret="whsec_wrong").status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_unrelated_events_and_unknown_orders_are_acknowledged(self):
        self.assertEqual(self.send({"id": "evt_2", "object": "event", "type": "customer.created",
                                    "data": {"object": {}}}).status_code, 200)
        self.assertEqual(self.send(self.completed_event(999999)).status_code, 200)

    def test_webhook_is_csrf_exempt_and_post_only(self):
        self.assertEqual(self.client.get(reverse("payments:webhook")).status_code, 405)
