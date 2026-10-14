from django_components import Component, register


@register("error_card")
class ErrorCard(Component):
    """Reusable, visible error message. Usage: {% component "error_card" message=error / %}"""

    template_file = "error_card.html"
    css_file = "error_card.css"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "message": kwargs.get("message", "Something went wrong."),
            "title": kwargs.get("title", "Something went wrong"),
        }
