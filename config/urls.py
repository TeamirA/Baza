from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("users.urls")),
    path("payments/", include("payments.urls")),
    path("", include("django_components.urls")),
    path("", include("orders.urls")),
    path("", include("products.urls")),
]
