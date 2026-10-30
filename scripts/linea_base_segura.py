#!/usr/bin/env python3
"""Línea base segura N/G/R. No se ejecuta sin autorización y manifiesto de congelación.

N: búsqueda normal; G1/G2: contexto BFS activo; R: ráfaga forzada en una copia
que se verifica completamente activa para que no mida despertar. W queda fuera.

La preparación crea únicamente una fixture bajo BIORAG_QA_TEMP_ROOT mediante MCP
stdio real y genera una revisión del grafo. La medición es una fase aparte: exige
un manifiesto de aprobación humana con hashes exactos de gold y fixture.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict, deque
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stopwords import STOPWORDS
from scripts.evaluar_qa_intuicion_asociaciones_e1 import (
    GOLD, MCPProcess, bridge_payload, context_concepts, copy_sqlite,
    main_result_concepts, metrics_by_channel, percentile, readonly_snapshot,
    response_concepts, serialize_report, snapshot_sha256,
)

NAME_PATTERN = re.compile(r"[a-zA-Záéíóúñ]{4,}")
ARMS = {
    "N0": {"deep": False, "asociados": False, "context_window": 0, "forzar_rafaga": False},
    "N1": {"deep": False, "asociados": True, "context_window": 0, "forzar_rafaga": False},
    "G1": {"deep": False, "asociados": True, "context_window": 1, "forzar_rafaga": False},
    "G2": {"deep": False, "asociados": True, "context_window": 2, "forzar_rafaga": False},
    "R":  {"deep": False, "asociados": True, "context_window": 0, "forzar_rafaga": True},
}
BASE_GOLD_SHA256 = "d91e9ee1437f2695b2278ff06cf2ad202e5d124c500c0f8dc22a6865e0e2497e"
READ_WRITES = {"log_busquedas", "nodo_accesos_historial"}
BURST_WRITES = READ_WRITES | {"sinapsis", "sdm_dirty"}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_temp_root(root: Path) -> Path:
    root = root.resolve()
    configured = os.environ.get("BIORAG_QA_TEMP_ROOT")
    if not configured or Path(configured).resolve() != root:
        raise RuntimeError("--temp-root debe coincidir con BIORAG_QA_TEMP_ROOT explícito")
    if root == ROOT or root in ROOT.parents or ROOT in root.parents:
        raise RuntimeError("BIORAG_QA_TEMP_ROOT debe estar fuera del repositorio y sus directorios padre")
    return root


def _inside(path: Path, root: Path, label: str) -> Path:
    path, root = path.resolve(), _safe_temp_root(root)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Guardrail: {label} fuera de BIORAG_QA_TEMP_ROOT: {path}") from exc
    return path


def mcp_concept_key(concept: str) -> str:
    """Clave preliminar exactamente como write.py: lower + espacios→guion bajo."""
    return concept.lower().replace(" ", "_")


def _name_words(concept: str) -> list[str]:
    # Replica la pasada co_nombre sin ejecutar ni modificar el motor.
    value = concept.lower().replace("_", " ").replace("-", " ")
    return [word for word in NAME_PATTERN.findall(value) if word not in STOPWORDS]


def audit_names(episodes: list[dict]) -> dict:
    """Detecta colisiones de clave y riesgos co_nombre; no predice aristas reales."""
    concepts = [node["concepto"] for ep in episodes for node in ep["nodos"]]
    keyed: dict[str, list[str]] = defaultdict(list)
    for concept in concepts:
        keyed[mcp_concept_key(concept)].append(concept)
    collisions = {key: values for key, values in keyed.items() if len(values) > 1}
    risks = []
    for i, left in enumerate(concepts):
        lw = _name_words(left)
        if len(lw) < 2:
            continue
        for right in concepts[i + 1:]:
            rw = _name_words(right)
            if not rw:
                continue
            # core/sinapsis.py evalúa cada dirección. Es un marcador de riesgo
            # estático, no una emulación completa de LIKE/WORD_COMPLETA/orden/fanout.
            ratios = [
                sum(1 for word in source if word in target.lower()) / len(source)
                for source, target in ((lw, right), (rw, left)) if len(source) >= 2
            ]
            if ratios and max(ratios) >= 0.30:
                risks.append({
                    "a": left, "b": right,
                    "palabras_a": lw, "palabras_b": rw,
                    "solapamiento_max_aproximado": round(max(ratios), 4),
                    "riesgo_co_nombre": True,
                })
    return {
        "nombres": [{"original": value, "clave_mcp_preliminar": mcp_concept_key(value),
                     "palabras_co_nombre": _name_words(value)} for value in concepts],
        "colisiones_clave": collisions,
        "pares_riesgo_co_nombre": risks,
        "nota": "Riesgo léxico estático; la fuente de verdad es el grafo observado tras MCP.",
    }


def _table_columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")')]


def inspect_fixture(db_path: Path, temp_root: Path) -> dict:
    """Lee solo una DB bajo el temporal; devuelve grafo, espejo, estados e integridad."""
    db_path = _inside(db_path, temp_root, "BIORAG_PATH")
    uri = "file:" + quote(str(db_path), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"largo_plazo", "sinapsis"} <= tables:
            raise ValueError("La fixture requiere largo_plazo y sinapsis")
        lp_cols = set(_table_columns(con, "largo_plazo"))
        lp_select = [c for c in ("concepto", "estado", "peso_sinaptico", "ultimo_acceso", "asociaciones") if c in lp_cols]
        nodes = {}
        for row in con.execute("SELECT " + ",".join('"'+c+'"' for c in lp_select) + " FROM largo_plazo"):
            item = dict(zip(lp_select, row))
            nodes[item["concepto"]] = item
        syn_cols = set(_table_columns(con, "sinapsis"))
        direct_cols = [c for c in ("origen", "destino", "peso", "tipo", "creado_en", "ultimo_uso") if c in syn_cols]
        direct = [dict(zip(direct_cols, row)) for row in con.execute(
            "SELECT " + ",".join('"'+c+'"' for c in direct_cols) + " FROM sinapsis ORDER BY origen,destino")]
        latent = []
        if "sinapsis_latentes" in tables:
            latent_cols = _table_columns(con, "sinapsis_latentes")
            latent = [dict(zip(latent_cols, row)) for row in con.execute(
                'SELECT * FROM sinapsis_latentes ORDER BY origen,destino')]
        canonical = {concept: set() for concept in nodes}
        adjacency = {concept: set() for concept, row in nodes.items() if row.get("estado") == "activo"}
        for edge in direct:
            a, b = edge["origen"], edge["destino"]
            if a in canonical:
                canonical[a].add(b)
            if b in canonical:
                canonical[b].add(a)
            if a in adjacency and b in adjacency:
                adjacency[a].add(b)
                adjacency[b].add(a)
        mirror_diff = []
        for concept, row in nodes.items():
            raw = row.get("asociaciones") or ""
            mirror = {name.strip() for name in raw.split(",") if name.strip()}
            canonical_neighbors = canonical.get(concept, set())
            if mirror != canonical_neighbors:
                mirror_diff.append({"concepto": concept,
                                    "solo_en_espejo": sorted(mirror - canonical_neighbors),
                                    "solo_en_sinapsis": sorted(canonical_neighbors - mirror)})
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"Fixture no íntegra: {integrity}")
        return {
            "integridad": integrity,
            "nodos": nodes,
            "aristas_directas": direct,
            "sinapsis_latentes": latent,
            "adjacency_activos": adjacency,
            "divergencias_espejo": mirror_diff,
            "conteos": {"nodos": len(nodes), "nodos_activos": len(adjacency),
                        "nodos_dormidos": sum(x.get("estado") == "dormido" for x in nodes.values()),
                        "aristas_directas_dirigidas": len(direct), "sinapsis_latentes": len(latent)},
            "tablas_sha256": readonly_snapshot(db_path),
            "sha256_fixture_logica": snapshot_sha256(db_path),
        }
    finally:
        con.close()


def _shortest_stats(adjacency: dict[str, set[str]], start: str, goal: str) -> tuple[int | None, int]:
    dist, ways = {start: 0}, {start: 1}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in adjacency.get(node, set()):
            nd = dist[node] + 1
            if nxt not in dist:
                dist[nxt], ways[nxt] = nd, ways[node]
                queue.append(nxt)
            elif dist[nxt] == nd:
                ways[nxt] += ways[node]
    return dist.get(goal), ways.get(goal, 0)


def audit_fixture_gold(episodes: list[dict], graph: dict, names: dict | None = None) -> dict:
    """Reporta rutas reales; atajos bloquean congelación, sin borrar ninguna arista."""
    node_ids = set(graph["nodos"])
    active = set(graph["adjacency_activos"])
    expected = {node["concepto"] for ep in episodes for node in ep["nodos"]}
    missing = sorted(expected - node_ids)
    actual_pairs = {frozenset((edge["origen"], edge["destino"])) for edge in graph["aristas_directas"]}
    expected_pairs = {frozenset((a, b)) for ep in episodes for a, b in ep.get("aristas_gold", [])}
    missing_edges = sorted([sorted(pair) for pair in expected_pairs - actual_pairs])
    route_rows = []
    for ep in episodes:
        route = ep.get("ruta_2_saltos")
        if not route:
            continue
        a, mid, goal = route["objetivo"], route["intermedio"], route["pista"]
        distance, count = _shortest_stats(graph["adjacency_activos"], a, goal)
        nodes_active = all(x in active for x in (a, mid, goal))
        declared_edges_present = mid in graph["adjacency_activos"].get(a, set()) and goal in graph["adjacency_activos"].get(mid, set())
        route_rows.append({"episode_id": ep["episode_id"], "ruta_declarada": [a, mid, goal],
                           "nodos_activos": nodes_active,
                           "aristas_ruta_declarada_presentes": declared_edges_present,
                           "distancia_minima_activa": distance, "caminos_minimos_activos": count,
                           "exactamente_dos_saltos_unico": distance == 2 and count == 1 and nodes_active and declared_edges_present})
    name_report = names or {}
    blockers = []
    if missing:
        blockers.append("nodos_gold_ausentes")
    if missing_edges:
        blockers.append("aristas_gold_explicitas_ausentes")
    if name_report.get("colisiones_clave"):
        blockers.append("colision_clave_mcp")
    if any(not row["exactamente_dos_saltos_unico"] for row in route_rows):
        blockers.append("ruta_gold_2_saltos_no_es_unica")
    return {
        "gold_nodes_missing": missing,
        "gold_explicit_edges_missing": missing_edges,
        "rutas_2_saltos": route_rows,
        "pares_riesgo_co_nombre": name_report.get("pares_riesgo_co_nombre", []),
        "divergencias_espejo": graph["divergencias_espejo"],
        "conteos_grafo": graph["conteos"],
        "bloqueos_congelacion": blockers,
        "congelacion_estructural_permitida": not blockers,
        "nota": "No se borra/ignora arista por tipo. Revisar o versionar gold antes de cualquier búsqueda de medición.",
    }


def write_gold_revision(source: Path, destination: Path, revised: list[dict], adjustments: list[dict]) -> dict:
    """Escribe nueva versión sin sobrescribir gold; exige motivo por episodio cambiado."""
    source, destination = source.resolve(), destination.resolve()
    if source == destination or destination.exists():
        raise ValueError("La revisión debe escribirse en un archivo nuevo, sin sobrescribir gold")
    original = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    orig_map = {row["episode_id"]: row for row in original}
    new_map = {row["episode_id"]: row for row in revised}
    if set(orig_map) != set(new_map):
        raise ValueError("Una revisión de gold debe conservar el conjunto de episode_id")
    changed = {key for key in orig_map if _canonical(orig_map[key]) != _canonical(new_map[key])}
    reasons = {}
    for item in adjustments:
        eid = item.get("episode_id")
        reason = (item.get("reason") or "").strip()
        if not eid or not reason or eid in reasons:
            raise ValueError("Cada ajuste requiere episode_id único y reason no vacío")
        reasons[eid] = reason
    if changed != set(reasons):
        raise ValueError(f"Ledger de ajustes no coincide con episodios cambiados: changed={sorted(changed)}, ledger={sorted(reasons)}")
    if not changed:
        raise ValueError("No hay cambios para versionar")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sidecar = destination.with_suffix(destination.suffix + ".revision.json")
    if sidecar.exists():
        raise ValueError(f"El ledger ya existe: {sidecar}")
    body = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in revised).encode("utf-8")
    destination.write_bytes(body)
    manifest = {
        "schema": "gold_revision_v1",
        "source_file": str(source), "source_sha256": file_sha256(source),
        "revised_file": str(destination), "revised_sha256": hashlib.sha256(body).hexdigest(),
        "changed_episodes": [{"episode_id": eid, "reason": reasons[eid],
                               "before": orig_map[eid].get("ruta_2_saltos"),
                               "after": new_map[eid].get("ruta_2_saltos")}
                              for eid in sorted(changed)],
        "closed_before_search": False,
    }
    sidecar.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def close_gold_revision(revision_manifest_path: Path, approved_by: str, graph_review_sha256: str) -> dict:
    """Registra que una revisión se aprobó/cerró antes de medir; no altera el ledger original."""
    revision_manifest_path = revision_manifest_path.resolve()
    revision = json.loads(revision_manifest_path.read_text(encoding="utf-8"))
    revised_file = Path(revision["revised_file"])
    if file_sha256(revised_file) != revision["revised_sha256"]:
        raise ValueError("El gold versionado no coincide con su hash del ledger")
    if not approved_by.strip() or not graph_review_sha256.strip():
        raise ValueError("El cierre requiere revisor y hash de revisión estructural")
    closed = {
        "schema": "gold_revision_closure_v1",
        "revision_manifest_sha256": file_sha256(revision_manifest_path),
        "gold_sha256": revision["revised_sha256"],
        "graph_review_sha256": graph_review_sha256,
        "closed_before_search": True,
        "approved_by": approved_by,
        "changed_episode_ids": [row["episode_id"] for row in revision["changed_episodes"]],
    }
    output = revision_manifest_path.with_suffix(".closed.json")
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(closed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return closed


def audit_repeatability(first_path: Path, second_path: Path, temp_root: Path) -> dict:
    """Compara dos construcciones temporales sin elegir la que favorezca búsquedas."""
    first = inspect_fixture(first_path, temp_root)
    second = inspect_fixture(second_path, temp_root)
    fields = ("nodos", "aristas_directas", "sinapsis_latentes", "divergencias_espejo")
    differences = {field: {"primera": first[field], "segunda": second[field]}
                   for field in fields if first[field] != second[field]}
    return {
        "schema": "fixture_repeatability_v1",
        "mode": "REPEATABLE_PAIR",
        "fixture_1_sha256": first["sha256_fixture_logica"],
        "fixture_2_sha256": second["sha256_fixture_logica"],
        "identical_structural": not differences,
        "differences": differences,
        "limitation": "Comparación estructural exacta; los campos temporales se comparan tal como quedaron capturados.",
    }


def validate_freeze_approval(manifest: dict, gold_sha: str, fixture_sha: str,
                             revision_closure: dict | None = None,
                             graph_review_sha256: str | None = None,
                             repeatability_report: dict | None = None) -> None:
    """Gate: medición solo con aprobación humana y hashes exactos revisados."""
    if manifest.get("estado") != "APROBADO" or manifest.get("aprobado_por") != "Dennys":
        raise PermissionError("Falta aprobación expresa de Dennys para medir")
    if manifest.get("gold_sha256") != gold_sha or manifest.get("fixture_sha256") != fixture_sha:
        raise ValueError("Hashes de gold/fixture no coinciden con manifiesto aprobado")
    if not manifest.get("graph_review_sha256"):
        raise ValueError("El manifiesto aprobado debe fijar hash de auditoría del grafo")
    if graph_review_sha256 is not None and manifest.get("graph_review_sha256") != graph_review_sha256:
        raise ValueError("El manifiesto aprobado no coincide con el hash de auditoría del grafo recalculado")
    if revision_closure is not None:
        if not revision_closure.get("closed_before_search") or revision_closure.get("gold_sha256") != gold_sha:
            raise ValueError("La revisión del gold no está cerrada antes de observar búsquedas")
        if manifest.get("gold_revision_closure_sha256") != revision_closure.get("_file_sha256"):
            raise ValueError("El freeze manifest no fija el ledger de cierre del gold")
        if revision_closure.get("graph_review_sha256") != manifest.get("graph_review_sha256"):
            raise ValueError("El cierre gold y el freeze no usan la misma revisión del grafo")
    if repeatability_report is None:
        raise ValueError("Falta informe de repetibilidad o aprobación explícita de fixture materializada")
    if repeatability_report.get("fixture_1_sha256") != fixture_sha:
        raise ValueError("El informe de repetibilidad no referencia esta fixture")
    mode = repeatability_report.get("mode")
    if mode == "REPEATABLE_PAIR":
        if not repeatability_report.get("identical_structural") or not repeatability_report.get("fixture_2_sha256"):
            raise ValueError("Las dos construcciones difieren; no son línea base pareada")
    elif mode == "MATERIALIZED_ONLY":
        if not (repeatability_report.get("not_tested_reason") or "").strip():
            raise ValueError("Scope materializado requiere explicar que repetibilidad no se probó")
    else:
        raise ValueError("Informe de repetibilidad debe ser REPEATABLE_PAIR o MATERIALIZED_ONLY")
    if manifest.get("repeatability_report_sha256") != repeatability_report.get("_file_sha256"):
        raise ValueError("El freeze manifest no fija el hash del informe de repetibilidad")
    expected_arms = sorted(ARMS)
    if sorted(manifest.get("arms", [])) != expected_arms:
        raise ValueError(f"Manifiesto debe aprobar exactamente brazos {expected_arms}")
    if manifest.get("wake_W_included"):
        raise ValueError("W queda pendiente y no puede incluirse en esta línea base")


def require_all_active(graph: dict, expected_concepts: set[str]) -> None:
    states = graph["nodos"]
    if set(states) != expected_concepts:
        raise ValueError("La fixture R contiene nodos extra o faltantes respecto del gold congelado")
    dormant = sorted(c for c in expected_concepts if states[c].get("estado") != "activo")
    if dormant:
        raise ValueError(f"R requiere todos los nodos activos; estados no activos: {dormant[:10]}")


def _graph_cut(graph: dict | None) -> dict | None:
    if graph is None:
        return None
    return {
        "nodos_estado_espejo": graph["nodos"],
        "aristas_directas_dirigidas": graph["aristas_directas"],
        "sinapsis_latentes": graph["sinapsis_latentes"],
        "divergencias_espejo": graph["divergencias_espejo"],
        "conteos": graph["conteos"],
        "tablas_sha256": graph["tablas_sha256"],
        "sha256_fixture_logica": graph["sha256_fixture_logica"],
    }


def persist_evidence(directory: Path, name: str, payload: dict) -> Path:
    """Persistencia atómica de evidencia en la raíz temporal; no se borra al fallar."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=repr) + "\n"
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def classify_attempt(response: dict | None, call_errors: list[dict], unexpected: list[str]) -> dict:
    """Un error de transporte/MCP o un diff inesperado invalida la corrida, no solo el query."""
    issues = list(call_errors)
    response = response or {}
    status = str(response.get("status", "")).casefold()
    if response.get("_mcp_is_error") or response.get("isError") or response.get("is_error"):
        issues.append({"tipo": "error_mcp", "status": status or None})
    elif status in {"error", "mcp_error", "transport_error", "failed", "exception"}:
        issues.append({"tipo": "error_mcp", "status": status})
    if unexpected:
        issues.append({"tipo": "mutacion_inesperada", "detalles": sorted(set(unexpected))})
    return {"invalida": bool(issues), "motivos": issues}


