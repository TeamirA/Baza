from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "products"

    def ready(self):
        warm_component_media()


def warm_component_media():
    """Resolve every registered component's template/CSS/JS once, at startup.

    django-components loads these lazily on first render and flags them as resolved
    before the template is assigned, so two concurrent first requests can crash with
    "received a Template instance which was not patched". Loading them here, in a
    single thread before any request is served, avoids that race.

    Runs after django_components' own ready() (it is earlier in INSTALLED_APPS),
    so autodiscovery has already registered all components.
    """
    from django_components import registry

    for component_cls in registry.all().values():
        component_cls.template
        component_cls.css
        component_cls.js
