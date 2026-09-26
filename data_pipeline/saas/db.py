"""SaaS-layer database access (schema `app`). Kept separate from engine/db.py on purpose:
the two sides may live in different services one day."""

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from . import config  # noqa: F401  (loads .env)


def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "bayan"),
        user=os.getenv("POSTGRES_USER", "bayan_user"),
        password=os.getenv("POSTGRES_PASSWORD", "bayan_pass"),
    )


@contextmanager
def transaction():
    """Yields a dict cursor inside one transaction (commit on success, rollback on error)."""
    conn = get_connection()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        conn.close()
