from django_components import Component, register


@register("form_field")
class FormField(Component):
    """Renders one bound form field with label, help text and errors.

    Usage: {% component "form_field" field=form.username / %}
    """

    template_file = "form_field.html"
    css_file = "form_field.css"

    def get_template_data(self, args, kwargs, slots, context):
        return {"field": kwargs["field"]}
