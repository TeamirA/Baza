from django_components import Component, register


@register("toast")
class Toast(Component):
    """Pop-up confirmation for non-error messages; fades out after a few seconds.

    Render inside the page's .toast-stack (see base.html), e.g.
    {% component "toast" message=msg / %}. Errors stay inline via error_card.
    """

    template_file = "toast.html"
    css_file = "toast.css"
    js_file = "toast.js"

    def get_template_data(self, args, kwargs, slots, context):
        return {"message": kwargs["message"]}
