from django.urls import include, path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("profile/email/", views.email_change, name="email_change"),
    path("profile/addresses/add/", views.address_add, name="address_add"),
    path("profile/addresses/<int:address_id>/default/", views.address_default, name="address_default"),
    path("profile/addresses/<int:address_id>/delete/", views.address_delete, name="address_delete"),
    # login/, logout/, password_change/, password_reset/ ...
    path("", include("django.contrib.auth.urls")),
]
