from products.services import ProductNotFound, ProductService

from .cart import SessionCartStore
from .dtos import CartDTO, CartLineDTO, OrderDTO, OrderItemDTO
from .models import Order
from .repositories import OrderRepository

MAX_QUANTITY_PER_LINE = 99


class CartError(Exception):
    """A cart operation the user asked for can't be done; the message is shown to them."""


class OrderError(Exception):
    """An order can't be placed or paid; the message is shown to the user."""


class OrderNotFound(Exception):
    pass


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


def _order_to_dto(order):
    return OrderDTO(
        id=order.pk,
        status=order.status,
        status_label=order.get_status_display(),
        created_at=order.created_at,
        full_name=order.full_name,
        email=order.email,
        address=order.address,
        items=[
            OrderItemDTO(
                product_name=item.product.name,
                product_url=item.product.get_absolute_url(),
                quantity=item.quantity,
                price=item.price,
            )
            for item in order.items.all()
        ],
    )


class OrderService:
    def __init__(self, orders=None):
        self.orders = orders or OrderRepository()

    def create_order(self, user, cart, shipping):
        """Turns the cart into a pending order, snapshotting current prices."""
        if cart.is_empty:
            raise OrderError("Your cart is empty.")
        for line in cart.lines:
            if line.quantity > line.product.stock:
                raise OrderError(
                    f"Only {line.product.stock} of {line.product.name} left. Please update your cart."
                )
        order = self.orders.create(
            user=user,
            full_name=shipping.full_name,
            email=shipping.email,
            address=shipping.address,
            lines=[(line.product.id, line.quantity, line.product.price) for line in cart.lines],
        )
        return _order_to_dto(order)

    def get_order(self, order_id):
        try:
            return _order_to_dto(self.orders.get_by_id(order_id))
        except Order.DoesNotExist:
            raise OrderNotFound(f"Order #{order_id} was not found.")

    def get_order_for_user(self, order_id, user):
        try:
            return _order_to_dto(self.orders.get_for_user(order_id, user))
        except Order.DoesNotExist:
            raise OrderNotFound(f"Order #{order_id} was not found.")

    def list_orders(self, user):
        return [_order_to_dto(o) for o in self.orders.list_for_user(user)]

    def attach_payment_session(self, order_id, session_id):
        self.orders.set_payment_session(order_id, session_id)

    def mark_as_paid(self, order_id, session_id=""):
        """Idempotent: returns True only the first time an order is marked paid."""
        try:
            return self.orders.mark_paid(order_id, session_id)
        except Order.DoesNotExist:
            raise OrderNotFound(f"Order #{order_id} was not found.")
