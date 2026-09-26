"""
End-to-end through HTTP: login -> account + welcome credits -> upload -> build
(credit spent) -> history; top-ups through the dev payment provider; isolation
between accounts. Uses real signed tokens and the migrated test database.
"""
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from engine.mapper.mapper import BayanMapper
from engine.service import Engine, LoadFailed
from saas.auth import TokenVerifier
from saas.db import transaction
from saas.payments.dev import DevProvider
from tests.tokens import AUDIENCE, ISSUER, PUBLIC_KEY, make_token

CSV = "Jour,Article,Qte,Montant,Ville\n2024-01-03,Chaise,2,80,Tunis\n2024-01-04,Table,1,250,Sfax\n2024-02-10,Chaise,5,200,Sousse\n"


def big_csv(rows=60_000):
    """~2.5 MB, 6 columns: big enough that it costs more than the minimum."""
    lines = ["Jour,Article,Qte,Montant,Ville,Client"]
    for i in range(rows):
        lines.append(f"2024-{1 + i % 12:02d}-{1 + i % 28:02d},Article {i % 500},{1 + i % 9},{(i % 997) * 1.5:.2f},"
                     f"Ville {i % 24},Client numero {i % 3000}")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def client(migrated_db, tmp_path_factory):
    import api

    engine = Engine(BayanMapper(load_llm=False), tmp_path_factory.mktemp("uploads"), 20 * 1024 * 1024)
    app = api.create_app(
        engine=engine,
        verifier=TokenVerifier(ISSUER, AUDIENCE, key_resolver=lambda _: PUBLIC_KEY),
        payment_provider=DevProvider("http://testserver"),
    )
    with TestClient(app) as c:
        c.engine = engine
        yield c


def login(client):
    """A brand-new user; returns request headers."""
    return {"Authorization": f"Bearer {make_token('user-' + uuid.uuid4().hex[:8])}"}


