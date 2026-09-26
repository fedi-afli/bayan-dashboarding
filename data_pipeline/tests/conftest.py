import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Tests get their own database, built from the migrations every run.
TEST_DB = "bayan_test"
os.environ["POSTGRES_DB"] = TEST_DB
os.environ.setdefault("WELCOME_CREDITS", "3")
os.environ.setdefault("PAYMENT_PROVIDER", "dev")


def _admin_connection():
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(ROOT.parent / ".env")
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"), port=os.getenv("POSTGRES_PORT", "5432"),
        dbname="postgres", user=os.getenv("POSTGRES_USER", "bayan_user"),
        password=os.getenv("POSTGRES_PASSWORD", "bayan_pass"),
    )
    conn.autocommit = True
    return conn


try:
    _admin_connection().close()
    HAVE_DB = True
except Exception:
    HAVE_DB = False


@pytest.fixture(scope="session")
def migrated_db():
    if not HAVE_DB:
        pytest.skip("Postgres not reachable")
    conn = _admin_connection()
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        cur.execute(f"CREATE DATABASE {TEST_DB}")
    conn.close()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    yield TEST_DB
