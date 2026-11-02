#!/usr/bin/env python3
"""Diagnóstico aislado de dos FP ingleses y del grupo MCP «pendiente hueco 1».

Solo construye una base temporal desde el fixture E3A y busca en copias limpias.
Las ablaciones son diagnósticas; no editan el motor ni cambian etiquetas. La salida
contiene consultas, etiquetas y trazas por caso: guárdese en un destino privado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def first_word_boundary_hit(trace: dict) -> dict:
    snippets = trace.get("hits_fts_model_airplane", [])
    result = []
    for hit in snippets:
        text = hit["contenido_resaltado"].replace("[", "").replace("]", "")
        term = hit["termino_fts"]
        whole_word = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None
        result.append({"term": term, "fts_substring_hit": True,
                       "complete_word_hit": whole_word})
    return {"hits": result, "has_complete_word_hit": any(row["complete_word_hit"] for row in result)}


def probe_boundary_predicates(source: Path, case: dict, temp_dir: Path) -> dict:
    """Compara los dos predicados en una copia; no cambia la implementación."""
    from core.memory_store import SQLiteMemoryBioRAG

    tokens = re.findall(r"\w{3,}", case["query"].lower())
    if len(tokens) != 1:
        raise RuntimeError(f"{case['id']}: se esperaba un token CJK contiguo")
    copy = temp_dir / f"boundary_{case['id']}.db"
    shutil.copyfile(source, copy)
    memory = SQLiteMemoryBioRAG(str(copy))
    try:
        row = memory.conn.execute(
            "SELECT concepto, contenido, COALESCE(sinonimos, ''), COALESCE(sustantivos_clave, '') "
            "FROM largo_plazo WHERE concepto = ?", (case["concepto"],),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"{case['id']}: no aparece el esperado en la fixture")
        values = row
        legacy = any(memory.conn.execute(
            "SELECT PALABRA_PREFIJO(?, ?)", (tokens[0], value),
        ).fetchone()[0] for value in values)
        width_aware = any(memory.conn.execute(
            "SELECT PALABRA_INICIO_ANCHO(?, ?)", (tokens[0], value),
        ).fetchone()[0] for value in values)
        return {"case_id": case["id"], "legacy_prefix_accepts": bool(legacy),
                "width_aware_prefix_accepts": bool(width_aware),
                "wide_boundary_delta": bool(width_aware and not legacy)}
    finally:
        memory.cerrar_sistema()
        copy.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True,
                        help="JSON detallado; debe quedar en almacenamiento privado")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicie el intérprete con PYTHONHASHSEED=0 BIORAG_NEURONA=0")

    from scripts.evaluar_qa_multilingue_e3a import (
        RELOJ_FIJO, cargar_gold, crear_base, buscar_caso, sha256,
    )
    from scripts.evaluar_qa_multilingue_mcp_e3a import cargar_sustantivos, buscar_mcp
    from scripts.diagnostico_aciertos_fp_e3a import trazar

    gold = cargar_gold()
    labels = cargar_sustantivos(gold)
    pending_ref_path = ROOT / "docs/e3b3_comparacion_multilingue_20261028.json"
    pending_ref = json.loads(pending_ref_path.read_text(encoding="utf-8"))["pendiente_hueco_1"]
    cases = {case["id"]: case for case in gold}
    if len(pending_ref) != 14 or len(set(pending_ref)) != 14:
        raise RuntimeError("La referencia debe contener exactamente 14 etiquetas pendientes")
    if any(case_id not in cases for case_id in pending_ref):
        raise RuntimeError("Una etiqueta pendiente no tiene caso en la fuente")
    negatives = [case["id"] for case in gold
                 if case["idioma"] == "en" and case["tipo"] == "negativo"]
    if len(negatives) != 2:
        raise RuntimeError("Se esperaban dos controles negativos ingleses")
    selected_ids = negatives + pending_ref
    selected = [cases[case_id] for case_id in selected_ids]

    ref_direct_all = json.loads((ROOT / "docs/e3b3_directa_20261028.json").read_text(encoding="utf-8"))
    ref_direct = {row["id"]: row for row in ref_direct_all["casos"]}
    ref_mcp_all = json.loads((ROOT / "docs/e3b3_mcp_brazo_a_20261028.json").read_text(encoding="utf-8"))
    ref_mcp = {row["id"]: row for row in ref_mcp_all["recordar_sobre_base_directa"]["casos"]}
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="e3_fp_pending_") as temp, \
         patch("time.time", return_value=RELOJ_FIJO):
        temp_dir = Path(temp)
        base_path = temp_dir / "baseline_120.db"
        base_info = crear_base(base_path, gold)
        source_hash = sha256(base_path)
        direct = [buscar_caso(base_path, case, temp_dir) for case in selected]
        mcp = [buscar_mcp(base_path, case, labels, temp_dir) for case in selected]
        direct_first = {row["id"]: row for row in direct}
        mcp_first = {row["id"]: row for row in mcp}
        direct_reverse = [buscar_caso(base_path, case, temp_dir) for case in reversed(selected)]
        mcp_reverse = [buscar_mcp(base_path, case, labels, temp_dir) for case in reversed(selected)]
        direct_repeat_diffs = [row["id"] for row in direct_reverse
                               if row["resultados"] != direct_first[row["id"]]["resultados"]
                               or row["rango"] != direct_first[row["id"]]["rango"]]
        mcp_repeat_fields = ("error", "termino_invalido", "busqueda_ejecutada", "resultados", "rango", "falso_positivo")
        mcp_repeat_diffs = [row["id"] for row in mcp_reverse
                            if any(row.get(key) != mcp_first[row["id"]].get(key)
                                   for key in mcp_repeat_fields)]
        fp_traces = {
            case_id: {
                "wordnet_enabled": trazar(base_path, cases[case_id], temp_dir, wordnet="1"),
                "wordnet_disabled_diagnostic": trazar(base_path, cases[case_id], temp_dir, wordnet="0"),
            }
            for case_id in negatives
        }
        historical_diff_ids = [case_id for case_id in selected_ids
                               if direct_first[case_id]["resultados"] != ref_direct[case_id]["resultados"]]
        boundary_delta = [probe_boundary_predicates(base_path, cases[case_id], temp_dir)
                          for case_id in historical_diff_ids if cases[case_id]["idioma"] == "ja"]
        if sha256(base_path) != source_hash:
            raise RuntimeError("La base de referencia cambió durante las copias aisladas")
    elapsed = round(time.perf_counter() - start, 4)

    direct_by_id = {row["id"]: row for row in direct}
    mcp_by_id = {row["id"]: row for row in mcp}
    direct_match = {}
    mcp_match = {}
    for case_id in selected_ids:
        direct_match[case_id] = direct_by_id[case_id]["resultados"] == ref_direct[case_id]["resultados"]
        current = mcp_by_id[case_id]
        historic = ref_mcp[case_id]
        mcp_match[case_id] = all(current.get(key) == historic.get(key) for key in (
            "error", "termino_invalido", "busqueda_ejecutada", "resultados", "rango", "falso_positivo"))
    mcp_diff_nfc_only = []
    for case_id, same in mcp_match.items():
        if same:
            continue
        current, historic = mcp_by_id[case_id], ref_mcp[case_id]
        same_other_fields = all(current.get(key) == historic.get(key) for key in (
            "error", "busqueda_ejecutada", "resultados", "rango", "falso_positivo"))
        current_term, historic_term = current.get("termino_invalido"), historic.get("termino_invalido")
        if (same_other_fields and current_term and historic_term
                and unicodedata.normalize("NFC", current_term) == unicodedata.normalize("NFC", historic_term)):
            mcp_diff_nfc_only.append(case_id)
    pending_direct = [direct_by_id[case_id] for case_id in pending_ref]
    pending_mcp = [mcp_by_id[case_id] for case_id in pending_ref]
    english_fp_baseline = [direct_by_id[case_id] for case_id in negatives]
    english_fp_mcp = [mcp_by_id[case_id] for case_id in negatives]
    wordnet_summary = {}
    for case_id in negatives:
        with_wordnet = fp_traces[case_id]["wordnet_enabled"]
        without_wordnet = fp_traces[case_id]["wordnet_disabled_diagnostic"]
        wordnet_summary[case_id] = {
            "baseline_nonempty": bool(with_wordnet["resultados"]),
            "wordnet_off_nonempty": bool(without_wordnet["resultados"]),
            "false_positive_persists_without_wordnet": bool(without_wordnet["resultados"]),
            "baseline_score": with_wordnet["resultados"][0]["score"] if with_wordnet["resultados"] else None,
            "wordnet_off_score": without_wordnet["resultados"][0]["score"] if without_wordnet["resultados"] else None,
            "substring_boundary_diagnostic": first_word_boundary_hit(with_wordnet),
        }

    summary = {
        "current_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "archived_reference_commit": ref_direct_all["metadatos"].get("commit_motor"),
        "engine_sha256": sha(ROOT / "core/memory/search.py"),
        "gold_sha256": sha(ROOT / "scripts/casos_qa_multilingue_e3a.jsonl"),
        "labels_sha256": sha(ROOT / "scripts/casos_qa_multilingue_sustantivos_e3a.jsonl"),
        "baseline_fixture_integrity": base_info["integridad"],
        "baseline_memory_count": base_info["nodos"],
        "selected_case_count": len(selected),
        "direct_baseline_matches_archived": sum(direct_match.values()),
        "direct_baseline_diff_case_ids": [case_id for case_id, same in direct_match.items() if not same],
        "mcp_baseline_matches_archived": sum(mcp_match.values()),
        "mcp_baseline_diff_case_ids": [case_id for case_id, same in mcp_match.items() if not same],
        "pending_label_count": len(pending_ref),
        "pending_mcp_rejected_before_search": sum(
            row["error"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO" and not row["busqueda_ejecutada"]
            for row in pending_mcp),
        "pending_direct_expected_in_top5": sum(row["rango"] is not None for row in pending_direct),
        "pending_direct_rank1": sum(row["rango"] == 1 for row in pending_direct),
        "pending_direct_rank2": sum(row["rango"] == 2 for row in pending_direct),
        "pending_direct_no_results": sum(not row["resultados"] for row in pending_direct),
        "current_expected_returns_vs_historical_direct": sum(
            direct_by_id[case_id]["rango"] is not None and ref_direct[case_id]["rango"] is None
            for case_id in pending_ref),
        "mcp_reference_differences_only_nfc_representation": len(mcp_diff_nfc_only),
        "pending_labels_changed": 0,
        "isolated_repeatability": {
            "direct_cases_compared": len(selected),
            "direct_different_case_count": len(direct_repeat_diffs),
            "direct_different_case_ids": direct_repeat_diffs,
            "mcp_cases_compared": len(selected),
            "mcp_different_case_count": len(mcp_repeat_diffs),
            "mcp_different_case_ids": mcp_repeat_diffs,
        },
        "baseline_fixture_sha256": source_hash,
        "historical_japanese_boundary_probe": boundary_delta,
        "english_negative_count": len(negatives),
        "english_direct_false_positives": sum(bool(row["resultados"]) for row in english_fp_baseline),
        "english_mcp_false_positives": sum(bool(row["falso_positivo"]) for row in english_fp_mcp),
        "wordnet_isolated_ablation": wordnet_summary,
        "source_sha256_before_and_after_equal": True,
        "per_query_fresh_copy": True,
        "elapsed_s": elapsed,
        "patches_applied": False,
    }
    output = {
        "summary": summary,
        "baseline_direct_by_case": direct,
        "baseline_mcp_by_case": mcp,
        "english_fp_diagnostic_traces": fp_traces,
        "reference_comparison": {"direct_exact_results": direct_match, "mcp_semantic_fields": mcp_match},
        "private_sources": {
            "pending_case_ids": pending_ref,
            "selected_negative_case_ids": negatives,
            "baseline_fixture_sha256": source_hash,
        },
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Detailed diagnostic saved to private target: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
