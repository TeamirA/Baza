import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.services import OrderError, OrderNotFound, OrderService
from orders.views import payment_urls

from .gateways import PaymentError, WebhookVerificationError
from .services import PaymentService

logger = logging.getLogger(__name__)


@login_required
@require_POST
def pay(request, order_id):
    """(Re)start payment for one of the user's pending orders."""
    try:
        order = OrderService().get_order_for_user(order_id, request.user)
        return redirect(PaymentService().start_checkout(order, *payment_urls(request, order.id)))
    except OrderNotFound as e:
        messages.error(request, str(e))
        return redirect("orders:list")
    except (OrderError, PaymentError) as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("Failed to start payment for order %s", order_id)
        messages.error(request, f"We couldn't start payment: {e}")
    return redirect("orders:detail", order_id=order_id)


@login_required
def success(request):
    session_id = request.GET.get("session_id", "")
    if not session_id:
        messages.error(request, "Missing payment session.")
        return redirect("orders:list")
    try:
        order_id, paid = PaymentService().confirm_checkout(session_id)
    except (PaymentError, OrderNotFound) as e:
        messages.error(request, str(e))
        return redirect("orders:list")
    except Exception as e:
        logger.exception("Failed to confirm payment session")
        messages.error(request, f"We couldn't confirm your payment: {e}")
        return redirect("orders:list")

    if paid:
        messages.success(request, f"Payment received. Thanks for your order #{order_id}!")
    else:
        messages.success(request, f"Order #{order_id} is processing. We'll update it once payment clears.")
    return redirect("orders:detail", order_id=order_id)


@login_required
def cancel(request, order_id):
    messages.error(request, "Payment was cancelled. Your order is saved, and you can pay for it whenever you're ready.")
    return redirect("orders:detail", order_id=order_id)


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
