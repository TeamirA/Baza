from django.conf import settings
from django.core.management.base import BaseCommand

from payments.services import PaymentService


class Command(BaseCommand):
    help = "Cancel unpaid orders older than ORDER_HOLD_HOURS and put their stock back."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=settings.ORDER_HOLD_HOURS)

    def handle(self, *args, hours, **options):
        cancelled = PaymentService().expire_unpaid_orders(hours)
        self.stdout.write(self.style.SUCCESS(f"Cancelled {cancelled} unpaid order(s) older than {hours}h."))
