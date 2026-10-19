from django.conf import settings
from django.conf.urls.static import static
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

if settings.DEBUG:
    # Locally uploaded photos (production serves them from Vercel Blob).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
