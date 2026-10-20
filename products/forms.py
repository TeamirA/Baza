from django import forms

SORT_CHOICES = [
    ("", "Best match"),  # relevance with a search, newest without
    ("newest", "Newest"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("name", "Name: A–Z"),
]


class BrowseForm(forms.Form):
    """Validates the product list's query string. Bad values are dropped, not fatal."""

    q = forms.CharField(required=False, max_length=100, strip=True)
    category = forms.SlugField(required=False)
    min_price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label="Min price")
    max_price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label="Max price")
    in_stock = forms.BooleanField(required=False, label="In stock only")
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES, label="Sort by")
    exact = forms.BooleanField(required=False)

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("min_price"), cleaned.get("max_price")
        if low is not None and high is not None and low > high:
            cleaned["min_price"], cleaned["max_price"] = high, low  # be forgiving: swap them
        return cleaned


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=[(n, f"{n} star{'s' if n > 1 else ''}") for n in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect,
        label="Your rating",
        error_messages={"required": "Choose a star rating."},
    )
    title = forms.CharField(max_length=100, required=False, label="Headline")
    body = forms.CharField(
        max_length=2000, required=False, label="Your review", widget=forms.Textarea(attrs={"rows": 4})
    )
