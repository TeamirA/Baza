from .services import WishlistService


def wishlist(request):
    """Which products the shopper has saved (for hearts) and how many (for the header)."""
    if not request.user.is_authenticated:
        return {"wishlist_ids": frozenset(), "wishlist_count": 0}
    ids = WishlistService(request.user).ids()
    return {"wishlist_ids": ids, "wishlist_count": len(ids)}