async def guarded_mcp_call(db_path: Path, temp_root: Path, arguments: dict) -> tuple[str, dict, list[dict]]:
    """Captura fallos de arranque, tool y teardown sin perder respuesta parcial."""
    process = MCPProcess(db_path, temp_root)
    raw = ""
    response = {}
    errors = []
    try:
        await process.__aenter__()
    except Exception as exc:
        errors.append({"fase": "inicio_mcp", "tipo": type(exc).__name__, "mensaje": str(exc)})
        if hasattr(process, "_stdio"):
            try:
                await process.__aexit__(None, None, None)
            except Exception as cleanup_exc:
                errors.append({"fase": "limpieza_inicio_mcp", "tipo": type(cleanup_exc).__name__,
                               "mensaje": str(cleanup_exc)})
        return raw, {"status": "transport_error", "_mcp_is_error": True,
                     "mensaje": errors[0]["mensaje"]}, errors
    try:
        raw, response = await process.call("recordar", arguments)
    except Exception as exc:
        errors.append({"fase": "llamada_mcp", "tipo": type(exc).__name__, "mensaje": str(exc)})
        response = {"status": "transport_error", "_mcp_is_error": True,
                    "mensaje": errors[-1]["mensaje"]}
    try:
        await process.__aexit__(None, None, None)
    except Exception as exc:
        errors.append({"fase": "cierre_mcp", "tipo": type(exc).__name__, "mensaje": str(exc)})
        response = response or {"status": "transport_error", "_mcp_is_error": True}
    return raw, response, errors


