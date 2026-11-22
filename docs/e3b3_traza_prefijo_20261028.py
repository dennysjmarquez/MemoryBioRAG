#!/usr/bin/env python3
"""E3B3: observar tres búsquedas MCP sin modificar archivos ni locales del motor.

Cada búsqueda con traza y su control sin traza parten de copias idénticas de
la semilla sintética B3. Además se comprueba la respuesta íntegra contra los
resultados MCP registrados antes de instrumentar. La traza se limita a leer
variables de las líneas concretas de search.py; no altera llamadas ni scores.

PYTHONHASHSEED=0 BIORAG_NEURONA=0 python docs/e3b3_traza_prefijo_20261028.py \
    --semilla /tmp/biorag-e3b3-qa/semilla_b3.db --salida /tmp/trazas.json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEARCH = (ROOT / "core/memory/search.py").resolve()
MCP_SEARCH = (ROOT / "core/mcp_server/search.py").resolve()
HUB = (ROOT / "core/concept_hub.py").resolve()
CASES = ROOT / "scripts/casos_qa_guardado_nativo_e3b2.jsonl"
REFERENCE = ROOT / "docs/e3b3_busquedas_hub_b3_base_b3_20261028.json"
IDS = ("zh-01", "zh-19", "ja-01")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pool_sin_score(rows, esperado):
    # `todos` usa (rowid, concepto, contenido, peso, estado, asociaciones).
    conceptos = [row[1] for row in rows]
    return {"total": len(conceptos), "conceptos": conceptos,
            "esperado_en_pool": esperado in conceptos}


def _pool_con_score(rows, origenes, esperado):
    # `resultados_con_hibrido` usa (concepto, contenido, peso, estado, score, asociaciones).
    registros = [{"concepto": row[0], "score": row[4], "origen": origenes.get(row[0])} for row in rows]
    coincidencias = [r for r in registros if r["concepto"] == esperado]
    return {"total": len(registros), "candidatos": registros,
            "esperado": coincidencias[0] if coincidencias else None}


class TrazaLectura:
    """Lee snapshots al entrar en una línea, sin modificar ningún local."""

    def __init__(self, esperado: str):
        self.esperado = esperado
        self.pasos = {}

    def __call__(self, frame, event, arg):
        if event != "call":
            return None
        code = frame.f_code
        if (Path(code.co_filename).resolve() == SEARCH and code.co_name == "buscar_por_frase") or (
            Path(code.co_filename).resolve() == MCP_SEARCH and code.co_name == "_recordar_impl"
        ):
            return self.lineas
        return None

    def lineas(self, frame, event, arg):
        if event != "line":
            return self.lineas
        code, line, loc = frame.f_code, frame.f_lineno, frame.f_locals
        esperado = self.esperado
        if code.co_name == "buscar_por_frase":
            origenes = loc.get("origen_scores", {})
            if line == 218:
                self.pasos["expansion_hub"] = {"archivo_linea": "core/memory/search.py:217-218",
                    "valor": loc.get("hub_expansion")}
            elif line == 1688:
                self.pasos["pool_antes_de_score"] = {"archivo_linea": "core/memory/search.py:1686-1690",
                    **_pool_sin_score(loc.get("todos", []), esperado)}
            elif line == 1976:
                self.pasos["antes_de_promocion_hub"] = {"archivo_linea": "core/memory/search.py:1976-1981",
                    **_pool_con_score(loc.get("resultados_con_hibrido", []), origenes, esperado)}
            elif line == 2001:
                self.pasos["decision_promocion"] = {"archivo_linea": "core/memory/search.py:1979-2001",
                    "ya_existia": loc.get("ya_existe"), "hub_gana": loc.get("hub_gana"),
                    "score_forzado": loc.get("score_forzado"), "score_promocion": loc.get("score_promocion")}
            elif line == 2010:
                row = loc.get("row")
                self.pasos["consulta_canonico"] = {"archivo_linea": "core/memory/search.py:2004-2010",
                    "recuperado_de_sql": bool(row), "concepto": row[0] if row else None}
            elif line == 2053:
                self.pasos["despues_de_promocion_hub"] = {"archivo_linea": "core/memory/search.py:2011-2053",
                    **_pool_con_score(loc.get("resultados_con_hibrido", []), origenes, esperado)}
            elif line == 2074:
                self.pasos["entrada_filtro_prefijo"] = {"archivo_linea": "core/memory/search.py:2073-2074",
                    "query_words": list(loc.get("query_words", [])),
                    **_pool_con_score(loc.get("resultados_con_hibrido", []), origenes, esperado)}
            elif line == 2081:
                literales = [row[0] for row in loc.get("literal_results", [])]
                no_literales = [row[0] for row in loc.get("non_literal_results", [])]
                self.pasos["clasificacion_prefijo"] = {"archivo_linea": "core/memory/search.py:2076-2081",
                    "literal_results": literales, "non_literal_results": no_literales,
                    "esperado_tratado_como_literal": esperado in literales}
            elif line == 2092:
                self.pasos["respuesta_sql_prefijo"] = {"archivo_linea": "core/memory/search.py:2084-2092",
                    "validos": sorted(loc.get("validos", set())),
                    "esperado_en_validos": esperado in loc.get("validos", set())}
            elif line == 2112:
                # 2112 es la primera línea ejecutable tras el filtro; 2111 es solo `if (`.
                self.pasos["despues_filtro_prefijo"] = {"archivo_linea": "core/memory/search.py:2091-2092",
                    **_pool_con_score(loc.get("resultados_con_hibrido", []), origenes, esperado)}
            elif line == 2164:
                self.pasos["pagina_motor"] = {"archivo_linea": "core/memory/search.py:2161-2163",
                    **_pool_con_score(loc.get("pagina_base", []), origenes, esperado)}
            elif line == 2342:
                self.pasos["salida_motor"] = {"archivo_linea": "core/memory/search.py:2334-2345",
                    **_pool_con_score(loc.get("pagina_resultados", []), origenes, esperado)}
        elif code.co_name == "_recordar_impl":
            if line == 495:
                rows = loc.get("resultados", [])
                self.pasos["entrada_mcp"] = {"archivo_linea": "core/mcp_server/search.py:480-495",
                    "conceptos": [row[0] for row in rows], "esperado": any(row[0] == esperado for row in rows)}
            elif line == 593:
                rows = loc.get("resultados", [])
                self.pasos["gate_mcp"] = {"archivo_linea": "core/mcp_server/search.py:585-596",
                    "resultados_antes_del_umbral": len(rows), "umbral_invocado": bool(rows)}
        return self.lineas


async def ejecutar(semilla: Path, ids: tuple[str, ...]) -> dict:
    from mcp.server.fastmcp import FastMCP
    from core.mcp_server.search import register as register_search
    from core.mcp_server.write import register as register_write
    from scripts.evaluar_qa_guardado_y_busqueda_b3 import consultas_de_caso, recordar
    from scripts.evaluar_qa_multilingue_e3a import RELOJ_FIJO

    registro = json.loads(REFERENCE.read_text(encoding="utf-8"))
    semilla_sha = registro["metadatos"]["semilla"]["sha256"]
    if sha256(semilla) != semilla_sha:
        raise ValueError("La semilla difiere de las 414 consultas ya medidas")
    corpus = {c["id"]: c for c in map(json.loads, CASES.read_text(encoding="utf-8").splitlines())}
    referencia = {(c["id"], c["tipo"]): c for c in registro["casos"]}
    codigo = {str(p.relative_to(ROOT)): sha256(p) for p in (SEARCH, MCP_SEARCH, HUB)}
    mcp = FastMCP("E3B3-traza-observacional")
    register_write(mcp)
    register_search(mcp)
    resultados = []
    with tempfile.TemporaryDirectory(prefix="biorag_e3b3_traza_") as tmp, patch("time.time", return_value=RELOJ_FIJO):
        tmp = Path(tmp)
        for ident in ids:
            caso = corpus[ident]
            consulta = consultas_de_caso(caso)["puente_completo"]
            esperado = caso["concepto"].lower().replace(" ", "_").strip()
            control = await recordar(mcp, caso, consulta, "on", semilla,
                                     tmp / f"{ident}_control.db", tmp / f"{ident}_control.json")
            observador = TrazaLectura(esperado)
            trace_previo = sys.gettrace()
            if trace_previo is not None:
                raise RuntimeError("Ya hay otra traza activa; no se la reemplaza")
            try:
                sys.settrace(observador)
                observado = await recordar(mcp, caso, consulta, "on", semilla,
                                           tmp / f"{ident}_traza.db", tmp / f"{ident}_traza.json")
            finally:
                sys.settrace(trace_previo)
            ref = referencia[(ident, "puente_completo")]["on"]
            igual_control = observado == control
            igual_referencia = observado == ref
            if not igual_control or not igual_referencia:
                raise RuntimeError(f"{ident}: el observador o la reproducción cambió la respuesta")
            obligatorios = ("expansion_hub", "pool_antes_de_score", "antes_de_promocion_hub",
                            "decision_promocion", "despues_de_promocion_hub", "entrada_filtro_prefijo",
                            "clasificacion_prefijo", "respuesta_sql_prefijo", "despues_filtro_prefijo",
                            "pagina_motor", "salida_motor", "entrada_mcp", "gate_mcp")
            faltantes = [x for x in obligatorios if x not in observador.pasos]
            if faltantes:
                raise RuntimeError(f"{ident}: no se observaron las líneas {faltantes}")
            resultados.append({"id": ident, "idioma": caso["idioma"], "concepto": caso["concepto"],
                               "query": consulta["query"], "sustantivos_clave": consulta["sustantivos_clave"],
                               "respuesta_traza_igual_a_control_y_referencia": True,
                               "respuesta_mcp": observado["respuesta"], "pasos": observador.pasos})
            print(f"{ident}: respuesta con traza = control = referencia; {len(observador.pasos)} pasos", flush=True)
    if sha256(semilla) != semilla_sha or any(sha256(ROOT/p) != h for p, h in codigo.items()):
        raise RuntimeError("La semilla o algún archivo de motor cambió durante la traza")
    return {"metadatos": {"semilla_sha256": semilla_sha, "sha256_archivos": codigo,
                           "observador": "sys.settrace de solo lectura en dos funciones; sin escribir variables del motor",
                           "reloj_fijo_unix": RELOJ_FIJO, "pythonhashseed": "0", "biorag_neurona": "0",
                           "control": "copia independiente sin traza + respuesta completa de las 414 consultas registradas",
                           "parametros": "FastMCP en proceso; activos, límite público 5, pool interno 15, peso predeterminado, hub ON"},
            "casos": resultados}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Usar PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    data = asyncio.run(ejecutar(args.semilla, IDS))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for c in data["casos"]:
        p = c["pasos"]
        print(c["id"], "pool previo", p["pool_antes_de_score"]["esperado_en_pool"],
              "score tras hub", (p["despues_de_promocion_hub"]["esperado"] or {}).get("score"),
              "literal", p["clasificacion_prefijo"]["esperado_tratado_como_literal"],
              "válido prefijo", p["respuesta_sql_prefijo"]["esperado_en_validos"],
              "en pool después", bool(p["despues_filtro_prefijo"]["esperado"]),
              "umbral invocado", p["gate_mcp"]["umbral_invocado"])
    print("Salida:", args.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
