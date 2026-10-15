"""Session-backed cart storage.

The cart lives in the Django session as {"<product_id>": quantity}. This is the
only module that reads or writes that session key, the same way repositories
are the only modules that touch the ORM.
"""

SESSION_KEY = "cart"


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
