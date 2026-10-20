import uuid

from django.conf import settings

from config.media_store import get_media_store

from .dtos import CategoryDTO, ProductDTO, ProductImageDTO, ReviewDTO
from . import search
from .images import ImageProcessingError, process_image
from .models import Category, Product
from .repositories import (
    CategoryRepository,
    ProductImageRepository,
    ProductRepository,
    ReviewRepository,
    SavedProductRepository,
)


class ProductNotFound(Exception):
    pass


def _category_to_dto(category):
    return CategoryDTO(name=category.name, slug=category.slug) if category else None


DEFAULT_IMAGE_WIDTH = 800


def _image_to_dto(image):
    variants = sorted(((int(w), url) for w, url in image.variants.items()), key=lambda v: v[0])
    if not variants:
        return None
    default = next((url for w, url in variants if w >= DEFAULT_IMAGE_WIDTH), variants[-1][1])
    return ProductImageDTO(
        url=default,
        srcset=", ".join(f"{url} {w}w" for w, url in variants),
        width=image.width,
        height=image.height,
        alt=image.alt_text,
        thumb_url=variants[0][1],
        large_url=variants[-1][1],
    )


def _images_for(product):
    images = tuple(filter(None, (_image_to_dto(i) for i in product.images.all())))
    if not images and product.image_url:
        # Older products point at an external image URL instead of uploads.
        url = product.image_url
        images = (ProductImageDTO(url=url, alt=product.name, thumb_url=url, large_url=url),)
    return images


def _product_to_dto(product):
    return ProductDTO(
        id=product.pk,
        name=product.name,
        slug=product.slug,
        description=product.description,
        price=product.price,
        image_url=product.image_url,
        stock=product.stock,
        category=_category_to_dto(product.category),
        url=product.get_absolute_url(),
        images=_images_for(product),
        rating_avg=round(float(product.rating_avg), 2) if getattr(product, "rating_avg", None) is not None else None,
        rating_count=getattr(product, "rating_count", 0) or 0,
    )


class ProductService:
    def __init__(self, products=None, categories=None):
        self.products = products or ProductRepository()
        self.categories = categories or CategoryRepository()

    def list_products(self, category_slug=None):
        return [_product_to_dto(p) for p in self.products.get_all_active(category_slug)]

    SORTS = ("relevance", "newest", "price_asc", "price_desc", "name")

    def browse(self, filters):
        """Products for the list page. Returns (products, corrected query or None, sort used).

        With a search query the default sort is relevance; otherwise newest.
        """
        sort = filters.sort if filters.sort in self.SORTS else ("relevance" if filters.query else "newest")
        if sort == "relevance" and not filters.query:
            sort = "newest"
        candidates = [
            _product_to_dto(p)
            for p in self.products.get_all_active(
                filters.category_slug or None,
                filters.min_price,
                filters.max_price,
                filters.in_stock,
                order="newest" if sort == "relevance" else sort,
            )
        ]
        if not filters.query:
            return candidates, None, sort
        ranked, corrected = search.search(candidates, filters.query, allow_correction=not filters.exact)
        if sort != "relevance":
            # Keep the search's matches, in the order the shopper picked.
            matched = {p.id for p in ranked}
            ranked = [p for p in candidates if p.id in matched]
        return ranked, corrected, sort

    def suggest(self, query, limit=6):
        """Top matches for the search box. Returns (products, total matches, corrected query or None)."""
        ranked, corrected = search.search(self.list_products(), query)
        return ranked[:limit], len(ranked), corrected

    def search_products(self, query, category_slug=None, allow_correction=True):
        """Returns (products ranked by relevance, corrected query or None)."""
        return search.search(self.list_products(category_slug), query, allow_correction)

    def list_categories(self):
        return [_category_to_dto(c) for c in self.categories.get_all()]

    def get_category(self, slug):
        try:
            return _category_to_dto(self.categories.get_by_slug(slug))
        except Category.DoesNotExist:
            return None

    def get_product(self, slug):
        try:
            return _product_to_dto(self.products.get_by_slug(slug))
        except Product.DoesNotExist:
            raise ProductNotFound(f'No product found for "{slug}".')

    def get_product_by_id(self, product_id):
        try:
            return _product_to_dto(self.products.get_by_id(product_id))
        except (Product.DoesNotExist, ValueError):
            raise ProductNotFound("That product is no longer available.")

    def related_products(self, product, limit=4):
        """Products to suggest under a ProductDTO: same category first, then others."""
        category_slug = product.category.slug if product.category else None
        return [_product_to_dto(p) for p in self.products.get_related(product.id, category_slug, limit)]

    def products_in_order(self, product_ids, exclude_id=None, limit=None):
        """Active products for the given ids, in that order; missing/inactive ones are skipped."""
        found = self.get_products_by_ids(product_ids)
        ordered = [found[pk] for pk in product_ids if pk in found and pk != exclude_id]
        return ordered[:limit] if limit else ordered

    def get_products_by_ids(self, product_ids):
        """Returns {id: ProductDTO} for the active products among product_ids."""
        return {pk: _product_to_dto(p) for pk, p in self.products.get_by_ids(product_ids).items()}