def _edge_diff(before: dict, after: dict) -> dict:
    def edge_map(graph):
        return {(e["origen"], e["destino"]): e for e in graph["aristas_directas"]}
    left, right = edge_map(before), edge_map(after)
    return {
        "insertadas": [right[k] for k in sorted(right.keys() - left.keys())],
        "eliminadas": [left[k] for k in sorted(left.keys() - right.keys())],
        "actualizadas": [{"antes": left[k], "despues": right[k]} for k in sorted(left.keys() & right.keys()) if left[k] != right[k]],
    }


async def prepare_fixture(db_path: Path, temp_root: Path, episodes: list[dict], gold_path: Path) -> dict:
    """Arma fixture MCP; toda llamada queda persistida antes de propagar un fallo."""
    db_path = _inside(db_path, temp_root, "DB de fixture")
    if db_path.exists():
        raise FileExistsError(db_path)
    names = audit_names(episodes)
    if names["colisiones_clave"]:
        raise ValueError(f"Colisiones de concepto antes de MCP: {names['colisiones_clave']}")
    wanted = {n["concepto"] for ep in episodes for n in ep["nodos"]}
    events = []
    temp_root.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_root = db_path.parent / (db_path.name + ".evidence")
    persist_evidence(evidence_root, "run_manifest", {
        "phase": "fixture_preparation", "gold_sha256": file_sha256(gold_path),
        "fixture_path": str(db_path), "evidence_root": str(evidence_root),
    })
    sqlite3.connect(db_path).close()
    mcp = MCPProcess(db_path, temp_root)
    try:
        await mcp.__aenter__()
    except Exception as exc:
        failure = {"phase": "mcp_startup", "estado": "INVALIDA", "valida": False,
                   "exception_type": type(exc).__name__, "message": str(exc)}
        if hasattr(mcp, "_stdio"):
            try:
                await mcp.__aexit__(None, None, None)
            except Exception as cleanup_exc:
                failure["cleanup_error"] = {"type": type(cleanup_exc).__name__, "message": str(cleanup_exc)}
        persist_evidence(evidence_root, "run_failure", failure)
        raise RuntimeError(f"Fixture preparation inválida; evidencia: {evidence_root}") from exc

    async def call(tool: str, args: dict, label: str) -> dict:
        before_tables = readonly_snapshot(db_path)
        before_graph = inspect_fixture(db_path, temp_root) if db_path.exists() and db_path.stat().st_size else None
        call_errors = []
        try:
            raw, parsed = await mcp.call(tool, args)
        except Exception as exc:
            raw = ""
            parsed = {"status": "transport_error", "_mcp_is_error": True, "mensaje": str(exc)}
            call_errors.append({"phase": "tool_call", "exception_type": type(exc).__name__, "message": str(exc)})
        try:
            after_tables = readonly_snapshot(db_path)
        except Exception as exc:
            after_tables = {}
            call_errors.append({"phase": "after_table_snapshot", "exception_type": type(exc).__name__, "message": str(exc)})
        try:
            after_graph = inspect_fixture(db_path, temp_root)
        except Exception as exc:
            after_graph = None
            call_errors.append({"phase": "after_graph_snapshot", "exception_type": type(exc).__name__, "message": str(exc)})
        changed = sorted(k for k in set(before_tables) | set(after_tables)
                         if before_tables.get(k) != after_tables.get(k))
        event = {
            "sequence": len(events) + 1, "label": label, "tool": tool, "arguments": args,
            "raw_response": raw, "parsed_response": parsed, "call_errors": call_errors,
            "tables_sha256_before": before_tables, "tables_sha256_after": after_tables,
            "tables_changed": changed, "graph_before": _graph_cut(before_graph),
            "graph_after": _graph_cut(after_graph),
            "edge_diff": _edge_diff(before_graph, after_graph) if before_graph and after_graph else None,
            "graph_sha_after": after_graph["sha256_fixture_logica"] if after_graph else None,
        }
        events.append(event)
        persist_evidence(evidence_root, f"event_{event['sequence']:06d}", event)
        outcome = classify_attempt(parsed, call_errors, [])
        if outcome["invalida"]:
            persist_evidence(evidence_root, "run_failure", {
                "phase": "mcp_tool_call", "estado": "INVALIDA", "valida": False,
                "label": label, "sequence": event["sequence"],
                "outcome": outcome, "event_file": f"event_{event['sequence']:06d}.json",
            })
            raise RuntimeError(f"MCP {tool} falló; corrida inválida, evidencia: {evidence_root}")
        return parsed

    primary_error = None
    try:
        for episode in episodes:
            for node in episode["nodos"]:
                query_args = {"query": node["concepto"] + " " + node["contenido"],
                              "sustantivos_clave": node["sustantivos_clave"], "deep": False,
                              "limite": 5, "asociados": False, "context_window": 0}
                prior = await call("recordar", query_args, "preflight:" + node["concepto"])
                exact = [r for r in prior.get("resultados", []) if r.get("concepto") == node["concepto"]]
                if exact:
                    raise RuntimeError(f"Preflight MCP encontró duplicado: {node['concepto']}")
                bridges = bridge_payload(node["concepto"])
                learned = await call("aprender", {
                    "concepto": node["concepto"], "contenido": node["contenido"],
                    "bridges": bridges, "sustantivos_clave": node["sustantivos_clave"],
                    "cat": "General", "busqueda_previa": True,
                }, "aprender:" + node["concepto"])
                if learned.get("status") != "ok" or learned.get("concepto") != node["concepto"]:
                    raise RuntimeError(f"MCP no confirmó aprendizaje de {node['concepto']}: {learned}")
            consolidated = await call("consolidar", {}, "consolidar:" + episode["episode_id"])
            if consolidated.get("status") != "ok":
                raise RuntimeError(f"Consolidación MCP falló: {episode['episode_id']}")
            for a, b in episode["aristas_gold"]:
                linked = await call("vincular", {"a": a, "b": b}, f"vincular:{a}:{b}")
                if linked.get("status") != "ok":
                    raise RuntimeError(f"Vínculo MCP falló: {a} <-> {b}")
    except Exception as exc:
        primary_error = exc
        persist_evidence(evidence_root, "run_failure", {
            "phase": "fixture_construction", "estado": "INVALIDA", "valida": False,
            "exception_type": type(exc).__name__,
            "message": str(exc), "events_persisted": len(events),
        })
        raise
    finally:
        try:
            await mcp.__aexit__(None, None, None)
        except Exception as exc:
            persist_evidence(evidence_root, "mcp_teardown_failure", {
                "estado": "INVALIDA", "valida": False,
                "exception_type": type(exc).__name__, "message": str(exc),
                "primary_error_already_recorded": primary_error is not None,
                "events_persisted": len(events),
            })
            if primary_error is None:
                raise RuntimeError(f"Cierre MCP falló; corrida inválida, evidencia: {evidence_root}") from exc
    graph = inspect_fixture(db_path, temp_root)
    audit = audit_fixture_gold(episodes, graph, names)
    missing = wanted - set(graph["nodos"])
    if missing:
        audit["bloqueos_congelacion"].append("nodos_gold_ausentes")
        audit["gold_nodes_missing"] = sorted(missing)
        audit["congelacion_estructural_permitida"] = False
    audit_sha = hashlib.sha256(_canonical(audit).encode("utf-8")).hexdigest()
    report = {
        "estado": "requiere_revision_gold" if audit["bloqueos_congelacion"] else "listo_para_auditoria_humana",
        "gold_file": str(gold_path.resolve()), "gold_sha256": file_sha256(gold_path),
        "name_preflight": names, "fixture": graph, "graph_audit": audit,
        "graph_audit_sha256": audit_sha, "fixture_events": events,
        "evidence_root": str(evidence_root), "baseline_searches_run": 0,
        "nota": "La preparación incluye solo preflight de escritura y construcción MCP; no ejecuta los queries de evaluación.",
    }
    persist_evidence(evidence_root, "preparation_report", report)
    return report


