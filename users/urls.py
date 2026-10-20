from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import include, path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("profile/email/", views.email_change, name="email_change"),
    path("profile/addresses/add/", views.address_add, name="address_add"),
    path("profile/addresses/<int:address_id>/default/", views.address_default, name="address_default"),
    path("profile/addresses/<int:address_id>/delete/", views.address_delete, name="address_delete"),
    # Reset emails are rendered without the request, so pass the store name in.
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(extra_email_context={"store_name": settings.STORE_NAME}),
        name="password_reset",
    ),
    # login/, logout/, password_change/, password_reset/ ...
    path("", include("django.contrib.auth.urls")),
]
