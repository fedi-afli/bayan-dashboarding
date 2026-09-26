"""
Prepaid credits.

Every balance change is a row in app.credit_ledger (append-only);
app.accounts.credit_balance is a cached running total, updated in the same
transaction under a row lock, so concurrent requests can't overspend.

Idempotency:
  - top-ups / welcome bonus / refunds: unique (kind, ref) — a provider
    retrying its callback can't credit twice
  - dashboards: app.dashboard_charges.credits_paid — a dashboard is paid up to
    its quote (saas/pricing.py). Rebuilding it only costs the difference if the
    new version needs more resources, never less than nothing.
"""

from dataclasses import dataclass
from typing import Optional

from psycopg2.extras import Json

from .db import transaction


@dataclass(frozen=True)
class Pack:
    code: str
    credits: int
    price_millimes: int  # 1 TND = 1000 millimes

    def as_dict(self) -> dict:
        return {"code": self.code, "credits": self.credits,
                "price_millimes": self.price_millimes, "price_tnd": self.price_millimes / 1000}


# Placeholder prices — change here, nothing else depends on the numbers.
PACKS = {
    p.code: p for p in [
        Pack("starter", credits=10, price_millimes=10_000),
        Pack("standard", credits=30, price_millimes=25_000),
        Pack("business", credits=100, price_millimes=70_000),
    ]
}


class InsufficientCredits(Exception):
    def __init__(self, balance: int, needed: int):
        super().__init__(f"This needs {needed} credit(s), you have {balance}.")
        self.balance = balance
        self.needed = needed


def _apply(cur, account_id: str, delta: int, kind: str, ref: str, description: str) -> Optional[int]:
    """Insert one ledger row and move the cached balance. Returns the ledger id, or None if already applied."""
    cur.execute("SELECT credit_balance FROM app.accounts WHERE id = %s FOR UPDATE", (account_id,))
    balance = cur.fetchone()["credit_balance"]
    new_balance = balance + delta
    if new_balance < 0:
        raise InsufficientCredits(balance, -delta)
    cur.execute(
        """INSERT INTO app.credit_ledger (account_id, delta, balance_after, kind, ref, description)
           VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id""",
        (account_id, delta, new_balance, kind, ref, description),
    )
    row = cur.fetchone()
    if row is None:
        return None
    cur.execute("UPDATE app.accounts SET credit_balance = %s WHERE id = %s", (new_balance, account_id))
    return row["id"]


def grant(cur, account_id: str, amount: int, kind: str, ref: str, description: str) -> Optional[int]:
    """Add credits (welcome / topup / adjustment) inside the caller's transaction."""
    assert amount > 0
    return _apply(cur, account_id, amount, kind, ref, description)


def balance(account_id: str) -> int:
    with transaction() as cur:
        cur.execute("SELECT credit_balance FROM app.accounts WHERE id = %s", (account_id,))
        return cur.fetchone()["credit_balance"]


@dataclass(frozen=True)
class Charge:
    amount: int                 # credits taken by this call (0 if already covered)
    ledger_id: Optional[int]    # ledger row of this call, None if nothing was charged
    paid_total: int             # credits paid for this dashboard so far, this call included


def credits_paid(dataset_id: str) -> int:
    with transaction() as cur:
        cur.execute("SELECT credits_paid FROM app.dashboard_charges WHERE dataset_id = %s", (dataset_id,))
        row = cur.fetchone()
        return row["credits_paid"] if row else 0


def credits_paid_by_dataset(account_id: str) -> dict[str, int]:
    with transaction() as cur:
        cur.execute("SELECT dataset_id, credits_paid FROM app.dashboard_charges WHERE account_id = %s",
                    (account_id,))
        return {r["dataset_id"]: r["credits_paid"] for r in cur.fetchall()}


def charge_dashboard(account_id: str, dataset_id: str, quoted: int, description: str) -> Charge:
    """
    Make sure `quoted` credits have been paid for this dashboard: charges only
    what's missing. Raises InsufficientCredits (nothing is charged then).
    """
    with transaction() as cur:
        # one charge at a time per dashboard (double clicks, parallel tabs)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('bayan.dashboard:' || %s))", (dataset_id,))
        cur.execute("SELECT credits_paid FROM app.dashboard_charges WHERE dataset_id = %s", (dataset_id,))
        row = cur.fetchone()
        paid = row["credits_paid"] if row else 0
        due = quoted - paid
        if due <= 0:
            return Charge(0, None, paid)
        ledger_id = _apply(cur, account_id, -due, "dashboard", dataset_id, description)
        cur.execute(
            """INSERT INTO app.dashboard_charges (dataset_id, account_id, credits_paid) VALUES (%s, %s, %s)
               ON CONFLICT (dataset_id) DO UPDATE
               SET credits_paid = app.dashboard_charges.credits_paid + EXCLUDED.credits_paid, updated_at = now()""",
            (dataset_id, account_id, due),
        )
        return Charge(due, ledger_id, paid + due)


def refund_charge(account_id: str, dataset_id: str, charge: Charge, reason: str) -> None:
    """Give back what one charge_dashboard() call took (the build failed). Safe to call more than once."""
    if not charge.amount or charge.ledger_id is None:
        return
    with transaction() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('bayan.dashboard:' || %s))", (dataset_id,))
        refunded = _apply(cur, account_id, charge.amount, "refund", str(charge.ledger_id), f"Refund: {reason}")
        if refunded is None:
            return  # already refunded
        cur.execute(
            "UPDATE app.dashboard_charges SET credits_paid = credits_paid - %s, updated_at = now() "
            "WHERE dataset_id = %s AND credits_paid > %s",
            (charge.amount, dataset_id, charge.amount),
        )
        if cur.rowcount == 0:
            cur.execute("DELETE FROM app.dashboard_charges WHERE dataset_id = %s", (dataset_id,))


def record_usage(account_id: str, dataset_id: str, quote: dict, charged: int, measured: dict) -> None:
    """Keep the quote next to what the build really consumed (for recalibrating pricing)."""
    with transaction() as cur:
        cur.execute(
            """INSERT INTO app.dashboard_usage (dataset_id, account_id, quoted_credits, charged_credits, quote, measured)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (dataset_id, account_id, quote["credits"], charged, Json(quote), Json(measured)),
        )


def history(account_id: str, limit: int = 100) -> list[dict]:
    with transaction() as cur:
        cur.execute(
            """SELECT id, delta, balance_after, kind, description, created_at
               FROM app.credit_ledger WHERE account_id = %s ORDER BY id DESC LIMIT %s""",
            (account_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]
