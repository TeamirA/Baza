import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from products.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        CANCELLED = "cancelled", "Cancelled"

    # Empty for guest checkouts.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Private link to the order page and payment for anyone holding it (guests included).
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    full_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    stripe_session_id = models.CharField(max_length=255, blank=True)
    # What the customer was actually charged, as reported by the payment provider.
    # Can be lower than the item total when a promo code was used.
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # True when the items were taken out of stock at checkout (orders from before
    # reservations existed take stock at payment instead).
    stock_reserved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Order #{self.pk} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    # Snapshot of the unit price at purchase time, so later price edits don't rewrite history.
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"


class CartItem(models.Model):
    """A line in a signed-in shopper's cart. Guests keep their cart in the session."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="cart_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="cart_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_cart_item_per_product")]

    def __str__(self):
        return f"{self.quantity} × {self.product} for {self.user}"
