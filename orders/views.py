import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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


def payment_urls(request, order_id):
    """Absolute return URLs for the payment provider. {CHECKOUT_SESSION_ID} is filled in by the gateway."""
    success = request.build_absolute_uri(reverse("payments:success")) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel = request.build_absolute_uri(reverse("payments:cancel", args=[order_id]))
    return success, cancel


# --- Cart -----------------------------------------------------------------


def cart_detail(request):
    try:
        cart = CartService(request.session).get_cart()
    except Exception as e:
        logger.exception("Failed to load cart")
        return render(request, "orders/cart.html", {"cart": None, "error": f"We couldn't load your cart: {e}"})
    return render(request, "orders/cart.html", {"cart": cart})


@require_POST
def cart_add(request, product_id):
    try:
        product = CartService(request.session).add(product_id, request.POST.get("quantity", 1))
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
        CartService(request.session).update(product_id, request.POST.get("quantity"))
    except CartError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("Failed to update cart line %s", product_id)
        messages.error(request, f"We couldn't update your cart: {e}")
    return redirect("orders:cart")


@require_POST
def cart_remove(request, product_id):
    try:
        CartService(request.session).remove(product_id)
        messages.success(request, "Item removed from your cart.")
    except Exception as e:
        logger.exception("Failed to remove cart line %s", product_id)
        messages.error(request, f"We couldn't remove that item: {e}")
    return redirect("orders:cart")


# --- Checkout & orders ----------------------------------------------------


@login_required
def checkout(request):
    cart_service = CartService(request.session)
    try:
        cart = cart_service.get_cart()
    except Exception as e:
        logger.exception("Failed to load cart for checkout")
        return render(request, "orders/checkout.html", {"error": f"We couldn't load your cart: {e}"})

    if cart.is_empty:
        messages.error(request, "Your cart is empty.")
        return redirect("orders:cart")

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
        return redirect(PaymentService().start_checkout(order, *payment_urls(request, order.id)))
    except PaymentError as e:
        messages.error(request, f"Your order was saved, but we couldn't start payment: {e}")
    except Exception as e:
        logger.exception("Failed to start payment for order %s", order.id)
        messages.error(request, f"Your order was saved, but we couldn't start payment: {e}")
    return redirect("orders:detail", order_id=order.id)


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
    return render(request, "orders/order_detail.html", {"order": order})
