from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .cart import merge_session_cart_into_user


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    if request is not None:
        merge_session_cart_into_user(request.session, user)
