from django_components import Component, register


@register("stock_badge")
class StockBadge(Component):
    """Sold out / Only N left / In stock. Usage: {% component "stock_badge" product=product / %}"""

    template_file = "stock_badge.html"

    def get_template_data(self, args, kwargs, slots, context):
        return {"product": kwargs["product"]}
