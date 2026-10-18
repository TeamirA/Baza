import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def give_existing_orders_their_own_token(apps, schema_editor):
    # A unique field's default is evaluated once when added to existing rows, so
    # every existing order would share one token. Assign a fresh one to each.
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(access_token__isnull=True).only("pk"):
        order.access_token = uuid.uuid4()
        order.save(update_fields=["access_token"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0003_cart_item"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(give_existing_orders_their_own_token, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
