"""
Top-ups, independent of the provider:
  start_topup()         records a pending payment, asks the provider for a checkout URL
  handle_notification() the ONLY place credits are added: verifies the payment with
                        the provider server-to-server, then credits exactly once
"""

import json
from typing import Optional

from psycopg2.extras import Json

from .. import credits
from ..config import Settings
from ..db import transaction
from .base import PaymentProvider, PaymentProviderError


def build_provider(settings: Settings) -> PaymentProvider:
    if settings.payment_provider == "konnect":
        from .konnect import KonnectProvider
        return KonnectProvider(settings.konnect_api_base, settings.konnect_api_key, settings.konnect_wallet_id)
    if settings.payment_provider == "dev":
        from .dev import DevProvider
        return DevProvider(settings.public_api_url)
    raise ValueError(f"Unknown PAYMENT_PROVIDER {settings.payment_provider!r}")


def start_topup(provider: PaymentProvider, account_id: str, email: Optional[str], pack_code: str,
                public_api_url: str) -> dict:
    pack = credits.PACKS.get(pack_code)
    if pack is None:
        raise KeyError(pack_code)

    with transaction() as cur:
        cur.execute(
            """INSERT INTO app.payments (account_id, provider, pack_code, credits, amount_millimes)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (account_id, provider.name, pack.code, pack.credits, pack.price_millimes),
        )
        payment_id = str(cur.fetchone()["id"])

    try:
        checkout = provider.create_checkout(
            payment_id=payment_id,
            amount_millimes=pack.price_millimes,
            description=f"bayan — {pack.credits} credits",
            notify_url=f"{public_api_url.rstrip('/')}/webhooks/{provider.name}",
            customer_email=email,
        )
    except PaymentProviderError:
        with transaction() as cur:
            cur.execute("UPDATE app.payments SET status = 'failed' WHERE id = %s", (payment_id,))
        raise

    with transaction() as cur:
        cur.execute("UPDATE app.payments SET provider_ref = %s WHERE id = %s", (checkout.provider_ref, payment_id))
    return {"payment_id": payment_id, "checkout_url": checkout.url}


def handle_notification(provider: PaymentProvider, provider_ref: str) -> tuple[Optional[str], str]:
    """
    Returns (payment_id, outcome). outcome: credited | already_credited | pending | mismatch | unknown.
    Safe to call any number of times for the same payment.
    """
    with transaction() as cur:
        cur.execute(
            "SELECT id, account_id, credits, amount_millimes, pack_code FROM app.payments "
            "WHERE provider = %s AND provider_ref = %s",
            (provider.name, provider_ref),
        )
        payment = cur.fetchone()

    if payment is None:
        _log(provider.name, provider_ref, None, "unknown", {})
        return None, "unknown"

    payment_id = str(payment["id"])
    remote = provider.fetch_payment(provider_ref)  # server-to-server: the notification itself proves nothing

    if not remote.completed:
        outcome = "pending"
    elif remote.order_id != payment_id or (remote.amount_millimes or 0) < payment["amount_millimes"]:
        outcome = "mismatch"
    else:
        with transaction() as cur:
            cur.execute(
                "UPDATE app.payments SET status = 'paid', paid_at = now() "
                "WHERE id = %s AND status = 'pending' RETURNING id",
                (payment_id,),
            )
            if cur.fetchone():
                credits.grant(cur, str(payment["account_id"]), payment["credits"], "topup", payment_id,
                              f"Top-up: {payment['credits']} credits")
                outcome = "credited"
            else:
                outcome = "already_credited"

    _log(provider.name, provider_ref, payment_id, outcome, remote.raw)
    return payment_id, outcome


def _log(provider: str, provider_ref: str, payment_id: Optional[str], outcome: str, detail: dict) -> None:
    with transaction() as cur:
        cur.execute(
            "INSERT INTO app.payment_notifications (provider, provider_ref, payment_id, outcome, detail) "
            "VALUES (%s, %s, %s, %s, %s)",
            (provider, provider_ref, payment_id, outcome, Json(detail, dumps=lambda o: json.dumps(o, default=str))),
        )
