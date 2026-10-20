import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from payments.gateways import PaymentError
from payments.services import PaymentService

from .dtos import ShippingDTO
from .forms import ShippingForm
from .services import CartError, CartService, OrderError, OrderNotFound, OrderService

logger = logging.getLogger(__name__)


def _redirect_back(request, fallback="orders:cart"):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


def payment_urls(request, order):
    """Absolute return URLs for the payment provider. {CHECKOUT_SESSION_ID} is filled in by the gateway."""
    success = request.build_absolute_uri(reverse("payments:success")) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel = request.build_absolute_uri(reverse("payments:cancel", args=[order.access_token]))
    return success, cancel


def order_page_url(order):
    """Guests use the private link; signed-in owners get their normal order page."""
    if order.is_guest:
        return reverse("orders:track", args=[order.access_token])
    return reverse("orders:detail", args=[order.id])


# --- Cart -----------------------------------------------------------------


def cart_detail(request):
    try:
        cart = CartService.for_request(request).get_cart()
    except Exception as e:
        logger.exception("Failed to load cart")
        return render(request, "orders/cart.html", {"cart": None, "error": f"We couldn't load your cart: {e}"})
    return render(request, "orders/cart.html", {"cart": cart})


@require_POST
def cart_add(request, product_id):
    try:
        product = CartService.for_request(request).add(product_id, request.POST.get("quantity", 1))
        messages.success(request, f"Added {product.name} to your cart.")
    except CartError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("Failed to add product %s to cart", product_id)
        messages.error(request, f"We couldn't add that to your cart: {e}")
    return _redirect_back(request)


@require_POST
def cart_update(request, product_id):
    try:
        CartService.for_request(request).update(product_id, request.POST.get("quantity"))
    except CartError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("Failed to update cart line %s", product_id)
        messages.error(request, f"We couldn't update your cart: {e}")
    return redirect("orders:cart")


@require_POST
def cart_remove(request, product_id):
    try:
        CartService.for_request(request).remove(product_id)
        messages.success(request, "Item removed from your cart.")
    except Exception as e:
        logger.exception("Failed to remove cart line %s", product_id)
        messages.error(request, f"We couldn't remove that item: {e}")
    return redirect("orders:cart")


# --- Checkout & orders ----------------------------------------------------


def _order_context(order):
    return {"order": order, "hold_until": order.hold_until(settings.ORDER_HOLD_HOURS)}


def checkout(request):
    cart_service = CartService.for_request(request)
    try:
        cart = cart_service.get_cart()
    except Exception as e:
        logger.exception("Failed to load cart for checkout")
        return render(request, "orders/checkout.html", {"error": f"We couldn't load your cart: {e}"})

    if cart.is_empty:
        messages.error(request, "Your cart is empty.")
        return redirect("orders:cart")

    initial = {}
    if request.user.is_authenticated:
        initial = {"full_name": request.user.get_full_name(), "email": request.user.email}
    form = ShippingForm(request.POST or None, initial=initial)
    context = {"cart": cart, "form": form}

    if request.method != "POST" or not form.is_valid():
        return render(request, "orders/checkout.html", context)

    try:
        order = OrderService().create_order(request.user, cart, ShippingDTO(**form.cleaned_data))
    except OrderError as e:
        context["error"] = str(e)
        return render(request, "orders/checkout.html", context)
    except Exception as e:
        logger.exception("Failed to create order")
        context["error"] = f"We couldn't place your order: {e}"
        return render(request, "orders/checkout.html", context)

    cart_service.clear()

    try:
        return redirect(PaymentService().start_checkout(order, *payment_urls(request, order)))
    except PaymentError as e:
        messages.error(request, f"Your order was saved, but we couldn't start payment: {e}")
    except Exception as e:
        logger.exception("Failed to start payment for order %s", order.id)
        messages.error(request, f"Your order was saved, but we couldn't start payment: {e}")
    return redirect(order_page_url(order))


@login_required
def order_list(request):
    try:
        orders = OrderService().list_orders(request.user)
    except Exception as e:
        logger.exception("Failed to list orders")
        return render(request, "orders/order_list.html", {"orders": [], "error": f"We couldn't load your orders: {e}"})
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail(request, order_id):
    try:
        order = OrderService().get_order_for_user(order_id, request.user)
    except OrderNotFound as e:
        return render(request, "orders/order_detail.html", {"error": str(e)}, status=404)
    except Exception as e:
        logger.exception("Failed to load order %s", order_id)
        return render(request, "orders/order_detail.html", {"error": f"We couldn't load this order: {e}"}, status=500)
    return render(request, "orders/order_detail.html", _order_context(order))


def order_track(request, token):
    """Order page reached by its private link; works without an account."""
    try:
        order = OrderService().get_order_by_token(token)
    except OrderNotFound as e:
        return render(request, "orders/order_detail.html", {"error": str(e), "via_link": True}, status=404)
    except Exception as e:
        logger.exception("Failed to load order by link")
        return render(
            request, "orders/order_detail.html", {"error": f"We couldn't load this order: {e}", "via_link": True}, status=500
        )
    return render(request, "orders/order_detail.html", {**_order_context(order), "via_link": True})


@require_POST
def order_cancel(request, token):
    """Cancel a pending order from its page (owner or private link)."""
    try:
        order = OrderService().get_order_by_token(token)
    except OrderNotFound as e:
        messages.error(request, str(e))
        return redirect("products:list")
    try:
        _, cancelled = PaymentService().cancel_order(order)
        if cancelled:
            messages.success(request, f"Order #{order.id} was cancelled.")
        else:
            messages.success(request, f"Order #{order.id} had already been paid, so it wasn't cancelled.")
    except (OrderError, PaymentError) as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("Failed to cancel order %s", order.id)
        messages.error(request, f"We couldn't cancel this order: {e}")
    return redirect(order_page_url(order))


def cron_expire_unpaid(request):
    """Called daily by Vercel Cron (see vercel.json). Cancels unpaid orders older
    than ORDER_HOLD_HOURS and puts their stock back."""
    expected = f"Bearer {settings.CRON_SECRET}"
    given = request.headers.get("Authorization", "")
    if not settings.CRON_SECRET or not hmac.compare_digest(given, expected):
        return HttpResponseForbidden("Forbidden")
    cancelled = PaymentService().expire_unpaid_orders(settings.ORDER_HOLD_HOURS)
    logger.info("Expired %s unpaid order(s)", cancelled)
    return JsonResponse({"cancelled": cancelled})


@require_POST
def order_buy_again(request, token):
    """Puts a past order's items back in the cart, as far as stock allows."""
    try:
        order = OrderService().get_order_by_token(token)
    except OrderNotFound as e:
        messages.error(request, str(e))
        return redirect("products:list")
    added, skipped = CartService.for_request(request).add_many([(i.product_id, i.quantity) for i in order.items])
    if added:
        count = sum(q for _, q in added)
        messages.success(request, f"Added {count} item{'s' if count != 1 else ''} from order #{order.id} to your cart.")
    for name, reason in skipped:
        messages.error(request, f"{name or 'An item'}: {reason}.")
    if not added and not skipped:
        messages.error(request, "That order had nothing to add.")
    return redirect("orders:cart" if added else order_page_url(order))
