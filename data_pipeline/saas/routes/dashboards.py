"""
Public dashboard API: authenticates, scopes everything to the caller's
account, charges credits — and delegates the data work to the engine.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel

from engine.service import Engine

from .. import credits, pricing
from ..accounts import CurrentUser
from ..deps import current_user, engine

router = APIRouter(tags=["dashboards"])


def _price(user: CurrentUser, eng: Engine, dataset_id: str, mapping: dict) -> dict:
    """The quote for building `dataset_id` with `mapping`, and what's still due on it."""
    q = pricing.quote(eng.estimate_build(user.account_id, dataset_id, mapping))
    paid = credits.credits_paid(dataset_id)
    return {**q, "paid": paid, "due": max(0, q["credits"] - paid), "balance": credits.balance(user.account_id)}


def _suggested_mapping(review: dict) -> dict:
    return {c["name"]: c["target"] for c in review["result"]["columns"]}


@router.get("/schema/fields")
def schema_fields(eng: Engine = Depends(engine)):
    return eng.schema_fields()


@router.post("/datasets/upload")
def upload(file: UploadFile = File(...), user: CurrentUser = Depends(current_user), eng: Engine = Depends(engine)):
    review = eng.ingest_upload(user.account_id, file.filename, file.file)
    review["quote"] = _price(user, eng, review["dataset_id"], _suggested_mapping(review))
    return review


@router.get("/datasets/{dataset_id}/review")
def review(dataset_id: str, user: CurrentUser = Depends(current_user), eng: Engine = Depends(engine)):
    data = eng.get_review(user.account_id, dataset_id)
    data["quote"] = _price(user, eng, dataset_id, _suggested_mapping(data))
    return data


class ConfirmRequest(BaseModel):
    # every column of the file -> schema field, or null/"" to leave it out
    mapping: dict[str, Optional[str]]


@router.post("/datasets/{dataset_id}/quote")
def quote(dataset_id: str, body: ConfirmRequest, user: CurrentUser = Depends(current_user),
          eng: Engine = Depends(engine)):
    """Price of building with this mapping — the review screen calls it as columns are changed."""
    mapping = {src: tgt for src, tgt in body.mapping.items() if tgt}
    return _price(user, eng, dataset_id, mapping)


@router.post("/datasets/{dataset_id}/confirm")
def confirm(dataset_id: str, body: ConfirmRequest, user: CurrentUser = Depends(current_user),
            eng: Engine = Depends(engine)):
    mapping = eng.check_mapping(user.account_id, dataset_id, body.mapping)  # never charge for an invalid mapping
    review = eng.get_review(user.account_id, dataset_id)
    price = _price(user, eng, dataset_id, mapping)
    d = price["drivers"]
    label = f"{review['filename']} — {d['rows']:,} rows × {d['columns']} columns"

    charge = credits.charge_dashboard(
        user.account_id, dataset_id, price["credits"],
        f"Dashboard: {label}" if price["paid"] == 0 else f"Dashboard update: {label}",
    )
    try:
        overview = eng.build_dashboard(user.account_id, dataset_id, mapping)
    except Exception:
        credits.refund_charge(user.account_id, dataset_id, charge, f"{review['filename']} couldn't be built")
        raise

    quote_shown = {k: price[k] for k in ("credits", "exact", "lines", "drivers")}
    credits.record_usage(user.account_id, dataset_id, quote_shown, charge.amount, overview.get("usage", {}))
    overview["credits"] = {
        "charged": charge.amount,
        "total_paid": charge.paid_total,
        "balance": credits.balance(user.account_id),
    }
    return overview


@router.get("/datasets")
def list_dashboards(user: CurrentUser = Depends(current_user), eng: Engine = Depends(engine)):
    paid = credits.credits_paid_by_dataset(user.account_id)
    return [{**d, "credits_used": paid.get(d["id"], 0)} for d in eng.list_dashboards(user.account_id)]


@router.get("/datasets/{dataset_id}")
def get_dashboard(dataset_id: str, user: CurrentUser = Depends(current_user), eng: Engine = Depends(engine)):
    return {**eng.overview(user.account_id, dataset_id), "credits_used": credits.credits_paid(dataset_id)}


class LayoutRequest(BaseModel):
    hidden_charts: list[str]


@router.put("/datasets/{dataset_id}/layout")
def update_layout(dataset_id: str, body: LayoutRequest, user: CurrentUser = Depends(current_user),
                  eng: Engine = Depends(engine)):
    return {"hidden_charts": eng.set_hidden_charts(user.account_id, dataset_id, body.hidden_charts)}


@router.get("/datasets/{dataset_id}/charts/{chart_name}/data")
def chart_data(dataset_id: str, chart_name: str, date_from: Optional[date] = Query(None),
               date_to: Optional[date] = Query(None), user: CurrentUser = Depends(current_user),
               eng: Engine = Depends(engine)):
    return eng.chart_data(user.account_id, dataset_id, chart_name, date_from, date_to)


@router.delete("/datasets/{dataset_id}")
def delete_dashboard(dataset_id: str, user: CurrentUser = Depends(current_user), eng: Engine = Depends(engine)):
    eng.delete(user.account_id, dataset_id)
    return {"deleted": dataset_id}