class ImageUploadError(Exception):
    """A photo couldn't be added; the message is safe to show to staff."""


class ProductImageService:
    def __init__(self, store=None, images=None):
        self.store = store or get_media_store()
        self.images = images or ProductImageRepository()

    @staticmethod
    def prepare(data):
        """Validates and resizes an upload. Call during form validation so errors show on the form."""
        if len(data) > settings.MAX_IMAGE_UPLOAD_BYTES:
            limit = settings.MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)
            raise ImageUploadError(f"Photos must be under {limit} MB. Resize or compress it and try again.")
        try:
            return process_image(data)
        except ImageProcessingError as e:
            raise ImageUploadError(str(e))

    def add_prepared(self, product_id, processed, alt_text="", position=None):
        """Uploads the resized variants and records the photo. All-or-nothing:
        if anything fails, files already uploaded are removed again."""
        product = self.images.get_product(product_id)
        stem = f"products/{product.slug or product.pk}/{uuid.uuid4().hex[:12]}"
        uploaded = {}
        try:
            for width, data in processed.variants.items():
                uploaded[str(width)] = self.store.save(f"{stem}-{width}.webp", data, "image/webp")
            return self.images.create(product_id, uploaded, processed.width, processed.height, alt_text, position)
        except Exception as e:
            self.store.delete(list(uploaded.values()))
            raise ImageUploadError(f"Couldn't save the photo: {e}") from e

    def add_image(self, product_id, data, alt_text="", position=None):
        return self.add_prepared(product_id, self.prepare(data), alt_text, position)


class WishlistService:
    def __init__(self, user, saved=None, products=None):
        self.user = user
        self.saved = saved or SavedProductRepository()
        self.products = products or ProductService()

    def ids(self):
        return self.saved.ids(self.user) if self.user.is_authenticated else set()

    def toggle(self, product_id):
        """Returns True if now saved. Raises ProductNotFound for unknown/inactive products."""
        self.products.get_product_by_id(product_id)
        return self.saved.toggle(self.user, product_id)

    def remove(self, product_id):
        self.saved.remove(self.user, product_id)

    def items(self):
        """Saved products that are still available, most recently saved first."""
        return self.products.products_in_order(self.saved.product_ids_newest_first(self.user))


class ReviewNotAllowed(Exception):
    """The shopper can't review this product; the message explains why."""


def _author_name(user):
    first = (user.first_name or "").strip()
    if first:
        last = (user.last_name or "").strip()
        return f"{first} {last[:1]}." if last else first
    return user.get_username()


class ReviewService:
    def __init__(self, reviews=None):
        self.reviews = reviews or ReviewRepository()

    def list_for_product(self, product_id, viewer=None):
        viewer_id = viewer.pk if viewer is not None and viewer.is_authenticated else None
        return [
            ReviewDTO(
                rating=r.rating,
                title=r.title,
                body=r.body,
                author=_author_name(r.user),
                created_at=r.created_at,
                edited=(r.updated_at - r.created_at).total_seconds() > 60,
                is_own=r.user_id == viewer_id,
            )
            for r in self.reviews.for_product(product_id)
        ]

    def can_review(self, user, product_id):
        return user.is_authenticated and self.reviews.has_bought(user, product_id)

    def own_review(self, user, product_id):
        return self.reviews.get(user, product_id) if user.is_authenticated else None

    def save(self, user, product_id, rating, title="", body=""):
        if not user.is_authenticated:
            raise ReviewNotAllowed("Log in to write a review.")
        if not self.reviews.has_bought(user, product_id):
            raise ReviewNotAllowed("Only customers who bought this product can review it.")
        return self.reviews.save(user, product_id, rating, title.strip(), body.strip())
