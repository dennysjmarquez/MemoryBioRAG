#!/usr/bin/env python3
"""Extensión sintética MCP stdio de rutas de creación y densidad de grafo para E3.

Prueba `aprender`/`guardar` y transferencia `corto_plazo`→`largo_plazo` sobre
copias independientes. Cruza tres historias sintéticas con cuatro densidades
(control separado de vecinos explícitos y candidatos adicionales) y brazos de
pista activa/neutral. No toca motor, datos reales, política de etiquetas ni E4.
Las trazas y el manifiesto íntegro se escriben solo en una carpeta privada nueva.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replicar_hipotesis_etiquetas_controles_e3 import (
    FIXED_CLOCK,
    GRAPH_QUERIES,
    GRAPH_SNAPSHOT_SCOPE,
    StdioSession,
    canonical_json_bytes,
    full_graph_snapshot,
    normalized_pair,
    parse_tool_result,
    recall_error_fields,
    recall_result_ok,
)

TARGET = "nodo_sintetico_aprendido"
ANCHOR = "ancla_sintetica_apertura"
FIXED_NEIGHBORS = 2
FIXED_CANDIDATES = 2

HISTORY_FAMILIES = {
    "util_solo_etiqueta": {
        "probe": "thermistor",
        "neutral": "qzxcontrol",
        "other_labels": ["sensor", "reference"],
        "content": "The original instrument reading remains the validated baseline; the later review agrees.",
        "old_truth": "la pista histórica se considera útil en el fixture, ausente del texto",
        "current_query": "reference",
        "target_synonyms": "zx_syn_a,zx_syn_b,zx_syn_c,zx_syn_d,zx_syn_e",
        "neighbor_cue_index": None,
    },
    "contradicho_en_contenido": {
        "probe": "openstate",
        "neutral": "qzxostate",
        "other_labels": ["valve", "closedstate"],
        "content": "Prior entry openstate was explicitly corrected; the inspection confirms closedstate.",
        "old_truth": "el registro de la pista aparece contradicho en el texto sintético",
        "current_query": "closedstate",
        "target_synonyms": "zx_syn_a,zx_syn_b,zx_syn_c,zx_syn_d,zx_syn_e",
        "neighbor_cue_index": None,
    },
    "ruta_vecino": {
        "probe": "archivecue",
        "neutral": "qzxcontrol",
        "other_labels": ["network", "evidence"],
        "content": "A synthetic archive node records the linked context for later review.",
        "old_truth": "la pista aparece en un vecino manual solo cuando esa densidad está presente",
        "current_query": "network",
        "target_synonyms": "zx_syn_a,zx_syn_b,zx_syn_c,zx_syn_d,zx_syn_e",
        "neighbor_cue_index": 0,
    },
}

DENSITIES = {
    "sparse": {"manual_neighbor_count": 0, "candidate_count": 0},
    "neighbors_only": {"manual_neighbor_count": 2, "candidate_count": 0},
    "candidates_only": {"manual_neighbor_count": 0, "candidate_count": 2},
    "dense": {"manual_neighbor_count": 2, "candidate_count": 2},
}

MCP_TOOL_STAGES = (
    "open_first_tool", "preflight_recordar", "create_short", "read_short_labels",
    "consolidate", "read_long_labels", "historical_recordar",
)
RECORDAR_STAGES = ("preflight_recordar", "historical_recordar")

BRIDGES = [
    {"text": "synthetic instrument alternate wording", "angle": "sinonimo"},
    {"text": "synthetic measurement drift issue", "angle": "problema"},
    {"text": "synthetic channel review procedure", "angle": "solucion"},
    {"text": "synthetic laboratory inspection setting", "angle": "situacion"},
    {"text": "synthetic way to check a reading", "angle": "ingenuo"},
]


def resolve_output_dir(requested: str | None) -> Path:
    private_root = (ROOT / ".private_evidence").resolve()
    if requested:
        candidate = Path(requested)
        output = (candidate if candidate.is_absolute() else ROOT / candidate).resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = (private_root / f"e3_creation_density_{stamp}").resolve()
    if private_root not in output.parents:
        raise ValueError("Full evidence must stay under .private_evidence/")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing evidence directory: {output}")
    return output


def full_clue_manifest() -> dict:
    return {
        "experiment": "E3 synthetic creation routes and graph density",
        "audit_reference": "docs/e3_inventario_pendiente_20261102.md",
        "arms": ["cue_activo", "neutral_igual_longitud"],
        "write_routes": ["aprender", "guardar"],
        "transfer_route": "consolidar corto_plazo to largo_plazo",
        "fixed_clock": FIXED_CLOCK,
        "history_families": HISTORY_FAMILIES,
        "density_conditions": DENSITIES,
        "density_note": (
            "A fixed seed anchor exists in every copy; candidate_count means extra non-cue nodes. "
            "Manual-neighbor count and candidate count vary independently."
        ),
        "preservation_note": (
            "Every probe, neutral, history text, query anchor, candidate/neighbor template, and arm payload "
            "is listed here whether or not it is active or present in a specific density condition."
        ),
        "query_anchor": "xqzqueryanchor",
        "target_concept": TARGET,
        "anchor_concept": ANCHOR,
        "neighbor_ids_by_count": {str(i): [f"vecino_sintetico_{j + 1}" for j in range(i)] for i in (0, 2)},
        "candidate_ids_by_count": {str(i): [f"candidato_sintetico_{j + 1}" for j in range(i)] for i in (0, 2)},
        "aprender_bridges": BRIDGES,
        "dimensions_payload": '{"dominio":["dominio_tecnico"]}',
        "seed_templates": {
            "anchor_content": "A fixed synthetic anchor for opening and preflight controls.",
            "neighbor_generic_content": "A synthetic related note for graph-density control.",
            "candidate_content": "A synthetic sensor measurement channel context used as a non-cue candidate.",
            "neighbor_cue_rule": "Only the specified neighbor-route family may place its probe in neighbor index zero, and only when that neighbor is present.",
        },
    }


def count_edges_of_type(rows: list, edge_type: str) -> int:
    return sum(len(row) > 3 and row[3] == edge_type for row in rows)


def safe_rows(path: Path, table: str, concept: str) -> dict:
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    try:
        try:
            row = conn.execute(
                f"SELECT concepto,contenido,sinonimos,sustantivos_clave,sustantivos_clave_exactos "
                f"FROM {table} WHERE concepto=?",
                (concept,),
            ).fetchone()
            return {"row": row, "query_error": None}
        except sqlite3.Error as exc:
            return {"row": None, "query_error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


def storage_snapshot(path: Path) -> dict:
    return {
        table: safe_rows(path, table, TARGET)
        for table in ("corto_plazo", "largo_plazo")
    }


def seed_database(path: Path, history: dict, density: dict) -> None:
    from core.memory import consolidation
    from core.memory_store import SQLiteMemoryBioRAG

    memory = SQLiteMemoryBioRAG(str(path))
    try:
        category = memory._resolver_categoria_id("General")
        nodes = [(ANCHOR, "A fixed synthetic anchor for opening and preflight controls.")]
        neighbor_count = density["manual_neighbor_count"]
        for i in range(neighbor_count):
            if i == history["neighbor_cue_index"]:
                content = f"A linked synthetic history note contains {history['probe']} for contextual route testing."
            else:
                content = f"A generic synthetic linked neighbor {i + 1} provides unrelated context."
            nodes.append((f"vecino_sintetico_{i + 1}", content))
        for i in range(density["candidate_count"]):
            nodes.append((
                f"candidato_sintetico_{i + 1}",
                f"Synthetic sensor measurement channel candidate {i + 1}; non-cue context only.",
            ))

        for concept, content in nodes:
            folded, exact = normalized_pair(["context", "synthetic"])
            consolidation.fusionar_en_largo_plazo(
                memory, concept, content, "", category, 0.0, folded, exact
            )
        memory.conn.commit()
        memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        memory.cerrar_sistema()


def payload(history: dict, arm: str) -> list[str]:
    cue = history["probe"] if arm == "cue_activo" else history["neutral"]
    labels = [*history["other_labels"], cue]
    if len(history["probe"]) != len(history["neutral"]):
        raise AssertionError("Pista y control neutral deben tener igual longitud")
    if len(set(labels)) != len(labels):
        raise AssertionError("Payload de etiqueta no único")
    return labels


def snapshot_stage(db_path: Path, snapshots: dict, storage: dict, stage: str) -> None:
    graph = full_graph_snapshot(db_path)
    snapshots[stage] = graph
    storage[stage] = storage_snapshot(db_path)


def query_args(term: str) -> dict:
    return {
        "query": term,
        "sustantivos_clave": f"{term},xqzqueryanchor",
        "completo": True,
        "asociados": True,
        "asociaciones_max": 0,
        "context_window": 1,
        "limite": 10,
        "usar_inferencia": False,
        "forzar_rafaga": False,
    }


def tool_result_is_ok(result: dict) -> bool:
    return (
        not result.get("_mcp_is_error")
        and result.get("status") not in {"error", "exception"}
        and not result.get("exception_type")
        and not result.get("error")
    )


def summarize_recall(result: dict) -> dict:
    primary = result.get("resultados", [])
    expanded = result.get("contexto_expandido", [])
    target = next((row for row in primary if row.get("concepto") == TARGET), None)
    context_target = next((row for row in expanded if row.get("concepto") == TARGET), None)
    return {
        **recall_error_fields(result),
        "total": result.get("total"),
        "target_primary_found": target is not None,
        "target_rank": next((i + 1 for i, row in enumerate(primary) if row.get("concepto") == TARGET), None),
        "target_score": target.get("score_hibrido") if target else None,
        "target_context_found": context_target is not None,
        "primary_concepts": [row.get("concepto") for row in primary],
        "context_concepts": [row.get("concepto") for row in expanded],
        "target_neighbors": sorted(
            row.get("concepto") for row in (target or {}).get("asociaciones_enriquecidas", [])
        ),
    }


async def run_arm(seed: Path, db_path: Path, temp_root: Path, history_id: str,
                  history: dict, density_id: str, density: dict,
                  route: str, arm: str) -> dict:
    # Clone through SQLite backup; no fixture source is ever opened as a live DB.
    src = sqlite3.connect(str(seed))
    dst = sqlite3.connect(str(db_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    snapshots = {"before_stdio": full_graph_snapshot(db_path)}
    storage = {"before_stdio": storage_snapshot(db_path)}
    clues = payload(history, arm)
    expected_folded, expected_exact = normalized_pair(clues)
    neighbor_ids = [f"vecino_sintetico_{i + 1}" for i in range(density["manual_neighbor_count"])]
    stage_results = {}
    recall_results = {}
    errors = []
    python_exception_records = []
    async with StdioSession(db_path, temp_root) as mcp:
        stage_results["after_initialize"] = {"graph": full_graph_snapshot(db_path)}
        snapshots["after_initialize"] = stage_results["after_initialize"]["graph"]
        storage["after_initialize"] = storage_snapshot(db_path)

        async def tool(stage: str, name: str, args: dict) -> dict:
            try:
                result = await mcp.call(name, args)
            except Exception as exc:
                record = {"stage": stage, "tool": name, "error_type": type(exc).__name__, "error": str(exc)[:500]}
                errors.append(record)
                python_exception_records.append(dict(record))
                return {"status": "exception", "exception_type": type(exc).__name__, "error": str(exc)[:500]}
            if (
                result.get("_mcp_is_error") or result.get("status") in {"error", "exception"}
                or result.get("exception_type") or result.get("error")
            ):
                errors.append({
                    "stage": stage,
                    "tool": name,
                    "mcp_is_error": bool(result.get("_mcp_is_error")),
                    "status": result.get("status"),
                    "exception_type": result.get("exception_type"),
                    "error": str(result.get("error") or result.get("message") or "")[:500],
                })
            return result

        stage_results["open_first_tool"] = await tool("open_first_tool", "sustantivos", {"concepto": ANCHOR})
        snapshot_stage(db_path, snapshots, storage, "after_first_tool_call")

        stage_results["preflight_recordar"] = await tool("preflight_recordar", "recordar", query_args(history["probe"]))
        preflight = summarize_recall(stage_results["preflight_recordar"])
        snapshot_stage(db_path, snapshots, storage, "after_preflight_recordar")

        labels = payload(history, arm)
        stage_results["create_short"] = await tool("create_short", route, {
            "concepto": TARGET,
            "contenido": history["content"],
            "syn": history["target_synonyms"],
            "cat": "General",
            "dimensiones": '{"dominio":["dominio_tecnico"]}',
            "bridges": BRIDGES,
            "sustantivos_clave": ",".join(labels),
            "busqueda_previa": True,
            "vincular_con": neighbor_ids,
        })
        snapshot_stage(db_path, snapshots, storage, "after_create_short")

        stage_results["read_short_labels"] = await tool("read_short_labels", "sustantivos", {"concepto": TARGET})
        snapshot_stage(db_path, snapshots, storage, "after_short_read")

        stage_results["consolidate"] = await tool("consolidate", "consolidar", {})
        snapshot_stage(db_path, snapshots, storage, "after_consolidate")

        stage_results["read_long_labels"] = await tool("read_long_labels", "sustantivos", {"concepto": TARGET})
        snapshot_stage(db_path, snapshots, storage, "after_long_read")

        stage_results["historical_recordar"] = await tool("historical_recordar", "recordar", query_args(history["probe"]))
        recall_results["historical"] = summarize_recall(stage_results["historical_recordar"])
        snapshot_stage(db_path, snapshots, storage, "after_historical_recordar")

    short_row = storage["after_short_read"]["corto_plazo"]["row"]
    long_row = storage["after_long_read"]["largo_plazo"]["row"]
    short_folded = short_row[3] if short_row and len(short_row) > 3 else None
    short_exact = short_row[4] if short_row and len(short_row) > 4 else None
    long_folded = long_row[3] if long_row and len(long_row) > 3 else None
    long_exact = long_row[4] if long_row and len(long_row) > 4 else None

    graph_deltas = {}
    previous = snapshots["before_stdio"]["rows"]
    for stage, snapshot in list(snapshots.items())[1:]:
        current = snapshot["rows"]
        graph_deltas[stage] = {
            "added": {table: [row for row in current[table] if row not in previous[table]] for table in GRAPH_QUERIES},
            "removed": {table: [row for row in previous[table] if row not in current[table]] for table in GRAPH_QUERIES},
        }
        previous = current

    all_tool_results = list(stage_results.values())
    snapshot_ok = all(not snap.get("query_errors") for snap in snapshots.values())
    storage_ok = all(not item[table].get("query_error") for item in storage.values() for table in item)
    statuses_ok = all(tool_result_is_ok(result) for result in all_tool_results) and all(
        recall_result_ok(q) for q in (preflight, recall_results.get("historical", {}))
    )
    direct_storage_ok = (
        short_folded == expected_folded and short_exact == expected_exact
        and long_folded == expected_folded and long_exact == expected_exact
    )
    arm_status = "ok" if snapshot_ok and storage_ok and statuses_ok and direct_storage_ok and not errors else "inconclusive"
    return {
        "arm_status": arm_status,
        "history_family": history_id,
        "density": density_id,
        "density_settings": density,
        "write_route": route,
        "arm": arm,
        "target_concept": TARGET,
        "labels_payload": labels,
        "expected_folded": expected_folded,
        "expected_exact": expected_exact,
        "short_term_folded_actual_sql": short_folded,
        "short_term_exact_actual_sql": short_exact,
        "long_term_folded_actual_sql": long_folded,
        "long_term_exact_actual_sql": long_exact,
        "short_term_pair_matches": short_folded == expected_folded and short_exact == expected_exact,
        "long_term_pair_matches": long_folded == expected_folded and long_exact == expected_exact,
        "preflight_target_primary_found": preflight["target_primary_found"],
        "preflight_target_context_found": preflight["target_context_found"],
        "historical_recall": recall_results.get("historical", {}),
        "tool_results": stage_results,
        "errors": errors,
        "python_exception_records": python_exception_records,
        "preflight_recall_status": preflight,
        "graph_snapshots_full_rows": snapshots,
        "storage_snapshots_exact_rows": storage,
        "graph_deltas_full_rows": graph_deltas,
        "graph_snapshot_query_errors": sum(len(snap.get("query_errors", {})) for snap in snapshots.values()),
        "storage_query_errors": sum(bool(item[table].get("query_error")) for item in storage.values() for table in item),
        "dmn_edges_after_first_tool_call": count_edges_of_type(
            graph_deltas.get("after_first_tool_call", {}).get("added", {}).get("sinapsis", []), "dmn_synthesized"
        ),
        "manual_neighbor_edges_after_create": count_edges_of_type(
            graph_deltas.get("after_create_short", {}).get("added", {}).get("sinapsis", []), "manual"
        ),
        "clock": FIXED_CLOCK,
    }


def summarize(report: dict) -> dict:
    bykey = {(a["history_family"], a["density"], a["write_route"], a["arm"]): a for a in report["arms"]}
    valid_arms = [a for a in report["arms"] if a.get("arm_status") == "ok"]
    pairs = []
    for h in HISTORY_FAMILIES:
        for d in DENSITIES:
            for route in ("aprender", "guardar"):
                cue = bykey.get((h, d, route, "cue_activo"))
                neutral = bykey.get((h, d, route, "neutral_igual_longitud"))
                if not cue or not neutral or cue.get("arm_status") != "ok" or neutral.get("arm_status") != "ok":
                    pairs.append({"history_family": h, "density": d, "write_route": route, "status": "inconclusive"})
                    continue
                graph_equal = {
                    stage: cue["graph_snapshots_full_rows"][stage]["rows"] == neutral["graph_snapshots_full_rows"][stage]["rows"]
                    for stage in cue["graph_snapshots_full_rows"]
                    if stage in neutral["graph_snapshots_full_rows"]
                }
                pairs.append({
                    "history_family": h,
                    "density": d,
                    "write_route": route,
                    "status": "ok",
                    "graph_equal_full_rows_by_stage": graph_equal,
                    "short_term_labels_match_both": cue["short_term_pair_matches"] and neutral["short_term_pair_matches"],
                    "long_term_labels_match_both": cue["long_term_pair_matches"] and neutral["long_term_pair_matches"],
                    "preflight_no_target_both": (
                        not cue["preflight_target_primary_found"] and not cue["preflight_target_context_found"]
                        and not neutral["preflight_target_primary_found"] and not neutral["preflight_target_context_found"]
                    ),
                    "historical_query": {
                        "cue_arm": cue["historical_recall"],
                        "neutral_arm": neutral["historical_recall"],
                    },
                    "dmn_open_edges": {
                        "cue_arm": cue["dmn_edges_after_first_tool_call"],
                        "neutral_arm": neutral["dmn_edges_after_first_tool_call"],
                    },
                    "manual_edges_after_create": {
                        "cue_arm": cue["manual_neighbor_edges_after_create"],
                        "neutral_arm": neutral["manual_neighbor_edges_after_create"],
                    },
                })
    valid_pairs = [p for p in pairs if p.get("status") == "ok"]
    tool_result_pairs = [
        (a, stage, a.get("tool_results", {}).get(stage))
        for a in report["arms"] for stage in MCP_TOOL_STAGES
        if isinstance(a.get("tool_results", {}).get(stage), dict)
    ]
    raw_status_missing_by_stage = {
        stage: sum(
            isinstance(a.get("tool_results", {}).get(stage), dict)
            and "status" not in a["tool_results"][stage]
            for a in report["arms"]
        )
        for stage in MCP_TOOL_STAGES
    }
    exception_count = 0
    for arm in report["arms"]:
        if "python_exception_records" in arm:
            exception_count += len(arm["python_exception_records"])
        else:  # legacy raw artifacts before exception telemetry was explicit
            exception_count += sum("error_type" in item for item in arm.get("errors", []))
            exception_count += int(bool(arm.get("error_type")))
    return {
        "successful_arms": len(valid_arms),
        "inconclusive_or_error_arms": sum(a.get("arm_status") != "ok" for a in report["arms"]),
        "arm_count": len(report["arms"]),
        "paired_contrasts": len(pairs),
        "successful_pairs": sum(p.get("status") == "ok" for p in pairs),
        "exact_label_columns_match_in_short_and_long": all(
            a.get("short_term_pair_matches") and a.get("long_term_pair_matches") for a in valid_arms
        ) if valid_arms else None,
        "full_graph_pair_equal_all_stages": all(
            all(p.get("graph_equal_full_rows_by_stage", {}).values()) for p in valid_pairs
        ) if valid_pairs else None,
        "python_exception_count": exception_count,
        "mcp_tool_call_count": len(tool_result_pairs),
        "mcp_error_flag_count": sum(bool(result.get("_mcp_is_error")) for _, _, result in tool_result_pairs),
        "tool_status_error_count": sum(result.get("status") == "error" for _, _, result in tool_result_pairs),
        "tool_error_field_count": sum(bool(result.get("error")) for _, _, result in tool_result_pairs),
        "tool_status_exception_count": sum(
            result.get("status") == "exception" or bool(result.get("exception_type"))
            for _, _, result in tool_result_pairs
        ),
        "mcp_tool_raw_status_missing_count": sum(raw_status_missing_by_stage.values()),
        "mcp_tool_raw_status_missing_by_stage": raw_status_missing_by_stage,
        "recordar_raw_status_missing_without_error_count": sum(
            stage in RECORDAR_STAGES
            and "status" not in result
            and not result.get("_mcp_is_error")
            and not result.get("error")
            and not result.get("message")
            for _, stage, result in tool_result_pairs
        ),
        "snapshot_query_error_count": sum(a.get("graph_snapshot_query_errors", 0) for a in report["arms"]),
        "storage_query_error_count": sum(a.get("storage_query_errors", 0) for a in report["arms"]),
        "preflight_target_unseen_all_arms": all(
            not a.get("preflight_target_primary_found") and not a.get("preflight_target_context_found")
            for a in valid_arms
        ) if valid_arms else None,
        "density_levels": len(DENSITIES),
        "write_routes": ["aprender", "guardar"],
        "history_families": len(HISTORY_FAMILIES),
        "pairs": pairs,
        "dmn_edges_after_open_by_density": {
            density: [a["dmn_edges_after_first_tool_call"] for a in report["arms"] if a["density"] == density]
            for density in DENSITIES
        },
        "manual_edges_after_create_by_density": {
            density: [a["manual_neighbor_edges_after_create"] for a in report["arms"] if a["density"] == density]
            for density in DENSITIES
        },
    }


def write_evidence(report: dict, manifest: dict, out_dir: Path) -> dict:
    private_root = (ROOT / ".private_evidence").resolve()
    out_dir = out_dir.resolve()
    if private_root not in out_dir.parents or out_dir.exists():
        raise ValueError("Evidence output must be a new directory under .private_evidence/")
    manifest_file_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    canonical_hash = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    file_hash = hashlib.sha256(manifest_file_bytes).hexdigest()
    report["manifest_hashes"] = {"canonical_json_utf8_sha256": canonical_hash, "file_bytes_sha256": file_hash}
    report["summary"] = summarize(report)
    report["graph_snapshot_scope"] = {
        **GRAPH_SNAPSHOT_SCOPE,
        "snapshot_result_key_to_source": {
            "sinapsis": "sinapsis",
            "sinapsis_latentes": "sinapsis_latentes",
            "sinapsis_cuarentena": "sinapsis_cuarentena",
            "dimensiones_nodo": "largo_plazo_dimensiones",
            "grupos_semanticos": "grupos_semanticos",
            "grupos_nodo": "nodo_grupos_semanticos",
            "concept_hubs": "concept_hubs",
            "concept_hub_nodes": "concept_hub_nodes",
            "concept_hub_bridges": "concept_hub_bridges",
            "espejo_asociaciones": "largo_plazo(concepto, asociaciones) [proyección]",
        },
    }
    out_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = out_dir / "all_synthetic_clues_manifest.json"
    report_path = out_dir / "stdio_cases_full.json"
    manifest_path.write_bytes(manifest_file_bytes)
    manifest_readback = manifest_path.read_bytes()
    if manifest_readback != manifest_file_bytes or hashlib.sha256(manifest_readback).hexdigest() != file_hash:
        raise RuntimeError("Manifest file-byte hash mismatch")
    if hashlib.sha256(canonical_json_bytes(json.loads(manifest_readback))).hexdigest() != canonical_hash:
        raise RuntimeError("Manifest canonical hash mismatch")
    report_bytes = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    report_path.write_bytes(report_bytes)
    report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if report_path.read_bytes() != report_bytes:
        raise RuntimeError("Private report file-byte verification failed")
    sums = {
        "all_synthetic_clues_manifest.json": file_hash,
        "all_synthetic_clues_manifest_canonical_json_sha256": canonical_hash,
        "stdio_cases_full.json": report_hash,
        "case_count": len(report["arms"]),
        "source_databases_opened": 0,
    }
    sums_bytes = json.dumps(sums, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    sums_path = out_dir / "SHA256SUMS.json"
    sums_path.write_bytes(sums_bytes)
    if sums_path.read_bytes() != sums_bytes:
        raise RuntimeError("Private checksum manifest byte verification failed")
    return {
        "private_artifact_dir": str(out_dir),
        "manifest_file_sha256": file_hash,
        "manifest_canonical_json_sha256": canonical_hash,
    }


def public_summary(report: dict, private_paths: dict) -> dict:
    summary = report["summary"]
    arms = report["arms"]
    pair_rows = summary["pairs"]
    grouped = []
    for history_id in HISTORY_FAMILIES:
        for route in ("aprender", "guardar"):
            cells = [p for p in pair_rows if p.get("history_family") == history_id and p.get("write_route") == route and p.get("status") == "ok"]
            grouped.append({
                "history_type": history_id,
                "write_route": route,
                "density_cells": len(cells),
                "cue_arm_primary_hits": sum(bool(p["historical_query"]["cue_arm"].get("target_primary_found")) for p in cells),
                "neutral_arm_primary_hits": sum(bool(p["historical_query"]["neutral_arm"].get("target_primary_found")) for p in cells),
                "neutral_arm_context_hits": sum(bool(p["historical_query"]["neutral_arm"].get("target_context_found")) for p in cells),
                "full_graph_equal_cells": sum(all(p["graph_equal_full_rows_by_stage"].values()) for p in cells),
            })
    density_summary = {}
    for density in DENSITIES:
        cases = [a for a in arms if a.get("density") == density and a.get("arm_status") == "ok"]
        density_summary[density] = {
            "successful_arms": len(cases),
            "dmn_edges_observed_after_first_tool_call_total": sum(a.get("dmn_edges_after_first_tool_call", 0) for a in cases),
            "explicit_manual_edges_observed_after_create_total": sum(a.get("manual_neighbor_edges_after_create", 0) for a in cases),
        }
    return {
        "synthetic_only": True,
        "user_databases_opened": 0,
        "engine_patch": False,
        "policy_selected": False,
        "e4_advanced": False,
        "arm_count": summary["arm_count"],
        "successful_arms": summary["successful_arms"],
        "inconclusive_or_error_arms": summary["inconclusive_or_error_arms"],
        "paired_contrasts": summary["paired_contrasts"],
        "successful_pairs": summary["successful_pairs"],
        "short_and_long_exact_folded_columns_match": summary["exact_label_columns_match_in_short_and_long"],
        "paired_graph_equal_at_every_stage": summary["full_graph_pair_equal_all_stages"],
        "python_exceptions": summary["python_exception_count"],
        "mcp_tool_calls": summary["mcp_tool_call_count"],
        "mcp_error_flags": summary["mcp_error_flag_count"],
        "tool_status_errors": summary["tool_status_error_count"],
        "tool_error_fields": summary["tool_error_field_count"],
        "tool_status_exceptions": summary["tool_status_exception_count"],
        "mcp_tool_raw_status_missing": summary["mcp_tool_raw_status_missing_count"],
        "mcp_tool_raw_status_missing_by_stage": summary["mcp_tool_raw_status_missing_by_stage"],
        "recordar_raw_status_missing_without_error": summary["recordar_raw_status_missing_without_error_count"],
        "graph_snapshot_query_errors": summary["snapshot_query_error_count"],
        "storage_query_errors": summary["storage_query_error_count"],
        "preflight_target_absent": summary["preflight_target_unseen_all_arms"],
        "history_types": len(HISTORY_FAMILIES),
        "density_conditions": len(DENSITIES),
        "write_routes": ["aprender", "guardar"],
        "historical_query_outcomes_by_history_and_route": grouped,
        "density_aggregate_observations": density_summary,
        "private_outputs": private_paths,
    }


async def execute() -> dict:
    manifest = full_clue_manifest()
    with tempfile.TemporaryDirectory(prefix="e3_creation_density_") as temp:
        temp_root = Path(temp)
        arms = []
        for history_id, history in HISTORY_FAMILIES.items():
            for density_id, density in DENSITIES.items():
                seed = temp_root / f"seed_{history_id}_{density_id}.db"
                try:
                    seed_database(seed, history, density)
                    seed_hash = hashlib.sha256(seed.read_bytes()).hexdigest()
                except Exception as exc:
                    for route in ("aprender", "guardar"):
                        for arm in ("cue_activo", "neutral_igual_longitud"):
                            arms.append({
                                "arm_status": "inconclusive",
                                "history_family": history_id,
                                "density": density_id,
                                "density_settings": density,
                                "write_route": route,
                                "arm": arm,
                                "stage": "seed_creation",
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:500],
                                "python_exception_records": [{
                                    "stage": "seed_creation", "error_type": type(exc).__name__, "error": str(exc)[:500],
                                }],
                            })
                    continue
                for route in ("aprender", "guardar"):
                    for arm in ("cue_activo", "neutral_igual_longitud"):
                        db_path = temp_root / f"{history_id}_{density_id}_{route}_{arm}.db"
                        try:
                            arm_result = await run_arm(
                                seed, db_path, temp_root, history_id, history,
                                density_id, density, route, arm,
                            )
                            arm_result["seed_database_sha256"] = seed_hash
                            arms.append(arm_result)
                        except Exception as exc:
                            arms.append({
                                "arm_status": "inconclusive",
                                "family": history_id,
                                "density": density_id,
                                "density_settings": density,
                                "write_route": route,
                                "arm": arm,
                                "seed_database_sha256": seed_hash,
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:500],
                                "python_exception_records": [{
                                    "stage": "arm_execution", "error_type": type(exc).__name__, "error": str(exc)[:500],
                                }],
                            })
        report = {
            "experiment": "E3 creation routes and graph density",
            "audit_plan": "docs/e3_inventario_pendiente_20261102.md",
            "synthetic_only": True,
            "user_databases_opened": 0,
            "engine_patch": False,
            "memory_merges": 0,
            "backfill": False,
            "policy_selected": False,
            "e4_advanced": False,
            "arms": arms,
            "clue_manifest": manifest,
        }
        report["summary"] = summarize(report)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", help="directorio nuevo bajo .private_evidence/; no se sobrescribe")
    args = parser.parse_args()
    out_dir = resolve_output_dir(args.evidence_dir)
    report = asyncio.run(execute())
    private_paths = write_evidence(report, full_clue_manifest(), out_dir)
    print(json.dumps(public_summary(report, private_paths), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
