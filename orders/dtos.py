from dataclasses import dataclass, field
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
