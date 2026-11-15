#!/usr/bin/env python3
"""Sondea rutas MCP de escritura/lectura en copias SQLite completamente sintéticas.

No abre el snapshot ni la base configurada del usuario. Crea una DB vacía,
siembra tres nodos sintéticos y dos aristas manuales, clona la DB para cada
escenario/ruta/política y llama las funciones registradas de MCP. La unión es
un contrafactual ejecutado solo en la copia; no cambia el código del motor.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("BIORAG_NEURONA", "0")
os.environ.setdefault("BIORAG_NO_LOG", "1")

from core.memory import consolidation
from core.memory_store import (
    SQLiteMemoryBioRAG,
    normalizar_sustantivos_clave,
    normalizar_sustantivos_clave_exacto,
    normalizar_sustantivos_clave_exactos_coherentes,
)
from core.mcp_server import search as search_mcp
from core.mcp_server import write as write_mcp

TARGET = "recuerdo_sintetico_objetivo"
NEIGHBORS = ("vecino_sintetico_historia", "vecino_sintetico_verificacion")

SCENARIOS = {
    "historia_util": {
        "initial": "instrument,thermistor,offset",
        "incoming": "instrument,reference,precision",
        "content": (
            "Registro sintético: la primera lectura continúa vigente y la revisión posterior "
            "es compatible; dos fuentes aportan contexto complementario."
        ),
        "old_probe": "thermistor",
        "new_probe": "reference",
        "stable_probe": "instrument",
    },
    "historia_contradicha": {
        "initial": "valve,openstate,leakage",
        "incoming": "valve,closedstate,sealed",
        "content": (
            "Registro sintético inicial: openstate y leakage. Corrección posterior: "
            "el registro inicial fue contradicho; la inspección confirma closedstate y sealed."
        ),
        "old_probe": "openstate",
        "new_probe": "closedstate",
        "stable_probe": "valve",
    },
}


class ToolCapture:
    """Adaptador mínimo para capturar y llamar las funciones MCP registradas."""
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **_kwargs):
        def decorator(fn):
            self.tools[name] = fn
            return fn
        return decorator


def parse_json_result(text: str) -> dict:
    # recordar puede anteponer advertencias en texto plano; el resultado JSON
    # de la herramienta comienza en el último bloque de línea antes de '{'.
    positions = [m.start() for m in re.finditer(r"(?m)^\{", text)]
    if not positions:
        raise AssertionError("La ruta MCP no devolvió el objeto JSON esperado")
    return json.loads(text[positions[-1]:])


def normalize_pair(raw: str) -> tuple[str, str]:
    exact = normalizar_sustantivos_clave_exacto(raw)
    folded = normalizar_sustantivos_clave(exact)
    exact = normalizar_sustantivos_clave_exactos_coherentes(exact, folded) or ""
    return folded, exact


def create_seed(path: Path, scenario: dict) -> None:
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        category = memory._resolver_categoria_id("General")
        for concept, content, labels in (
            (TARGET, scenario["content"], scenario["initial"]),
            (NEIGHBORS[0], "Contexto sintético de una observación anterior.", "archive,context"),
            (NEIGHBORS[1], "Contexto sintético de una verificación independiente.", "review,source"),
        ):
            folded, exact = normalize_pair(labels)
            consolidation.fusionar_en_largo_plazo(
                memory, concept, content, "", category, 0.0, folded, exact
            )
        memory.conn.commit()
        for neighbor in NEIGHBORS:
            memory.establecer_asociacion(TARGET, neighbor)
        memory.conn.commit()
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


def current_labels(path: Path) -> dict:
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        row = memory.cursor.execute(
            "SELECT sustantivos_clave, sustantivos_clave_exactos "
            "FROM largo_plazo WHERE concepto=?", (TARGET,),
        ).fetchone()
        return {"folded": row[0] or "", "exact": row[1] or ""}
    finally:
        memory.cerrar_sistema()


def tag_fts_hits(path: Path, terms: list[str]) -> dict[str, bool]:
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        return {
            term: bool(memory.cursor.execute(
                "SELECT 1 FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ? LIMIT 1",
                (f'sustantivos_clave : "{term}"',),
            ).fetchone())
            for term in terms
        }
    finally:
        memory.cerrar_sistema()


def run_arm(seed: Path, scratch_root: Path, scenario_name: str,
            scenario: dict, policy: str, write_route: str, tools: dict) -> dict:
    db = scratch_root / f"{scenario_name}_{policy}_{write_route}.db"
    clone_sqlite(seed, db)

    def open_copy():
        return SQLiteMemoryBioRAG(str(db))

    incoming = scenario["incoming"]
    # La ruta MCP real escribe primero. La unión experimental posterior, si se
    # solicita, es una intervención en esta copia solamente.
    with patch.object(write_mcp, "_get_cerebro", open_copy), \
         patch.object(search_mcp, "_get_cerebro", open_copy):
        if write_route == "actualizar":
            write_response = parse_json_result(tools["actualizar"](
                concepto=TARGET, sustantivos_clave=incoming,
            ))
        else:
            write_response = parse_json_result(tools["agregar_sustantivos"](
                concepto=TARGET, sustantivos_clave=incoming,
            ))
        if write_response.get("status") != "ok":
            raise AssertionError(f"Falló ruta MCP de escritura: {write_response}")

        if policy == "acumulacion_sintetica":
            memory = open_copy()
            try:
                old = SCENARIOS[scenario_name]["initial"]
                folded, exact = normalize_pair(old + "," + incoming)
                memory.cursor.execute(
                    "UPDATE largo_plazo SET sustantivos_clave=?, sustantivos_clave_exactos=? "
                    "WHERE concepto=?", (folded, exact, TARGET),
                )
                memory.conn.commit()
            finally:
                memory.cerrar_sistema()

        readback = parse_json_result(tools["sustantivos"](concepto=TARGET))
        labels = current_labels(db)
        probes = [scenario["old_probe"], scenario["new_probe"], scenario["stable_probe"]]
        tag_hits = tag_fts_hits(db, probes)

        searches = {}
        for probe_name in ("old_probe", "new_probe", "stable_probe"):
            term = scenario[probe_name]
            second = scenario["stable_probe"] if term != scenario["stable_probe"] else scenario["new_probe"]
            response = tools["recordar"](
                query=term,
                sustantivos_clave=f"{term},{second}",
                completo=True,
                asociados=True,
                asociaciones_max=0,
                context_window=1,
                limite=10,
                usar_inferencia=False,
            )
            result = parse_json_result(response)
            primary = result.get("resultados", [])
            expanded = result.get("contexto_expandido", [])
            target_item = next((x for x in primary if x.get("concepto") == TARGET), None)
            if target_item is None:
                target_item = next((x for x in expanded if x.get("concepto") == TARGET), None)
            searches[probe_name] = {
                "target_found": target_item is not None,
                "target_rank": next((i + 1 for i, x in enumerate(primary) if x.get("concepto") == TARGET), None),
                "target_score": target_item.get("score_hibrido") if target_item else None,
                "associated_neighbors": sorted(
                    item.get("concepto") for item in (target_item or {}).get("asociaciones_enriquecidas", [])
                ),
                "expanded_neighbors": sorted(
                    item.get("concepto") for item in expanded
                    if item.get("concepto") in NEIGHBORS
                ),
            }
        return {
            "scenario": scenario_name,
            "policy": policy,
            "write_route": write_route,
            "write_status": write_response.get("status"),
            "readback_status": readback.get("status"),
            "labels": labels,
            "tag_fts_hits": tag_hits,
            "mcp_recall": searches,
            "neighbor_edges_seeded": len(NEIGHBORS),
        }


def main() -> None:
    capture = ToolCapture()
    write_mcp.register(capture)
    search_mcp.register(capture)
    with tempfile.TemporaryDirectory(prefix="e3_mcp_label_routes_") as tmp:
        root = Path(tmp)
        cases = []
        # El motor puede emitir trazas de diagnóstico durante la búsqueda;
        # mantenerlas fuera del JSON para que el artefacto sea reproducible.
        with contextlib.redirect_stdout(io.StringIO()):
            for scenario_name, scenario in SCENARIOS.items():
                seed = root / f"seed_{scenario_name}.db"
                create_seed(seed, scenario)
                for policy in ("reemplazo_actual", "acumulacion_sintetica"):
                    for route in ("actualizar", "agregar_sustantivos"):
                        cases.append(run_arm(
                            seed, root, scenario_name, scenario, policy, route, capture.tools
                        ))
        print(json.dumps({
            "synthetic_only": True,
            "user_databases_opened": 0,
            "source_data_copied": False,
            "engine_patches_applied": False,
            "backfill": False,
            "memory_merges_between_records": 0,
            "policy_selected": False,
            "neighbor_links_modified_outside_copies": False,
            "scenarios": list(SCENARIOS),
            "write_routes": ["actualizar", "agregar_sustantivos"],
            "read_routes": ["sustantivos", "recordar"],
            "assumption_notes": {
                "historia_util": "Las pistas exclusivas históricas siguen siendo pertinentes según el caso sintético.",
                "historia_contradicha": "El contenido mantiene el registro inicial y explicita que fue contradicho por la revisión posterior.",
                "accumulacion_sintetica": "Contrafactual SQL en la copia después de ejecutar la ruta MCP real; no es una ruta de producción.",
            },
            "cases": cases,
        }, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
