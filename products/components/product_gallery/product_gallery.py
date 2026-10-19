from django_components import Component, register


@register("product_gallery")
class ProductGallery(Component):
    """Product photos: swipeable slides (CSS scroll-snap), thumbnails, tap to zoom.

    Usage: {% component "product_gallery" product=product / %}
    """

    template_file = "product_gallery.html"
    css_file = "product_gallery.css"
    js_file = "product_gallery.js"

    def get_template_data(self, args, kwargs, slots, context):
        product = kwargs["product"]
        return {"product": product, "images": product.images, "count": len(product.images)}
