"""The only module in the products app that talks to the ORM."""

from django.db.models import Avg, BooleanField, Case, Count, F, When
from django.db.models.functions import Greatest

from .models import Category, Product, ProductImage, Review, SavedProduct


class ProductRepository:
    def _active(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("images")
            .annotate(rating_avg=Avg("reviews__rating"), rating_count=Count("reviews", distinct=True))
        )

    ORDERINGS = {
        "newest": ["-created_at", "-pk"],
        "price_asc": ["price", "-created_at"],
        "price_desc": ["-price", "-created_at"],
        "name": ["name"],
    }

    def get_all_active(self, category_slug=None, min_price=None, max_price=None, in_stock=False, order="newest"):
        """Active products matching the filters. Text search and ranking happen in products/search.py."""
        qs = self._active()
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        if min_price is not None:
            qs = qs.filter(price__gte=min_price)
        if max_price is not None:
            qs = qs.filter(price__lte=max_price)
        if in_stock:
            qs = qs.filter(stock__gt=0)
        return list(qs.order_by(*self.ORDERINGS.get(order, self.ORDERINGS["newest"])))

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

    def reserve_stock(self, product_id, quantity):
        """Takes quantity out of stock only if that much is available. Returns True on success.

        A single conditional UPDATE, so two buyers can't both take the last unit.
        """
        return Product.objects.filter(pk=product_id, stock__gte=quantity).update(stock=F("stock") - quantity) == 1

    def release_stock(self, product_id, quantity):
        Product.objects.filter(pk=product_id).update(stock=F("stock") + quantity)

    def decrement_stock(self, product_id, quantity):
        """Lowers stock by quantity, never below zero. Call inside the caller's transaction."""
        Product.objects.filter(pk=product_id).update(stock=Greatest(F("stock") - quantity, 0))


class CategoryRepository:
    def get_all(self):
        return list(Category.objects.all())

    def get_by_slug(self, slug):
        return Category.objects.get(slug=slug)


class ProductImageRepository:
    def create(self, product_id, variants, width, height, alt_text="", position=None):
        if position is None:
            last = ProductImage.objects.filter(product_id=product_id).order_by("-position").first()
            position = last.position + 1 if last else 0
        return ProductImage.objects.create(
            product_id=product_id, variants=variants, width=width, height=height, alt_text=alt_text, position=position
        )

    def get_product(self, product_id):
        """Raises Product.DoesNotExist. Includes inactive products (admins add photos to drafts)."""
        return Product.objects.get(pk=product_id)


class SavedProductRepository:
    def ids(self, user):
        return set(SavedProduct.objects.filter(user=user).values_list("product_id", flat=True))

    def product_ids_newest_first(self, user):
        return list(SavedProduct.objects.filter(user=user).values_list("product_id", flat=True))

    def toggle(self, user, product_id):
        """Saves or unsaves; returns True if the product is now saved."""
        deleted, _ = SavedProduct.objects.filter(user=user, product_id=product_id).delete()
        if deleted:
            return False
        SavedProduct.objects.get_or_create(user=user, product_id=product_id)
        return True

    def remove(self, user, product_id):
        SavedProduct.objects.filter(user=user, product_id=product_id).delete()


class ReviewRepository:
    def for_product(self, product_id):
        return list(Review.objects.filter(product_id=product_id).select_related("user"))

    def get(self, user, product_id):
        return Review.objects.filter(user=user, product_id=product_id).first()

    def save(self, user, product_id, rating, title, body):
        review, _ = Review.objects.update_or_create(
            user=user, product_id=product_id, defaults={"rating": rating, "title": title, "body": body}
        )
        return review

    def has_bought(self, user, product_id):
        """True if the user has a paid or shipped order containing the product."""
        from orders.models import Order, OrderItem  # orders depends on products, so import lazily

        return OrderItem.objects.filter(
            order__user=user, product_id=product_id, order__status__in=[Order.Status.PAID, Order.Status.SHIPPED]
        ).exists()
