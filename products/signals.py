from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from config.media_store import get_media_store

from .models import ProductImage


@receiver(post_delete, sender=ProductImage)
def delete_photo_files(sender, instance, **kwargs):
    """Remove a photo's files once its row is gone (admin delete, product delete...).
    Runs after commit so a rolled-back delete never loses files."""
    urls = list(instance.variants.values())
    transaction.on_commit(lambda: get_media_store().delete(urls))
