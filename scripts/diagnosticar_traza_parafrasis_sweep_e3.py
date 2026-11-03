#!/usr/bin/env python3
"""Barrido sintético emparejado de recall MCP con/sin paráfrasis para E3.

Usa el transporte MCP stdio y el harness aislado existente. El nodo objetivo,
los distractores y todas las consultas son sintéticos. Solo genera evidencia
privada en un directorio nuevo bajo .private_evidence; no toca el motor ni DBs
originales.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from scripts import diagnosticar_feedback_recordar_respuesta_stdio_e3 as base

TARGET = base.TARGET
NODES = [
    (TARGET, "A synthetic archive records a quartz reading and a cobalt impulse in a controlled laboratory fixture."),
    ("noise_one", "Unrelated synthetic note about flowers and maps, entry one."),
    ("noise_two", "Unrelated synthetic note about flowers and maps, entry two."),
    ("noise_three", "Unrelated synthetic note about flowers and maps, entry three."),
    ("noise_four", "Unrelated synthetic note about flowers and maps, entry four."),
]

# Paired fixtures vary only the presence of parafrasis. Raw terms live only in
# the private manifest/report; the public aggregate contains counts, not text.
QUERY_PAIRS = [
    ("quarxz", "quartz"),
    ("quartzs", "quartz"),
    ("coblt", "cobalt impulse"),
    ("cobalt impuls", "cobalt impulse"),
    ("qzxnovelquery", "quartz"),
]


def make_cases() -> list[dict]:
    cases = []
    for i, (query, paraphrase) in enumerate(QUERY_PAIRS, start=1):
        for arm, para in (("with_paraphrase", paraphrase), ("without_paraphrase", None)):
            cases.append({
                "case_id": f"pair_{i}_{arm}",
                "query": query,
                "parafrasis": para,
                "keywords": "granite,orchid",
                "asociados": False,
                "context_window": 0,
                "limite": 10,
                "asociaciones_max": 0,
                "completo": True,
                "modo_estricto": False,
            })
    return cases


def summarize(rows: list[dict]) -> dict:
    pairs = []
    for i in range(1, len(QUERY_PAIRS) + 1):
        with_para = next(r for r in rows if r["case_id"] == f"pair_{i}_with_paraphrase")
        without = next(r for r in rows if r["case_id"] == f"pair_{i}_without_paraphrase")
        pairs.append((bool(with_para["target_found"]), bool(without["target_found"])))
    return {
        "synthetic_only": True,
        "engine_patch": False,
        "user_databases_opened": 0,
        "mcp_calls": len(rows),
        "mcp_error_flags": sum(bool(r["mcp_is_error"]) for r in rows),
        "python_exceptions": sum(bool(r["python_exception"]) for r in rows),
        "target_hits_with_paraphrase": sum(a for a, _ in pairs),
        "target_hits_without_paraphrase": sum(b for _, b in pairs),
        "paired_outcomes": {
            "paraphrase_only": sum(a and not b for a, b in pairs),
            "control_only": sum(b and not a for a, b in pairs),
            "both": sum(a and b for a, b in pairs),
            "neither": sum(not a and not b for a, b in pairs),
        },
        "direct_fts_paraphrase_term_target_hits": sum(
            any(x["role"] == "paraphrase" and x["target_found"] for x in r["fts_term_controls"])
            for r in rows if r["input"]["parafrasis"]
        ),
        "paraphrase_trace_values_for_target_hits": sorted({
            r["target_trace"].get("capa_parafrasis")
            for r in rows if r["target_found"]
        }),
        "positive_paraphrase_specific_mcp_case": any(a and not b for a, b in pairs),
        "interpretation": (
            "A direct FTS term match alone does not establish a paraphrase-specific MCP retrieval."
        ),
    }


async def run() -> dict:
    base.NODES = NODES
    cases = make_cases()
    with tempfile.TemporaryDirectory(prefix="e3_paraphrase_sweep_") as tmp:
        root = Path(tmp)
        seed = root / "seed.db"
        base.seed_db(seed)
        rows = [await base.run_case(seed, root, spec) for spec in cases]
    summary = summarize(rows)
    return {
        "experiment": "E3 paired synthetic paraphrase MCP stdio sweep",
        "synthetic_only": True,
        "user_databases_opened": 0,
        "engine_patch": False,
        "cases": rows,
        "public_aggregate": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    out = Path(args.evidence_dir)
    private_root = (Path(__file__).resolve().parents[1] / ".private_evidence").resolve()
    out = (out if out.is_absolute() else Path(__file__).resolve().parents[1] / out).resolve()
    if private_root not in out.parents or out.exists():
        raise ValueError("Use a new directory under .private_evidence/")
    report = asyncio.run(run())
    manifest = {"nodes": NODES, "cases": make_cases(), "query_pairs": QUERY_PAIRS}
    out.mkdir(parents=True, exist_ok=False)
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
