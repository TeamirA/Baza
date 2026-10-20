from django.conf import settings
from django.db import models


class Address(models.Model):
    """A shipping address saved to an account, offered at checkout."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, blank=True, help_text='e.g. "Home" or "Work"')
    full_name = models.CharField(max_length=200)
    address = models.TextField(max_length=1000)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at", "-id"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return self.label or self.full_name
