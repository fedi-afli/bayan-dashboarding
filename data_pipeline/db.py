import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # reads .env in the current working directory


def get_connection():
    """
    Opens a connection to the bayan_db Postgres container.
    Reads credentials from environment variables (see .env.example).
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "bayan"),
        user=os.getenv("POSTGRES_USER", "bayan_user"),
        password=os.getenv("POSTGRES_PASSWORD", "bayan_pass"),
    )


def execute_sql(sql: str, autocommit: bool = True):
    """
    Executes a SQL statement (e.g. a CREATE TABLE script) directly
    against bayan_db.
    """
    conn = get_connection()
    try:
        conn.autocommit = autocommit
        with conn.cursor() as cur:
            cur.execute(sql)
        print("[✓] SQL executed successfully against bayan_db")
    except Exception as e:
        conn.rollback()
        print(f"[✗] Failed to execute SQL: {e}")
        raise
    finally:
        conn.close()