"""Sends visitors on old addresses to the store's current one (SITE_URL)."""

from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class LegacyHostRedirectMiddleware:
    """Redirects page views on LEGACY_HOSTS to SITE_URL's host.

    Only GET/HEAD requests move. Webhooks (POST) and the daily cron keep
    working on the old address, since Stripe and cron don't follow redirects.
    """

    SKIP_PREFIXES = ("/cron/",)

    def __init__(self, get_response):
        self.get_response = get_response
        self.legacy_hosts = {h.lower() for h in settings.LEGACY_HOSTS}
        self.target = urlsplit(settings.SITE_URL)

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        if (
            host in self.legacy_hosts
            and host != self.target.hostname
            and request.method in ("GET", "HEAD")
            and not request.path.startswith(self.SKIP_PREFIXES)
        ):
            return HttpResponsePermanentRedirect(f"{self.target.scheme}://{self.target.netloc}{request.get_full_path()}")
        return self.get_response(request)
