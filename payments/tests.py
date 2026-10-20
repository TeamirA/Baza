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

from .gateways import PaymentError, PaymentResult, get_payment_gateway
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
        self.assertContains(response, "Mug just sold out or has fewer left")
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


@override_settings(DEBUG=False, STRIPE_SECRET_KEY="", CRON_SECRET="cron-test-secret", ORDER_HOLD_HOURS=24)
class StockReservationTests(CheckoutTestCase):
    def place_order(self, quantity):
        self.fill_cart(quantity)
        self.client.post(reverse("orders:checkout"), SHIPPING)
        return Order.objects.latest("pk")

    def stock(self):
        self.mug.refresh_from_db()
        return self.mug.stock

    def test_checkout_reserves_stock_and_payment_does_not_take_it_twice(self):
        order = self.place_order(2)
        self.assertTrue(order.stock_reserved)
        self.assertEqual(self.stock(), 3)
        OrderService().mark_as_paid(order.pk)
        self.assertEqual(self.stock(), 3)

    def test_last_unit_cannot_be_sold_twice(self):
        Product.objects.filter(pk=self.mug.pk).update(stock=1)
        self.place_order(1)
        # Another shopper had the same unit in their cart.
        self.client.force_login(self.other)
        self.other.cart_items.create(product=self.mug, quantity=1)
        response = self.client.post(reverse("orders:checkout"), SHIPPING)
        self.assertContains(response, "just sold out")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.stock(), 0)

    def test_shopper_can_cancel_unpaid_order_and_stock_returns(self):
        order = self.place_order(2)
        response = self.client.post(reverse("orders:cancel", args=[order.access_token]), follow=True)
        self.assertContains(response, f"Order #{order.pk} was cancelled.")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.stock(), 5)
        summary = response.content.decode().split('class="cart-summary"')[1]
        self.assertIn("<span>Total</span>", summary)
        self.assertNotIn("<span>Paid</span>", summary)
        # Cancelling again changes nothing.
        response = self.client.post(reverse("orders:cancel", args=[order.access_token]), follow=True)
        self.assertContains(response, "Only unpaid orders can be cancelled.")
        self.assertEqual(self.stock(), 5)

    def test_payment_after_cancellation_is_honoured(self):
        order = self.place_order(2)
        self.client.post(reverse("orders:cancel", args=[order.access_token]))
        OrderService().mark_as_paid(order.pk, "cs_late")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self.stock(), 3)

    def test_cancel_does_not_happen_if_customer_already_paid(self):
        order = self.place_order(1)
        Order.objects.filter(pk=order.pk).update(stripe_session_id="cs_paid")
        gateway = mock.Mock()
        gateway.expire_checkout_session.return_value = False
        gateway.get_session_result.return_value = PaymentResult("cs_paid", order.pk, True, Decimal("10.00"))
        from payments.services import PaymentService

        PaymentService(gateway=gateway).cancel_order(OrderService().get_order(order.pk))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self.stock(), 4)

    def test_legacy_unreserved_orders_still_take_stock_at_payment(self):
        order = self.make_order(quantity=2)  # created directly, like pre-reservation orders
        self.assertFalse(order.stock_reserved)
        OrderService().mark_as_paid(order.pk)
        self.assertEqual(self.stock(), 3)

    def test_cron_cancels_only_old_unpaid_orders(self):
        from datetime import timedelta

        from django.utils import timezone

        old = self.place_order(1)
        Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=25))
        fresh = self.place_order(1)
        paid_old = self.place_order(1)
        OrderService().mark_as_paid(paid_old.pk)
        Order.objects.filter(pk=paid_old.pk).update(created_at=timezone.now() - timedelta(hours=30))
        self.assertEqual(self.stock(), 2)

        url = reverse("orders:cron_expire_unpaid")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION="Bearer wrong").status_code, 403)
        response = self.client.get(url, HTTP_AUTHORIZATION="Bearer cron-test-secret")
        self.assertEqual(response.json(), {"cancelled": 1})

        statuses = dict(Order.objects.values_list("pk", "status"))
        self.assertEqual(statuses[old.pk], Order.Status.CANCELLED)
        self.assertEqual(statuses[fresh.pk], Order.Status.PENDING)
        self.assertEqual(statuses[paid_old.pk], Order.Status.PAID)
        self.assertEqual(self.stock(), 3)

    @override_settings(CRON_SECRET="")
    def test_cron_refuses_everything_when_secret_unset(self):
        response = self.client.get(reverse("orders:cron_expire_unpaid"), HTTP_AUTHORIZATION="Bearer ")
        self.assertEqual(response.status_code, 403)

    def test_order_page_shows_hold_and_cancel_for_pending_only(self):
        order = self.place_order(1)
        page = self.client.get(reverse("orders:detail", args=[order.pk]))
        self.assertContains(page, "Items are held for you until")
        self.assertContains(page, "Cancel order")
        OrderService().mark_as_paid(order.pk)
        self.assertNotContains(self.client.get(reverse("orders:detail", args=[order.pk])), "Cancel order")


