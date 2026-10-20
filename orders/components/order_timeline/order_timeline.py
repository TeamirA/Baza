from django_components import Component, register


@register("order_timeline")
class OrderTimeline(Component):
    """Placed → Paid → Shipped (or → Cancelled). Usage: {% component "order_timeline" order=order / %}"""

    template_file = "order_timeline.html"
    css_file = "order_timeline.css"

    def get_template_data(self, args, kwargs, slots, context):
        steps = kwargs["order"].timeline
        # The step after the last finished one is "in progress".
        done = [s.done for s in steps]
        current = done.index(False) if False in done else None
        return {"steps": [(step, i == current) for i, step in enumerate(steps)], "cancelled": kwargs["order"].status == "cancelled"}
