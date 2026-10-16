from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class PaymentError(Exception):
    """A payment provider call failed; the message is safe to show to the user."""


class WebhookVerificationError(PaymentError):
    """The webhook payload or signature could not be verified."""


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str


@dataclass(frozen=True)
class PaymentResult:
    """Outcome of a checkout session, from a webhook or a status lookup."""

    session_id: str
    order_id: Optional[int]
    paid: bool


class PaymentGateway(ABC):
    """Interface every payment provider implements. Views and services only use this."""

    @abstractmethod
    def create_checkout_session(self, order, success_url, cancel_url) -> CheckoutSession:
        """Start a hosted checkout for an OrderDTO. success_url may contain
        "{CHECKOUT_SESSION_ID}", which the provider replaces with the session id."""

    @abstractmethod
    def get_session_result(self, session_id) -> PaymentResult:
        """Look up whether a checkout session has been paid."""

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> Optional[PaymentResult]:
        """Verify and parse a webhook. Returns a PaymentResult for completed
        checkouts, None for events we don't act on. Raises WebhookVerificationError."""
