from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Category, Product, ProductImage, Review
from .services import ImageUploadError, ProductImageService


class ProductImageForm(forms.ModelForm):
    upload = forms.ImageField(
        required=False,
        label="Photo",
        help_text="JPEG, PNG or WebP, under 4 MB. It's resized automatically.",
    )

    class Meta:
        model = ProductImage
        fields = ["upload", "alt_text", "position"]

    def clean(self):
        cleaned = super().clean()
        upload = cleaned.get("upload")
        if not self.instance.pk and not upload and self.has_changed() and not cleaned.get("DELETE"):
            raise forms.ValidationError("Choose a photo to upload.")
        if upload:
            try:
                # Resize now so a bad file is reported on the form, not as a server error.
                self.prepared = ProductImageService.prepare(upload.read())
            except ImageUploadError as e:
                self.add_error("upload", str(e))
        return cleaned


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageForm
    extra = 1
    fields = ["preview", "upload", "alt_text", "position"]
    readonly_fields = ["preview"]

    @admin.display(description="Current")
    def preview(self, obj):
        if not obj.pk or not obj.variants:
            return "—"
        smallest = obj.variants[min(obj.variants, key=int)]
        return format_html('<img src="{}" alt="" style="height:64px;border-radius:6px">', smallest)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["thumbnail", "name", "brand", "category", "price", "stock", "is_active", "created_at"]
    list_display_links = ["thumbnail", "name"]
    list_filter = ["is_active", "category"]
    list_editable = ["price", "stock", "is_active"]
    search_fields = ["name", "brand", "sku", "description"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [ProductImageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    @admin.display(description="")
    def thumbnail(self, obj):
        image = next(iter(obj.images.all()), None)
        if not image or not image.variants:
            return ""
        return format_html('<img src="{}" alt="" style="height:40px;border-radius:4px">', image.variants[min(image.variants, key=int)])

    def save_formset(self, request, form, formset, change):
        if formset.model is not ProductImage:
            return super().save_formset(request, form, formset, change)

        service = ProductImageService()
        # The admin's change history reads these, normally filled by formset.save().
        formset.new_objects, formset.changed_objects, formset.deleted_objects = [], [], []
        for image_form in formset.forms:
            data = getattr(image_form, "cleaned_data", None)
            if not data:
                continue
            instance = image_form.instance
            if data.get("DELETE"):
                if instance.pk:
                    formset.deleted_objects.append(instance)
                    instance.delete()  # files are removed by the post_delete signal
                continue
            if not instance.pk:
                prepared = getattr(image_form, "prepared", None)
                if prepared is None:
                    continue
                try:
                    formset.new_objects.append(
                        service.add_prepared(form.instance.pk, prepared, data.get("alt_text", ""), data.get("position"))
                    )
                except ImageUploadError as e:
                    messages.error(request, str(e))
                continue
            if image_form.has_changed():
                prepared = getattr(image_form, "prepared", None)
                if prepared is not None:
                    # A new file replaces this photo: add the new one, then remove the old.
                    try:
                        formset.new_objects.append(
                            service.add_prepared(form.instance.pk, prepared, data.get("alt_text", ""), data.get("position"))
                        )
                        formset.deleted_objects.append(instance)
                        instance.delete()
                    except ImageUploadError as e:
                        messages.error(request, str(e))
                    continue
                instance.save()
                formset.changed_objects.append((instance, image_form.changed_data))


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "rating", "title", "user", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["product__name", "title", "body", "user__username"]
    readonly_fields = ["product", "user", "created_at", "updated_at"]
