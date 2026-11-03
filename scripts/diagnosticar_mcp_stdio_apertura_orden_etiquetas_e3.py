#!/usr/bin/env python3
"""Mide apertura del store y orden de consultas por MCP stdio en copias sintéticas.

El proceso MCP real se lanza con scripts/qa_stdio_server_intuicion.py, que
requiere una ruta de base bajo BIORAG_QA_TEMP_ROOT y no lanza el daemon global.
La semilla se crea con síntesis DMN apagada; cada proceso stdio abre una copia
con la configuración normal DMN activa para observar cambios de apertura.
"""
from __future__ import annotations

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
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# El proceso padre solo construye las semillas. El subprocess MCP recibe ON.
os.environ["BIORAG_DMN_SINTESIS_ACTIVA"] = "0"
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

SCENARIOS = {
    "historia_util": {
        "initial": "instrument,thermistor,offset",
        "incoming": "instrument,reference,precision",
        "content": (
            "La primera lectura sigue vigente; la revisión posterior es compatible. "
            "shared calibration anchor_target."
        ),
        "old_probe": "thermistor",
        "new_probe": "reference",
        "stable_probe": "instrument",
    },
    "historia_contradicha": {
        "initial": "valve,openstate,leakage",
        "incoming": "valve,closedstate,sealed",
        "content": (
            "Registro previo openstate leakage; corrección contradice ese registro y confirma "
            "closedstate sealed. shared calibration anchor_target."
        ),
        "old_probe": "openstate",
        "new_probe": "closedstate",
        "stable_probe": "valve",
    },
}


def normalize_pair(raw: str) -> tuple[str, str]:
    exact = normalizar_sustantivos_clave_exacto(raw)
    folded = normalizar_sustantivos_clave(exact)
    exact = normalizar_sustantivos_clave_exactos_coherentes(exact, folded) or ""
    return folded, exact


def create_seed(path: Path, scenario: dict) -> None:
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        category = memory._resolver_categoria_id("General")
        nodes = (
            (TARGET, scenario["content"], scenario["initial"]),
            (MANUAL_NEIGHBORS[0], "Nota aislada ambar." , "archive,context"),
            (MANUAL_NEIGHBORS[1], "Fuente independiente violeta.", "review,source"),
            (AUTO_CANDIDATE, "shared calibration anchor_candidate.", "anchor,context"),
        )
        for concept, content, labels in nodes:
            folded, exact = normalize_pair(labels)
            consolidation.fusionar_en_largo_plazo(
                memory, concept, content, "", category, 0.0, folded, exact
            )
        memory.conn.commit()
        for neighbor in MANUAL_NEIGHBORS:
            memory.establecer_asociacion(TARGET, neighbor)
        memory.conn.commit()
        memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        memory.cerrar_sistema()


def clone_sqlite(source: Path, destination: Path) -> None:
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def graph_snapshot(path: Path) -> list[dict]:
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=10)
    try:
        rows = con.execute(
            "SELECT origen,destino,round(peso,4),tipo FROM sinapsis ORDER BY origen,destino,tipo"
        ).fetchall()
        return [dict(zip(("origen", "destino", "peso", "tipo"), row)) for row in rows]
    finally:
        con.close()


def parse_tool_result(result) -> dict:
    blocks = getattr(result, "content", None)
    raw = "\n".join(getattr(block, "text", "") for block in (blocks or []))
    for match in reversed(list(re.finditer(r"(?m)^\{", raw))):
        try:
            data = json.loads(raw[match.start():])
            if isinstance(data, dict):
                if getattr(result, "isError", False):
                    data["_mcp_is_error"] = True
                return data
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"MCP stdio retornó respuesta no JSON: {raw[:300]}")


