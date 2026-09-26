"""
The data engine's public interface — the ONLY thing the SaaS layer calls.

It knows nothing about users, accounts, credits or HTTP: every call takes
an opaque `tenant_id` and returns plain dicts or raises an EngineError.
If the SaaS layer ever moves to another service (e.g. Spring Boot), each
method here maps 1:1 to an internal endpoint.
"""

import re
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import BinaryIO, Optional

from . import storage
from .derived_fields import apply_mapping, column_stats, compute_derived_columns
from .mapper.mapper import BayanMapper
from .mapper.schema_loader import load_schema
from .mapper.validator import validate_mapping
from .matchers.synonym_store import get_static_synonyms, is_learnable
from .metering import DEFAULT_VALUE_BYTES, NUMERIC_BYTES, estimate_storage_bytes, meter
from .profiler.profiler import FileLoadError, ProfileOptions, profile_file
from .queries import ChartUnavailable, DateFilter, QueryContext, check_chart, date_bounds, run_chart_query
from .rules import DATE_PRIORITY, resolve_charts

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".xlsm", ".json", ".parquet"}


class EngineError(Exception):
    """Base class: a request the engine can't fulfil (message is user-facing)."""


class NotFound(EngineError):
    pass


class NotReady(EngineError):
    pass


class InvalidUpload(EngineError):
    pass


class MappingInvalid(EngineError):
    def __init__(self, errors: list[str], warnings: list[str]):
        super().__init__(" ".join(errors))
        self.errors = errors
        self.warnings = warnings


class LoadFailed(EngineError):
    pass


def _safe_filename(name: Optional[str]) -> str:
    """Basename only, conservative charset — never lets a client choose the path."""
    base = Path(name or "").name
    base = re.sub(r"[^\w.\- ]", "_", base).strip(" .")
    return base or "upload"