def _result_row(episode: dict, query: dict, response: dict, raw: str, known: set[str], mode: str) -> dict:
    results = main_result_concepts(response.get("resultados", []), known)
    channels = {"resultados": set(results), "contexto_expandido": context_concepts(response.get("contexto_expandido", []), known),
                "asociaciones_enriquecidas": set(), "asociaciones": set()}
    for result in response.get("resultados", []):
        if isinstance(result, dict):
            channels["asociaciones"].update(response_concepts(result.get("asociaciones", {}), known))
            channels["asociaciones_enriquecidas"].update(response_concepts(result.get("asociaciones_enriquecidas", []), known))
    rank = next((i + 1 for i, concept in enumerate(results) if concept in query["objetivos_principales"]), None)
    return {
        "condicion": mode, "episode_id": episode["episode_id"], "query_id": query["query_id"],
        "stratum": episode["stratum"], "idioma": query["idioma"], "query": query["query"],
        "objetivos_principales": query["objetivos_principales"],
        "relacionados_utiles": query["relacionados_utiles"], "ruido_tonto": query["ruido_tonto"],
        "espera_abstencion": query["espera_abstencion"], "ranking_resultados": results,
        "rango_objetivo_resultados": rank,
        "canales": {k: sorted(v) for k, v in channels.items()},
        "respuesta_parseada": response, "respuesta_mcp_cruda": raw,
    }


