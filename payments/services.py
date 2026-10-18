import logging

from orders.services import OrderError, OrderService

from .gateways import PaymentError, get_payment_gateway

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, gateway=None, orders=None):
        self._gateway = gateway
        self.orders = orders or OrderService()

    @property
    def gateway(self):
        if self._gateway is None:
            self._gateway = get_payment_gateway()
        return self._gateway

    def start_checkout(self, order, success_url, cancel_url):
        """Creates a hosted checkout for a pending OrderDTO and returns the URL to send the user to."""
        if not order.is_pending:
            raise OrderError(f"Order #{order.id} is already {order.status_label.lower()}.")
        session = self.gateway.create_checkout_session(order, success_url, cancel_url)
        self.orders.attach_payment_session(order.id, session.id)
        return session.url

    def confirm_checkout(self, session_id):
        """Called when the user returns from checkout. Returns the order id.

        The webhook is the source of truth in production; this makes the order
        show as paid immediately even if the webhook hasn't arrived yet.
        """
        result = self.gateway.get_session_result(session_id)
        if result.order_id is None:
            raise PaymentError("That payment session isn't linked to an order.")
        if result.paid:
            self.orders.mark_as_paid(result.order_id, result.session_id, result.amount_total)
        return result.order_id, result.paid

    def cancel_order(self, order):
        """Cancels a pending OrderDTO: closes its payment page first, and if the
        customer turns out to have paid already, marks it paid instead.

        Returns the order id and whether it was cancelled.
        """
        if order.payment_session_id and not self.gateway.expire_checkout_session(order.payment_session_id):
            result = self.gateway.get_session_result(order.payment_session_id)
            self.orders.mark_as_paid(order.id, result.session_id, result.amount_total)
            return order.id, False
        self.orders.cancel(order.id)
        return order.id, True

    def expire_unpaid_orders(self, hours):
        """Cancels pending orders older than `hours`. Returns how many were cancelled."""
        cancelled = 0
        for order_id in self.orders.pending_order_ids_older_than(hours):
            try:
                _, was_cancelled = self.cancel_order(self.orders.get_order(order_id))
                cancelled += was_cancelled
            except (OrderError, PaymentError) as e:
                logger.warning("Could not expire order %s: %s", order_id, e)
        return cancelled

    def handle_webhook(self, payload, signature):
        """Raises WebhookVerificationError for bad signatures."""
        result = self.gateway.verify_webhook(payload, signature)
        if result and result.paid and result.order_id is not None:
            changed = self.orders.mark_as_paid(result.order_id, result.session_id, result.amount_total)
            logger.info("Webhook: order %s paid (changed=%s)", result.order_id, changed)
        return result
