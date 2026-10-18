"""The only module in the orders app that talks to the ORM."""

from django.db import transaction
from django.db.models import Sum

from products.repositories import ProductRepository

from .models import CartItem, Order, OrderItem


class OrderRepository:
    def __init__(self, products=None):
        self.products = products or ProductRepository()

    def _with_items(self):
        return Order.objects.prefetch_related("items__product")

    @transaction.atomic
    def create(self, user, full_name, email, address, lines):
        """lines: iterable of (product_id, quantity, unit_price)."""
        order = Order.objects.create(user=user, full_name=full_name, email=email, address=address)
        OrderItem.objects.bulk_create(
            [OrderItem(order=order, product_id=pid, quantity=qty, price=price) for pid, qty, price in lines]
        )
        return self._with_items().get(pk=order.pk)

    def get_by_id(self, order_id):
        """Raises Order.DoesNotExist."""
        return self._with_items().get(pk=order_id)

    def get_for_user(self, order_id, user):
        """Raises Order.DoesNotExist if the order doesn't exist or belongs to someone else."""
        return self._with_items().get(pk=order_id, user=user)

    def list_for_user(self, user):
        return list(self._with_items().filter(user=user))

    def set_payment_session(self, order_id, session_id):
        Order.objects.filter(pk=order_id).update(stripe_session_id=session_id)

    @transaction.atomic
    def mark_paid(self, order_id, session_id="", amount_paid=None):
        """Marks a pending order paid and takes its items out of stock.

        Returns True if this call changed the order, False if it was already
        handled (so webhook retries and the success redirect can't double-count).
        Raises Order.DoesNotExist.
        """
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.PENDING:
            return False
        order.status = Order.Status.PAID
        if session_id:
            order.stripe_session_id = session_id
        if amount_paid is not None:
            order.amount_paid = amount_paid
        order.save(update_fields=["status", "stripe_session_id", "amount_paid", "updated_at"])
        for item in order.items.all():
            self.products.decrement_stock(item.product_id, item.quantity)
        return True


class CartItemRepository:
    def items(self, user):
        return dict(CartItem.objects.filter(user=user).values_list("product_id", "quantity"))

    def get(self, user, product_id):
        return CartItem.objects.filter(user=user, product_id=product_id).values_list("quantity", flat=True).first() or 0

    def set(self, user, product_id, quantity):
        CartItem.objects.update_or_create(user=user, product_id=product_id, defaults={"quantity": quantity})

    def remove(self, user, product_id):
        CartItem.objects.filter(user=user, product_id=product_id).delete()

    def clear(self, user):
        CartItem.objects.filter(user=user).delete()

    def count(self, user):
        return CartItem.objects.filter(user=user).aggregate(total=Sum("quantity"))["total"] or 0
