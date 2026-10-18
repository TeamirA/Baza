from .cart import get_cart_store


def cart(request):
    """Exposes the cart item count to every template (for the header badge)."""
    return {"cart_count": get_cart_store(request).count()}
