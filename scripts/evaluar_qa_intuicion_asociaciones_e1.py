#!/usr/bin/env python3
"""QA E1 de intuición/asociaciones, pendiente de autorización de ejecución.

No correr hasta que Dennys autorice expresamente la medición y apruebe sus
umbrales. Cuando se autorice:
  PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_intuicion_asociaciones_e1.py \\
      --ejecutar --salida /ruta/segura/qa_e1.json

El arnés llama tools MCP por transporte stdio contra FastMCP real. Su launcher
solo evita el spawn del daemon global y exige que la DB sea temporal.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict, deque
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import sqlite3
import sys
import tempfile
import time
import unicodedata
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLD = ROOT / "scripts" / "casos_qa_intuicion_asociaciones_e1.jsonl"
ALLOWED_SEARCH_WRITES = {"log_busquedas", "nodo_accesos_historial"}
GRAPH_TABLES = {"largo_plazo", "corto_plazo", "sinapsis", "concept_hub_bridges", "concept_hub_nodes"}
BRIDGE_ANGLES = ("sinonimo", "problema", "solucion", "situacion", "ingenuo")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fold_text(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(c))


def load_gold(path: Path = GOLD) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 88 or len({x.get("episode_id") for x in rows}) != 88:
        raise ValueError("Gold debe contener 88 episodios con IDs únicos")
    counts = Counter(x["stratum"] for x in rows)
    expected = {
        "objetivo_directo": 12, "parafrasis_contexto": 12,
        "pista_1_salto": 12, "pista_baja_coincidencia_2_saltos": 12,
        "negativo_asunto_ausente": 10, "negativo_colision_lexica": 10,
        "negativo_arista_engañosa": 10, "negativo_hub_generico": 10,
    }
    if counts != Counter(expected):
        raise ValueError(f"Estratos gold inesperados: {counts}")
    route_count = sum(ep.get("ruta_2_saltos") is not None for ep in rows)
    if route_count != 12 or sum(bool(ep["positivo"]) for ep in rows) != 48:
        raise ValueError("El gold debe conservar 48 positivos y 12 rutas etiquetadas de dos saltos")
    query_ids, concepts = set(), set()
    total_queries = 0
    for ep in rows:
        expected_queries = 3 if ep["positivo"] else 2
        if len(ep["consultas"]) != expected_queries:
            raise ValueError(f"Número de consultas incorrecto: {ep['episode_id']}")
        if (ep["stratum"] == "pista_baja_coincidencia_2_saltos") != bool(ep.get("ruta_2_saltos")):
            raise ValueError(f"Ruta 2-hop y estrato no coinciden: {ep['episode_id']}")
        if not ep["nodos"] or not ep["consultas"]:
            raise ValueError(f"Episodio incompleto: {ep['episode_id']}")
        local = {n["concepto"] for n in ep["nodos"]}
        if len(local) != len(ep["nodos"]):
            raise ValueError(f"Conceptos duplicados en {ep['episode_id']}")
        if concepts.intersection(local):
            raise ValueError(f"Concepto repetido entre episodios: {ep['episode_id']}")
        concepts.update(local)
        if ep["ancla"] not in local:
            raise ValueError(f"Ancla fuera del episodio: {ep['episode_id']}")
        for edge in ep["aristas_gold"]:
            if len(edge) != 2 or not set(edge) <= local:
                raise ValueError(f"Arista gold inválida: {ep['episode_id']} {edge}")
        route = ep.get("ruta_2_saltos")
        if route:
            if set(route) != {"objetivo", "intermedio", "pista"} or not set(route.values()) <= local:
                raise ValueError(f"Ruta gold inválida: {ep['episode_id']}")
            if [route["objetivo"], route["intermedio"]] not in ep["aristas_gold"] or [route["intermedio"], route["pista"]] not in ep["aristas_gold"]:
                raise ValueError(f"Ruta gold no coincide con aristas: {ep['episode_id']}")
        for n in ep["nodos"]:
            terms = n["sustantivos_clave"].split(",")
            if not 2 <= len(terms) <= 10:
                raise ValueError(f"Sustantivos fuera de rango: {n['concepto']}")
            if any(not t or len(t) > 15 or not t.replace("_", "").isalnum() for t in terms):
                raise ValueError(f"Formato de sustantivos inválido: {n['concepto']}")
            if any(fold_text(t) not in fold_text(n["contenido"]) for t in terms):
                raise ValueError(f"Sustantivos de escritura no respaldados por el recuerdo: {n['concepto']}")
        for q in ep["consultas"]:
            total_queries += 1
            if q.get("idioma") not in {"es", "en"}:
                raise ValueError(f"Idioma ausente o no admitido: {q.get('query_id')}")
            if q["query_id"] in query_ids:
                raise ValueError(f"query_id duplicado: {q['query_id']}")
            query_ids.add(q["query_id"])
            if any(t.lower() not in q["query"].lower() for t in q["sustantivos_clave"].split(",")):
                raise ValueError(f"Término de búsqueda no presente en la pregunta: {q['query_id']}")
            tags = set(q["objetivos_principales"]) | set(q["relacionados_utiles"]) | set(q["ruido_tonto"])
            if not tags <= local:
                raise ValueError(f"Etiqueta fuera del episodio: {q['query_id']}")
            if set(q["objetivos_principales"]) & set(q["ruido_tonto"]):
                raise ValueError(f"Objetivo y ruido se solapan: {q['query_id']}")
    if total_queries != 224:
        raise ValueError(f"Se esperaban 224 consultas lógicas, hay {total_queries}")
    language_counts = Counter(q.get("idioma") for ep in rows for q in ep["consultas"])
    if language_counts != Counter({"es": 172, "en": 52}):
        raise ValueError(f"Desglose de idioma gold inesperado: {language_counts}")
    return rows


def all_queries(episodes: list[dict]) -> list[tuple[dict, dict]]:
    return [(ep, q) for ep in episodes for q in ep["consultas"]]


def ordered_queries(episodes: list[dict], mode: str) -> list[tuple[dict, dict]]:
    """A/B/C: roles/posiciones en bloques; D: episodio-secuencia; D-inv: episodios inversos."""
    if mode in {"A", "B", "C1", "C2"}:
        indexed = [(ep, q, i) for ep in episodes for i, q in enumerate(ep["consultas"])]
        return [(ep, q) for ep, q, _ in sorted(indexed, key=lambda row: (row[2], row[0]["episode_id"]))]
    ordered_eps = list(episodes if mode == "D" else reversed(episodes))
    return [(ep, q) for ep in ordered_eps for q in ep["consultas"]]


def bridge_payload(concept: str) -> list[dict]:
    # Bridges con una marca namespaced para evitar colisiones entre hubs sintéticos.
    marker = " ".join(concept.split("_")[-3:])
    texts = (f"significado equivalente {marker}", f"problema recurrente {marker}",
             f"solucion operativa {marker}", f"escenario practico {marker}",
             f"consulta sencilla {marker}")
    return [{"angle": angle, "text": text} for angle, text in zip(BRIDGE_ANGLES, texts)]


def parse_tool_result(result) -> tuple[str, dict]:
    is_error = bool(getattr(result, "isError", False))
    blocks = getattr(result, "content", None)
    if not isinstance(blocks, (list, tuple)):
        raise TypeError(f"Respuesta MCP sin bloques content: {type(result).__name__}")
    raw = "\n".join(getattr(block, "text", "") for block in blocks)
    starts = [i for i, char in enumerate(raw) if char == "{"]
    for start in reversed(starts):
        try:
            obj = json.loads(raw[start:])
            if isinstance(obj, dict):
                if is_error:
                    obj["_mcp_is_error"] = True
                return raw, obj
        except json.JSONDecodeError:
            continue
    if is_error:
        return raw, {"status": "mcp_error", "_mcp_is_error": True, "mensaje": raw[:400]}
    raise ValueError(f"Respuesta MCP sin objeto JSON: {raw[:400]}")


class MCPProcess:
    """Una sesión del protocolo MCP stdio real apuntada forzosamente al temporal."""
    def __init__(self, db_path: Path, temp_root: Path):
        self.db_path = db_path.resolve()
        self.temp_root = temp_root.resolve()
        try:
            self.db_path.relative_to(self.temp_root)
        except ValueError as exc:
            raise RuntimeError(f"Guardrail local: DB fuera del temporal: {self.db_path}") from exc

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        env = os.environ.copy()
        state_key = hashlib.sha256(str(self.db_path).encode()).hexdigest()[:16]
        env.update({
            "BIORAG_PATH": str(self.db_path),
            "BIORAG_QA_TEMP_ROOT": str(self.temp_root),
            "BIORAG_DMN_ESTADO_PATH": str(self.temp_root / "dmn" / (state_key + ".json")),
            "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
            "BIORAG_MCP_AUTO_PARAFRASIS": "0",
            "BIORAG_MCP_AUTO_DIMS": "0",
            "BIORAG_NEURONA": "0",
            "BIORAG_NO_LOG": "0",
            "BIORAG_QA_RELOJ_FIJO": "1793059200.0",
        })
        Path(env["BIORAG_DMN_ESTADO_PATH"]).parent.mkdir(parents=True, exist_ok=True)
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "qa_stdio_server_intuicion.py")],
            env=env,
            cwd=str(ROOT),
        )
        self._stdio = stdio_client(params)
        self._read, self._write = await self._stdio.__aenter__()
        self._session = ClientSession(self._read, self._write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self._session.__aexit__(exc_type, exc, tb)
        finally:
            await self._stdio.__aexit__(exc_type, exc, tb)

    async def call(self, name: str, arguments: dict) -> tuple[str, dict]:
        result = await self._session.call_tool(name, arguments=arguments)
        return parse_tool_result(result)


def readonly_snapshot(path: Path) -> dict[str, str]:
    """SHA por tabla de toda la DB; abre solo la copia sintética en modo read-only."""
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        out = {}
        for table in tables:
            # Los nombres provienen del catálogo local; quote defensivo de identificador.
            ident = '"' + table.replace('"', '""') + '"'
            rows = con.execute(f"SELECT * FROM {ident}").fetchall()
            blob = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=repr, separators=(",", ":")).encode()
            out[table] = hashlib.sha256(blob).hexdigest()
        return out
    finally:
        con.close()


def snapshot_sha256(path: Path) -> str:
    payload = json.dumps(readonly_snapshot(path), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def fixture_node_text(path: Path) -> dict[str, str]:
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return {concept: content or "" for concept, content in
                con.execute("SELECT concepto, contenido FROM largo_plazo")}
    finally:
        con.close()


def graph_snapshot(path: Path) -> tuple[set[str], dict[str, set[str]], str]:
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        nodes = {r[0] for r in con.execute("SELECT concepto FROM largo_plazo WHERE estado='activo'")}
        adjacency: dict[str, set[str]] = defaultdict(set)
        for a, b in con.execute("SELECT origen, destino FROM sinapsis"):
            # expandir_contexto_vecinos consulta ambos sentidos de cada fila.
            if a in nodes and b in nodes:
                adjacency[a].add(b)
                adjacency[b].add(a)
        check = con.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"Fixture temporal corrupta: {check}")
        return nodes, adjacency, check
    finally:
        con.close()


def shortest_path(adjacency: dict[str, set[str]], start: str, goal: str) -> list[str] | None:
    if start == goal:
        return [start]
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        for neighbor in sorted(adjacency.get(node, ())):
            if neighbor in seen:
                continue
            new_path = path + [neighbor]
            if neighbor == goal:
                return new_path
            seen.add(neighbor)
            queue.append((neighbor, new_path))
    return None


def response_concepts(value, known: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in known:
                found.add(key)
            if key in {"concepto", "concept", "node", "nombre"} and isinstance(item, str) and item in known:
                found.add(item)
            found.update(response_concepts(item, known))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(response_concepts(item, known))
    elif isinstance(value, str) and value in known:
        found.add(value)
    return found


def attribute_two_hop(ep: dict, q: dict, response: dict, adjacency: dict[str, set[str]], known: set[str], max_depth: int) -> dict:
    route = ep.get("ruta_2_saltos")
    candidate = route["pista"] if route else None
    if not route:
        return {"estado": "no aplica", "motivo": "consulta sin ruta gold de dos saltos"}
    if route["pista"] not in set(q.get("objetivos_principales", [])) | set(q.get("relacionados_utiles", [])):
        return {"estado": "no aplica", "motivo": "pista no está etiquetada como relevante para esta consulta"}
    if max_depth < 2:
        return {"estado": "no atribuible", "motivo": "condición sin expansión de dos saltos"}
    primaries = response_concepts(response.get("resultados", []), known)
    context = response_concepts(response.get("contexto_expandido", []), known)
    if candidate not in context:
        return {"estado": "no atribuible", "motivo": "pista no aparece en contexto_expandido"}
    anchor = route["objetivo"]
    if anchor not in primaries:
        return {"estado": "no atribuible", "motivo": "objetivo/ancla no está entre las semillas devueltas"}
    path = shortest_path(adjacency, anchor, candidate)
    if path is None or len(path) - 1 != 2:
        return {"estado": "no atribuible", "motivo": "ruta efectiva desde el objetivo no tiene exactamente dos saltos", "ruta_efectiva": path}
    if path != [route["objetivo"], route["intermedio"], route["pista"]]:
        return {"estado": "no atribuible", "motivo": "la ruta efectiva no coincide con la ruta gold congelada", "ruta_efectiva": path}
    seed_paths = {seed: shortest_path(adjacency, seed, candidate) for seed in primaries}
    shortcut = {seed: p for seed, p in seed_paths.items() if p is not None and len(p) - 1 < 2}
    if shortcut:
        return {"estado": "no atribuible", "motivo": "otra semilla devuelta ofrece una ruta más corta", "ruta_efectiva": path, "atajos_desde_semillas": shortcut}
    return {
        "estado": "atribuible_2_saltos",
        "motivo": "pista en contexto_expandido y ruta efectiva comprobada desde el objetivo",
        "ruta_efectiva": path,
        "coincide_ruta_gold": path == [route["objetivo"], route["intermedio"], route["pista"]],
        "distancia_minima": 2,
    }


def copy_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


async def build_fixture(db_path: Path, temp_root: Path, episodes: list[dict]) -> dict:
    if db_path.exists():
        raise FileExistsError(db_path)
    keys = {n["concepto"] for ep in episodes for n in ep["nodos"]}
    tool_log = []
    async with MCPProcess(db_path, temp_root) as mcp:
        for ep in episodes:
            for node in ep["nodos"]:
                preflight_query = node["concepto"] + " " + node["contenido"]
                raw, prior = await mcp.call("recordar", {
                    "query": preflight_query, "sustantivos_clave": node["sustantivos_clave"],
                    "deep": False, "limite": 5, "asociados": False, "context_window": 0,
                })
                exact = [r for r in prior.get("resultados", []) if r.get("concepto") == node["concepto"]]
                if exact:
                    raise RuntimeError(f"Preflight halló duplicado en fixture nueva: {node['concepto']}")
                tool_log.append({"tool": "recordar", "concepto": node["concepto"], "respuesta_cruda": raw})
                bridges = bridge_payload(node["concepto"])
                raw, learned = await mcp.call("aprender", {
                    "concepto": node["concepto"], "contenido": node["contenido"],
                    "bridges": bridges, "sustantivos_clave": node["sustantivos_clave"],
                    "cat": "General", "busqueda_previa": True,
                })
                if learned.get("status") != "ok" or learned.get("concepto") != node["concepto"]:
                    raise RuntimeError(f"aprender MCP no confirmó {node['concepto']}: {learned}")
                tool_log.append({"tool": "aprender", "concepto": node["concepto"], "respuesta_cruda": raw,
                                 "puentes": bridges, "sinapsis_auto_reportadas": learned.get("sinapsis")})
            raw, consolidated = await mcp.call("consolidar", {})
            if consolidated.get("status") != "ok":
                raise RuntimeError(f"consolidar MCP falló para {ep['episode_id']}: {consolidated}")
            tool_log.append({"tool": "consolidar", "episode_id": ep["episode_id"], "respuesta_cruda": raw})
            for a, b in ep["aristas_gold"]:
                raw, linked = await mcp.call("vincular", {"a": a, "b": b})
                if linked.get("status") != "ok":
                    raise RuntimeError(f"vincular MCP falló ({a}, {b}): {linked}")
                tool_log.append({"tool": "vincular", "a": a, "b": b, "respuesta_cruda": raw})
    nodes, adjacency, integrity = graph_snapshot(db_path)
    missing = keys - nodes
    if missing:
        raise RuntimeError(f"Recuerdos no consolidados: {sorted(missing)[:10]}")
    route_checks = {}
    for ep in episodes:
        route = ep.get("ruta_2_saltos")
        if route:
            path = shortest_path(adjacency, route["objetivo"], route["pista"])
            route_checks[ep["episode_id"]] = {
                "ruta_gold": [route["objetivo"], route["intermedio"], route["pista"]],
                "ruta_efectiva": path,
                "distancia_minima": len(path) - 1 if path else None,
                "prevalidada_exactamente_2": path == [route["objetivo"], route["intermedio"], route["pista"]],
            }
    return {"integridad": integrity, "sha256_fixture_logica": snapshot_sha256(db_path),
            "nodos_esperados": len(keys), "nodos_activos": len(nodes),
            "llamadas_construccion": len(tool_log), "registro_tools": tool_log,
            "validacion_rutas": route_checks}


def metrics_by_channel(outputs: list[dict]) -> dict:
    summary = {}
    channel_names = ("resultados", "asociaciones_enriquecidas", "asociaciones", "contexto_expandido", "union_canales")
    for channel in channel_names:
        objective_rows = [o for o in outputs if o["objetivos_principales"]]
        numerator_useful = denominator_useful = noise = lateral_total = 0
        for row in outputs:
            visible = (set().union(*row["canales"].values()) if channel == "union_canales"
                       else set(row["canales"][channel]))
            expected_useful = set(row["relacionados_utiles"])
            numerator_useful += len(visible & expected_useful)
            denominator_useful += len(expected_useful)
            noise += len(visible & set(row["ruido_tonto"]))
            if channel != "resultados":
                lateral_total += len(visible - set(row["objetivos_principales"]))
        result = {
            "consultas": len(outputs),
            "objetivo_visible_consultas": sum(bool(set(o["objetivos_principales"]) & set(o["canales"][channel])) for o in objective_rows),
            "relacionados_utiles_visibles": numerator_useful,
            "relacionados_utiles_gold": denominator_useful,
            "recall_relacionados_utiles": numerator_useful / denominator_useful if denominator_useful else None,
            "ruido_tonto_visible": noise,
        }
        episodes_with_useful_gold = {o["episode_id"] for o in outputs if o["relacionados_utiles"]}
        episodes_with_useful_visible = {
            o["episode_id"] for o in outputs
            if set(o["relacionados_utiles"]) & (
                set().union(*o["canales"].values()) if channel == "union_canales" else set(o["canales"][channel])
            )
        }
        result["episodios_con_pista_util_visible"] = len(episodes_with_useful_visible)
        result["episodios_con_pista_util_gold"] = len(episodes_with_useful_gold)
        result["cobertura_pista_por_episodio"] = (
            len(episodes_with_useful_visible & episodes_with_useful_gold) / len(episodes_with_useful_gold)
            if episodes_with_useful_gold else None
        )
        if channel == "resultados":
            ranks = [o["rango_objetivo_resultados"] for o in objective_rows]
            result.update({
                "objetivos_evaluables": len(objective_rows),
                "R_at_1": sum(r == 1 for r in ranks) / len(ranks) if ranks else None,
                "R_at_5": sum(r is not None and r <= 5 for r in ranks) / len(ranks) if ranks else None,
                "MRR_at_5": sum((1 / r) if r is not None and r <= 5 else 0 for r in ranks) / len(ranks) if ranks else None,
                "falsos_positivos_consultas_sin_objetivo": sum(
                    bool(o["ranking_resultados"]) for o in outputs if not o["objetivos_principales"]
                ),
                "consultas_sin_objetivo": sum(not o["objetivos_principales"] for o in outputs),
            })
        else:
            result["candidatos_laterales_visibles"] = lateral_total
            result["precision_utilidad_gold_parcial"] = numerator_useful / lateral_total if lateral_total else None
        summary[channel] = result
    return summary


async def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * p + 0.999999)))
    return ordered[index]


async def run_arm(db_path: Path, temp_root: Path, episodes: list[dict], mode: str,
                  adjacency: dict[str, set[str]], known: set[str]) -> dict:
    before = readonly_snapshot(db_path)
    ordered = ordered_queries(episodes, mode)
    outputs = []
    started = time.perf_counter()
    context_window = 0 if mode in {"A", "B"} else 1 if mode == "C1" else 2
    associated = mode != "A"
    async with MCPProcess(db_path, temp_root) as mcp:
        for ep, q in ordered:
            transport_error = None
            call_started = time.perf_counter()
            try:
                raw, parsed = await mcp.call("recordar", {
                    "query": q["query"], "sustantivos_clave": q["sustantivos_clave"],
                    "deep": False, "asociados": associated, "limite": 5,
                    "context_window": context_window, "forzar_rafaga": False,
                })
            except Exception as exc:
                raw = ""
                parsed = {"status": "transport_error", "_mcp_is_error": True,
                          "mensaje": f"{type(exc).__name__}: {exc}"}
                transport_error = parsed["mensaje"]
            latency_ms = round((time.perf_counter() - call_started) * 1000, 3)
            output_bytes = len(raw.encode("utf-8"))
            channels = {
                "resultados": response_concepts(parsed.get("resultados", []), known),
                "contexto_expandido": response_concepts(parsed.get("contexto_expandido", []), known),
                "asociaciones_enriquecidas": set(),
                "asociaciones": set(),
            }
            # Ambos canales laterales vienen adjuntos a cada resultado principal.
            for result in parsed.get("resultados", []):
                if isinstance(result, dict):
                    channels["asociaciones"].update(response_concepts(result.get("asociaciones", {}), known))
                    channels["asociaciones_enriquecidas"].update(
                        response_concepts(result.get("asociaciones_enriquecidas", []), known)
                    )
            rank = next((i + 1 for i, x in enumerate(parsed.get("resultados", []))
                         if isinstance(x, dict) and x.get("concepto") in q["objetivos_principales"]), None)
            route_attr = attribute_two_hop(ep, q, parsed, adjacency, known, context_window)
            outputs.append({
                "episode_id": ep["episode_id"], "query_id": q["query_id"],
                "stratum": ep["stratum"], "idioma": q["idioma"], "positivo": ep["positivo"], "query": q["query"],
                "objetivos_principales": q["objetivos_principales"],
                "relacionados_utiles": q["relacionados_utiles"], "ruido_tonto": q["ruido_tonto"],
                "canales": {name: sorted(values) for name, values in channels.items()},
                "ranking_resultados": [x.get("concepto") for x in parsed.get("resultados", [])
                                       if isinstance(x, dict) and x.get("concepto") in known],
                "rango_objetivo_resultados": rank,
                "atribucion_dos_saltos": route_attr,
                "mcp_is_error": bool(parsed.get("_mcp_is_error")),
                "respuesta_status_error": parsed.get("status") in {"error", "mcp_error"},
                "error_transporte_o_parseo": transport_error,
                "respuesta_recibida": transport_error is None,
                "latencia_ms": latency_ms, "salida_bytes": output_bytes,
                "respuesta_parseada": parsed, "respuesta_mcp_cruda": raw,
            })
    after = readonly_snapshot(db_path)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    unexpected = [t for t in changed if t not in ALLOWED_SEARCH_WRITES]
    if unexpected:
        raise RuntimeError(f"Mutaciones inesperadas durante {mode}: {unexpected}")
    graph_changed = [t for t in changed if t in GRAPH_TABLES]
    if graph_changed:
        raise RuntimeError(f"Grafo/recuerdos mutaron durante recordar ({mode}): {graph_changed}")
    # R@/MRR solo se calculan sobre resultados; los canales laterales quedan separados.
    summary = metrics_by_channel(outputs)
    twohop_rows = [o for o in outputs if o["atribucion_dos_saltos"].get("estado") != "no aplica"]
    twohop = [o["atribucion_dos_saltos"] for o in twohop_rows]
    episodes_with_route = {o["episode_id"] for o in twohop_rows}
    attributed_episodes = {o["episode_id"] for o in twohop_rows
                           if o["atribucion_dos_saltos"].get("estado") == "atribuible_2_saltos"}
    return {
        "condicion": mode, "consultas_logicas": len(outputs), "llamadas_recordar_intentadas": len(outputs),
        "respuestas_mcp_recibidas": sum(o["respuesta_recibida"] for o in outputs),
        "llamadas_recordar_con_error": sum(o["mcp_is_error"] or o["respuesta_status_error"] for o in outputs),
        "orden_query_ids": [o["query_id"] for o in outputs],
        "orden_hash": hashlib.sha256("\n".join(o["query_id"] for o in outputs).encode()).hexdigest(),
        "latencia_ms": {
            "p50": percentile([o["latencia_ms"] for o in outputs], 0.50),
            "p95": percentile([o["latencia_ms"] for o in outputs], 0.95),
            "max": max((o["latencia_ms"] for o in outputs), default=None),
        },
        "salida_bytes": {
            "p50": percentile([o["salida_bytes"] for o in outputs], 0.50),
            "p95": percentile([o["salida_bytes"] for o in outputs], 0.95),
            "max": max((o["salida_bytes"] for o in outputs), default=None),
        },
        "escrituras_por_tabla": changed,
        "telemetria_esperada_cambiada": [t for t in changed if t in ALLOWED_SEARCH_WRITES],
        "atribuciones_2_saltos": {
            "episodios_gold": len(episodes_with_route),
            "episodios_con_al_menos_una_atribucion": len(attributed_episodes),
            "consultas_atribuibles": sum(x.get("estado") == "atribuible_2_saltos" for x in twohop),
            "consultas_no_atribuibles": sum(x.get("estado") == "no atribuible" for x in twohop),
            "detalle": [{"episode_id": o["episode_id"], "query_id": o["query_id"], **o["atribucion_dos_saltos"]}
                        for o in twohop_rows],
        },
        "metricas_por_canal": summary,
        "metricas_por_idioma": {
            language: metrics_by_channel([o for o in outputs if o["idioma"] == language])
            for language in ("es", "en")
        },
        "metricas_por_estrato": {
            stratum: metrics_by_channel([o for o in outputs if o["stratum"] == stratum])
            for stratum in sorted({o["stratum"] for o in outputs})
        },
        "duracion_s": round(time.perf_counter() - started, 3),
        "salidas": outputs,
    }


def write_blind_annotation_packets(arms: dict, episodes: list[dict], output_path: Path,
                                   node_text: dict[str, str]) -> dict:
    """Escribe dos lotes ciegos y un crosswalk privado para adjudicación."""
    query_info = {q["query_id"]: q for ep in episodes for q in ep["consultas"]}
    query_candidates: dict[str, set[str]] = defaultdict(set)
    for arm in arms.values():
        for row in arm["salidas"]:
            qid = row["query_id"]
            for concepts in row["canales"].values():
                query_candidates[qid].update(concepts)
    salt = secrets.token_hex(24)
    crosswalk = {"sal": salt, "casos": {}, "candidatos": {}}
    base_rows = []
    for qid, concepts in query_candidates.items():
        cid = hashlib.sha256((salt + "query:" + qid).encode()).hexdigest()[:16]
        crosswalk["casos"][cid] = qid
        for concept in sorted(concepts):
            if concept not in node_text:
                continue
            item_id = hashlib.sha256((salt + "node:" + concept).encode()).hexdigest()[:16]
            crosswalk["candidatos"][item_id] = concept
            base_rows.append({
                "case_id": cid, "idioma": query_info[qid]["idioma"],
                "query": query_info[qid]["query"], "candidate_id": item_id,
                "candidate_text": node_text[concept], "rating_0_3": None,
                "etiqueta": None, "evidencia": "", "justificacion": "",
            })
    packets = {}
    for reviewer in ("revisor_1", "revisor_2"):
        rows = [dict(row) for row in base_rows]
        random.SystemRandom().shuffle(rows)
        path = output_path.parent / f"{output_path.stem}_{reviewer}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        packets[reviewer] = {"archivo": str(path), "filas": len(rows)}
    crosswalk_path = output_path.parent / f"{output_path.stem}_crosswalk_PRIVADO.json"
    crosswalk_path.write_text(json.dumps(crosswalk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"paquetes": packets, "crosswalk_privado": str(crosswalk_path),
            "instruccion": "No compartir el crosswalk ni el reporte completo con los anotadores."}


def run_async(episodes: list[dict], output_path: Path) -> dict:
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        raise RuntimeError("La ejecución requiere PYTHONHASHSEED=0 y BIORAG_NEURONA=0")
    output_path = output_path.resolve()
    try:
        output_path.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise RuntimeError("El reporte debe guardarse fuera del repositorio")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="biorag_qa_asociaciones_e1_") as raw_tmp:
        temp_root = Path(raw_tmp).resolve()
        fixture_path = temp_root / "fixture" / "base_sintetica.db"
        fixture_path.parent.mkdir(parents=True)
        build_meta = asyncio.run(build_fixture(fixture_path, temp_root, episodes))
        nodes, adjacency, _ = graph_snapshot(fixture_path)
        node_text = fixture_node_text(fixture_path)
        all_concepts = set(node_text)
        arms = {}
        template_snapshot = readonly_snapshot(fixture_path)
        for mode in ("A", "B", "C1", "C2", "D", "D-inv"):
            arm_db = temp_root / "runs" / mode / "run.db"
            copy_sqlite(fixture_path, arm_db)
            if readonly_snapshot(arm_db) != template_snapshot:
                raise RuntimeError(f"La copia inicial del brazo {mode} no coincide con la plantilla")
            arms[mode] = asyncio.run(run_arm(arm_db, temp_root, episodes, mode, adjacency, all_concepts))
        q_by_id = {q["query_id"]: q for ep in episodes for q in ep["consultas"]}
        d_map = {row["query_id"]: row for row in arms["D"]["salidas"]}
        inv_map = {row["query_id"]: row for row in arms["D-inv"]["salidas"]}
        order_diffs = []
        for query_id in q_by_id:
            left, right = d_map[query_id], inv_map[query_id]
            comparable_left = {"canales": left["canales"], "rango": left["rango_objetivo_resultados"],
                               "atribucion": left["atribucion_dos_saltos"]}
            comparable_right = {"canales": right["canales"], "rango": right["rango_objetivo_resultados"],
                                "atribucion": right["atribucion_dos_saltos"]}
            if comparable_left != comparable_right:
                order_diffs.append({"query_id": query_id, "D": comparable_left, "D-inv": comparable_right})
        d_order_expected = [q["query_id"] for _, q in ordered_queries(episodes, "D")]
        inv_order_expected = [q["query_id"] for _, q in ordered_queries(episodes, "D-inv")]
        if arms["D"]["orden_query_ids"] != d_order_expected or arms["D-inv"]["orden_query_ids"] != inv_order_expected:
            raise RuntimeError("La ejecución no respetó el orden fijo/inverso especificado")
        annotation_packets = write_blind_annotation_packets(arms, episodes, output_path, node_text)
        logical = sum(len(ep["consultas"]) for ep in episodes)
        total_searches = sum(a["llamadas_recordar_intentadas"] for a in arms.values())
        construction_calls = build_meta["llamadas_construccion"]
        if logical != 224 or total_searches != 1344 or construction_calls != 608:
            raise RuntimeError(f"Conteo protocolario inesperado: base={logical}, búsquedas={total_searches}, construcción={construction_calls}")
        report = {
            "estado": "sin_umbral_aplicado; métricas descriptivas para revisión",
            "gold_sha256": sha256(GOLD),
            "launcher": "FastMCP real por stdio; launcher aislado sin daemon global",
            "proteccion_db": "BIORAG_PATH temporal validado por servidor y cliente",
            "conteo": {
                "episodios": len(episodes), "consultas_logicas_base": logical,
                "llamadas_recordar_por_brazos": total_searches,
                "llamadas_mcp_construccion_fixture": construction_calls,
                "llamadas_mcp_totales": total_searches + construction_calls,
                "reintentos_automaticos": 0,
                "llamadas_recordar_esperadas": 1344,
            },
            "escrituras_esperadas_recordar": {
                "log_busquedas": "INSERT de telemetría y UPDATE de params_json por búsqueda textual exitosa",
                "nodo_accesos_historial": "accesos a recuerdos principales recuperados, con retención FIFO del motor",
                "otras_tablas": "ninguna permitida; cualquier diferencia contamina/falla la corrida",
            },
            "umbrales": "no fijados ni evaluados; requieren aprobación expresa de Dennys",
            "fixture": build_meta,
            "brazos": arms,
            "control_orden": {
                "comparacion": "D contra D-inv, emparejada por query_id; orden interno de cada episodio permanece fijo",
                "orden_original_hash": arms["D"]["orden_hash"],
                "orden_inverso_hash": arms["D-inv"]["orden_hash"],
                "consultas_con_salida_distinta": order_diffs,
                "diferencias": len(order_diffs),
            },
            "anotacion_ciega": annotation_packets,
            "duracion_total_s": round(time.perf_counter() - started, 3),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ejecutar", action="store_true", help="barrera explícita; ejecutar solo con autorización de Dennys")
    parser.add_argument("--salida", type=Path, help="archivo de reporte; se escribe solo si --ejecutar está presente")
    args = parser.parse_args()
    if not args.ejecutar:
        parser.error("QA NO ejecutada: requiere --ejecutar y autorización previa de Dennys")
    if not args.salida:
        parser.error("Indica --salida fuera del repositorio para el reporte de la futura corrida")
    episodes = load_gold()
    report = run_async(episodes, args.salida)
    print(json.dumps({"conteo": report["conteo"], "salida": str(args.salida)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
