from urllib.parse import urlencode

from django.urls import reverse
from django_components import Component, register


@register("wishlist_button")
class WishlistButton(Component):
    """♥ toggle for a product. Reads `wishlist_ids` and `request` from the page context.

    Usage: {% component "wishlist_button" product=product / %}
           {% component "wishlist_button" product=product variant="large" / %}
    Signed-out shoppers get a link to log in (and come back to the same page).
    """

    template_file = "wishlist_button.html"
    css_file = "wishlist_button.css"
    js_file = "wishlist_button.js"

    def get_template_data(self, args, kwargs, slots, context):
        product = kwargs["product"]
        request = context.get("request")
        user = getattr(request, "user", None)
        here = request.get_full_path() if request else "/"
        return {
            "product": product,
            "saved": product.id in (context.get("wishlist_ids") or ()),
            "signed_in": bool(user and user.is_authenticated),
            "action": reverse("products:wishlist_toggle", args=[product.id]),
            "login_url": f"{reverse('login')}?{urlencode({'next': here, 'reason': 'save'})}",
            "next": here,
            "large": kwargs.get("variant") == "large",
        }
