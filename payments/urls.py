from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<uuid:token>/", views.pay, name="pay"),
    path("success/", views.success, name="success"),
    path("cancel/<uuid:token>/", views.cancel, name="cancel"),
    path("webhook/", views.webhook, name="webhook"),
]
