from django_components import Component, register


@register("theme_toggle")
class ThemeToggle(Component):
    """Header button that cycles the colour theme: System -> Light -> Dark.

    The choice is saved in localStorage ("theme") and applied as data-theme on
    <html>. base.html applies it again in <head> before first paint, so the page
    never flashes the wrong theme. Usage: {% component "theme_toggle" / %}
    """

    template_file = "theme_toggle.html"
    css_file = "theme_toggle.css"
    js_file = "theme_toggle.js"
