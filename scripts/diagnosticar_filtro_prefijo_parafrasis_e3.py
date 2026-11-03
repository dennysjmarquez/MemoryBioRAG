#!/usr/bin/env python3
"""Mide en copias sintéticas el guardia de prefijo frente a FTS y paráfrasis.

Empareja MCP stdio baseline/instrumentado para mostrar una defensa contra hits
subword y una ruta válida de prefijo, y para detectar el caso donde un hit de
paráfrasis se somete al token de una query distinta. No modifica core/ ni datos
originales. La salida íntegra contiene fixture/queries y debe quedar privada.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import diagnosticar_traza_interna_parafrasis_e3 as harness

TARGET = "synthetic_prefix_probe"
CONTENT = (
    "A synthetic note contains the code-like string xxprobeanchorzz, describes "
    "reactive systems and artículos in a catalog, and mentions a quartz archive."
)
CASES = [
    ("subword_guard", "probeanchor", None, "protect_subword"),
    ("short_word_boundary", "culo", None, "substring_inside_articulos"),
    ("valid_word_prefix", "react", None, "allow_prefix"),
    ("one_word_paraphrase", "qzxnovelquery", "quartz", "drop_para_hint"),
    ("multiword_paraphrase", "qzxnovelquery archive", "quartz", "prefix_guard_skipped"),
]


def configure_harness() -> None:
    harness.TARGET = TARGET
    harness.NODES = [(TARGET, CONTENT)]
    harness.PAIRS = [(case_id, query, para) for case_id, query, para, _ in CASES]


def make_spec(case_id: str, query: str, para: str) -> dict:
    return {
        "case_id": case_id,
        "pair_id": case_id,
        "arm": "with_paraphrase" if para else "plain_query",
        "query": query,
        "parafrasis": para,
        "sustantivos_clave": "helium,vector",
        "limite": 10,
        "asociados": False,
        "asociaciones_max": 0,
        "context_window": 0,
        "completo": True,
        "usar_inferencia": False,
        "forzar_rafaga": False,
        "modo_estricto": False,
    }


def attribution(run: dict) -> dict:
    events = run.get("internal_search_events", [])
    statements = [statement for event in events for statement in event.get("fts_statements", [])]
    matched = [
        {
            "statement_index": statement.get("statement_index"),
            "branch_slots": [
                slot
                for probe in statement.get("variant_probes", [])
                if TARGET in probe.get("candidate_concepts", [])
                for slot in probe.get("source_slots", [probe.get("source_slot")])
            ],
        }
        for statement in statements
        if TARGET in statement.get("candidate_concepts", [])
    ]
    filters = [
        {
            "filter_kind": statement.get("filter_kind"),
            "input_target": TARGET in statement.get("input_candidates", []),
            "rows_returned": statement.get("rows_returned"),
            "returned_target": TARGET in statement.get("candidate_concepts", []),
        }
        for event in events
        for statement in event.get("post_search_filter_statements", [])
        if TARGET in statement.get("input_candidates", [])
    ]
    stages = [stage for event in events for stage in event.get("search_stage_trace", [])]
    return {
        "fts_statements_returning_target": matched,
        "target_in_internal_pool": any(TARGET in event.get("candidate_concepts", []) for event in events),
        "candidate_score_stages": [
            {"stage": stage.get("stage"), "transition": stage.get("transition"), "score": stage.get("score"), "origin": stage.get("origin")}
            for stage in stages
            if stage.get("stage") == "resultados_con_hibrido"
        ],
        "prefix_guard_inputs_and_outputs": filters,
        "engine_returned_target": any(TARGET in event.get("returned_concepts", []) for event in events),
        "query_token_counts": [event.get("query_token_count") for event in events],
        "mcp_contingency": bool(run.get("raw_response_text", {}).get("contingencia_contexto")),
        "mcp_target_found": run.get("target_found", False),
        "mcp_error": run.get("response_mcp_error", False),
    }


async def execute() -> dict:
    configure_harness()
    original_qcr = os.environ.get("BIORAG_QCR_ACTIVO")
    os.environ["BIORAG_QCR_ACTIVO"] = "0"  # Aislar el efecto del guardia de prefijo en la comparación multiword.
    rows = []
    try:
        with tempfile.TemporaryDirectory(prefix="e3_prefix_paraphrase_") as temp:
            root = Path(temp)
            seed = root / "seed.db"
            harness.seed_db(seed)
            for case_id, query, para, role in CASES:
                spec = make_spec(case_id, query, para)
                baseline = await harness.run_one(seed, root, spec, instrumented=False)
                traced = await harness.run_one(seed, root, spec, instrumented=True)
                rows.append({
                    "case_id": case_id,
                    "role": role,
                    "input": spec,
                    "baseline": baseline,
                    "instrumented": traced,
                    "instrumentation_equivalent": (
                        baseline["response_concepts"] == traced["response_concepts"]
                        and baseline["target_score"] == traced["target_score"]
                        and baseline["response_mcp_error"] == traced["response_mcp_error"]
                    ),
                    "attribution": attribution(traced),
                })
    finally:
        if original_qcr is None:
            os.environ.pop("BIORAG_QCR_ACTIVO", None)
        else:
            os.environ["BIORAG_QCR_ACTIVO"] = original_qcr

    by_id = {row["case_id"]: row for row in rows}
    subword = by_id["subword_guard"]["attribution"]
    prefix = by_id["valid_word_prefix"]["attribution"]
    para_one = by_id["one_word_paraphrase"]["attribution"]
    para_multi = by_id["multiword_paraphrase"]["attribution"]
    checks = {
        "subword_hit_removed_by_guard": (
            subword["target_in_internal_pool"]
            and any(f["input_target"] and f["rows_returned"] == 0 for f in subword["prefix_guard_inputs_and_outputs"])
            and not subword["mcp_target_found"]
        ),
        "valid_prefix_survives_guard": (
            prefix["target_in_internal_pool"]
            and any(f["input_target"] and f["returned_target"] for f in prefix["prefix_guard_inputs_and_outputs"])
            and prefix["mcp_target_found"]
        ),
        "one_word_paraphrase_hit_removed_by_guard": (
            any("paraphrase_1" in s["branch_slots"] for s in para_one["fts_statements_returning_target"])
            and any(f["input_target"] and f["rows_returned"] == 0 for f in para_one["prefix_guard_inputs_and_outputs"])
            and not para_one["mcp_target_found"]
        ),
        "multiword_paraphrase_survives_without_prefix_guard": (
            any("paraphrase_1" in s["branch_slots"] for s in para_multi["fts_statements_returning_target"])
            and not para_multi["prefix_guard_inputs_and_outputs"]
            and para_multi["mcp_target_found"]
        ),
        "all_baseline_instrumentation_pairs_equal": all(row["instrumentation_equivalent"] for row in rows),
    }
    return {
        "experiment": "E3 synthetic single-word prefix guard versus FTS/paraphrase candidates",
        "synthetic_only": True,
        "engine_source_modified": False,
        "user_databases_opened": 0,
        "qcr_disabled_for_isolation": True,
        "candidate_fixture_count": 1,
        "tool_calls": 2 * len(CASES) * 2,
        "mcp_errors": sum(row[arm]["response_mcp_error"] for row in rows for arm in ("baseline", "instrumented")),
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    out = Path(args.evidence_dir)
    private_root = (ROOT / ".private_evidence").resolve()
    out = (out if out.is_absolute() else ROOT / out).resolve()
    if private_root not in out.parents or out.exists():
        raise ValueError("Use a new directory under .private_evidence/")
    out.mkdir(parents=True, exist_ok=False)
    result = asyncio.run(execute())
    if not result["all_checks_pass"]:
        raise AssertionError("La matriz sintética no confirmó todas las expectativas del guardia")
    result_path = out / "synthetic_prefix_guard_results.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {result_path.name: hashlib.sha256(result_path.read_bytes()).hexdigest()}
    (out / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"checks": result["checks"], "tool_calls": result["tool_calls"], "mcp_errors": result["mcp_errors"], "all_checks_pass": result["all_checks_pass"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
