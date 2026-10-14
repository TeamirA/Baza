from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


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
