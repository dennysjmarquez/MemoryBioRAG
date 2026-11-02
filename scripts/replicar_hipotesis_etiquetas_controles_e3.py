#!/usr/bin/env python3
"""Réplica pareada de H-E3-ETQ-01 con controles aprobados en e71d7bc.

Usa únicamente fixtures SQLite sintéticas temporales y el FastMCP stdio real.
Cada brazo parte del mismo seed por familia, tiene estado DMN propio y reloj
fijo. El control cambia una sola etiqueta por un término neutral de igual
longitud; las dos columnas plegada/exacta cambian coherentemente como un par.
Todos los términos y casos quedan en un manifiesto por corrida, aunque un
brazo no los active como etiquetas. Se registran hashes canónicos y de archivo;
el runner usa salidas nuevas y rechaza sobrescribirlas. No toca motor ni bases reales.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["BIORAG_DMN_SINTESIS_ACTIVA"] = "0"  # solo para crear seeds, sin edges de apertura
os.environ.setdefault("BIORAG_NEURONA", "0")
os.environ.setdefault("BIORAG_NO_LOG", "1")

from core.memory import consolidation
from core.memory_store import (
    SQLiteMemoryBioRAG,
    normalizar_sustantivos_clave,
    normalizar_sustantivos_clave_exacto,
    normalizar_sustantivos_clave_exactos_coherentes,
)

TARGET = "recuerdo_sintetico_objetivo"
MANUAL_NEIGHBORS = ("vecino_sintetico_historia", "vecino_sintetico_verificacion")
AUTO_CANDIDATE = "vecino_sintetico_candidato_dmn"
QUERY_ANCHOR = "xqzqueryanchor"  # ausente de todos los recuerdos y del grafo
FIXED_CLOCK = "1793059200.0"

# El manifiesto es la fuente íntegra de pistas. El tratamiento/control cambia
# solo `probe` por un neutral del mismo largo en la etiqueta activa del objetivo.
FAMILIES = {
    "cue_solo_etiqueta": {
        "probe": "thermistor", "neutral": "qzxcontrol",
        "other_labels": ["sensor", "reference"], "current_query": "reference",
        "target_content": "La primera lectura sigue vigente; la revisión posterior es compatible. silver lattice targetanchor.",
        "target_synonyms": "",
        "history_neighbor_content": "Nota sintética previa sin la pista objetivo.",
        "current_neighbor_content": "Fuente independiente para la revisión nueva.",
        "auto_candidate_content": "silver lattice candidateanchor.",
        "old_truth": "historia útil, cue ausente de texto, sinónimos y vecinos",
    },
    "cue_contenido_contradicho": {
        "probe": "openstate", "neutral": "qzxostate",
        "other_labels": ["valve", "closedstate"], "current_query": "closedstate",
        "target_content": "Registro previo openstate; corrección explícita: ese estado fue contradicho y la inspección confirma closedstate. silver lattice targetanchor.",
        "target_synonyms": "",
        "history_neighbor_content": "Nota sintética de contexto separada.",
        "current_neighbor_content": "Fuente independiente para la revisión.",
        "auto_candidate_content": "silver lattice candidateanchor.",
        "old_truth": "historia contradicha que permanece en contenido",
    },
    "cue_por_sinonimo": {
        "probe": "calibration", "neutral": "qzxneutralx",
        "other_labels": ["sensor", "precision"], "current_query": "precision",
        "target_content": "Registro sintético de una medición reproducible. silver lattice targetanchor.",
        "target_synonyms": "calibration",
        "history_neighbor_content": "Nota sintética previa no relacionada.",
        "current_neighbor_content": "Fuente sintética sin la pista de consulta.",
        "auto_candidate_content": "silver lattice candidateanchor.",
        "old_truth": "control de ruta léxica alternativa: cue también está en sinonimos",
    },
    "cue_por_vecino": {
        "probe": "archivecue", "neutral": "qzxcontrol",
        "other_labels": ["network", "evidence"], "current_query": "network",
        "target_content": "Registro sintético de contexto enlazado. silver lattice targetanchor.",
        "target_synonyms": "",
        "history_neighbor_content": "El registro vecino contiene archivecue y una nota histórica relacionada.",
        "current_neighbor_content": "Fuente independiente de revisión reciente.",
        "auto_candidate_content": "silver lattice candidateanchor.",
        "old_truth": "control de ruta asociativa: cue aparece solo en vecino manual enlazado",
    },
}

# Complete rows for the enumerated graph tables plus one node-association projection.
# This is intentionally a graph-structure snapshot, not a backup of every SQLite table.
GRAPH_SNAPSHOT_SCOPE = {
    "full_row_tables": [
        "sinapsis", "sinapsis_latentes", "sinapsis_cuarentena",
        "largo_plazo_dimensiones", "grupos_semanticos", "nodo_grupos_semanticos",
        "concept_hubs", "concept_hub_nodes", "concept_hub_bridges",
    ],
    "row_projections": ["largo_plazo(concepto, asociaciones)"],
    "complete_sqlite_database_snapshot": False,
}

GRAPH_QUERIES = {
    "sinapsis": "SELECT * FROM sinapsis ORDER BY origen,destino",
    "sinapsis_latentes": "SELECT * FROM sinapsis_latentes ORDER BY origen,destino",
    "sinapsis_cuarentena": "SELECT * FROM sinapsis_cuarentena ORDER BY origen,destino",
    "dimensiones_nodo": "SELECT * FROM largo_plazo_dimensiones ORDER BY concepto,dimension_id",
    "grupos_semanticos": "SELECT * FROM grupos_semanticos ORDER BY id",
    "grupos_nodo": "SELECT * FROM nodo_grupos_semanticos ORDER BY concepto,palabra,grupo_id",
    "concept_hubs": "SELECT * FROM concept_hubs ORDER BY hub_id",
    "concept_hub_nodes": "SELECT * FROM concept_hub_nodes ORDER BY hub_id,node_concepto,role",
    "concept_hub_bridges": "SELECT * FROM concept_hub_bridges ORDER BY hub_id,bridge_id",
    "espejo_asociaciones": "SELECT concepto,asociaciones FROM largo_plazo ORDER BY concepto",
}


def normalized_pair(terms: list[str]) -> tuple[str, str]:
    raw = ",".join(terms)
    exact = normalizar_sustantivos_clave_exacto(raw)
    folded = normalizar_sustantivos_clave(exact)
    coherent = normalizar_sustantivos_clave_exactos_coherentes(exact, folded) or ""
    return folded, coherent


def all_clue_manifest() -> dict:
    return {
        "replica": "H-E3-ETQ-01 paired controls",
        "audit_controls_commit": "e71d7bc0927f137a6a51bf5afb8d6261755061a3",
        "policy_selected": False,
        "arms": ["cue_activo", "neutral_largo_igual"],
        "query_anchor": QUERY_ANCHOR,
        "families": {
            name: {
                **row,
                "neutral_control_same_length": row["neutral"],
                "other_labels_held_fixed": row["other_labels"],
                "payload_cue_active": [*row["other_labels"], row["probe"]],
                "payload_matched_neutral": [*row["other_labels"], row["neutral"]],
                "synthetic_truth_assumption": row["old_truth"],
                "cue_occurrences_by_design": {
                    "target_content": row["probe"] in row["target_content"],
                    "target_synonyms": row["probe"] in row["target_synonyms"],
                    "history_neighbor_content": row["probe"] in row["history_neighbor_content"],
                    "current_neighbor_content": row["probe"] in row["current_neighbor_content"],
                    "auto_candidate_content": row["probe"] in row["auto_candidate_content"],
                },
            }
            for name, row in FAMILIES.items()
        },
        "preservation_note": "Every probe and neutral remains in this ledger in all arms; only active synthetic label payload varies.",
    }


def resolve_private_output_dir(requested: str | None) -> Path:
    private_root = (ROOT / ".private_evidence").resolve()
    if requested:
        candidate = Path(requested)
        out_dir = (candidate if candidate.is_absolute() else ROOT / candidate).resolve()
    else:
        run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = (private_root / f"e3_tag_replica_e71d7bc_20261102_corrected_{run_stamp}").resolve()
    if private_root not in out_dir.parents:
        raise ValueError("La evidencia completa debe permanecer bajo .private_evidence/")
    if out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing evidence directory: {out_dir}")
    return out_dir


def canonical_json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_private_artifacts(report: dict, out_dir: Path) -> dict:
    private_root = (ROOT / ".private_evidence").resolve()
    out_dir = out_dir.resolve()
    if private_root not in out_dir.parents:
        raise ValueError("La evidencia completa debe permanecer bajo .private_evidence/")
    if out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing evidence directory: {out_dir}")
    ledger = all_clue_manifest()
    ledger_file_bytes = json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    ledger_canonical_hash = hashlib.sha256(canonical_json_bytes(ledger)).hexdigest()
    ledger_file_hash = hashlib.sha256(ledger_file_bytes).hexdigest()
    report["manifest_hashes"] = {
        "canonical_json_utf8_sha256": ledger_canonical_hash,
        "file_bytes_sha256": ledger_file_hash,
    }
    report["evidence_revision"] = "corrected_harness_preserving_original"
    out_dir.mkdir(parents=True, exist_ok=False)
    ledger_path = out_dir / "all_synthetic_clues_manifest.json"
    report_path = out_dir / "stdio_cases_full.json"
    ledger_path.write_bytes(ledger_file_bytes)
    ledger_readback = ledger_path.read_bytes()
    if ledger_readback != ledger_file_bytes or hashlib.sha256(ledger_readback).hexdigest() != ledger_file_hash:
        raise RuntimeError("Manifest byte verification failed after write")
    canonical_readback_hash = hashlib.sha256(canonical_json_bytes(json.loads(ledger_readback))).hexdigest()
    if canonical_readback_hash != ledger_canonical_hash:
        raise RuntimeError("Manifest canonical-JSON verification failed after write")
    report_bytes = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    report_expected_hash = hashlib.sha256(report_bytes).hexdigest()
    report_path.write_bytes(report_bytes)
    report_readback = report_path.read_bytes()
    report_file_hash = hashlib.sha256(report_readback).hexdigest()
    if report_readback != report_bytes or report_file_hash != report_expected_hash:
        raise RuntimeError("Case-report byte verification failed after write")
    manifest = {
        "audit_controls_commit": ledger["audit_controls_commit"],
        "all_synthetic_clues_manifest.json": ledger_file_hash,
        "all_synthetic_clues_manifest_canonical_json_sha256": ledger_canonical_hash,
        "stdio_cases_full.json": report_file_hash,
        "case_count": len(report["arms"]),
        "source_databases_opened": 0,
    }
    sums_path = out_dir / "SHA256SUMS.json"
    sums_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    sums_path.write_bytes(sums_bytes)
    if sums_path.read_bytes() != sums_bytes:
        raise RuntimeError("Checksum-manifest byte verification failed after write")
    for path, expected_hash in ((ledger_path, ledger_file_hash), (report_path, report_file_hash)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise RuntimeError(f"Evidence file checksum verification failed: {path.name}")
    return {
        "private_artifact_dir": str(out_dir),
        "private_manifest_file_sha256": ledger_file_hash,
        "private_manifest_canonical_json_sha256": ledger_canonical_hash,
    }


def seed_db(path: Path, family: dict) -> None:
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        category = memory._resolver_categoria_id("General")
        nodes = (
            (TARGET, family["target_content"], family["target_synonyms"], family["other_labels"][0] + "," + family["other_labels"][1] + ",seedcue"),
            (MANUAL_NEIGHBORS[0], family["history_neighbor_content"], "", "archive,history"),
            (MANUAL_NEIGHBORS[1], family["current_neighbor_content"], "", "review,source"),
            (AUTO_CANDIDATE, family["auto_candidate_content"], "", "candidate,context"),
        )
        for concept, content, synonyms, labels_raw in nodes:
            labels = labels_raw.split(",")
            folded, exact = normalized_pair(labels)
            consolidation.fusionar_en_largo_plazo(
                memory, concept, content, synonyms, category, 0.0, folded, exact
            )
        memory.conn.commit()
        for neighbor in MANUAL_NEIGHBORS:
            memory.establecer_asociacion(TARGET, neighbor)
        memory.conn.commit()
        memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        memory.cerrar_sistema()


def clone_db(source: Path, destination: Path) -> None:
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def readonly_rows(path: Path, query: str) -> list:
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=10)
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def full_graph_snapshot(path: Path) -> dict:
    """Exact rows for GRAPH_SNAPSHOT_SCOPE; not a full SQLite database snapshot."""
    rows_by_table = {}
    query_errors = {}
    for name, query in GRAPH_QUERIES.items():
        try:
            rows_by_table[name] = readonly_rows(path, query)
        except sqlite3.Error as exc:
            rows_by_table[name] = []
            query_errors[name] = f"{type(exc).__name__}: {exc}"
    canonical = json.dumps(
        {"rows": rows_by_table, "query_errors": query_errors},
        ensure_ascii=False, sort_keys=True, default=repr, separators=(",", ":")
    )
    return {
        "rows": rows_by_table,
        "query_errors": query_errors,
        "sha256_exact_rows": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def target_row(path: Path) -> dict:
    rows = readonly_rows(
        path,
        "SELECT concepto,contenido,sinonimos,sustantivos_clave,sustantivos_clave_exactos,asociaciones "
        "FROM largo_plazo WHERE concepto='recuerdo_sintetico_objetivo'",
    )
    return {"row": rows[0] if rows else None}


def fts_channel_hits(path: Path, concept: str, term: str) -> dict[str, bool]:
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=10)
    try:
        rowid = con.execute("SELECT rowid FROM largo_plazo WHERE concepto=?", (concept,)).fetchone()
        if not rowid:
            return {}
        result = {}
        for col in ("concepto", "contenido", "sinonimos", "sustantivos_clave"):
            match = con.execute(
                "SELECT 1 FROM largo_plazo_fts WHERE rowid=? AND largo_plazo_fts MATCH ? LIMIT 1",
                (rowid[0], f'{col} : "{term}"'),
            ).fetchone()
            result[col] = bool(match)
        return result
    finally:
        con.close()


def parse_tool_result(result) -> dict:
    raw = "\n".join(getattr(block, "text", "") for block in (getattr(result, "content", None) or []))
    for match in reversed(list(re.finditer(r"(?m)^\{", raw))):
        try:
            data = json.loads(raw[match.start():])
            if isinstance(data, dict):
                if getattr(result, "isError", False):
                    data["_mcp_is_error"] = True
                return data
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"MCP tool result no JSON: {raw[:300]}")


def recall_error_fields(result: dict) -> dict:
    raw_status = result.get("status")
    mcp_is_error = bool(result.get("_mcp_is_error"))
    status = "mcp_error" if mcp_is_error and raw_status is None else "ok" if raw_status is None else raw_status
    return {
        "response_status": status,
        "response_status_raw": raw_status,
        "mcp_is_error": mcp_is_error,
        "mcp_error_detail": (result.get("error") or result.get("message")) if mcp_is_error else None,
    }


def recall_result_ok(output: dict) -> bool:
    return not output.get("mcp_is_error") and output.get("response_status") == "ok"


class StdioSession:
    def __init__(self, db_path: Path, temp_root: Path):
        self.db_path = db_path.resolve()
        self.temp_root = temp_root.resolve()

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        try:
            self.db_path.relative_to(self.temp_root)
        except ValueError as exc:
            raise RuntimeError("Guardrail: MCP DB outside temporary root") from exc
        state_key = hashlib.sha256(str(self.db_path).encode()).hexdigest()[:16]
        state_path = self.temp_root / "dmn_state" / f"{state_key}.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({
            "BIORAG_PATH": str(self.db_path),
            "BIORAG_QA_TEMP_ROOT": str(self.temp_root),
            "BIORAG_DMN_ESTADO_PATH": str(state_path),
            "BIORAG_DMN_SINTESIS_ACTIVA": "1",
            "BIORAG_DMN_SINTESIS_MAX": "8",
            "BIORAG_DMN_SINTESIS_PESO": "0.30",
            "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
            "BIORAG_MCP_AUTO_PARAFRASIS": "0",
            "BIORAG_MCP_AUTO_DIMS": "0",
            "BIORAG_NEURONA": "0",
            "BIORAG_NO_LOG": "1",
            "BIORAG_QA_RELOJ_FIJO": FIXED_CLOCK,
        })
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "qa_stdio_server_intuicion.py")],
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
        return parse_tool_result(await self._session.call_tool(name, arguments=args))


def arm_payload(family: dict, arm: str) -> list[str]:
    variable = family["probe"] if arm == "cue_activo" else family["neutral"]
    labels = [*family["other_labels"], variable]
    if len(set(labels)) != len(labels) or len(labels) > 10:
        raise AssertionError("Etiqueta duplicate o límite de payload excedido")
    if len(family["probe"]) != len(family["neutral"]):
        raise AssertionError("Control neutral no tiene igual longitud")
    return labels


async def run_arm(seed: Path, db_path: Path, temp_root: Path,
                  family_name: str, family: dict, arm: str,
                  mode: str) -> dict:
    clone_db(seed, db_path)
    snapshots = {"before_stdio": full_graph_snapshot(db_path)}
    rows = {"before_stdio": target_row(db_path)}
    labels_input = arm_payload(family, arm)
    folded_expected, exact_expected = normalized_pair(labels_input)
    query_plan = {
        "sequence_old_then_current": ["old", "current"],
        "sequence_current_then_old": ["current", "old"],
        "single_old": ["old"],
        "single_current": ["current"],
    }[mode]
    outputs = []
    async with StdioSession(db_path, temp_root) as mcp:
        snapshots["after_initialize"] = full_graph_snapshot(db_path)
        rows["after_initialize"] = target_row(db_path)
        read_before = await mcp.call("sustantivos", {"concepto": TARGET})
        snapshots["after_first_tool_call"] = full_graph_snapshot(db_path)
        rows["after_first_tool_call"] = target_row(db_path)
        write = await mcp.call("actualizar", {
            "concepto": TARGET,
            "sustantivos_clave": ",".join(labels_input),
        })
        read_after = await mcp.call("sustantivos", {"concepto": TARGET})
        snapshots["after_write"] = full_graph_snapshot(db_path)
        rows["after_write"] = target_row(db_path)
        stored_target = rows["after_write"].get("row")
        stored_folded_actual = stored_target[3] if stored_target and len(stored_target) > 3 else None
        stored_exact_actual = stored_target[4] if stored_target and len(stored_target) > 4 else None
        for role in query_plan:
            term = family["probe"] if role == "old" else family["current_query"]
            result = await mcp.call("recordar", {
                "query": term,
                "sustantivos_clave": f"{term},{QUERY_ANCHOR}",
                "completo": True,
                "asociados": True,
                "asociaciones_max": 0,
                "context_window": 1,
                "limite": 10,
                "usar_inferencia": False,
                "forzar_rafaga": False,
            })
            primary = result.get("resultados", [])
            expanded = result.get("contexto_expandido", [])
            target_primary = next((x for x in primary if x.get("concepto") == TARGET), None)
            target_context = next((x for x in expanded if x.get("concepto") == TARGET), None)
            outputs.append({
                "role": role,
                "query_term": term,
                **recall_error_fields(result),
                "total": result.get("total"),
                "target_primary_found": target_primary is not None,
                "target_rank": next((i + 1 for i, x in enumerate(primary) if x.get("concepto") == TARGET), None),
                "target_score": target_primary.get("score_hibrido") if target_primary else None,
                "target_context_found": target_context is not None,
                "primary_concepts": [x.get("concepto") for x in primary],
                "context_concepts": [x.get("concepto") for x in expanded],
                "target_associated_neighbors": sorted(
                    x.get("concepto") for x in (target_primary or {}).get("asociaciones_enriquecidas", [])
                ),
            })
            snapshots[f"after_{role}_{len(outputs)}"] = full_graph_snapshot(db_path)
            rows[f"after_{role}_{len(outputs)}"] = target_row(db_path)

    graph_keys = list(snapshots)
    graph_deltas = {}
    previous = snapshots["before_stdio"]["rows"]
    for key in graph_keys[1:]:
        current = snapshots[key]["rows"]
        graph_deltas[key] = {
            "added": {table: [row for row in current[table] if row not in previous[table]]
                      for table in GRAPH_QUERIES},
            "removed": {table: [row for row in previous[table] if row not in current[table]]
                        for table in GRAPH_QUERIES},
        }
        previous = current

    channel_hits = {
        role: fts_channel_hits(db_path, TARGET,
                               family["probe"] if role == "old" else family["current_query"])
        for role in dict.fromkeys(query_plan)
    }
    manual_seed_rows = [row for row in snapshots["before_stdio"]["rows"]["sinapsis"] if len(row) > 3 and row[3] == "manual"]
    manual_edges_preserved_by_stage = {
        stage: all(row in snap["rows"]["sinapsis"] for row in manual_seed_rows)
        for stage, snap in snapshots.items()
    }
    tool_results = [read_before, write, read_after]
    snapshot_queries_ok = all(not snap["query_errors"] for snap in snapshots.values())
    arm_status = "ok" if snapshot_queries_ok \
        and all(r.get("status") == "ok" and not r.get("_mcp_is_error") for r in tool_results) \
        and all(recall_result_ok(q) for q in outputs) else "inconclusive"
    return {
        "arm_status": arm_status,
        "family": family_name,
        "arm": arm,
        "mode": mode,
        "query_order": query_plan,
        "write_route": "actualizar",
        "raw_payload": ",".join(labels_input),
        "payload_term_count": len(labels_input),
        "input_unique_count": len(set(labels_input)),
        "input_max_length": max(map(len, labels_input)),
        "payload_char_count": len(",".join(labels_input)),
        "normalized_expected_folded": folded_expected,
        "normalized_expected_exact": exact_expected,
        "stored_folded_actual_from_sql_column": stored_folded_actual,
        "stored_exact_actual_from_sql_column": stored_exact_actual,
        "stored_folded_matches_expected": stored_folded_actual == folded_expected,
        "stored_exact_matches_expected": stored_exact_actual == exact_expected,
        "mcp_write_result": write,
        "mcp_read_before": read_before,
        "mcp_read_after": read_after,
        "stored_pair_matches_expected": (stored_folded_actual == folded_expected and stored_exact_actual == exact_expected),
        "initial_manual_synapse_rows": manual_seed_rows,
        "manual_synapse_rows_preserved_by_stage": manual_edges_preserved_by_stage,
        "fts_channels": channel_hits,
        "queries": outputs,
        "graph_snapshots_exact_rows": snapshots,
        "target_row_snapshots": rows,
        "graph_deltas_exact_rows": graph_deltas,
        "clock": FIXED_CLOCK,
        "dmn_state_path_key": hashlib.sha256(str(db_path.resolve()).encode()).hexdigest()[:16],
    }


def summarize_arms(arms: list[dict]) -> dict:
    by_key = {(a["family"], a["mode"], a["arm"]): a for a in arms}
    modes = ("sequence_old_then_current", "sequence_current_then_old", "single_old", "single_current")
    pairs = []
    for family_name in FAMILIES:
        for mode in modes:
            treatment = by_key.get((family_name, mode, "cue_activo"))
            control = by_key.get((family_name, mode, "neutral_largo_igual"))
            if not treatment or not control or treatment.get("arm_status") != "ok" or control.get("arm_status") != "ok":
                pairs.append({
                    "family": family_name,
                    "mode": mode,
                    "status": "inconclusive",
                    "cue_arm_status": treatment.get("arm_status") if treatment else "missing",
                    "neutral_arm_status": control.get("arm_status") if control else "missing",
                    "errors": [x.get("error") for x in (treatment, control) if x and x.get("error")],
                })
                continue
            tq = {q["role"]: q for q in treatment["queries"]}
            cq = {q["role"]: q for q in control["queries"]}
            graph_compare = {}
            for stage in treatment["graph_snapshots_exact_rows"]:
                if stage in control["graph_snapshots_exact_rows"]:
                    graph_compare[stage] = (
                        treatment["graph_snapshots_exact_rows"][stage]["rows"]
                        == control["graph_snapshots_exact_rows"][stage]["rows"]
                    )
            pairs.append({
                "family": family_name,
                "mode": mode,
                "status": "ok",
                "graph_exact_equal_by_stage": graph_compare,
                "stored_labels_valid_both": treatment["stored_pair_matches_expected"] and control["stored_pair_matches_expected"],
                "old_query": {
                    "cue_arm": {k: tq["old"].get(k) for k in ("target_primary_found", "target_rank", "target_score", "target_context_found") if "old" in tq},
                    "neutral_arm": {k: cq["old"].get(k) for k in ("target_primary_found", "target_rank", "target_score", "target_context_found") if "old" in cq},
                },
                "current_query": {
                    "cue_arm": {k: tq["current"].get(k) for k in ("target_primary_found", "target_rank", "target_score", "target_context_found") if "current" in tq},
                    "neutral_arm": {k: cq["current"].get(k) for k in ("target_primary_found", "target_rank", "target_score", "target_context_found") if "current" in cq},
                },
            })
    # Sequence order invariance is checked by query role, not by position.
    order_checks = []
    for family_name in FAMILIES:
        for arm_name in ("cue_activo", "neutral_largo_igual"):
            first = by_key.get((family_name, "sequence_old_then_current", arm_name))
            second = by_key.get((family_name, "sequence_current_then_old", arm_name))
            if not first or not second or first.get("arm_status") != "ok" or second.get("arm_status") != "ok":
                order_checks.append({"family": family_name, "arm": arm_name, "status": "inconclusive"})
                continue
            role_signature = lambda arm: {
                q["role"]: (q["target_primary_found"], q["target_rank"], q["target_score"], q["target_context_found"])
                for q in arm["queries"]
            }
            first_final = list(first["graph_snapshots_exact_rows"].values())[-1]["rows"]
            second_final = list(second["graph_snapshots_exact_rows"].values())[-1]["rows"]
            order_checks.append({
                "family": family_name,
                "arm": arm_name,
                "status": "ok",
                "same_per_role": role_signature(first) == role_signature(second),
                "old_then_current": role_signature(first),
                "current_then_old": role_signature(second),
                "graph_final_exact_equal": first_final == second_final,
            })
    return {"pairs": pairs, "query_order_checks": order_checks}


async def execute_replica() -> dict:
    manifest = all_clue_manifest()
    with tempfile.TemporaryDirectory(prefix="e3_etq_controls_") as tmp:
        temp_root = Path(tmp)
        arms = []
        for family_name, family in FAMILIES.items():
            probe = family["probe"]
            neutral = family["neutral"]
            if len(probe) != len(neutral):
                raise AssertionError(f"Matched neutral has wrong length in {family_name}")
            seed = temp_root / f"seed_{family_name}.db"
            try:
                seed_db(seed, family)
                source_hash = hashlib.sha256(seed.read_bytes()).hexdigest()
            except Exception as exc:
                for arm in ("cue_activo", "neutral_largo_igual"):
                    for mode in ("sequence_old_then_current", "sequence_current_then_old", "single_old", "single_current"):
                        arms.append({
                            "arm_status": "inconclusive",
                            "family": family_name,
                            "arm": arm,
                            "mode": mode,
                            "stage": "seed_creation",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        })
                continue
            for arm in ("cue_activo", "neutral_largo_igual"):
                for mode in ("sequence_old_then_current", "sequence_current_then_old", "single_old", "single_current"):
                    db_path = temp_root / f"{family_name}_{arm}_{mode}.db"
                    try:
                        arm_result = await run_arm(seed, db_path, temp_root, family_name, family, arm, mode)
                        arm_result["seed_database_sha256"] = source_hash
                        arms.append(arm_result)
                    except Exception as exc:
                        arms.append({
                            "arm_status": "inconclusive",
                            "family": family_name,
                            "arm": arm,
                            "mode": mode,
                            "write_route": "actualizar",
                            "seed_database_sha256": source_hash,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        })
        pair_summary = summarize_arms(arms)
        return {
            "audit_controls_commit": "e71d7bc0927f137a6a51bf5afb8d6261755061a3",
            "hypothesis_id": "H-E3-ETQ-01",
            "synthetic_only": True,
            "user_database_opened": False,
            "source_database_copied": False,
            "memory_merges": 0,
            "backfill": False,
            "engine_patch": False,
            "policy_selected": False,
            "e4_advanced": False,
            "source_seed_count": len(FAMILIES),
            "graph_snapshot_scope": GRAPH_SNAPSHOT_SCOPE,
            "arms": arms,
            "pair_summary": pair_summary,
            "clue_manifest": manifest,
        }


def public_summary(report: dict, private_paths: dict) -> dict:
    pairs = report["pair_summary"]["pairs"]
    order = report["pair_summary"]["query_order_checks"]
    all_queries = [q for arm in report["arms"] for q in arm.get("queries", [])]
    historical_queries = [q for q in all_queries if q.get("role") == "old"]
    current_queries = [q for q in all_queries if q.get("role") == "current"]
    historical_modes = {
        arm.get("mode") for arm in report["arms"]
        if any(q.get("role") == "old" for q in arm.get("queries", []))
    }
    valid_pairs = [row for row in pairs if row.get("status") == "ok"]
    valid_order = [row for row in order if row.get("status") == "ok"]
    return {
        "hypothesis_id": report["hypothesis_id"],
        "audit_controls_commit": report["audit_controls_commit"],
        "synthetic_families": len(FAMILIES),
        "paired_arms_per_family": 2,
        "total_stdio_sessions": len(report["arms"]),
        "successful_stdio_sessions": sum(a.get("arm_status") == "ok" for a in report["arms"]),
        "inconclusive_or_error_sessions": sum(a.get("arm_status") != "ok" for a in report["arms"]),
        "graph_snapshot_query_errors_total": sum(
            len(snap.get("query_errors", {}))
            for a in report["arms"]
            for snap in a.get("graph_snapshots_exact_rows", {}).values()
        ),
        "all_graph_snapshot_queries_succeeded": all(
            not snap.get("query_errors", {})
            for a in report["arms"]
            for snap in a.get("graph_snapshots_exact_rows", {}).values()
        ) if report["arms"] else None,
        "query_modalities_total": 4,
        "historical_query_modes_actually_executed": len(historical_modes),
        "historical_query_calls": len(historical_queries),
        "current_query_calls": len(current_queries),
        "recordar_calls_total": len(all_queries),
        "recordar_mcp_error_flags": sum(bool(q.get("mcp_is_error")) for q in all_queries),
        "recordar_status_error_responses": sum(q.get("response_status_raw") == "error" for q in all_queries),
        "label_or_neutral_differential_pairs": len(pairs),
        "matched_neutral_lengths": all(
            len(row["probe"]) == len(row["neutral"]) for row in FAMILIES.values()
        ),
        "payload_shape_equal_within_pair": all(row.get("stored_labels_valid_both", False) for row in valid_pairs) if valid_pairs else None,
        "paired_graph_exact_equal_at_each_stage": all(
            all(item["graph_exact_equal_by_stage"].values()) for item in valid_pairs
        ) if valid_pairs else None,
        "query_order_same_per_role_all_arms": all(x.get("same_per_role", False) for x in valid_order) if valid_order else None,
        "dmn_edges_added_after_first_tool_call_total": sum(
            len(a.get("graph_deltas_exact_rows", {}).get("after_first_tool_call", {}).get("added", {}).get("sinapsis", []))
            for a in report["arms"]
        ),
        "manual_edges_preserved_all_successful_arms": all(
            all(a.get("manual_synapse_rows_preserved_by_stage", {}).values())
            for a in report["arms"] if a.get("arm_status") == "ok"
        ) if any(a.get("arm_status") == "ok" for a in report["arms"]) else None,
        "initialize_db_open_inferred_from_graph_nonchange": False,
        "graph_compare_method": "exact full rows from listed graph tables plus the listed association projection, not counts or rounded weights",
        "graph_snapshot_scope": report["graph_snapshot_scope"],
        "manual_edges_preserved_and_graph_compared_by_full_rows": True,
        "all_probe_and_neutral_terms_preserved_in_manifest": True,
        "private_outputs": private_paths,
        "decision": "hypothesis replication only; neither replacement nor accumulation selected",
        "scope": "E3 remains open; no engine diff; no E4",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir",
        help="ruta nueva bajo .private_evidence/; se rechaza si ya existe. Si se omite, se usa un directorio UTC único.",
    )
    args = parser.parse_args()
    output_dir = resolve_private_output_dir(args.evidence_dir)
    # Keep tools/logs out of stdout so it contains only the sanitized aggregate.
    with contextlib.redirect_stdout(io.StringIO()):
        report = asyncio.run(execute_replica())
    private_paths = write_private_artifacts(report, output_dir)
    print(json.dumps(public_summary(report, private_paths), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
