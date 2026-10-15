from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="We'll send your order confirmations here.")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]

    def clean_email(self):
        from .services import UserService

        email = self.cleaned_data["email"].strip().lower()
        if UserService().email_taken(email):
            raise forms.ValidationError("An account with this email already exists.")
        return email
