from products.services import ProductNotFound, ProductService

from .cart import SessionCartStore
from .dtos import CartDTO, CartLineDTO

MAX_QUANTITY_PER_LINE = 99


class CartError(Exception):
    """A cart operation the user asked for can't be done; the message is shown to them."""


class CartService:
    def __init__(self, session, products=None):
        self.store = SessionCartStore(session)
        self.products = products or ProductService()

    def _parse_quantity(self, quantity):
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise CartError("Quantity must be a whole number.")
        if quantity < 0:
            raise CartError("Quantity can't be negative.")
        return quantity

    def _check_stock(self, product, quantity):
        if not product.in_stock:
            raise CartError(f"{product.name} is sold out.")
        if quantity > product.stock:
            raise CartError(f"Only {product.stock} of {product.name} available.")
        if quantity > MAX_QUANTITY_PER_LINE:
            raise CartError(f"You can order at most {MAX_QUANTITY_PER_LINE} of one item.")

    def _get_product(self, product_id):
        try:
            return self.products.get_product_by_id(product_id)
        except ProductNotFound as e:
            raise CartError(str(e))

    def add(self, product_id, quantity=1):
        quantity = self._parse_quantity(quantity)
        if quantity == 0:
            raise CartError("Choose at least one item to add.")
        product = self._get_product(product_id)
        new_quantity = self.store.get(product.id) + quantity
        self._check_stock(product, new_quantity)
        self.store.set(product.id, new_quantity)
        return product

    def update(self, product_id, quantity):
        quantity = self._parse_quantity(quantity)
        if quantity == 0:
            self.store.remove(product_id)
            return None
        product = self._get_product(product_id)
        self._check_stock(product, quantity)
        self.store.set(product.id, quantity)
        return product

    def remove(self, product_id):
        self.store.remove(product_id)

    def clear(self):
        self.store.clear()

    def count(self):
        return self.store.count()

    def get_cart(self):
        """Builds the cart, dropping products that were deactivated since they were added."""
        items = self.store.items()
        products = self.products.get_products_by_ids(list(items))
        lines = []
        for product_id, quantity in items.items():
            product = products.get(product_id)
            if product is None:
                self.store.remove(product_id)
                continue
            lines.append(CartLineDTO(product=product, quantity=quantity))
        return CartDTO(lines=lines)
