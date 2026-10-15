from django_components import Component, register


@register("notice")
class Notice(Component):
    """Non-error flash message. Usage: {% component "notice" message=msg / %}"""

    template_file = "notice.html"
    css_file = "notice.css"

    def get_template_data(self, args, kwargs, slots, context):
        return {"message": kwargs["message"]}
