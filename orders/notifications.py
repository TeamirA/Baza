"""Customer emails about orders. Sending never raises: a failed email is logged
and must not break payment handling or the admin."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)

KINDS = ("confirmation", "shipped")


def order_link(order):
    # The private link works for guests and members alike, from any device.
    return settings.SITE_URL + reverse("orders:track", args=[order.access_token])


def send_order_email(order, kind):
    """Sends the `kind` email for an OrderDTO. Returns True if it was handed to the mail backend."""
    if kind not in KINDS:
        raise ValueError(f"Unknown order email: {kind}")
    if not order.email:
        return False
    context = {"order": order, "link": order_link(order), "store_name": settings.STORE_NAME}
    subject = render_to_string(f"orders/emails/{kind}_subject.txt", context).strip()
    body = render_to_string(f"orders/emails/{kind}.txt", context)
    try:
        send_mail(subject, body, None, [order.email])
    except Exception:
        logger.exception("Could not send %s email for order %s", kind, order.id)
        return False
    return True
