from .cart import SessionCartStore


def cart(request):
    """Exposes the cart item count to every template (for the header badge)."""
    return {"cart_count": SessionCartStore(request.session).count()}
