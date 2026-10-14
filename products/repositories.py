"""The only module in the products app that talks to the ORM."""

from django.db.models import Q

from .models import Category, Product


class ProductRepository:
    def _active(self):
        return Product.objects.filter(is_active=True).select_related("category")

    def get_all_active(self, category_slug=None, query=None):
        qs = self._active()
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return list(qs)

    def get_by_slug(self, slug):
        """Raises Product.DoesNotExist if there is no active product with this slug."""
        return self._active().get(slug=slug)

    def get_by_id(self, product_id):
        """Raises Product.DoesNotExist if there is no active product with this id."""
        return self._active().get(pk=product_id)

    def get_by_ids(self, product_ids):
        return {p.pk: p for p in self._active().filter(pk__in=product_ids)}


class CategoryRepository:
    def get_all(self):
        return list(Category.objects.all())

    def get_by_slug(self, slug):
        return Category.objects.get(slug=slug)
