from django import forms


class ShippingForm(forms.Form):
    full_name = forms.CharField(max_length=200, label="Full name")
    email = forms.EmailField(label="Email", help_text="We'll send your receipt here.")
    address = forms.CharField(
        label="Shipping address", widget=forms.Textarea(attrs={"rows": 3}), max_length=1000
    )
