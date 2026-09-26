"""
Provider-agnostic payment interface. Adding a provider (Lemon Squeezy,
ClicToPay, …) means implementing these two methods — nothing else in the
app knows which provider is in use.
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol


class PaymentProviderError(Exception):
    """The provider couldn't be reached or refused the request."""


@dataclass(frozen=True)
class Checkout:
    provider_ref: str   # the provider's id for this payment
    url: str            # where to send the customer to pay


@dataclass(frozen=True)
class ProviderPayment:
    """What the provider says about a payment, fetched server-to-server (never trusted from the browser)."""
    completed: bool
    amount_millimes: Optional[int]
    order_id: Optional[str]
    raw: dict = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    def create_checkout(self, *, payment_id: str, amount_millimes: int, description: str,
                        notify_url: str, customer_email: Optional[str]) -> Checkout: ...

    def fetch_payment(self, provider_ref: str) -> ProviderPayment: ...
