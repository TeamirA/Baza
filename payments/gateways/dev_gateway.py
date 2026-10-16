from django.core import signing

from .base import CheckoutSession, PaymentError, PaymentGateway, PaymentResult, WebhookVerificationError

SALT = "payments.dev_gateway"


class DevGateway(PaymentGateway):
    """Local-only stand-in used when DEBUG is on and no Stripe key is set.

    "Checkout" skips straight to the success URL with a signed session id, so the
    full order flow can be exercised without a Stripe account. Never used when
    DEBUG is off (see payments.gateways.get_payment_gateway).
    """

    def create_checkout_session(self, order, success_url, cancel_url):
        session_id = signing.dumps({"order_id": order.id}, salt=SALT)
        return CheckoutSession(id=session_id, url=success_url.replace("{CHECKOUT_SESSION_ID}", session_id))

    def get_session_result(self, session_id):
        try:
            data = signing.loads(session_id, salt=SALT)
        except signing.BadSignature:
            raise PaymentError("That payment session is not valid.")
        return PaymentResult(session_id=session_id, order_id=data["order_id"], paid=True)

    def verify_webhook(self, payload, signature):
        raise WebhookVerificationError("Webhooks are not used by the development gateway.")
