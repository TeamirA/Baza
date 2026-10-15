from django.urls import include, path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    # login/, logout/, password_change/, password_reset/ ...
    path("", include("django.contrib.auth.urls")),
]
