from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("products/<slug:slug>/", views.product_detail, name="detail"),
    path("search/suggest/", views.search_suggest, name="suggest"),
    path("saved/", views.wishlist, name="wishlist"),
    path("saved/toggle/<int:product_id>/", views.wishlist_toggle, name="wishlist_toggle"),
    path("saved/move-to-cart/<int:product_id>/", views.wishlist_move_to_cart, name="wishlist_move_to_cart"),
]