async def measure_baseline(fixture_path: Path, temp_root: Path, episodes: list[dict], gold_path: Path,
                           approval_path: Path, repeatability_path: Path, output_path: Path) -> dict:
    fixture_path = _inside(fixture_path, temp_root, "fixture congelada")
    output_path = output_path.resolve()
    try:
        output_path.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise ValueError("Reporte de medición debe escribirse fuera del repositorio")
    graph = inspect_fixture(fixture_path, temp_root)
    names = audit_names(episodes)
    preflight = audit_fixture_gold(episodes, graph, names)
    if not preflight["congelacion_estructural_permitida"]:
        raise RuntimeError(f"Fixture no pasa preflight estructural: {preflight['bloqueos_congelacion']}")
    graph_review_sha = hashlib.sha256(_canonical(preflight).encode("utf-8")).hexdigest()
    gold_sha = file_sha256(gold_path)
    revision_manifest_path = gold_path.with_suffix(gold_path.suffix + ".revision.json")
    revision_closure = None
    if gold_sha != BASE_GOLD_SHA256:
        if not revision_manifest_path.exists():
            raise ValueError("Gold distinto de la versión base requiere ledger de revisión versionado")
        closure_path = revision_manifest_path.with_suffix(".closed.json")
        if not closure_path.exists():
            raise PermissionError("La revisión de gold no está cerrada antes de búsquedas")
        revision_closure = json.loads(closure_path.read_text(encoding="utf-8"))
        revision = json.loads(revision_manifest_path.read_text(encoding="utf-8"))
        if revision.get("revised_sha256") != gold_sha or revision_closure.get("revision_manifest_sha256") != file_sha256(revision_manifest_path):
            raise ValueError("Hashes del ledger/cierre no corresponden al gold medido")
        revision_closure["_file_sha256"] = file_sha256(closure_path)
    fixture_sha = graph["sha256_fixture_logica"]
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    repeatability = json.loads(repeatability_path.read_text(encoding="utf-8"))
    repeatability["_file_sha256"] = file_sha256(repeatability_path)
    validate_freeze_approval(approval, gold_sha, fixture_sha, revision_closure,
                             graph_review_sha, repeatability)
    known = set(graph["nodos"])
    if known != {n["concepto"] for ep in episodes for n in ep["nodos"]}:
        raise RuntimeError("La fixture congelada contiene nodos extra/faltantes")
    if any(arm == "R" for arm in approval["arms"]):
        require_all_active(graph, known)

    temp_root.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[dict]] = {arm: [] for arm in sorted(ARMS)}
    transitions: dict[str, list[dict]] = {arm: [] for arm in sorted(ARMS)}
    invalidations = []
    # Run roots are intentionally persistent: a failed/contaminated run must leave
    # the copied DBs and per-call snapshots available for the auditor.
    run_root = Path(tempfile.mkdtemp(prefix="biorag_linea_base_", dir=temp_root)).resolve()
    evidence_root = run_root / "evidence"
    persist_evidence(evidence_root, "run_manifest", {
        "gold_sha256": gold_sha, "fixture_sha256": fixture_sha,
        "freeze_manifest_sha256": file_sha256(approval_path),
        "repeatability_report_sha256": repeatability["_file_sha256"],
        "graph_review_sha256": graph_review_sha, "fixture_path": str(fixture_path),
        "arms": sorted(ARMS), "wake_W": "pending_not_run",
    })
    for arm, config in ARMS.items():
        if invalidations:
            break
        for episode in episodes:
            if invalidations:
                break
            for query in episode["consultas"]:
                key = hashlib.sha256(f"{arm}:{query['query_id']}".encode()).hexdigest()[:20]
                attempt_dir = evidence_root / arm / key
                db_path = run_root / "db" / arm / (key + ".sqlite")
                db_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    copy_sqlite(fixture_path, db_path)
                    if snapshot_sha256(db_path) != fixture_sha:
                        raise RuntimeError("La copia de consulta no coincide con el hash congelado")
                    before_tables = readonly_snapshot(db_path)
                    before_graph = inspect_fixture(db_path, run_root)
                    if arm == "R":
                        require_all_active(before_graph, known)
                    args = {"query": query["query"], "sustantivos_clave": query["sustantivos_clave"],
                            "limite": 5, **config}
                    if arm == "R":
                        terms = query["sustantivos_clave"]
                        args["rafaga_palabras"] = terms if isinstance(terms, str) else ",".join(map(str, terms))
                    persist_evidence(attempt_dir, "before", {
                        "arm": arm, "episode_id": episode["episode_id"], "query_id": query["query_id"],
                        "arguments": args, "tables_sha256": before_tables, "graph": _graph_cut(before_graph),
                        "db_path": str(db_path),
                    })
                    call_started = time.perf_counter()
                    raw, response, call_errors = await guarded_mcp_call(db_path, run_root, args)
                    latency_ms = round((time.perf_counter() - call_started) * 1000, 3)
                    output_bytes = len(raw.encode("utf-8"))
                    call_failure = classify_attempt(response, call_errors, [])
                    persist_evidence(attempt_dir, "call", {
                        "raw_response": raw, "parsed_response": response,
                        "call_errors": call_errors, "call_failure": call_failure,
                        "latency_ms": latency_ms, "output_bytes": output_bytes,
                    })
                    after_tables = readonly_snapshot(db_path)
                    after_graph = inspect_fixture(db_path, run_root)
                    changed_tables = sorted(t for t in set(before_tables) | set(after_tables)
                                            if before_tables.get(t) != after_tables.get(t))
                    allowed = BURST_WRITES if arm == "R" else READ_WRITES
                    unexpected = sorted(set(changed_tables) - allowed)
                    edge_changes = _edge_diff(before_graph, after_graph)
                    state_changes = [{"concepto": c, "antes": before_graph["nodos"].get(c),
                                      "despues": after_graph["nodos"].get(c)}
                                     for c in set(before_graph["nodos"]) | set(after_graph["nodos"])
                                     if before_graph["nodos"].get(c) != after_graph["nodos"].get(c)]
                    if arm != "R" and (edge_changes["insertadas"] or edge_changes["eliminadas"]
                                        or edge_changes["actualizadas"] or state_changes):
                        unexpected.append("sinapsis/estado")
                    if arm == "R" and state_changes:
                        unexpected.append("estado_nodos_modificado_en_brazo_R")
                    attempt_status = classify_attempt(response, call_errors, unexpected)
                    diff_record = {
                        "query_id": query["query_id"], "tables_changed": changed_tables,
                        "unexpected_tables": sorted(set(unexpected)), "edge_diff": edge_changes,
                        "state_diff": state_changes,
                        "mirror_before": before_graph["divergencias_espejo"],
                        "mirror_after": after_graph["divergencias_espejo"],
                        "attempt_status": attempt_status,
                    }
                    persist_evidence(attempt_dir, "after", {
                        "tables_sha256": after_tables, "graph": _graph_cut(after_graph),
                    })
                    persist_evidence(attempt_dir, "diff", diff_record)
                    transitions[arm].append({"query_id": query["query_id"], "tablas_cambiadas": changed_tables,
                                             "tablas_inesperadas": sorted(set(unexpected)),
                                             "aristas": edge_changes, "estado": state_changes,
                                             "divergencias_espejo_antes": before_graph["divergencias_espejo"],
                                             "divergencias_espejo_despues": after_graph["divergencias_espejo"],
                                             "evidence_dir": str(attempt_dir)})
                    row = _result_row(episode, query, response, raw, known, arm)
                    row["mcp_is_error"] = bool(response.get("_mcp_is_error") or response.get("isError") or response.get("is_error"))
                    row["respuesta_status_error"] = str(response.get("status", "")).casefold() in {
                        "error", "mcp_error", "transport_error", "failed", "exception"}
                    row["respuesta_recibida"] = not any(
                        error.get("fase") in {"inicio_mcp", "llamada_mcp"} for error in call_errors)
                    row["call_errors"] = call_errors
                    row["latency_ms"] = latency_ms
                    row["output_bytes"] = output_bytes
                    results[arm].append(row)
                    if attempt_status["invalida"]:
                        invalidations.append({"arm": arm, "query_id": query["query_id"],
                                              "motivos": attempt_status["motivos"],
                                              "evidence_dir": str(attempt_dir), "db_path": str(db_path)})
                        break
                except Exception as exc:
                    failure = {"arm": arm, "episode_id": episode["episode_id"],
                               "query_id": query["query_id"], "fase": "preparacion_o_snapshot",
                               "tipo": type(exc).__name__, "mensaje": str(exc),
                               "evidence_dir": str(attempt_dir), "db_path": str(db_path)}
                    persist_evidence(attempt_dir, "harness_exception", failure)
                    invalidations.append({"arm": arm, "query_id": query["query_id"],
                                          "motivos": [{"tipo": "error_arnes", "mensaje": str(exc)}],
                                          "evidence_dir": str(attempt_dir), "db_path": str(db_path)})
                    break
    report = {
            "estado": "INVALIDA; detener y revisar evidencia" if invalidations else "medicion descriptiva; sin umbrales aplicados",
            "valida": not invalidations,
            "invalidaciones": invalidations,
            "evidence_root": str(evidence_root),
            "run_root_persistente": str(run_root),
            "gold_sha256": gold_sha, "fixture_sha256": fixture_sha,
            "repeatability_report_sha256": repeatability["_file_sha256"],
            "repeatability_mode": repeatability["mode"],
            "freeze_manifest_sha256": file_sha256(approval_path),
            "wake_W": "pendiente; no ejecutado ni incluido",
            "conteo": {"consultas_gold": sum(len(ep["consultas"]) for ep in episodes),
                       "brazos_planeados": list(ARMS),
                       "brazos_con_llamadas": [arm for arm, rows in results.items() if rows],
                       "llamadas_recordar": sum(map(len, results.values()))},
            "metricas_por_brazo": {arm: metrics_by_channel(rows) for arm, rows in results.items()},
            "telemetria_por_brazo": {arm: {
                "latencia_ms_p50": percentile([row["latency_ms"] for row in rows], 0.50),
                "latencia_ms_p95": percentile([row["latency_ms"] for row in rows], 0.95),
                "bytes_salida_total": sum(row["output_bytes"] for row in rows),
                "fallos_transporte": sum(bool(row["call_errors"]) for row in rows),
                "errores_mcp": sum(row["mcp_is_error"] or row["respuesta_status_error"] for row in rows),
            } for arm, rows in results.items()},
            "mutaciones_por_brazo": transitions,
            "salidas_por_brazo": results,
        }
    report_text = serialize_report(report)
    persist_evidence(evidence_root, "run_report", report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    return report


async def _prepare_cli(args) -> int:
    temp_root = args.temp_root.resolve()
    db_path = _inside(args.db, temp_root, "fixture")
    episodes = __import__("scripts.evaluar_qa_intuicion_asociaciones_e1", fromlist=["load_gold"]).load_gold(args.gold)
    if not args.ejecutar_preparacion:
        raise PermissionError("La preparación MCP requiere --ejecutar-preparacion y autorización previa")
    report = await prepare_fixture(db_path, temp_root, episodes, args.gold)
    out = args.salida.resolve()
    try:
        out.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise ValueError("Informe de preflight debe guardarse fuera del repositorio")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(serialize_report(report), encoding="utf-8")
    print(json.dumps({"estado": report["estado"], "gold_sha256": report["gold_sha256"],
                      "fixture_sha256": report["fixture"]["sha256_fixture_logica"],
                      "baseline_searches_run": 0, "salida": str(out)}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="fase", required=True)
    prep = sub.add_parser("preparar", help="Construye y audita una fixture temporal; no mide la línea base")
    prep.add_argument("--gold", type=Path, default=GOLD)
    prep.add_argument("--db", type=Path, required=True)
    prep.add_argument("--temp-root", type=Path, required=True)
    prep.add_argument("--salida", type=Path, required=True)
    prep.add_argument("--ejecutar-preparacion", action="store_true")
    measure = sub.add_parser("medir", help="Ejecuta N/G/R solo con freeze manifest aprobado por Dennys")
    measure.add_argument("--gold", type=Path, default=GOLD)
    measure.add_argument("--fixture", type=Path, required=True)
    measure.add_argument("--temp-root", type=Path, required=True)
    measure.add_argument("--aprobacion", type=Path, required=True)
    measure.add_argument("--repetibilidad", type=Path, required=True,
                         help="Informe externo de dos fixtures idénticas o de scope materializado aprobado")
    measure.add_argument("--salida", type=Path, required=True)
    measure.add_argument("--ejecutar-linea-base", action="store_true")
    compare = sub.add_parser("comparar", help="Compara repetibilidad entre dos fixtures ya construidas")
    compare.add_argument("--primera", type=Path, required=True)
    compare.add_argument("--segunda", type=Path, required=True)
    compare.add_argument("--temp-root", type=Path, required=True)
    compare.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if args.fase == "preparar":
        return asyncio.run(_prepare_cli(args))
    if args.fase == "comparar":
        _inside(args.primera, args.temp_root, "primera fixture")
        _inside(args.segunda, args.temp_root, "segunda fixture")
        result = audit_repeatability(args.primera, args.segunda, args.temp_root)
        out = args.salida.resolve()
        try:
            out.relative_to(ROOT)
        except ValueError:
            pass
        else:
            raise ValueError("Informe de repetibilidad debe guardarse fuera del repositorio")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(serialize_report(result), encoding="utf-8")
        print(json.dumps({"mode": result["mode"], "identical_structural": result["identical_structural"],
                          "salida": str(out)}, ensure_ascii=False))
        return 0 if result["identical_structural"] else 2
    if not args.ejecutar_linea_base:
        parser.error("Medición NO ejecutada: requiere --ejecutar-linea-base y manifiesto aprobado")
    episodes = __import__("scripts.evaluar_qa_intuicion_asociaciones_e1", fromlist=["load_gold"]).load_gold(args.gold)
    report = asyncio.run(measure_baseline(args.fixture, args.temp_root, episodes, args.gold,
                                         args.aprobacion, args.repetibilidad, args.salida))
    print(json.dumps({"estado": report["estado"], "conteo": report["conteo"], "salida": str(args.salida)}, ensure_ascii=False))
    return 2 if report["invalidaciones"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
