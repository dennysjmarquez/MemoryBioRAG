#!/usr/bin/env python3
"""Sondeo MCP stdio sintético de validación frente a búsqueda ejecutada en E3."""
from __future__ import annotations
import asyncio, hashlib, json, sqlite3, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.diagnosticar_rutas_creacion_densidad_e3 import (
    GRAPH_SNAPSHOT_SCOPE, StdioSession, full_graph_snapshot,
)
# Texto y consultas de fixture generados para esta prueba; evidencia íntegra privada.
TARGETS = {
    "en": ("meter_en", "Synthetic English measurement fixture."),
    "es": ("medidor_es", "Registro sintético español de medición."),
    "ru": ("синтездатчик", "Синтетическая запись измерения."),
    "zh": ("合成测量", "合成测量记录。"),
    "ja": ("合成計器", "合成計器の記録。"),
    "ko": ("합성측정", "합성 측정 기록."),
}
FIXED_CLOCK = "1793059200.0"


def seed_db(path: Path) -> None:
    from core.memory import consolidation
    from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        cat = memory._resolver_categoria_id("General")
        for concept, content in TARGETS.values():
            exact = normalizar_sustantivos_clave_exacto("synthetic,fixture")
            folded = normalizar_sustantivos_clave(exact)
            consolidation.fusionar_en_largo_plazo(memory, concept, content, "", cat, 0.0, folded, exact)
        memory.conn.commit()
        memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        memory.cerrar_sistema()


def cases() -> list[dict]:
    rows = []
    for lang, (concept, _) in TARGETS.items():
        rows.append({"case_id": f"exact_{lang}", "kind": "valid_exact", "language": lang,
                     "query": concept, "keywords": concept, "target": concept})
    rows.extend([
        {"case_id": "reject_missing_keywords", "kind": "missing_keywords", "language": "en",
         "query": "synthetic_meter_en", "keywords": None, "target": None},
        {"case_id": "reject_too_many_keywords", "kind": "too_many_keywords", "language": "en",
         "query": "synthetic_meter_en", "keywords": ",".join(f"qzx{i:02d}" for i in range(11)), "target": None},
        {"case_id": "valid_no_match", "kind": "valid_probe", "language": "en",
         "query": "qzxnonexistent", "keywords": "qzxnonexistent", "target": None},
    ])
    return rows


def classify(result: dict) -> str:
    if result.get("_mcp_is_error"):
        return "mcp_protocol_error"
    if result.get("status") == "exception" or result.get("exception_type"):
        return "exception_response"
    if result.get("status") == "error":
        if str(result.get("codigo", "")).startswith("SUSTANTIVOS_CLAVE_"):
            return "validation_rejection"
        return "tool_status_error"
    if result.get("error"):
        return "tool_error_field"
    if "resultados" in result and "total" in result:
        return "search_response"
    return "unclassified_response"


async def run_case(seed: Path, temp_root: Path, row: dict) -> dict:
    db = temp_root / f"copy_{row['case_id']}.db"
    src, dst = sqlite3.connect(str(seed)), sqlite3.connect(str(db))
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    before = full_graph_snapshot(db)
    error = None
    raw = None
    open_result = None
    after_open = None
    after_query = None
    try:
        async with StdioSession(db, temp_root) as session:
            open_result = await session.call("sustantivos", {"concepto": TARGETS["en"][0]})
            after_open = full_graph_snapshot(db)
            args = {
                "query": row["query"], "completo": True, "asociados": True,
                "asociaciones_max": 0, "context_window": 0, "limite": 5,
                "usar_inferencia": False, "forzar_rafaga": False,
            }
            if row["keywords"] is not None:
                args["sustantivos_clave"] = row["keywords"]
            raw = await session.call("recordar", args)
            after_query = full_graph_snapshot(db)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:500]}
    kind = classify(raw) if raw is not None else "python_exception"
    results = (raw or {}).get("resultados", [])
    target = row.get("target")
    return {
        "case_id": row["case_id"], "kind": row["kind"], "language": row["language"],
        "query": row["query"], "keywords": row["keywords"], "target": target,
            "classification": kind,
            "opening_tool_raw_status": (open_result or {}).get("status"),
            "opening_tool_mcp_is_error": bool((open_result or {}).get("_mcp_is_error")),
            "raw_status": (raw or {}).get("status"), "mcp_is_error": bool((raw or {}).get("_mcp_is_error")),
        "error_code": (raw or {}).get("codigo"),
        "error_message": (raw or {}).get("mensaje") or (raw or {}).get("message") or (raw or {}).get("error"),
        "has_search_shape": raw is not None and "resultados" in raw and "total" in raw,
        "total": (raw or {}).get("total"),
        "target_primary_found": any(item.get("concepto") == target for item in results) if target else None,
        "result_concepts": [item.get("concepto") for item in results],
        "context_count": len((raw or {}).get("contexto_expandido", [])),
        "python_exception": error,
        "graph_snapshots": {"before_stdio": before, "after_open": after_open, "after_recordar": after_query},
    }


