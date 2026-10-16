from django_components import Component, register


@register("order_status")
class OrderStatus(Component):
    """Usage: {% component "order_status" status=order.status label=order.status_label / %}"""

    template_file = "order_status.html"
    css_file = "order_status.css"

    def get_template_data(self, args, kwargs, slots, context):
        return {"status": kwargs["status"], "label": kwargs["label"]}
