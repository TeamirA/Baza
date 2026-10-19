"""Products a shopper has looked at, kept in their session (like a guest cart).

Only that browser sees the list. It survives logging in, and is cleared on logout.
"""

SESSION_KEY = "recently_viewed"
MAX_ITEMS = 8


class RecentlyViewedStore:
    def __init__(self, session):
        self.session = session

    def ids(self):
        return [int(pk) for pk in self.session.get(SESSION_KEY, [])]

    def add(self, product_id):
        ids = [pk for pk in self.ids() if pk != product_id]
        ids.insert(0, product_id)
        self.session[SESSION_KEY] = ids[:MAX_ITEMS]