@override_settings(
    DEBUG=True, STRIPE_SECRET_KEY="", SITE_URL="https://shop.example",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class OrderEmailTests(CheckoutTestCase):
    def test_confirmation_sent_once_with_private_link(self):
        from django.core import mail

        self.fill_cart(2)
        success_url = self.client.post(reverse("orders:checkout"), SHIPPING).url
        self.assertEqual(mail.outbox, [])  # nothing until it's paid
        self.client.get(success_url)
        self.client.get(success_url)  # returning to the page again doesn't resend
        order = Order.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["sam@example.com"])
        self.assertEqual(email.subject, f"Your Baza order #{order.pk} is confirmed")
        self.assertIn("2 × Mug  $20.00", email.body)
        self.assertIn(f"https://shop.example/orders/track/{order.access_token}/", email.body)

    def test_email_failure_does_not_break_payment(self):
        from unittest import mock as _mock

        self.fill_cart(1)
        success_url = self.client.post(reverse("orders:checkout"), SHIPPING).url
        with _mock.patch("orders.notifications.send_mail", side_effect=OSError("smtp down")):
            response = self.client.get(success_url, follow=True)
        self.assertContains(response, "Payment received")
        self.assertEqual(Order.objects.get().status, Order.Status.PAID)

    def test_marking_shipped_in_admin_emails_customer(self):
        from django.core import mail

        admin_user = User.objects.create_superuser("boss", "boss@example.com", PASSWORD)
        order = self.make_order(quantity=1)
        OrderService().mark_as_paid(order.pk)
        mail.outbox.clear()
        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("admin:orders_order_change", args=[order.pk]),
            {"status": "shipped", "full_name": order.full_name, "email": order.email, "address": order.address,
             "stripe_session_id": "", "amount_paid": "", "stock_reserved": "on",
             "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1", "items-MIN_NUM_FORMS": "0",
             "items-MAX_NUM_FORMS": "1000", "items-0-id": order.items.get().pk, "items-0-order": order.pk},
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context_data", {}).get("errors"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("has shipped", mail.outbox[0].subject)


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
    def test_expire_session_refuses_when_already_paid(self):
        gateway = StripeGateway("sk_test_x")
        sessions = gateway.client.v1.checkout.sessions
        with mock.patch.object(sessions, "retrieve", return_value=mock.Mock(payment_status="paid", status="complete")), \
                mock.patch.object(sessions, "expire") as expire:
            self.assertFalse(gateway.expire_checkout_session("cs_1"))
        expire.assert_not_called()
        with mock.patch.object(sessions, "retrieve", return_value=mock.Mock(payment_status="unpaid", status="open")), \
                mock.patch.object(sessions, "expire") as expire:
            self.assertTrue(gateway.expire_checkout_session("cs_2"))
        expire.assert_called_once_with("cs_2")

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
        self.assertAlmostEqual(params["expires_at"] - time.time(), 23 * 3600, delta=60)

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
