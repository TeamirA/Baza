import uuid

from django.conf import settings

from config.media_store import get_media_store

from .dtos import CategoryDTO, ProductDTO, ProductImageDTO
from .images import ImageProcessingError, process_image
from .models import Category, Product
from .repositories import CategoryRepository, ProductImageRepository, ProductRepository


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
    )


class ProductService:
    def __init__(self, products=None, categories=None):
        self.products = products or ProductRepository()
        self.categories = categories or CategoryRepository()

    def list_products(self, category_slug=None, query=None):
        return [_product_to_dto(p) for p in self.products.get_all_active(category_slug, query)]

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