async def execute() -> dict:
    rows = []
    with tempfile.TemporaryDirectory(prefix="e3_recordar_boundary_") as tmp:
        root = Path(tmp); seed = root / "seed.db"
        seed_db(seed)
        for row in cases():
            rows.append(await run_case(seed, root, row))
    return {
        "experiment": "E3 synthetic MCP stdio validation-versus-search boundary",
        "synthetic_only": True, "source_user_databases_opened": 0,
        "engine_patch": False, "memory_merges": 0, "backfill": False,
        "policy_selected": False, "e4_advanced": False,
        "graph_snapshot_scope": {
            **GRAPH_SNAPSHOT_SCOPE,
            "complete_sqlite_database_snapshot": False,
        },
        "cases": rows,
    }


def public_summary(report: dict) -> dict:
    counts = {}
    for row in report["cases"]:
        key = row["classification"]
        counts[key] = counts.get(key, 0) + 1
    exact = [r for r in report["cases"] if r["kind"] == "valid_exact"]
    rejects = [r for r in report["cases"] if r["classification"] == "validation_rejection"]
    probe = next(r for r in report["cases"] if r["case_id"] == "valid_no_match")
    return {
        "synthetic_only": True, "engine_patch": False, "e4_advanced": False,
        "case_count": len(report["cases"]), "classifications": counts,
        "exact_search_cases": len(exact),
        "exact_target_hits": sum(bool(r["target_primary_found"]) for r in exact),
        "validation_rejections": len(rejects),
        "tool_status_errors": sum(r["classification"] == "tool_status_error" for r in report["cases"]),
        "tool_error_fields": sum(r["classification"] == "tool_error_field" for r in report["cases"]),
        "exception_responses": sum(r["classification"] == "exception_response" for r in report["cases"]),
        "mcp_protocol_errors": sum(r["classification"] == "mcp_protocol_error" for r in report["cases"]),
        "rejection_codes": sorted({r["error_code"] for r in rejects if r["error_code"]}),
        "search_responses_without_raw_status": sum(
            r["classification"] == "search_response" and r["raw_status"] is None for r in report["cases"]
        ),
        "valid_probe_search_shape": probe["has_search_shape"],
        "valid_probe_total": probe["total"],
        "python_exceptions": sum(bool(r["python_exception"]) for r in report["cases"]),
        "mcp_error_flags": sum(r["mcp_is_error"] for r in report["cases"]),
        "opening_tool_mcp_errors": sum(r["opening_tool_mcp_is_error"] for r in report["cases"]),
        "opening_tool_status_errors": sum(
            r["opening_tool_raw_status"] in {"error", "exception"} for r in report["cases"]
        ),
        "snapshot_query_errors": sum(
            len(snap.get("query_errors", {}))
            for row in report["cases"] for snap in row["graph_snapshots"].values() if snap
        ),
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    out = Path(parser.parse_args().evidence_dir)
    private = (ROOT / ".private_evidence").resolve()
    out = (out if out.is_absolute() else ROOT / out).resolve()
    if private not in out.parents or out.exists():
        raise ValueError("Use a new output directory under .private_evidence/")
    report = asyncio.run(execute())
    summary = public_summary(report)
    report["public_aggregate"] = summary
    out.mkdir(parents=True, exist_ok=False)
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    (out / "stdio_cases_full.json").write_bytes(report_bytes)
    manifest = {"synthetic_fixtures": TARGETS, "cases": cases(), "fixed_clock": FIXED_CLOCK}
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    (out / "synthetic_manifest.json").write_bytes(manifest_bytes)
    hashes = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
              for name in ("stdio_cases_full.json", "synthetic_manifest.json")}
    (out / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