class Engine:
    def __init__(self, mapper: BayanMapper, upload_dir: Path, max_upload_bytes: int):
        self.mapper = mapper
        self.upload_dir = Path(upload_dir)
        self.max_upload_bytes = max_upload_bytes
        self.schema = load_schema()
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def schema_fields(self) -> list[dict]:
        return [
            {"name": name, "label": f.get("label", name), "type": f["type"]}
            for name, f in self.schema["fields"].items()
        ]

    # ------------------------------------------------------------------
    # upload -> review
    # ------------------------------------------------------------------
    def ingest_upload(self, tenant_id: str, filename: Optional[str], stream: BinaryIO) -> dict:
        filename = _safe_filename(filename)
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidUpload(f"Unsupported file type '{ext or '?'}'. Upload a CSV, Excel or JSON file.")

        dataset_id = str(uuid.uuid4())
        job_dir = self.upload_dir / dataset_id
        job_dir.mkdir(parents=True)
        file_path = job_dir / filename

        size = 0
        with open(file_path, "wb") as out:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > self.max_upload_bytes:
                    out.close()
                    shutil.rmtree(job_dir, ignore_errors=True)
                    raise InvalidUpload(f"File is larger than {self.max_upload_bytes // (1024 * 1024)} MB.")
                out.write(chunk)

        with meter() as profiling:
            try:
                dataset, profile = profile_file(ProfileOptions(file=str(file_path), example_values=3))
            except FileLoadError as e:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise InvalidUpload(str(e))

        with meter() as mapping_meter:
            result = self.mapper.map(profile, storage.load_learned_synonyms(tenant_id))

        usage = {
            "file_bytes": size,
            "rows": len(dataset),
            "columns": len(dataset.columns),
            "profile_seconds": profiling["seconds"],
            "mapping_seconds": mapping_meter["seconds"],
            "ai_columns": result["ai"]["columns"],
            "ai_seconds": result["ai"]["seconds"],
        }
        storage.create_pending(tenant_id, dataset_id, filename, str(file_path), len(dataset), profile, result, usage)
        review = self._review(dataset_id, filename, len(dataset), result, "pending")
        review["usage"] = usage
        return review

    def get_review(self, tenant_id: str, dataset_id: str) -> dict:
        ds = self._get(tenant_id, dataset_id)
        result = ds["suggestion"]
        if ds["mapping"] is not None:
            for col in result["columns"]:
                col["target"] = ds["mapping"].get(col["name"])
        return self._review(ds["id"], ds["filename"], ds["source_rows"], result, ds["status"])

    def _review(self, dataset_id, filename, rows, result, status) -> dict:
        return {
            "dataset_id": dataset_id,
            "filename": filename,
            "row_count": rows,
            "status": status,
            "result": result,
            "fields": self.schema_fields(),
        }

    # ------------------------------------------------------------------
    # confirm -> dashboard
    # ------------------------------------------------------------------
    def check_mapping(self, tenant_id: str, dataset_id: str, mapping: dict) -> dict:
        """Validate without loading anything. Returns the cleaned mapping; raises MappingInvalid."""
        ds = self._get(tenant_id, dataset_id)
        mapping = {src: tgt for src, tgt in mapping.items() if tgt}
        # also what keeps arbitrary strings out of generated SQL: targets must be schema fields
        errors, warnings = validate_mapping(mapping, self.schema, ds["profile"])
        if errors:
            raise MappingInvalid(errors, warnings)
        return mapping

    def estimate_build(self, tenant_id: str, dataset_id: str, mapping: dict) -> dict:
        """
        Resources a build with this mapping will consume — known before anything
        is loaded, so a price can be shown up front. Columns mapped to unknown
        fields are ignored here (check_mapping rejects them on build).
        """
        ds = self._get(tenant_id, dataset_id)
        profile_cols = {c["name"]: c for c in ds["profile"]["columns"]}
        fields = self.schema["fields"]
        kept = {src: tgt for src, tgt in mapping.items() if tgt in fields and src in profile_cols}

        value_bytes = [float(profile_cols[src].get("avg_bytes", DEFAULT_VALUE_BYTES)) for src in kept]
        # mirrors derived_fields.compute_derived_columns: revenue = quantity × unit_price
        by_target = {tgt: profile_cols[src] for src, tgt in kept.items()}
        numeric = {"integer", "float"}
        if ("revenue" not in by_target and {"quantity", "unit_price"} <= by_target.keys()
                and by_target["quantity"]["type"] in numeric and by_target["unit_price"]["type"] in numeric):
            value_bytes.append(NUMERIC_BYTES)

        upload = ds.get("upload_usage") or {}
        ai_columns = upload.get("ai_columns")
        if ai_columns is None:  # datasets uploaded before metering existed
            ai_columns = sum(1 for c in ds["suggestion"].get("columns", []) if c.get("method") == "llm")

        rows = ds["source_rows"] or 0
        return {
            "rows": rows,
            "columns": len(value_bytes),
            "cells": rows * len(value_bytes),
            "storage_bytes": estimate_storage_bytes(rows, value_bytes),
            "ai_columns": int(ai_columns),
        }

    def build_dashboard(self, tenant_id: str, dataset_id: str, mapping: dict) -> dict:
        """Load the data with this mapping and resolve its charts. Rebuilding replaces the data."""
        ds = self._get(tenant_id, dataset_id)
        mapping = self.check_mapping(tenant_id, dataset_id, mapping)
        _, warnings = validate_mapping(mapping, self.schema, ds["profile"])

        with meter() as build:
            try:
                dataset, _ = profile_file(ProfileOptions(file=ds["file_path"]))
            except FileLoadError as e:
                raise LoadFailed(str(e))

            cleaned = compute_derived_columns(apply_mapping(dataset, mapping))
            column_types = storage.column_types_for(cleaned)
            ctx = QueryContext(storage.table_name_for(dataset_id), column_types)

            charts = []
            for spec in resolve_charts(set(cleaned.columns), column_stats(cleaned)):
                try:
                    check_chart(spec, ctx)
                    charts.append(spec)
                except ChartUnavailable:
                    continue
            hidden = [c["name"] for c in charts if not c["default_visible"]]

            try:
                storage.save_dataset(tenant_id, dataset_id, cleaned, column_types, mapping, charts, hidden)
            except Exception as e:
                raise LoadFailed(f"Failed to load data: {e}")

        # what this build actually consumed (measured, not estimated)
        usage = {
            "rows": len(cleaned),
            "columns": len(cleaned.columns),
            "cells": len(cleaned) * len(cleaned.columns),
            "storage_bytes": storage.table_size_bytes(dataset_id),
            "seconds": build["seconds"],
            "cpu_seconds": build["cpu_seconds"],
        }
        storage.set_build_usage(tenant_id, dataset_id, usage)

        # remember choices that weren't already deterministic synonym hits,
        # so this tenant's next upload maps them instantly
        static = get_static_synonyms()
        suggested = {c["name"]: c for c in ds["suggestion"].get("columns", [])}
        for src, tgt in mapping.items():
            s = suggested.get(src, {})
            if s.get("method") != "synonym" or s.get("target") != tgt:
                key = is_learnable(src, static)
                if key:
                    storage.learn_synonym(tenant_id, key, tgt)

        overview = self.overview(tenant_id, dataset_id)
        overview["warnings"] = warnings
        overview["usage"] = usage
        return overview

    # ------------------------------------------------------------------
    # dashboards
    # ------------------------------------------------------------------
    def list_dashboards(self, tenant_id: str) -> list[dict]:
        """Newest first; includes uploads not built yet (status "pending") so they can be resumed."""
        return storage.list_datasets(tenant_id)

    def overview(self, tenant_id: str, dataset_id: str) -> dict:
        ds = self._get_ready(tenant_id, dataset_id)
        date_field = self._date_field(ds)
        date_min = date_max = None
        if date_field:
            date_min, date_max = date_bounds(QueryContext(ds["table_name"], ds["column_types"]), date_field)
        return {
            "id": ds["id"],
            "filename": ds["filename"],
            "created_at": ds["created_at"],
            "loaded_at": ds["loaded_at"],
            "row_count": ds["row_count"],
            "source_rows": ds["source_rows"],
            "mapping": ds["mapping"],
            "charts": ds["charts"],
            "hidden_charts": ds["hidden_charts"],
            "date_field": date_field,
            "date_min": date_min,
            "date_max": date_max,
        }

    def set_hidden_charts(self, tenant_id: str, dataset_id: str, hidden: list[str]) -> list[str]:
        ds = self._get_ready(tenant_id, dataset_id)
        known = {c["name"] for c in ds["charts"]}
        hidden = [n for n in hidden if n in known]
        storage.set_hidden_charts(tenant_id, dataset_id, hidden)
        return hidden

    def chart_data(self, tenant_id: str, dataset_id: str, chart_name: str,
                   date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
        ds = self._get_ready(tenant_id, dataset_id)
        chart = next((c for c in ds["charts"] if c["name"] == chart_name), None)
        if chart is None:
            raise NotFound("Unknown chart for this dashboard")
        ctx = QueryContext(ds["table_name"], ds["column_types"], DateFilter(self._date_field(ds), date_from, date_to))
        return {"chart": chart, "data": run_chart_query(chart, ctx)}

    def delete(self, tenant_id: str, dataset_id: str) -> None:
        ds = self._get(tenant_id, dataset_id)
        storage.delete_dataset(tenant_id, dataset_id)
        upload_dir = Path(ds["file_path"]).parent
        if upload_dir.parent == self.upload_dir:
            shutil.rmtree(upload_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    def _get(self, tenant_id: str, dataset_id: str) -> dict:
        ds = storage.get_dataset(tenant_id, dataset_id)
        if ds is None:
            raise NotFound("Dataset not found")
        return ds

    def _get_ready(self, tenant_id: str, dataset_id: str) -> dict:
        ds = self._get(tenant_id, dataset_id)
        if ds["status"] != "ready":
            raise NotReady("This dataset hasn't been confirmed and loaded yet")
        return ds

    @staticmethod
    def _date_field(ds: dict) -> Optional[str]:
        """First date-like field whose column can actually be read as dates."""
        ctx = QueryContext(ds["table_name"], ds["column_types"])
        for field in DATE_PRIORITY:
            try:
                ctx.ts(field)
                return field
            except ChartUnavailable:
                continue
        return None
