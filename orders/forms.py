from django import forms


class ShippingForm(forms.Form):
    full_name = forms.CharField(
        max_length=200, label="Full name", widget=forms.TextInput(attrs={"autocomplete": "shipping name"})
    )
    email = forms.EmailField(
        label="Email", help_text="We'll send your receipt here.", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    address = forms.CharField(
        label="Shipping address",
        widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "shipping street-address"}),
        max_length=1000,
    )
    # Only offered to signed-in customers (see checkout.html).
    save_address = forms.BooleanField(required=False, label="Save this address to my account")

    def shipping_data(self):
        """The cleaned fields an order needs (without the checkout-only options)."""
        return {k: v for k, v in self.cleaned_data.items() if k != "save_address"}
