import logging

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .services import CartError, CartService

logger = logging.getLogger(__name__)


def _redirect_back(request, fallback="orders:cart"):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


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
