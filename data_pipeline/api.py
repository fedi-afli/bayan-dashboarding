"""
FastAPI wrapper around the bayan.com.tn pipeline.

Flow:
  1. POST /pipeline/upload       -> saves the file, profiles + maps it,
                                     returns job_id + mapping result
                                     (stops BEFORE touching Postgres if
                                     anything needs manual confirmation)
  2. POST /pipeline/{id}/confirm -> applies the caller's confirmations,
                                     creates the table, loads the data,
                                     resolves the applicable charts
  3. GET  /pipeline/{id}/charts  -> re-fetch the resolved chart specs
  4. GET  /pipeline/{id}/charts/{chart_name}/data -> actual rows for one chart

NOTE: job state is kept in-memory (JOBS dict below). This only works with
a single Uvicorn worker and is lost on restart. Fine for now — move to
Redis or a `pipeline_jobs` table before running multiple workers or
needing jobs to survive a restart.
"""

import os
import shutil
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from profiler.profiler import ProfileOptions, profile_file
from mapper.mapper import BayanMapper
from mapper.sql_schema_generator import load_schema, generate_create_table_sql, save_sql_file
from db import execute_sql
from rules import resolve_charts_from_mapping
from queries import run_chart_query

# reuse the same logic the CLI pipeline uses, instead of duplicating it
from main import apply_mapping, load_dataframe_to_postgres


def _split_profile_result(result) -> tuple:
    """
    profile_file() is supposed to return (dataset, profile), but this
    codebase has had that order flip more than once — normalize by type
    instead of trusting positional order, so a future swap fails loudly
    here instead of surfacing as a cryptic pandas KeyError deep inside
    the mapper.
    """
    a, b = result
    if isinstance(a, pd.DataFrame) and isinstance(b, dict):
        return a, b
    if isinstance(b, pd.DataFrame) and isinstance(a, dict):
        return b, a
    raise TypeError(
        "profile_file() must return one pandas DataFrame and one dict "
        f"(got {type(a)} and {type(b)})"
    )

UPLOAD_DIR = "uploads"
TABLE_NAME = "sales"  # matches the hardcoded table name used elsewhere in the pipeline
SCHEMA_PATH = "schemas/sales_schema.json"  # adjust if your schema lives elsewhere

# job_id -> {"dataset": DataFrame, "result": dict, "charts": list | None}
JOBS: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the mapper (and its embedding/matcher models) exactly once,
    # not per-request — this is the whole point of not using subprocesses.
    app.state.mapper = BayanMapper()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(title="bayan.com.tn pipeline API", lifespan=lifespan)

# Angular dev server origin — tighten this to your real frontend origin(s) before prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FieldConfirmation(BaseModel):
    source_column: str
    target_field: Optional[str] = None  # None = leave unresolved


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema/fields")
def get_schema_fields():
    schema = load_schema(SCHEMA_PATH)
    return sorted(schema["fields"].keys())


@app.post("/pipeline/upload")
async def upload_and_map(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    options = ProfileOptions(file=file_path, example_values=3)
    dataset, profile = _split_profile_result(profile_file(options))

    mapper: BayanMapper = app.state.mapper
    result = mapper.map(profile)

    JOBS[job_id] = {"dataset": dataset, "result": result, "charts": None}

    return {"job_id": job_id, "result": result}


@app.post("/pipeline/{job_id}/confirm")
def confirm_and_load(job_id: str, confirmations: list[FieldConfirmation]):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    result = job["result"]
    mapper: BayanMapper = app.state.mapper

    for c in confirmations:
        if c.target_field:
            mapper.confirm_field(c.source_column, c.target_field)
            result["mapping"][c.source_column] = c.target_field
        # remove the resolved (or explicitly skipped) column from the
        # pending-review lists either way
        result["unresolved_columns"] = [
            u for u in result["unresolved_columns"] if u != c.source_column
        ]
        result["needs_confirmation"] = [
            n for n in result["needs_confirmation"] if n["source"] != c.source_column
        ]

    if result["errors"]:
        raise HTTPException(status_code=400, detail={"errors": result["errors"]})

    try:
        schema = load_schema(SCHEMA_PATH)
        create_table_sql = generate_create_table_sql(
            schema, mapping=result["mapping"], table_name=TABLE_NAME
        )
        os.makedirs("output", exist_ok=True)
        save_sql_file(create_table_sql, f"output/{job_id}_create_table.sql")
        execute_sql(create_table_sql)

        cleaned_dataset = apply_mapping(job["dataset"], result["mapping"])
        load_dataframe_to_postgres(cleaned_dataset, table_name=TABLE_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load data: {e}")

    charts = resolve_charts_from_mapping(result["mapping"])
    job["charts"] = charts
    job["result"] = result

    return {"job_id": job_id, "result": result, "charts": charts}


@app.get("/pipeline/{job_id}/charts")
def get_charts(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if job["charts"] is None:
        raise HTTPException(status_code=409, detail="Pipeline not confirmed/loaded yet")
    return job["charts"]


@app.get("/pipeline/{job_id}/charts/{chart_name}/data")
def get_chart_data(job_id: str, chart_name: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if job["charts"] is None:
        raise HTTPException(status_code=409, detail="Pipeline not confirmed/loaded yet")

    chart = next((c for c in job["charts"] if c["name"] == chart_name), None)
    if chart is None:
        raise HTTPException(status_code=404, detail="Unknown chart_name for this job")

    try:
        rows = run_chart_query(chart["config"], table=TABLE_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query chart data: {e}")

    return {"chart": chart, "data": rows}