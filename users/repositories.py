"""The only module in the users app that talks to the ORM."""

from django.contrib.auth.models import User


class UserRepository:
    def create(self, username, email, password):
        return User.objects.create_user(username=username, email=email, password=password)

    def email_exists(self, email):
        return User.objects.filter(email__iexact=email).exists()
