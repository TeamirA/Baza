from django.urls import reverse
from django_components import Component, register


@register("search_box")
class SearchBox(Component):
    """Header search: a plain GET form, enhanced with live suggestions and recent
    searches when JavaScript runs (ARIA combobox pattern).

    Usage: {% component "search_box" query=query / %}
    """

    template_file = "search_box.html"
    css_file = "search_box.css"
    js_file = "search_box.js"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "query": kwargs.get("query") or "",
            "action": reverse("products:list"),
            "suggest_url": reverse("products:suggest"),
        }