class StdioMCP:
    def __init__(self, db_path: Path, temp_root: Path):
        self.db_path = db_path.resolve()
        self.temp_root = temp_root.resolve()
        self.session = None
        self._stdio = None

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        try:
            self.db_path.relative_to(self.temp_root)
        except ValueError as exc:
            raise RuntimeError(f"Guardrail: la DB MCP quedó fuera del temporal: {self.db_path}") from exc
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
            "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
            "BIORAG_MCP_AUTO_PARAFRASIS": "0",
            "BIORAG_MCP_AUTO_DIMS": "0",
            "BIORAG_NEURONA": "0",
            "BIORAG_NO_LOG": "1",
            "BIORAG_QA_RELOJ_FIJO": "1793059200.0",
        })
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "qa_stdio_server_intuicion.py")],
            env=env,
            cwd=str(ROOT),
        )
        self._stdio = stdio_client(params)
        read_stream, write_stream = await self._stdio.__aenter__()
        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.session.__aexit__(exc_type, exc, tb)
        finally:
            await self._stdio.__aexit__(exc_type, exc, tb)

    async def call(self, name: str, args: dict) -> dict:
        response = await self.session.call_tool(name, arguments=args)
        return parse_tool_result(response)


async def run_arm(seed: Path, db: Path, temp_root: Path, scenario_name: str,
                  scenario: dict, policy: str, write_route: str,
                  query_order: tuple[str, str]) -> dict:
    clone_sqlite(seed, db)
    graph_before = graph_snapshot(db)
    async with StdioMCP(db, temp_root) as mcp:
        # MCP initialize no debe abrir la corteza; `sustantivos` es el primer
        # tool real y sirve de barrera antes/después de apertura.
        graph_after_initialize = graph_snapshot(db)
        labels_before = await mcp.call("sustantivos", {"concepto": TARGET})
        graph_after_open = graph_snapshot(db)

        incoming = scenario["incoming"]
        write_payload = incoming
        if policy == "acumulacion_payload_sintetico":
            write_payload = scenario["initial"] + "," + incoming
        tool_name = "actualizar" if write_route == "actualizar" else "agregar_sustantivos"
        write_args = {"concepto": TARGET, "sustantivos_clave": write_payload}
        write_result = await mcp.call(tool_name, write_args)
        labels_after_write = await mcp.call("sustantivos", {"concepto": TARGET})
        graph_after_write = graph_snapshot(db)

        by_name = {"old": scenario["old_probe"], "new": scenario["new_probe"]}
        query_results = []
        graph_after_each_query = []
        for position, key in enumerate(query_order, 1):
            term = by_name[key]
            stable = scenario["stable_probe"]
            result = await mcp.call("recordar", {
                "query": term,
                "sustantivos_clave": f"{term},{stable}",
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
            target = next((item for item in primary if item.get("concepto") == TARGET), None)
            query_results.append({
                "query_role": key,
                "response_status": result.get("status"),
                "mcp_is_error": bool(result.get("_mcp_is_error")),
                "target_found": target is not None,
                "target_rank": next((i + 1 for i, item in enumerate(primary) if item.get("concepto") == TARGET), None),
                "target_score": target.get("score_hibrido") if target else None,
                "associated_neighbors": sorted(
                    item.get("concepto") for item in (target or {}).get("asociaciones_enriquecidas", [])
                ),
                "expanded_neighbors": sorted(
                    item.get("concepto") for item in expanded
                    if item.get("concepto") in (*MANUAL_NEIGHBORS, AUTO_CANDIDATE)
                ),
            })
            graph_after_each_query.append(graph_snapshot(db))

    manual_seed_edges = [edge for edge in graph_before if edge["tipo"] == "manual"]
    after_open_new = [edge for edge in graph_after_open if edge not in graph_before]
    after_write_new = [edge for edge in graph_after_write if edge not in graph_after_open]
    after_write_removed = [edge for edge in graph_after_open if edge not in graph_after_write]
    query_added = []
    query_removed = []
    prev = graph_after_write
    for snap in graph_after_each_query:
        query_added.append([edge for edge in snap if edge not in prev])
        query_removed.append([edge for edge in prev if edge not in snap])
        prev = snap
    return {
        "scenario": scenario_name,
        "policy_payload": policy,
        "write_route": write_route,
        "query_order": list(query_order),
        "mcp_initialize_opened_database": graph_after_initialize != graph_before,
        "initial_manual_edge_count": len(manual_seed_edges),
        "initial_manual_edges_preserved_after_open": all(edge in graph_after_open for edge in manual_seed_edges),
        "initial_manual_edges_preserved_after_write": all(edge in graph_after_write for edge in manual_seed_edges),
        "initial_manual_edges_preserved_after_each_query": [
            all(edge in snap for edge in manual_seed_edges) for snap in graph_after_each_query
        ],
        "graph_before_open": graph_before,
        "graph_after_initialize": graph_after_initialize,
        "graph_after_first_tool_open": graph_after_open,
        "edges_added_by_first_tool_open": after_open_new,
        "labels_before_write": labels_before,
        "opening_tool_mcp_error": bool(labels_before.get("_mcp_is_error")),
        "write_result": write_result,
        "write_tool_mcp_error": bool(write_result.get("_mcp_is_error")),
        "labels_after_write": labels_after_write,
        "readback_tool_mcp_error": bool(labels_after_write.get("_mcp_is_error")),
        "readback_tool_status": labels_after_write.get("status"),

        "edges_added_by_write": after_write_new,
        "edges_removed_by_write": after_write_removed,
        "queries": query_results,
        "edges_added_after_each_query": query_added,
        "edges_removed_after_each_query": query_removed,
        "graph_after_queries": graph_after_each_query[-1] if graph_after_each_query else graph_after_write,
        "mcp_stdio": True,
    }


async def run_all() -> dict:
    with tempfile.TemporaryDirectory(prefix="e3_mcp_stdio_open_order_") as tmp:
        root = Path(tmp)
        cases = []
        for scenario_name, scenario in SCENARIOS.items():
            seed = root / f"seed_{scenario_name}.db"
            create_seed(seed, scenario)
            for policy in ("reemplazo_actual", "acumulacion_payload_sintetico"):
                for route in ("actualizar", "agregar_sustantivos"):
                    for order_name, query_order in (
                        ("historia_primero", ("old", "new")),
                        ("nueva_primero", ("new", "old")),
                    ):
                        db = root / f"{scenario_name}_{policy}_{route}_{order_name}.db"
                        cases.append(await run_arm(
                            seed, db, root, scenario_name, scenario, policy, route, query_order
                        ))
        tool_flags = [
            c["opening_tool_mcp_error"] or c["write_tool_mcp_error"] or c["readback_tool_mcp_error"]
            for c in cases
        ] + [q["mcp_is_error"] for c in cases for q in c["queries"]]
        return {
            "synthetic_only": True,
            "mcp_sessions": len(cases),
            "mcp_tool_calls": 5 * len(cases),
            "mcp_tool_error_flags": sum(bool(flag) for flag in tool_flags),
            "write_status_counts": {
                status: sum(c["write_result"].get("status") == status for c in cases)
                for status in sorted({c["write_result"].get("status") for c in cases}, key=str)
            },
            "remember_response_status_counts": {
                status: sum(q["response_status"] == status for c in cases for q in c["queries"])
                for status in sorted({q["response_status"] for c in cases for q in c["queries"]}, key=str)
            },
            "user_databases_opened": 0,
            "source_databases_copied": False,
            "engine_patches_applied": False,
            "backfill": False,
            "memory_merges_between_records": 0,
            "policy_selected": False,
            "real_mcp_stdio": True,
            "open_order_control": "record graph before stdio initialize, after initialize, then after first MCP tool sustantivos",
            "query_order_variants": [["old", "new"], ["new", "old"]],
            "cases": cases,
        }


def main() -> None:
    # El seed y la instrumentación local imprimen diagnósticos; que no rompan
    # el JSON de salida. El canal stdio del hijo MCP es su propio pipe.
    with contextlib.redirect_stdout(io.StringIO()):
        report = asyncio.run(run_all())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
