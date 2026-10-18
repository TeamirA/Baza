from django_components import Component, register


@register("qty_stepper")
class QtyStepper(Component):
    """Quantity input with − / + buttons; still a plain number input without JS.

    Usage:
        {% component "qty_stepper" name="quantity" value=1 min=1 max=product.stock
                     input_id="qty" label="Quantity" / %}

    In a list, pass key=<unique value> instead of input_id; the id becomes
    "<name>-<key>".

    Button presses fire a bubbling "change" event on the input, so forms can
    react to it (the cart auto-submits on change).
    """

    template_file = "qty_stepper.html"
    css_file = "qty_stepper.css"
    js_file = "qty_stepper.js"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "name": kwargs.get("name", "quantity"),
            "value": kwargs.get("value", 1),
            "min": kwargs.get("min", 1),
            "max": kwargs.get("max"),
            "input_id": kwargs.get("input_id") or f"{kwargs.get('name', 'quantity')}-{kwargs['key']}",
            "label": kwargs.get("label", "Quantity"),
        }
