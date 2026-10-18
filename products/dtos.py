from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# At or below this many units we tell shoppers stock is running low.
LOW_STOCK_THRESHOLD = 5


@dataclass(frozen=True)
class CategoryDTO:
    name: str
    slug: str


@dataclass(frozen=True)
class ProductDTO:
    id: int
    name: str
    slug: str
    description: str
    price: Decimal
    image_url: str
    stock: int
    category: Optional[CategoryDTO]
    url: str

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def low_stock(self) -> bool:
        return 0 < self.stock <= LOW_STOCK_THRESHOLD
