"""The only module in the orders app that talks to the ORM."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from products.repositories import ProductRepository

from .models import CartItem, Order, OrderItem


class InsufficientStock(Exception):
    def __init__(self, product_id):
        super().__init__(product_id)
        self.product_id = product_id


class OrderRepository:
    def __init__(self, products=None):
        self.products = products or ProductRepository()

    def _with_items(self):
        return Order.objects.prefetch_related("items__product")

    @transaction.atomic
    def create(self, user, full_name, email, address, lines):
        """Creates a pending order and reserves its stock, all or nothing.

        lines: iterable of (product_id, quantity, unit_price).
        Raises InsufficientStock (and saves nothing) if any line can't be reserved.
        """
        lines = list(lines)
        for product_id, quantity, _ in lines:
            if not self.products.reserve_stock(product_id, quantity):
                raise InsufficientStock(product_id)  # rolls back earlier reservations
        order = Order.objects.create(
            user=user, full_name=full_name, email=email, address=address, stock_reserved=True
        )
        OrderItem.objects.bulk_create(
            [OrderItem(order=order, product_id=pid, quantity=qty, price=price) for pid, qty, price in lines]
        )
        return self._with_items().get(pk=order.pk)

    def get_by_id(self, order_id):
        """Raises Order.DoesNotExist."""
        return self._with_items().get(pk=order_id)

    def get_by_token(self, token):
        """Raises Order.DoesNotExist."""
        return self._with_items().get(access_token=token)

    def get_for_user(self, order_id, user):
        """Raises Order.DoesNotExist if the order doesn't exist or belongs to someone else."""
        return self._with_items().get(pk=order_id, user=user)

    def list_for_user(self, user):
        return list(self._with_items().filter(user=user))

    def set_payment_session(self, order_id, session_id):
        Order.objects.filter(pk=order_id).update(stripe_session_id=session_id)

    @transaction.atomic
    def mark_paid(self, order_id, session_id="", amount_paid=None):
        """Marks a pending (or cancelled) order paid.

        Returns (changed, was_cancelled). changed is False if the order was already
        paid or shipped, so webhook retries and the success redirect can't
        double-count. A payment that arrives after cancellation is honoured: the
        customer was charged, so the order is revived and its stock taken again.
        Raises Order.DoesNotExist.
        """
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status not in (Order.Status.PENDING, Order.Status.CANCELLED):
            return False, False
        was_cancelled = order.status == Order.Status.CANCELLED
        take_stock = was_cancelled or not order.stock_reserved
        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.stock_reserved = True
        if session_id:
            order.stripe_session_id = session_id
        if amount_paid is not None:
            order.amount_paid = amount_paid
        order.save(update_fields=["status", "paid_at", "stock_reserved", "stripe_session_id", "amount_paid", "updated_at"])
        if take_stock:
            for item in order.items.all():
                self.products.decrement_stock(item.product_id, item.quantity)
        return True, was_cancelled

    @transaction.atomic
    def cancel(self, order_id):
        """Cancels a pending order and puts reserved stock back. Returns the order, or
        None if it wasn't pending (already paid/cancelled). Raises Order.DoesNotExist."""
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.PENDING:
            return None
        order.status = Order.Status.CANCELLED
        order.cancelled_at = timezone.now()
        if order.stock_reserved:
            for item in order.items.all():
                self.products.release_stock(item.product_id, item.quantity)
        order.stock_reserved = False
        order.save(update_fields=["status", "cancelled_at", "stock_reserved", "updated_at"])
        return order

    def pending_ids_older_than(self, hours):
        cutoff = timezone.now() - timedelta(hours=hours)
        return list(
            Order.objects.filter(status=Order.Status.PENDING, created_at__lt=cutoff).values_list("pk", flat=True)
        )


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
