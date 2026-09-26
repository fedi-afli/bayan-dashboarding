"""
Users and accounts. An account is the tenant: it owns dashboards and
credits. Today every user gets their own account; the model already
allows several users per account later (teams).
"""

from dataclasses import dataclass
from typing import Optional

from . import credits
from .auth import Principal
from .config import settings
from .db import transaction

# created by migration 0002; holds everything made before accounts existed
DEFAULT_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    account_id: str
    email: Optional[str]
    name: Optional[str]


def ensure_user(principal: Principal) -> CurrentUser:
    """
    Look up the user behind a verified token, creating user + account on
    first login. The very first user of an instance adopts the "Default
    workspace" (pre-login dashboards). New accounts get welcome credits.
    """
    with transaction() as cur:
        cur.execute(
            """UPDATE app.users SET last_seen_at = now(), email = COALESCE(%s, email),
                      display_name = COALESCE(%s, display_name)
               WHERE idp_subject = %s RETURNING id, account_id, email, display_name""",
            (principal.email, principal.name, principal.subject),
        )
        row = cur.fetchone()
        if row:
            return CurrentUser(str(row["id"]), str(row["account_id"]), row["email"], row["display_name"])

    with transaction() as cur:
        # serialize first logins so two users can't both adopt the default workspace
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('bayan.first_login'))")
        cur.execute("SELECT id, account_id, email, display_name FROM app.users WHERE idp_subject = %s",
                    (principal.subject,))
        row = cur.fetchone()
        if row:  # created concurrently by another request
            return CurrentUser(str(row["id"]), str(row["account_id"]), row["email"], row["display_name"])

        cur.execute("SELECT 1 FROM app.users WHERE account_id = %s LIMIT 1", (DEFAULT_ACCOUNT_ID,))
        default_taken = cur.fetchone() is not None
        if default_taken:
            label = principal.name or principal.email or "My account"
            cur.execute("INSERT INTO app.accounts (name) VALUES (%s) RETURNING id", (label,))
            account_id = str(cur.fetchone()["id"])
        else:
            account_id = DEFAULT_ACCOUNT_ID

        cur.execute(
            """INSERT INTO app.users (idp_subject, email, display_name, account_id)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (principal.subject, principal.email, principal.name, account_id),
        )
        user_id = str(cur.fetchone()["id"])

        if settings.welcome_credits > 0:
            credits.grant(cur, account_id, settings.welcome_credits, "welcome", account_id,
                          f"Welcome bonus: {settings.welcome_credits} free credits")

    return CurrentUser(user_id, account_id, principal.email, principal.name)


def get_account(account_id: str) -> dict:
    with transaction() as cur:
        cur.execute("SELECT id, name, credit_balance, created_at FROM app.accounts WHERE id = %s", (account_id,))
        row = cur.fetchone()
    return {**row, "id": str(row["id"])}
