import stripe

from .base import CheckoutSession, PaymentError, PaymentGateway, PaymentResult, WebhookVerificationError

CURRENCY = "usd"


def _to_cents(amount):
    return int((amount * 100).to_integral_value())


def _order_id(session):
    """session is a plain dict (StripeObject.to_dict())."""
    ref = session.get("client_reference_id") or (session.get("metadata") or {}).get("order_id")
    try:
        return int(ref)
    except (TypeError, ValueError):
        return None


class StripeGateway(PaymentGateway):
    def __init__(self, secret_key, webhook_secret=""):
        self.client = stripe.StripeClient(secret_key)
        self.webhook_secret = webhook_secret

    def create_checkout_session(self, order, success_url, cancel_url):
        params = {
            "mode": "payment",
            "client_reference_id": str(order.id),
            "metadata": {"order_id": str(order.id)},
            "line_items": [
                {
                    "quantity": item.quantity,
                    "price_data": {
                        "currency": CURRENCY,
                        "unit_amount": _to_cents(item.price),
                        "product_data": {"name": item.product_name},
                    },
                }
                for item in order.items
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if order.email:
            params["customer_email"] = order.email
        try:
            session = self.client.v1.checkout.sessions.create(params=params)
        except stripe.StripeError as e:
            raise PaymentError(e.user_message or "The payment provider rejected the request.") from e
        return CheckoutSession(id=session.id, url=session.url)

    def get_session_result(self, session_id):
        try:
            session = self.client.v1.checkout.sessions.retrieve(session_id)
        except stripe.StripeError as e:
            raise PaymentError(e.user_message or "Couldn't confirm the payment with the provider.") from e
        return PaymentResult(
            session_id=session.id, order_id=_order_id(session.to_dict()), paid=session.payment_status == "paid"
        )

    def verify_webhook(self, payload, signature):
        if not self.webhook_secret:
            raise WebhookVerificationError("STRIPE_WEBHOOK_SECRET is not configured.")
        try:
            event = stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as e:
            raise WebhookVerificationError(str(e)) from e

        event = event.to_dict()
        if event["type"] not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            return None
        session = event["data"]["object"]
        return PaymentResult(
            session_id=session["id"], order_id=_order_id(session), paid=session.get("payment_status") == "paid"
        )
