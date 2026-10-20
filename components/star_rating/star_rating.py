from django_components import Component, register


@register("star_rating")
class StarRating(Component):
    """Read-only stars. Usage: {% component "star_rating" rating=4.5 count=12 / %}
    (count is optional; size="large" for the product page summary)."""

    template_file = "star_rating.html"
    css_file = "star_rating.css"

    def get_template_data(self, args, kwargs, slots, context):
        rating = float(kwargs.get("rating") or 0)
        return {
            "rating": rating,
            "label": f"{rating:.1f}".rstrip("0").rstrip("."),
            "percent": max(0, min(100, rating / 5 * 100)),
            "count": kwargs.get("count"),
            "large": kwargs.get("size") == "large",
        }
