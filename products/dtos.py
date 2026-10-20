from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

# At or below this many units we tell shoppers stock is running low.
LOW_STOCK_THRESHOLD = 5


@dataclass(frozen=True)
class CategoryDTO:
    name: str
    slug: str


@dataclass(frozen=True)
class BrowseFilters:
    """What the shopper asked for on the product list (all optional)."""

    query: str = ""
    category_slug: str = ""
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    in_stock: bool = False
    sort: str = ""  # "", "relevance", "newest", "price_asc", "price_desc", "name"
    exact: bool = False  # don't auto-correct typos

    @property
    def is_filtered(self) -> bool:
        return self.min_price is not None or self.max_price is not None or self.in_stock


@dataclass(frozen=True)
class ProductImageDTO:
    url: str  # a sensible default size (~800px) for plain <img src>
    srcset: str = ""  # "…-400.webp 400w, …-800.webp 800w, …"; empty for legacy URL images
    width: int = 0
    height: int = 0
    alt: str = ""
    thumb_url: str = ""
    large_url: str = ""


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
    images: Tuple[ProductImageDTO, ...] = ()
    rating_avg: Optional[float] = None  # average stars (1-5), None without reviews
    rating_count: int = 0

    @property
    def cover(self) -> Optional[ProductImageDTO]:
        return self.images[0] if self.images else None

    @property
    def hover_image(self) -> Optional[ProductImageDTO]:
        """Second photo, shown when hovering a product card."""
        return self.images[1] if len(self.images) > 1 else None

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def low_stock(self) -> bool:
        return 0 < self.stock <= LOW_STOCK_THRESHOLD


@dataclass(frozen=True)
class ReviewDTO:
    rating: int
    title: str
    body: str
    author: str
    created_at: object
    edited: bool
    is_own: bool = False
