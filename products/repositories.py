"""The only module in the products app that talks to the ORM."""

from django.db.models import BooleanField, Case, F, Q, When
from django.db.models.functions import Greatest

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

    def get_related(self, product_id, category_slug, limit):
        """Other active products: same category first, then anything else; in stock and newest first."""
        qs = (
            self._active()
            .exclude(pk=product_id)
            .annotate(has_stock=Case(When(stock__gt=0, then=True), default=False, output_field=BooleanField()))
            .order_by("-has_stock", "-created_at")
        )
        related = list(qs.filter(category__slug=category_slug)[:limit]) if category_slug else []
        if len(related) < limit:
            related += list(qs.exclude(pk__in=[p.pk for p in related])[: limit - len(related)])
        return related

    def decrement_stock(self, product_id, quantity):
        """Lowers stock by quantity, never below zero. Call inside the caller's transaction."""
        Product.objects.filter(pk=product_id).update(stock=Greatest(F("stock") - quantity, 0))


class CategoryRepository:
    def get_all(self):
        return list(Category.objects.all())

    def get_by_slug(self, slug):
        return Category.objects.get(slug=slug)
