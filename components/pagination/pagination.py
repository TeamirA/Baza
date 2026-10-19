from django_components import Component, register


@register("pagination")
class Pagination(Component):
    """Page links for a Django Page that keep the current filters.

    Usage: {% component "pagination" page=page_obj querystring=querystring / %}
    querystring is the current query string without "page" (e.g. "q=mug&sort=name").
    """

    template_file = "pagination.html"
    css_file = "pagination.css"

    def get_template_data(self, args, kwargs, slots, context):
        page = kwargs["page"]
        qs = kwargs.get("querystring", "")
        prefix = f"?{qs}&page=" if qs else "?page="
        current, last = page.number, page.paginator.num_pages
        # First, last, and two either side of the current page, with gaps as None.
        wanted = sorted({1, last, *range(max(1, current - 2), min(last, current + 2) + 1)})
        items, previous = [], 0
        for number in wanted:
            if number - previous > 1:
                items.append(None)
            items.append(number)
            previous = number
        return {"page": page, "prefix": prefix, "items": items}
