from django_components import Component, register


@register("product_row")
class ProductRow(Component):
    """A titled row of product cards ("You might also like", "Recently viewed").

    Usage: {% component "product_row" title="Recently viewed" products=items / %}
    """

    template_file = "product_row.html"
    css_file = "product_row.css"

    def get_template_data(self, args, kwargs, slots, context):
        title = kwargs["title"]
        return {
            "title": title,
            "products": kwargs["products"],
            "heading_id": "row-" + "".join(c if c.isalnum() else "-" for c in title.lower()),
        }
