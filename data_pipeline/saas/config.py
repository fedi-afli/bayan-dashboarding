"""SaaS-layer settings, all from the environment (see .env.example at the repo root)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    # identity provider (any OIDC provider: Keycloak locally, Auth0 etc. later)
    oidc_issuer: str = _env("OIDC_ISSUER", "http://localhost:8080/realms/bayan")
    oidc_audience: str = _env("OIDC_AUDIENCE", "bayan-api")

    # where users are sent back after paying, and our own public base URL (webhooks)
    frontend_url: str = _env("FRONTEND_URL", "http://localhost:4200")
    public_api_url: str = _env("PUBLIC_API_URL", "http://localhost:8000")
    cors_origins: list = field(default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:4200").split(","))

    # credits
    welcome_credits: int = int(_env("WELCOME_CREDITS", "3"))

    # payments: "dev" (local simulated checkout) or "konnect"
    payment_provider: str = _env("PAYMENT_PROVIDER", "dev")
    konnect_api_base: str = _env("KONNECT_API_BASE", "https://api.sandbox.konnect.network/api/v2")
    konnect_api_key: str = _env("KONNECT_API_KEY", "")
    konnect_wallet_id: str = _env("KONNECT_WALLET_ID", "")

    # engine
    max_upload_mb: int = int(_env("MAX_UPLOAD_MB", "50"))


settings = Settings()
