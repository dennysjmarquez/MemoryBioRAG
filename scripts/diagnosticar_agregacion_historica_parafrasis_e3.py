#!/usr/bin/env python3
"""Compara sintéticamente la agregación externa de 0bf con la ruta combinada actual.

No ejecuta el motor histórico: aplica literalmente su política MCP de llamadas
por query, penalización 0.95 y merge por concepto sobre el search core actual.
Es una prueba de política de agregación, no reproducción del ranker de 0bf.
Toda salida íntegra debe guardarse bajo .private_evidence/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.memory_store import SQLiteMemoryBioRAG
from scripts.diagnosticar_traza_interna_parafrasis_e3 import (
    NODES, PAIRS, TARGET, clone_db, seed_db,
)

PENALTY = 0.95


def run() -> dict:
    cases = []
    with tempfile.TemporaryDirectory(prefix="e3_historical_paraphrase_policy_") as tmp:
        root = Path(tmp)
        seed = root / "seed.db"
        seed_db(seed)
        for pair_id, query, paraphrase in PAIRS:
            db_old = root / f"{pair_id}_legacy_policy.db"
            db_new = root / f"{pair_id}_combined_policy.db"
            clone_db(seed, db_old)
            clone_db(seed, db_new)
            kwargs = {
                "profundidad": "activos",
                "pagina": 1,
                "limite": 10,
                "preview_chars": 0,
                "context_window": 0,
                "usar_inferencia": False,
            }
            old_mem = SQLiteMemoryBioRAG(str(db_old))
            new_mem = SQLiteMemoryBioRAG(str(db_new))
            try:
                # 0bf outer control flow: ordinary initial search, then repeat
                # [original query] + each paraphrase and keep the best score.
                initial, initial_total = old_mem.buscar_por_frase(query, **kwargs)
                merged = {row[0]: row for row in initial}
                calls = []
                for index, search_query in enumerate([query] + [paraphrase]):
                    rows, total = old_mem.buscar_por_frase(search_query, **kwargs)
                    calls.append({
                        "slot": "query_repeat" if index == 0 else f"paraphrase_{index}",
                        "concepts": [row[0] for row in rows],
                        "scores": {row[0]: row[4] for row in rows},
                        "reported_total": total,
                    })
                    factor = 1.0 if index == 0 else PENALTY
                    for row in rows:
                        penalized = (*row[:4], row[4] * factor, row[5])
                        concept = row[0]
                        if concept not in merged or penalized[4] > merged[concept][4]:
                            merged[concept] = penalized
                legacy_merged = sorted(merged.values(), key=lambda row: row[4], reverse=True)[:10]

                combined, combined_total = new_mem.buscar_por_frase(
                    query, parafrasis_list=[paraphrase], **kwargs
                )
                old_target = next((row for row in legacy_merged if row[0] == TARGET), None)
                combined_target = next((row for row in combined if row[0] == TARGET), None)
                cases.append({
                    "pair_id": pair_id,
                    "initial_query_concepts": [row[0] for row in initial],
                    "initial_query_total": initial_total,
                    "legacy_separate_calls": calls,
                    "legacy_policy_merged_concepts": [row[0] for row in legacy_merged],
                    "legacy_policy_target_score": old_target[4] if old_target else None,
                    "current_combined_match_concepts": [row[0] for row in combined],
                    "current_combined_total": combined_total,
                    "current_combined_target_score": combined_target[4] if combined_target else None,
                    "target_found_legacy_policy": old_target is not None,
                    "target_found_current_combined_core": combined_target is not None,
                })
            finally:
                old_mem.cerrar_sistema()
                new_mem.cerrar_sistema()
    return {
        "synthetic_only": True,
        "engine_source_modified": False,
        "historical_0bf_source_executed": False,
        "historical_outer_policy_emulated": True,
        "emulation_limit": "uses current core search/ranking with the 0bf MCP loop/penalty/merge; not a full historical binary replay",
        "target": TARGET,
        "nodes": NODES,
        "pairs": PAIRS,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    private_root = (root / ".private_evidence").resolve()
    out = Path(args.evidence_dir)
    out = (out if out.is_absolute() else root / out).resolve()
    if private_root not in out.parents or out.exists():
        raise ValueError("Use a new directory under .private_evidence/")
    out.mkdir(parents=True, exist_ok=False)
    result = run()
    result_path = out / "historical_policy_comparison.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {result_path.name: hashlib.sha256(result_path.read_bytes()).hexdigest()}
    (out / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "synthetic_only": result["synthetic_only"],
        "historical_0bf_source_executed": result["historical_0bf_source_executed"],
        "cases": [
            {key: case[key] for key in (
                "pair_id", "target_found_legacy_policy", "target_found_current_combined_core",
                "legacy_policy_target_score", "current_combined_target_score",
            )}
            for case in result["cases"]
        ],
    }, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
