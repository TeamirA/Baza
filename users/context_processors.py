from django.conf import settings


def features(request):
    """Flags templates use to hide features that aren't configured yet."""
    return {
        "email_enabled": settings.EMAIL_ENABLED or settings.DEBUG,
        "store_name": settings.STORE_NAME,
        "demo_notice": settings.DEMO_NOTICE,
    }
