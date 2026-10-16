from django.conf import settings

from .base import CheckoutSession, PaymentError, PaymentGateway, PaymentResult, WebhookVerificationError


def get_payment_gateway() -> PaymentGateway:
    """Picks the configured gateway. Add new providers (PayPal, Razorpay...) here."""
    if settings.STRIPE_SECRET_KEY:
        from .stripe_gateway import StripeGateway

        return StripeGateway(settings.STRIPE_SECRET_KEY, settings.STRIPE_WEBHOOK_SECRET)
    if settings.DEBUG:
        from .dev_gateway import DevGateway

        return DevGateway()
    raise PaymentError("Payments aren't set up yet. Please try again later.")


__all__ = [
    "CheckoutSession",
    "PaymentError",
    "PaymentGateway",
    "PaymentResult",
    "WebhookVerificationError",
    "get_payment_gateway",
]
