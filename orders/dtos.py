from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List

from products.dtos import ProductDTO


@dataclass(frozen=True)
class CartLineDTO:
    product: ProductDTO
    quantity: int

    @property
    def subtotal(self) -> Decimal:
        return self.product.price * self.quantity


@dataclass(frozen=True)
class CartDTO:
    lines: List[CartLineDTO] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((line.subtotal for line in self.lines), Decimal("0.00"))

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines


@dataclass(frozen=True)
class ShippingDTO:
    full_name: str
    email: str
    address: str


@dataclass(frozen=True)
class OrderItemDTO:
    product_name: str
    product_url: str
    quantity: int
    price: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.price * self.quantity


@dataclass(frozen=True)
class OrderDTO:
    id: int
    status: str
    status_label: str
    created_at: datetime
    full_name: str
    email: str
    address: str
    items: List[OrderItemDTO]

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0.00"))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"
