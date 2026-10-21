from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    sku = models.CharField("SKU", max_length=40, blank=True, db_index=True)
    description = models.TextField(blank=True)
    # Spec rows for the product page, e.g. [["Warranty", "1 year"], ["Returns", "30 days"]].
    details = models.JSONField(default=list, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # A URL rather than an ImageField: Vercel's filesystem is read-only/ephemeral,
    # so uploaded media would not persist. Point this at a CDN or object storage.
    image_url = models.URLField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:detail", args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """A product photo, stored as resized WebP variants (see products/images.py)."""

    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=0, help_text="Lower comes first; the first photo is the cover.")
    alt_text = models.CharField(
        max_length=200, blank=True, help_text="Describe the photo for screen readers, e.g. “Mug from the side”."
    )
    # {"400": "https://…-400.webp", "800": "…", "1600": "…"}: width in px -> URL.
    variants = models.JSONField(default=dict)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Photo {self.position} of {self.product}"


class SavedProduct(models.Model):
    """A product on a signed-in shopper's wishlist."""

    user = models.ForeignKey("auth.User", related_name="saved_products", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="saved_by", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_saved_product")]


class Review(models.Model):
    """A rating (and optional text) from a customer who bought the product.

    Sample reviews (is_sample) come with the demo catalog: they have a display
    name instead of an account and are labelled as samples on the site.
    """

    product = models.ForeignKey(Product, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey("auth.User", related_name="reviews", on_delete=models.CASCADE, null=True, blank=True)
    author_name = models.CharField(max_length=100, blank=True, help_text="Shown for sample reviews.")
    is_sample = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=100, blank=True)
    body = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="one_review_per_customer")]

    def __str__(self):
        return f"{self.rating}★ for {self.product} by {self.user or self.author_name}"
