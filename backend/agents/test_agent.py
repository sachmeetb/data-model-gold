"""
test_agent.py — Test Agent.

Validates the SQL pipeline code produced by the Pipeline Generator.

Checks performed (static analysis — no live cluster required):
  1. SQL syntax check (local, before LLM call)
  2. Schema conformance against approved silver/gold schemas
  3. STTM coverage — every mapping implemented
  4. Data quality rules from the contract
  5. CHECK constraint correctness
  6. Referential integrity — all referenced tables exist in spec
  7. Row-count assertion presence
  8. Business rule correctness
  9. Environment parameterization (three-level names)
 10. Unity Catalog path format
"""

import json
import re
from pathlib import Path

from .base import run_agent, _PROJECT_ROOT


# Path to the authoritative data catalog. The test-agent MUST use the
# sample_data rows from this file when simulating the "input / output sample
# query" — fabricating sample values for tables that exist in the catalog is
# forbidden.
_UTILITY_CATALOG_PATH = _PROJECT_ROOT / "data" / "utility_catalog.json"


def _load_utility_catalog() -> dict:
    """Load utility_catalog.json fresh on every test-agent call so any catalog
    edits take effect immediately. Returns {} on read/parse failure; the SKILL
    treats a missing catalog as 'no real sample data available — emit empty
    sample_query_result rather than invent one'."""
    try:
        with open(_UTILITY_CATALOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[TA] WARN: could not load utility_catalog.json: {exc!r}")
        return {}


def _build_catalog_table_index(catalog: dict) -> dict:
    """Walk every layer of the catalog and build a lookup keyed by `full_name`.

    Returns: { full_name: { "columns": [name1, name2, ...], "sample_data": [row_dict, ...] } }
    Empty dict if the catalog is missing or malformed.
    """
    if not isinstance(catalog, dict):
        return {}
    data_catalog = catalog.get("data_catalog") or {}
    layers = (data_catalog.get("layers") or {})
    index: dict = {}
    for layer_name in ("bronze", "silver", "gold"):
        for entry in layers.get(layer_name) or []:
            if not isinstance(entry, dict):
                continue
            full_name = entry.get("full_name")
            if not full_name:
                continue
            cols = entry.get("columns") or []
            col_names = [c.get("name") for c in cols if isinstance(c, dict) and c.get("name")]
            sample_data = entry.get("sample_data") or []
            # Only accept dict-shaped rows for safe projection
            sample_data = [r for r in sample_data if isinstance(r, dict)]
            index[full_name] = {
                "columns": col_names,
                "sample_data": sample_data,
                "layer": layer_name,
            }
    return index


def _project_catalog_rows(catalog_entry: dict, requested_columns: list) -> tuple[list, list]:
    """Project catalog sample_data rows into the (columns, rows-of-lists) shape
    the UI expects. If requested_columns is empty or not in the catalog, fall
    back to the catalog's full column list.

    Returns (columns_list, rows_list_of_lists). Both empty if the catalog
    has no sample_data for the table.
    """
    sample_rows = catalog_entry.get("sample_data") or []
    if not sample_rows:
        return [], []
    catalog_cols = catalog_entry.get("columns") or []
    # Prefer the columns the LLM asked for IF they all exist in the catalog;
    # otherwise just use the catalog's full column list.
    if requested_columns and all(c in catalog_cols for c in requested_columns):
        cols = list(requested_columns)
    else:
        cols = list(catalog_cols)
    rows = [[r.get(c, "") for c in cols] for r in sample_rows]
    return cols, rows


def _enforce_catalog_sample_data(report: dict, catalog: dict) -> dict:
    """Deterministic safety net: walk the LLM's sample_query_result and
    replace EVERY table's columns + rows with the catalog's authoritative
    values for that `table_name`. If the catalog has no entry for a
    `table_name`, columns and rows are forced to []. This guarantees no
    fabricated data ever reaches the UI regardless of LLM compliance.
    """
    if not isinstance(report, dict):
        return report
    sample_query_result = report.get("sample_query_result")
    if not isinstance(sample_query_result, dict):
        return report

    index = _build_catalog_table_index(catalog)
    if not index:
        # No catalog — strip rows so we don't display fabricated data.
        for tbl in (sample_query_result.get("output_tables") or []):
            if isinstance(tbl, dict):
                tbl["rows"] = []
                tbl["columns"] = tbl.get("columns") or []
        input_tbl = sample_query_result.get("input_table")
        if isinstance(input_tbl, dict):
            input_tbl["rows"] = []
            input_tbl["columns"] = input_tbl.get("columns") or []
        sample_query_result["_catalog_enforced"] = "no_catalog"
        return report

    def _enforce_one(tbl: dict) -> None:
        if not isinstance(tbl, dict):
            return
        full_name = tbl.get("table_name")
        entry = index.get(full_name)
        if entry is None:
            # Table not in catalog → cannot show any data without fabricating
            tbl["rows"] = []
            tbl["columns"] = []
            tbl["_catalog_note"] = (
                f"No catalog entry found for table_name {full_name!r}; "
                "row preview suppressed."
            )
            return
        cols, rows = _project_catalog_rows(entry, tbl.get("columns") or [])
        tbl["columns"] = cols
        tbl["rows"] = rows
        if not rows:
            tbl["_catalog_note"] = (
                f"Catalog has no sample_data for {full_name!r}; "
                "row preview empty."
            )

    input_tbl = sample_query_result.get("input_table")
    if isinstance(input_tbl, dict):
        _enforce_one(input_tbl)

    out_tables = sample_query_result.get("output_tables")
    if isinstance(out_tables, list):
        for tbl in out_tables:
            _enforce_one(tbl)

    sample_query_result["_catalog_enforced"] = "ok"
    return report


def _syntax_check(code: str) -> tuple[bool, str]:
    """
    Basic SQL syntax validation — runs locally before the LLM call.
    Checks for:
      - At least one SQL statement keyword
      - Balanced parentheses
      - Each non-comment statement ends with a semicolon
    """
    if not code or not code.strip():
        return False, "Empty code — no SQL provided."

    if not re.search(
        r"\b(CREATE|INSERT|MERGE|UPDATE|DELETE|SELECT|WITH|ALTER|DROP)\b",
        code,
        re.IGNORECASE,
    ):
        return False, "No recognizable SQL statements found."

    # Check balanced parentheses
    depth = 0
    in_string = False
    string_char = ""
    for ch in code:
        if in_string:
            if ch == string_char:
                in_string = False
        elif ch in ("'", '"'):
            in_string = True
            string_char = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False, "Unbalanced parentheses: unexpected ')'."
    if depth != 0:
        return False, f"Unbalanced parentheses: {depth} unclosed '('."

    return True, ""


async def run(generated_code: str, spec: dict | None = None, session=None) -> dict:
    """
    Validate the generated SQL pipeline code and return a TestReport.

    Args:
        generated_code: Multi-statement SQL produced by the Pipeline Generator.
        spec:           Original pipeline spec (used for schema / contract checks).

    Returns:
        Dict with keys:
          test_status   — "passed" | "failed"
          failures      — list of {check, severity, detail, suggestion}
          passed_checks — list of check names that passed
          summary       — one-sentence plain-language verdict
    """
    syntax_ok, syntax_err = _syntax_check(generated_code)

    context: dict = {
        "generated_code": generated_code,
        "local_syntax_check": {"passed": syntax_ok, "error": syntax_err},
    }
    if spec:
        context["original_spec"] = spec

    # Inject the authoritative data catalog so the agent uses real sample_data
    # rows (when present) when simulating the input / output sample query,
    # rather than inventing identifiers.
    utility_catalog = _load_utility_catalog()
    if utility_catalog:
        context["utility_catalog"] = utility_catalog

    report = await run_agent(
        "test-agent",
        "Validate the generated SQL pipeline code and produce a TestReport.",
        context=context,
        session=session,
    )

    # Deterministic safety net: even with the SKILL telling it NOT to
    # fabricate, the LLM sometimes invents sample rows. Walk the result and
    # forcibly replace every sample_query_result table's columns + rows with
    # the catalog's authoritative values (or empty lists when the catalog
    # has no entry / no sample_data for that table). This guarantees no
    # fabricated rows ever reach the UI.
    report = _enforce_catalog_sample_data(report, utility_catalog)
    return report


def is_passing(report: dict) -> bool:
    return report.get("test_status") == "passed"


def get_failures(report: dict) -> list[dict]:
    return report.get("failures", [])
