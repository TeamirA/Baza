import logging

from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.services import OrderError, OrderNotFound, OrderService
from orders.views import order_page_url, payment_urls

from .gateways import PaymentError, WebhookVerificationError
from .services import PaymentService

logger = logging.getLogger(__name__)


def _fallback(request):
    return redirect("orders:list" if request.user.is_authenticated else "products:list")


@require_POST
def pay(request, token):
    """(Re)start payment for a pending order, from its page (owner or private link)."""
    try:
        order = OrderService().get_order_by_token(token)
    except OrderNotFound as e:
        messages.error(request, str(e))
        return _fallback(request)
    try:
        return redirect(PaymentService().start_checkout(order, *payment_urls(request, order)))
    except (OrderError, PaymentError) as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("Failed to start payment for order %s", order.id)
        messages.error(request, f"We couldn't start payment: {e}")
    return redirect(order_page_url(order))


def success(request):
    session_id = request.GET.get("session_id", "")
    if not session_id:
        messages.error(request, "Missing payment session.")
        return _fallback(request)
    try:
        order_id, paid = PaymentService().confirm_checkout(session_id)
        order = OrderService().get_order(order_id)
    except (PaymentError, OrderNotFound) as e:
        messages.error(request, str(e))
        return _fallback(request)
    except Exception as e:
        logger.exception("Failed to confirm payment session")
        messages.error(request, f"We couldn't confirm your payment: {e}")
        return _fallback(request)

    if paid:
        messages.success(request, f"Payment received. Thanks for your order #{order.id}!")
    else:
        messages.success(request, f"Order #{order.id} is processing. We'll update it once payment clears.")
    return redirect(order_page_url(order))


def cancel(request, token):
    try:
        order = OrderService().get_order_by_token(token)
    except OrderNotFound as e:
        messages.error(request, str(e))
        return _fallback(request)
    messages.error(request, "Payment was cancelled. Your order is saved, and you can pay for it whenever you're ready.")
    return redirect(order_page_url(order))


@csrf_exempt
@require_POST
def webhook(request):
    try:
        PaymentService().handle_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except WebhookVerificationError as e:
        logger.warning("Rejected webhook: %s", e)
        return HttpResponseBadRequest("Invalid webhook")
    except OrderNotFound as e:
        # Acknowledge so the provider doesn't retry forever; log for investigation.
        logger.error("Webhook for unknown order: %s", e)
    except PaymentError as e:
        logger.error("Webhook could not be processed: %s", e)
        return HttpResponseBadRequest("Payment provider not configured")
    return HttpResponse(status=200)