def upload(client, headers, csv=CSV, name="ventes.csv"):
    r = client.post("/datasets/upload", headers=headers, files={"file": (name, csv.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def mapping_of(review):
    return {c["name"]: c["target"] for c in review["result"]["columns"]}


def balance(client, headers):
    return client.get("/me", headers=headers).json()["account"]["credit_balance"]


# ---------------------------------------------------------------------------

def test_requires_login(client):
    assert client.get("/datasets").status_code == 401
    assert client.get("/datasets", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_first_login_creates_account_with_welcome_credits(client):
    h = login(client)
    me = client.get("/me", headers=h).json()
    assert me["account"]["credit_balance"] == 3
    history = client.get("/credits", headers=h).json()["history"]
    assert [e["kind"] for e in history] == ["welcome"]
    # logging in again doesn't grant it twice
    assert balance(client, h) == 3


def test_building_a_dashboard_spends_one_credit_and_rebuilds_are_free(client):
    h = login(client)
    review = upload(client, h)
    q = review["quote"]
    assert (q["credits"], q["due"], q["paid"], q["balance"]) == (1, 1, 0, 3)

    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert r.status_code == 200, r.text
    assert r.json()["credits"] == {"charged": 1, "total_paid": 1, "balance": 2}

    # re-mapping the same dashboard later costs nothing (it doesn't need more resources)
    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert r.json()["credits"] == {"charged": 0, "total_paid": 1, "balance": 2}

    dashboards = client.get("/datasets", headers=h).json()
    assert [(d["filename"], d["credits_used"]) for d in dashboards] == [("ventes.csv", 1)]
    kinds = [e["kind"] for e in client.get("/credits", headers=h).json()["history"]]
    assert kinds == ["dashboard", "welcome"]


def test_invalid_mapping_costs_nothing(client):
    h = login(client)
    review = upload(client, h)
    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h,
                    json={"mapping": {"Montant": "revenue) SELECT 1; --"}})
    assert r.status_code == 400
    assert balance(client, h) == 3


def test_out_of_credits_blocks_new_dashboards(client):
    h = login(client)
    for _ in range(3):
        review = upload(client, h)
        client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert balance(client, h) == 0

    review = upload(client, h)
    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "insufficient_credits"
    listed = client.get("/datasets", headers=h).json()
    assert [d["status"] for d in listed].count("ready") == 3
    assert [d["status"] for d in listed].count("pending") == 1   # kept as a draft to build after topping up


def test_failed_build_is_refunded(client, monkeypatch):
    h = login(client)
    review = upload(client, h)

    def boom(*a, **kw):
        raise LoadFailed("disk full")

    monkeypatch.setattr(client.engine, "build_dashboard", boom)
    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert r.status_code == 500
    assert balance(client, h) == 3
    assert [e["kind"] for e in client.get("/credits", headers=h).json()["history"]] == ["refund", "dashboard", "welcome"]

    monkeypatch.undo()  # retry works and is charged normally
    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert r.status_code == 200 and balance(client, h) == 2


def test_accounts_are_isolated(client):
    alice, bob = login(client), login(client)
    review = upload(client, alice)
    ds = review["dataset_id"]
    client.post(f"/datasets/{ds}/confirm", headers=alice, json={"mapping": mapping_of(review)})

    assert client.get(f"/datasets/{ds}", headers=bob).status_code == 404
    assert client.get(f"/datasets/{ds}/review", headers=bob).status_code == 404
    assert client.post(f"/datasets/{ds}/confirm", headers=bob, json={"mapping": mapping_of(review)}).status_code == 404
    assert client.delete(f"/datasets/{ds}", headers=bob).status_code == 404
    assert client.get("/datasets", headers=bob).json() == []
    assert balance(client, bob) == 3


# ---------------------------------------------------------------------------
# resource-based pricing
# ---------------------------------------------------------------------------

def test_bigger_files_cost_more_and_the_quote_is_what_gets_charged(client):
    h = login(client)
    review = upload(client, h, big_csv(), "grand.csv")
    q = review["quote"]
    assert q["credits"] >= 2
    assert q["drivers"]["rows"] == 60_000 and q["drivers"]["columns"] == 6
    assert {line["key"] for line in q["lines"]} >= {"base", "processing", "storage"}

    r = client.post(f"/datasets/{review['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(review)})
    assert r.status_code == 200, r.text
    assert r.json()["credits"]["charged"] == q["credits"]
    assert balance(client, h) == 3 - q["credits"]

    # the build's real resource use is recorded next to the quote
    with transaction() as cur:
        cur.execute("SELECT quoted_credits, charged_credits, quote, measured FROM app.dashboard_usage "
                    "WHERE dataset_id = %s", (review["dataset_id"],))
        row = cur.fetchone()
    assert row["quoted_credits"] == row["charged_credits"] == q["credits"]
    measured, estimated = row["measured"]["storage_bytes"], row["quote"]["drivers"]["storage_bytes"]
    assert row["measured"]["cells"] == 360_000 and row["measured"]["seconds"] > 0
    assert abs(measured - estimated) / measured < 0.25   # the estimate the user saw was close to reality


def test_rebuilding_with_more_data_pays_only_the_difference(client):
    h = login(client)
    review = upload(client, h, big_csv(), "grand.csv")
    ds, full = review["dataset_id"], mapping_of(review)
    small = {col: (tgt if col in ("Jour", "Montant") else None) for col, tgt in full.items()}

    small_q = client.post(f"/datasets/{ds}/quote", headers=h, json={"mapping": small}).json()
    full_q = client.post(f"/datasets/{ds}/quote", headers=h, json={"mapping": full}).json()
    assert small_q["credits"] < full_q["credits"]

    r = client.post(f"/datasets/{ds}/confirm", headers=h, json={"mapping": small})
    assert r.json()["credits"]["charged"] == small_q["credits"]

    # adding the other columns later: only the difference is due…
    again = client.post(f"/datasets/{ds}/quote", headers=h, json={"mapping": full}).json()
    assert again["paid"] == small_q["credits"] and again["due"] == full_q["credits"] - small_q["credits"]
    r = client.post(f"/datasets/{ds}/confirm", headers=h, json={"mapping": full})
    assert r.json()["credits"] == {"charged": again["due"], "total_paid": full_q["credits"],
                                   "balance": 3 - full_q["credits"]}

    # …and going back to fewer columns is free (no refunds for downsizing)
    r = client.post(f"/datasets/{ds}/confirm", headers=h, json={"mapping": small})
    assert r.json()["credits"]["charged"] == 0
    history = client.get("/credits", headers=h).json()["history"]
    assert history[0]["description"].startswith("Dashboard update: grand.csv")


def test_a_quote_above_the_balance_is_refused_without_charging(client):
    h = login(client)
    first = upload(client, h, big_csv(), "a.csv")
    client.post(f"/datasets/{first['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(first)})
    left = balance(client, h)

    second = upload(client, h, big_csv(), "b.csv")
    assert second["quote"]["due"] > left
    r = client.post(f"/datasets/{second['dataset_id']}/confirm", headers=h, json={"mapping": mapping_of(second)})
    assert r.status_code == 402
    assert r.json()["detail"]["needed"] == second["quote"]["due"]
    assert balance(client, h) == left


def test_quote_needs_the_owner(client):
    alice, bob = login(client), login(client)
    review = upload(client, alice)
    r = client.post(f"/datasets/{review['dataset_id']}/quote", headers=bob, json={"mapping": mapping_of(review)})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# top-ups
# ---------------------------------------------------------------------------

def start_checkout(client, h, pack="starter"):
    r = client.post("/credits/checkout", headers=h, json={"pack": pack})
    assert r.status_code == 200, r.text
    url = r.json()["checkout_url"]
    return urlparse(url).path.rsplit("/", 1)[-1]  # the provider ref


def notify(client, ref):
    r = client.get(f"/webhooks/dev?payment_ref={ref}", follow_redirects=False)
    assert r.status_code == 303
    return parse_qs(urlparse(r.headers["location"]).query)["status"][0]


def test_topup_credits_only_after_the_provider_confirms(client):
    h = login(client)
    ref = start_checkout(client, h, "starter")

    # a notification before paying (or a forged one) changes nothing
    assert notify(client, ref) == "pending"
    assert balance(client, h) == 3

    r = client.post(f"/payments/dev/checkout/{ref}/pay", follow_redirects=False)
    assert r.headers["location"].endswith(f"/webhooks/dev?payment_ref={ref}")
    assert notify(client, ref) == "credited"
    assert balance(client, h) == 13

    # providers retry: a second notification must not credit again
    assert notify(client, ref) == "already_credited"
    assert balance(client, h) == 13
    assert client.get("/credits", headers=h).json()["history"][0]["kind"] == "topup"


def test_amount_mismatch_is_not_credited(client):
    h = login(client)
    ref = start_checkout(client, h, "business")
    provider = client.app.state.payments
    provider.payments[ref]["status"] = "completed"
    provider.payments[ref]["amount"] = 1000  # paid 1 TND for a 70 TND pack
    assert notify(client, ref) == "mismatch"
    assert balance(client, h) == 3


def test_unknown_payment_reference(client):
    assert notify(client, "dev_doesnotexist") == "unknown"


def test_unknown_pack_is_rejected(client):
    h = login(client)
    assert client.post("/credits/checkout", headers=h, json={"pack": "free-money"}).status_code == 400


def test_ledger_matches_cached_balance(client):
    with transaction() as cur:
        cur.execute("""SELECT a.id FROM app.accounts a
                       LEFT JOIN app.credit_ledger l ON l.account_id = a.id
                       GROUP BY a.id, a.credit_balance
                       HAVING a.credit_balance <> COALESCE(SUM(l.delta), 0)""")
        assert cur.fetchall() == []
