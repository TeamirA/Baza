"""Cart storage.

Guests keep their cart in the Django session as {"<product_id>": quantity}.
Signed-in shoppers keep it in the database (CartItem), so it survives logging
out and follows them across devices. Both stores share one interface, and
get_cart_store() picks the right one for a request. When a guest signs in,
merge_session_cart_into_user() moves their session cart into their account.
"""

from .repositories import CartItemRepository

SESSION_KEY = "cart"
MAX_QUANTITY_PER_LINE = 99


class SessionCartStore:
    def __init__(self, session):
        self.session = session

    def _data(self):
        return self.session.setdefault(SESSION_KEY, {})

    def items(self):
        """Returns {product_id (int): quantity (int)}."""
        return {int(pk): qty for pk, qty in self._data().items()}

    def get(self, product_id):
        return self._data().get(str(product_id), 0)

    def set(self, product_id, quantity):
        self._data()[str(product_id)] = quantity
        self.session.modified = True

    def remove(self, product_id):
        if self._data().pop(str(product_id), None) is not None:
            self.session.modified = True

    def clear(self):
        self.session[SESSION_KEY] = {}
        self.session.modified = True

    def count(self):
        return sum(self._data().values())


class UserCartStore:
    def __init__(self, user, repository=None):
        self.user = user
        self.repository = repository or CartItemRepository()

    def items(self):
        return self.repository.items(self.user)

    def get(self, product_id):
        return self.repository.get(self.user, product_id)

    def set(self, product_id, quantity):
        self.repository.set(self.user, product_id, quantity)

    def remove(self, product_id):
        self.repository.remove(self.user, product_id)

    def clear(self):
        self.repository.clear(self.user)

    def count(self):
        return self.repository.count(self.user)


def get_cart_store(request):
    if request.user.is_authenticated:
        return UserCartStore(request.user)
    return SessionCartStore(request.session)


def merge_session_cart_into_user(session, user):
    """Adds a guest's session cart to the account cart, then empties the session cart.

    Quantities for the same product are added together (capped per line);
    stock is checked again when the cart is shown and at checkout.
    """
    guest = SessionCartStore(session)
    items = guest.items()
    if not items:
        return
    account = UserCartStore(user)
    for product_id, quantity in items.items():
        account.set(product_id, min(account.get(product_id) + quantity, MAX_QUANTITY_PER_LINE))
    guest.clear()
