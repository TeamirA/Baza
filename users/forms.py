from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="We'll send your order confirmations here.",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]

    def clean_email(self):
        from .services import UserService

        email = self.cleaned_data["email"].strip().lower()
        if UserService().email_taken(email):
            raise forms.ValidationError("An account with this email already exists.")
        return email


class AddressForm(forms.Form):
    label = forms.CharField(max_length=50, required=False, label="Label", help_text='Optional, e.g. "Home" or "Work".')
    full_name = forms.CharField(max_length=200, label="Full name", widget=forms.TextInput(attrs={"autocomplete": "name"}))
    address = forms.CharField(
        label="Address", widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}), max_length=1000
    )
    make_default = forms.BooleanField(required=False, label="Use as my default address")


class EmailChangeForm(forms.Form):
    """Changing the email needs the current password, since it's where reset links go."""

    email = forms.EmailField(label="New email", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        strip=False,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        from .services import UserService

        email = self.cleaned_data["email"].strip().lower()
        if email == (self.user.email or "").lower():
            raise forms.ValidationError("That's already your email.")
        if UserService().email_taken(email, exclude_user=self.user):
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("That password isn't right.")
        return password
