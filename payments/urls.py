from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<int:order_id>/", views.pay, name="pay"),
    path("success/", views.success, name="success"),
    path("cancel/<int:order_id>/", views.cancel, name="cancel"),
    path("webhook/", views.webhook, name="webhook"),
]
