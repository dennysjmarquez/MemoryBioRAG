#!/usr/bin/env python3
"""Instrumentación pasiva de caminos MCP en fixtures sintéticos E3.

Ejecuta pares de llamadas MCP stdio normales e instrumentadas con los mismos
inputs y configuración. Un launcher de QA envuelve buscar_por_frase en runtime,
sin alterar sus parámetros, retorno o código fuente; captura FTS MATCH, pool de
candidatos, etiqueta de origen, salida interna y respuesta final MCP. DBs, términos
y trazas completas se conservan solo en el directorio privado indicado.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.memory import consolidation
from core.memory_store import (
    SQLiteMemoryBioRAG,
    normalizar_sustantivos_clave,
    normalizar_sustantivos_clave_exacto,
)
from scripts import diagnosticar_feedback_recordar_respuesta_stdio_e3 as base

TARGET = base.TARGET
NODES = [
    (TARGET, "A synthetic archive records a quartz reading and a cobalt impulse in a controlled laboratory fixture."),
    ("noise_one", "Unrelated synthetic note about flowers and maps, entry one."),
    ("noise_two", "Unrelated synthetic note about flowers and maps, entry two."),
    ("noise_three", "Unrelated synthetic note about flowers and maps, entry three."),
    ("noise_four", "Unrelated synthetic note about flowers and maps, entry four."),
]
PAIRS = [
    ("far_query", "qzxnovelquery", "quartz"),
    ("near_query", "quarxz", "quartz"),
    ("mixed_coverage_query", "calibration cobalt impulse", "cobalt impulse"),
]


def make_cases() -> list[dict]:
    cases = []
    for pair_id, query, paraphrase in PAIRS:
        for arm, para in (("with_paraphrase", paraphrase), ("without_paraphrase", None)):
            cases.append({
                "case_id": f"{pair_id}_{arm}",
                "pair_id": pair_id,
                "arm": arm,
                "query": query,
                "parafrasis": para,
                "sustantivos_clave": "granite,orchid",
                "limite": 10,
                "asociados": False,
                "asociaciones_max": 0,
                "context_window": 0,
                "completo": True,
                "usar_inferencia": False,
                "forzar_rafaga": False,
                "modo_estricto": False,
            })
    return cases


def seed_db(path: Path) -> None:
    """Crea fixture sin aristas; la apertura y sus posibles deltas se observan aparte."""
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        category = memory._resolver_categoria_id("General")
        exact = normalizar_sustantivos_clave_exacto("fixture,synthetic")
        folded = normalizar_sustantivos_clave(exact)
        for concept, content in NODES:
            consolidation.fusionar_en_largo_plazo(
                memory, concept, content, "", category, 0.0, folded, exact
            )
        memory.conn.commit()
        memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        memory.cerrar_sistema()


def clone_db(seed: Path, destination: Path) -> None:
    src = sqlite3.connect(str(seed))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


class StdioSession:
    def __init__(self, db_path: Path, temp_root: Path, *, instrumented: bool):
        self.db_path = db_path.resolve()
        self.temp_root = temp_root.resolve()
        self.instrumented = instrumented

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self.db_path.relative_to(self.temp_root)
        env = os.environ.copy()
        state_path = self.temp_root / "dmn_state" / (self.db_path.stem + ".json")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        env.update({
            "BIORAG_PATH": str(self.db_path),
            "BIORAG_QA_TEMP_ROOT": str(self.temp_root),
            "BIORAG_DMN_ESTADO_PATH": str(state_path),
            "BIORAG_DMN_SINTESIS_ACTIVA": "0",
            "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
            "BIORAG_MCP_AUTO_PARAFRASIS": "0",
            "BIORAG_MCP_AUTO_DIMS": "0",
            "BIORAG_NEURONA": "0",
            "BIORAG_NO_LOG": "1",
            "BIORAG_QA_RELOJ_FIJO": str(base.FIXED_EPOCH),
        })
        launcher = "qa_stdio_server_trace_paraphrase.py" if self.instrumented else "qa_stdio_server_intuicion.py"
        if self.instrumented:
            env["BIORAG_QA_TRACE_PATH"] = str(self.temp_root / "telemetry" / f"{self.db_path.stem}.jsonl")
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / launcher)],
            env=env,
            cwd=str(ROOT),
        )
        self._stdio = stdio_client(params)
        read_stream, write_stream = await self._stdio.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self._session.__aexit__(exc_type, exc, tb)
        finally:
            await self._stdio.__aexit__(exc_type, exc, tb)

    async def call(self, name: str, args: dict) -> dict:
        return base.parse_tool_result(await self._session.call_tool(name, arguments=args))


async def run_one(seed: Path, root: Path, spec: dict, instrumented: bool) -> dict:
    label = "traced" if instrumented else "baseline"
    db = root / f"{spec['case_id']}_{label}.db"
    clone_db(seed, db)
    before = base.full_graph_snapshot(db)
    async with StdioSession(db, root, instrumented=instrumented) as mcp:
        opened = await mcp.call("sustantivos", {"concepto": TARGET})
        after_open = base.full_graph_snapshot(db)
        result = await mcp.call("recordar", {
            "query": spec["query"],
            "parafrasis": spec["parafrasis"],
            "sustantivos_clave": spec["sustantivos_clave"],
            "limite": spec["limite"],
            "asociados": spec["asociados"],
            "asociaciones_max": spec["asociaciones_max"],
            "context_window": spec["context_window"],
            "completo": spec["completo"],
            "usar_inferencia": spec["usar_inferencia"],
            "forzar_rafaga": spec["forzar_rafaga"],
            "modo_estricto": spec["modo_estricto"],
        })
        after_search = base.full_graph_snapshot(db)
    primary = result.get("resultados", [])
    target = next((row for row in primary if row.get("concepto") == TARGET), None)
    telemetry_path = root / "telemetry" / f"{db.stem}.jsonl"
    events = []
    if telemetry_path.exists():
        events = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "case_id": spec["case_id"],
        "mode": label,
        "opening_tool_mcp_error": bool(opened.get("_mcp_is_error")),
        "opening_tool_status": opened.get("status"),
        "response_mcp_error": bool(result.get("_mcp_is_error")),
        "response_status": result.get("status"),
        "response_total": result.get("total"),
        "response_concepts": [row.get("concepto") for row in primary],
        "target_found": target is not None,
        "target_score": target.get("score_hibrido") if target else None,
        "public_trace": result.get("trazabilidad", {}),
        "opening_graph_changed": before != after_open,
        "search_graph_changed": after_open != after_search,
        "graph_snapshots": {"before_open": before, "after_open": after_open, "after_search": after_search},
        "internal_search_events": events,
        "fts_term_controls": base.audit_fts_terms(db, spec),
        "raw_response_text": result,
    }


def summarize(cases: list[dict]) -> dict:
    pairs = []
    for pair_id, _, _ in PAIRS:
        with_para = next(c for c in cases if c["case_id"] == f"{pair_id}_with_paraphrase")
        without = next(c for c in cases if c["case_id"] == f"{pair_id}_without_paraphrase")
        baseline_with = next(c for c in with_para["runs"] if c["mode"] == "baseline")
        trace_with = next(c for c in with_para["runs"] if c["mode"] == "traced")
        baseline_without = next(c for c in without["runs"] if c["mode"] == "baseline")
        trace_without = next(c for c in without["runs"] if c["mode"] == "traced")
        pairs.append({
            "pair_id": pair_id,
            "baseline_instrumentation_equivalent": (
                baseline_with["response_concepts"] == trace_with["response_concepts"]
                and baseline_without["response_concepts"] == trace_without["response_concepts"]
                and baseline_with["response_total"] == trace_with["response_total"]
                and baseline_without["response_total"] == trace_without["response_total"]
                and baseline_with["target_score"] == trace_with["target_score"]
                and baseline_without["target_score"] == trace_without["target_score"]
                and baseline_with["response_mcp_error"] == trace_with["response_mcp_error"]
                and baseline_without["response_mcp_error"] == trace_without["response_mcp_error"]
                and baseline_with["public_trace"] == trace_with["public_trace"]
                and baseline_without["public_trace"] == trace_without["public_trace"]
            ),
            "target_with_paraphrase": trace_with["target_found"],
            "target_without_paraphrase": trace_without["target_found"],
            "paraphrase_only": trace_with["target_found"] and not trace_without["target_found"],
            "target_origin_when_returned_with_paraphrase": [
                event.get("candidate_origins", {}).get(TARGET)
                for event in trace_with["internal_search_events"]
                if TARGET in event.get("candidate_concepts", [])
            ],
            "target_fts_statement_attribution": [
                {
                    "search_call_index": event.get("search_call_index"),
                    "statement_index": statement.get("statement_index"),
                    "returned_by_statement": TARGET in statement.get("candidate_concepts", []),
                    "matching_branch_slots": [
                        slot
                        for probe in statement.get("variant_probes", [])
                        if TARGET in probe.get("candidate_concepts", [])
                        for slot in probe.get("source_slots", [probe.get("source_slot")])
                    ],
                }
                for event in trace_with["internal_search_events"]
                for statement in event.get("fts_statements", [])
                if TARGET in statement.get("candidate_concepts", [])
            ],
            "public_paraphrase_trace": trace_with["public_trace"].get("capa_parafrasis"),
            "fts_paraphrase_control_found": any(
                item["role"] == "paraphrase" and item["target_found"]
                for item in trace_with["fts_term_controls"]
            ),
        })
    return {
        "synthetic_only": True,
        "engine_source_modified": False,
        "runtime_instrumentation_only": True,
        "mcp_tool_calls": 4 * len(cases),
        "mcp_error_flags": sum(
            run[key]
            for case in cases for run in case["runs"]
            for key in ("opening_tool_mcp_error", "response_mcp_error")
        ),
        "instrumentation_equivalent_all_pairs": all(p["baseline_instrumentation_equivalent"] for p in pairs),
        "paired_cases": pairs,
        "paraphrase_only_positive_cases": sum(p["paraphrase_only"] for p in pairs),
    }


async def execute() -> dict:
    os.environ["TZ"] = "UTC"
    if hasattr(__import__("time"), "tzset"):
        __import__("time").tzset()
    specs = make_cases()
    cases = []
    with tempfile.TemporaryDirectory(prefix="e3_paraphrase_instrumented_") as tmp:
        root = Path(tmp)
        seed = root / "seed.db"
        seed_db(seed)
        for spec in specs:
            baseline = await run_one(seed, root, spec, instrumented=False)
            traced = await run_one(seed, root, spec, instrumented=True)
            cases.append({"case_id": spec["case_id"], "input": spec, "runs": [baseline, traced]})
    return {
        "experiment": "E3 internal synthetic MCP paraphrase-path instrumentation",
        "synthetic_only": True,
        "user_databases_opened": 0,
        "engine_source_modified": False,
        "cases": cases,
        "public_aggregate": summarize(cases),
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
    report = asyncio.run(execute())
    manifest = {"nodes": NODES, "pairs": PAIRS, "cases": make_cases(), "purpose": "trace MCP search paths without source edits"}
    for name, payload in (("stdio_cases_full.json", report), ("synthetic_manifest.json", manifest)):
        (out / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {
        name: hashlib.sha256((out / name).read_bytes()).hexdigest()
        for name in ("stdio_cases_full.json", "synthetic_manifest.json")
    }
    (out / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["public_aggregate"], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
