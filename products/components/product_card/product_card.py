from django_components import Component, register


@register("product_card")
class ProductCard(Component):
    """Usage: {% component "product_card" product=product / %} where product is a ProductDTO."""

    template_file = "product_card.html"
    css_file = "product_card.css"

    def get_template_data(self, args, kwargs, slots, context):
        return {"product": kwargs["product"]}
