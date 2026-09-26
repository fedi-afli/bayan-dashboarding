# bayan.com.tn

Upload a sales file (CSV / Excel / JSON — English, French or Arabic headers) and get a ready-to-read dashboard.
Users log in, top up prepaid **credits**, and spend 1 credit per dashboard built.

## Run locally

```bash
cp .env.example .env                      # first time only, then adjust
docker compose up -d                      # Postgres + Keycloak (login), http://localhost:8080
```

```bash
cd data_pipeline
python -m venv ../py_env && ../py_env/bin/pip install -r requirements.txt   # first time only
../py_env/bin/alembic upgrade head        # create / update the database schema
../py_env/bin/uvicorn api:app --port 8000
```

```bash
cd frontend
npm install                                # first time only
npx ng serve                               # http://localhost:4200
```

- **Dev login:** a ready-made test account is defined in [`auth/realm-bayan.dev.json`](auth/realm-bayan.dev.json) (dev only), or sign up with “Get started”.
- **Payments:** `PAYMENT_PROVIDER=dev` (default) shows a simulated checkout page — no money involved. For Konnect set `PAYMENT_PROVIDER=konnect`, `KONNECT_API_KEY`, `KONNECT_WALLET_ID` (sandbox base URL is the default).
- The API refuses to start if the database isn’t migrated — run `alembic upgrade head` after pulling.
- The first user to log in on an instance adopts the dashboards created before accounts existed (“Default workspace”).

## Architecture

```
Angular app ──login──▶ Keycloak (any OIDC provider)
     │ bearer token
     ▼
data_pipeline/api.py            composition root
 ├─ saas/     SaaS layer: token check, accounts, credits ledger, payments, public HTTP routes
 │            └─ payments/: provider-agnostic (dev, konnect) — credits change only after the
 │               provider confirms a payment server-to-server
 └─ engine/   data engine: profile → map columns → load → chart queries. Knows nothing about
              users or money; every call takes an opaque tenant id (= account id).
```

Rules (enforced by `tests/test_architecture.py`): `engine` never imports `saas`; `saas` only uses `engine.service`.
Database: SaaS tables live in schema `app`; engine tables in `public`; migrations in `data_pipeline/migrations/`.

### Credits
A dashboard's price comes from the resources it needs, quoted **before** building (`saas/pricing.py`):

| Resource | Rate | Measured on this server |
|---|---|---|
| Setup (charts, metadata, first render) | 0.5 credit | — |
| Data processed (rows × columns kept) | 1 credit / 1M cells | ≈ 2 µs CPU per cell (read + load) |
| Storage kept in Postgres | 1 credit / 25 MB | ≈ 13 bytes per cell; estimate within ±4% from 10k rows up |
| AI column matching | 0.25 credit / column | ≈ 0.8 s GPU per column |

Total rounded up, minimum 1 — e.g. 2k rows × 8 cols = 1 credit, 200k × 12 = 5, 500k × 15 = 13.
The quote is what's charged (never depends on server load). Rebuilding a dashboard only pays the difference
if the new version needs more; a failed build is refunded. Every build stores what it *actually* consumed next
to the quote in `app.dashboard_usage`, to recalibrate the rates:

```sql
SELECT quoted_credits, quote->'drivers'->>'storage_bytes' AS estimated, measured->>'storage_bytes' AS actual,
       measured->>'seconds' AS seconds FROM app.dashboard_usage ORDER BY id DESC;
```

- Every balance change is a row in `app.credit_ledger` (append-only); `app.accounts.credit_balance` is its cached total, updated under a row lock.
- New accounts get `WELCOME_CREDITS` (default 3). Pack prices are placeholders in `saas/credits.py: PACKS`.

## Tests

```bash
cd data_pipeline && ../py_env/bin/pytest          # uses its own `bayan_test` database, rebuilt from migrations
cd frontend && npx ng test --watch=false --browsers=ChromeHeadless
```

Terminal version of the pipeline: `cd data_pipeline && ../py_env/bin/python main.py path/to/file.csv`
