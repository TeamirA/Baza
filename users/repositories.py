"""The only module in the users app that talks to the ORM."""

from django.contrib.auth.models import User
from django.db import transaction

from .models import Address


class UserRepository:
    def create(self, username, email, password):
        return User.objects.create_user(username=username, email=email, password=password)

    def email_exists(self, email, exclude_user_id=None):
        users = User.objects.filter(email__iexact=email)
        if exclude_user_id is not None:
            users = users.exclude(pk=exclude_user_id)
        return users.exists()

    def set_email(self, user_id, email):
        User.objects.filter(pk=user_id).update(email=email)


class AddressRepository:
    def list_for_user(self, user_id):
        return list(Address.objects.filter(user_id=user_id))

    def get_for_user(self, address_id, user_id):
        return Address.objects.filter(pk=address_id, user_id=user_id).first()

    def count_for_user(self, user_id):
        return Address.objects.filter(user_id=user_id).count()

    def find_same(self, user_id, full_name, address):
        return Address.objects.filter(user_id=user_id, full_name__iexact=full_name, address__iexact=address).first()

    @transaction.atomic
    def create(self, user_id, label, full_name, address, is_default):
        if is_default:
            Address.objects.filter(user_id=user_id, is_default=True).update(is_default=False)
        return Address.objects.create(
            user_id=user_id, label=label, full_name=full_name, address=address, is_default=is_default
        )

    @transaction.atomic
    def set_default(self, address_id, user_id):
        if not Address.objects.filter(pk=address_id, user_id=user_id).exists():
            return False
        Address.objects.filter(user_id=user_id, is_default=True).exclude(pk=address_id).update(is_default=False)
        Address.objects.filter(pk=address_id).update(is_default=True)
        return True

    @transaction.atomic
    def delete(self, address_id, user_id):
        """Deletes an address; if it was the default, the newest remaining one takes over."""
        address = Address.objects.select_for_update().filter(pk=address_id, user_id=user_id).first()
        if address is None:
            return False
        was_default = address.is_default
        address.delete()
        if was_default:
            newest = Address.objects.filter(user_id=user_id).order_by("-created_at", "-id").first()
            if newest:
                Address.objects.filter(pk=newest.pk).update(is_default=True)
        return True
