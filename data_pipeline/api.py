"""
bayan.com.tn API — composition root.

    engine/   the data engine: files -> mapping -> tables -> chart data.
              Knows nothing about users, accounts or money (takes a tenant id).
    saas/     the SaaS layer: login (OIDC tokens), accounts, credits, payments,
              and the public HTTP API that calls the engine.

Rule: saas may import engine.service; engine never imports saas
(enforced by tests/test_architecture.py).

Run:  ../py_env/bin/alembic upgrade head && ../py_env/bin/uvicorn api:app --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from engine.queries import ChartUnavailable
from engine.service import Engine, EngineError, InvalidUpload, LoadFailed, MappingInvalid, NotFound, NotReady
from saas import credits
from saas.auth import TokenVerifier
from saas.config import settings
from saas.db import get_connection
from saas.payments import PaymentProvider, build_provider
from saas.routes import credits as credits_routes
from saas.routes import dashboards, me, webhooks

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"


def ensure_database_is_migrated() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(Config(str(BASE_DIR / "alembic.ini"))).get_current_head()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('alembic_version')")
            current = None
            if cur.fetchone()[0]:
                cur.execute("SELECT version_num FROM alembic_version")
                row = cur.fetchone()
                current = row[0] if row else None
    finally:
        conn.close()
    if current != head:
        raise RuntimeError(
            f"Database schema is at {current or 'nothing'}, the code expects {head}. "
            f"Run: cd data_pipeline && ../py_env/bin/alembic upgrade head"
        )


def create_app(engine: Optional[Engine] = None, verifier: Optional[TokenVerifier] = None,
               payment_provider: Optional[PaymentProvider] = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_database_is_migrated()
        if engine is None:
            # loads the embedding model + LLM once per process
            from engine.mapper.mapper import BayanMapper
            app.state.engine = Engine(BayanMapper(), UPLOAD_DIR, settings.max_upload_mb * 1024 * 1024)
        yield

    app = FastAPI(title="bayan.com.tn API", lifespan=lifespan)
    app.state.engine = engine
    app.state.verifier = verifier or TokenVerifier(settings.oidc_issuer, settings.oidc_audience)
    app.state.payments = payment_provider or build_provider(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # engine errors -> HTTP (routes stay free of try/except)
    status_for = {NotFound: 404, NotReady: 409, InvalidUpload: 400, LoadFailed: 500}

    @app.exception_handler(MappingInvalid)
    async def _mapping_invalid(_: Request, e: MappingInvalid):
        return JSONResponse({"detail": {"errors": e.errors, "warnings": e.warnings}}, status_code=400)

    @app.exception_handler(EngineError)
    async def _engine_error(_: Request, e: EngineError):
        code = next((c for t, c in status_for.items() if isinstance(e, t)), 400)
        return JSONResponse({"detail": str(e)}, status_code=code)

    @app.exception_handler(ChartUnavailable)
    async def _chart_unavailable(_: Request, e: ChartUnavailable):
        return JSONResponse({"detail": str(e)}, status_code=422)

    @app.exception_handler(credits.InsufficientCredits)
    async def _insufficient(_: Request, e: credits.InsufficientCredits):
        return JSONResponse(
            {"detail": {"code": "insufficient_credits", "message": str(e),
                        "balance": e.balance, "needed": e.needed}},
            status_code=402,
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(me.router)
    app.include_router(dashboards.router)
    app.include_router(credits_routes.router)
    app.include_router(webhooks.router)
    if app.state.payments.name == "dev":
        app.include_router(app.state.payments.router())

    return app


app = create_app()
