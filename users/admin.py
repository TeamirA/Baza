from django.contrib import admin

from .models import Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "label", "full_name", "is_default", "created_at"]
    search_fields = ["user__username", "full_name", "address"]
    readonly_fields = ["user", "created_at"]
