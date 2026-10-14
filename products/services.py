from .dtos import CategoryDTO, ProductDTO
from .models import Category, Product
from .repositories import CategoryRepository, ProductRepository


class ProductNotFound(Exception):
    pass


def _category_to_dto(category):
    return CategoryDTO(name=category.name, slug=category.slug) if category else None


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
