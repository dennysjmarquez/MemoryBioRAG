#!/usr/bin/env python3
"""E3B2: 80 intentos de guardado con MCP y entradas nativas fijas.

PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_guardado_nativo_b2.py \
    --salida docs/e3b2_guardado_nativo_20261027.json

Usa FastMCP en proceso (valida el esquema y ejecuta las tools, sin transporte
stdio ni agente real); realiza una búsqueda previa real por cada caso. La base
es temporal y empieza vacía. Las etiquetas de escritura y los cinco puentes
sintéticos están fijados en un archivo aparte: no se cambian los gold de E3A ni
las etiquetas de búsqueda de B1. No se sustituyen puentes rechazados.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluar_qa_multilingue_e3a import RELOJ_FIJO, cargar_gold
from scripts.evaluar_qa_multilingue_mcp_e3a import parsear_mcp

CASOS = ROOT / "scripts" / "casos_qa_guardado_nativo_e3b2.jsonl"
IDIOMAS = ("zh", "ja", "ko", "ru")
ANGULOS = ("sinonimo", "problema", "solucion", "situacion", "ingenuo")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cargar_entradas(path: Path = CASOS) -> list[dict]:
    """Verifica la fuente fija sin corregir ni filtrar términos rechazables."""
    from core.mcp_server._shared import _sustantivo_valido
    from core.memory_store import normalizar_sustantivos_clave

    filas = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    requeridos = {"id", "idioma", "concepto", "contenido", "sustantivos_guardado",
                  "sustantivo_busqueda_previa", "bridges"}
    gold = {c["id"]: c for c in cargar_gold() if c["idioma"] in IDIOMAS and c["concepto"] is not None}
    if len(filas) != 80 or len({x["id"] for x in filas}) != 80 or set(gold) != {x["id"] for x in filas}:
        raise ValueError("Las entradas deben cubrir los 80 positivos nativos exactamente una vez")
    if Counter(x["idioma"] for x in filas) != Counter({i: 20 for i in IDIOMAS}):
        raise ValueError("Se requieren 20 recuerdos por idioma")
    for x in filas:
        if set(x) != requeridos or any(x[k] != gold[x["id"]][k] for k in ("idioma", "concepto", "contenido")):
            raise ValueError(f"Datos distintos del gold: {x['id']}")
        texto = (x["concepto"] + " " + x["contenido"]).lower()
        terms = x["sustantivos_guardado"].split(",")
        if not 2 <= len(terms) <= 10 or any(not t or t.lower() not in texto for t in terms):
            raise ValueError(f"Etiquetas no sustentadas en el recuerdo: {x['id']}")
        if not _sustantivo_valido(normalizar_sustantivos_clave(x["sustantivo_busqueda_previa"])):
            raise ValueError(f"La etiqueta elegida para la búsqueda previa no cumple B1: {x['id']}")
        bridges = x["bridges"]
        if len(bridges) != 5 or tuple(b["angle"] for b in bridges) != ANGULOS:
            raise ValueError(f"Formato de ángulos inesperado: {x['id']}")
        if x["idioma"] in ("zh", "ja") and any(any(c.isspace() for c in b["text"]) for b in bridges):
            raise ValueError(f"No insertar espacios en frases zh/ja: {x['id']}")
    return filas


def texto_tool(response) -> str:
    """FastMCP devuelve (bloques, salida estructurada); conserva el texto real."""
    blocks = response[0] if isinstance(response, tuple) else response
    if not isinstance(blocks, (list, tuple)):
        raise TypeError(f"Respuesta MCP inesperada: {type(blocks).__name__}")
    textos = [getattr(block, "text", None) for block in blocks]
    if not textos or any(t is None for t in textos):
        raise ValueError("Respuesta MCP sin bloques de texto")
    return "\n".join(textos)


async def ejecutar(filas: list[dict], path: Path) -> dict:
    from core.mcp_server.server import _build_server
    from core.memory_service import get_cerebro, reset_cerebro
    from core.memory_store import normalizar_sustantivos_clave
    from middleware.auto_guardado import buffer_global

    if path.exists():
        raise FileExistsError(path)
    env = {"BIORAG_PATH": str(path), "BIORAG_DMN_ESTADO_PATH": str(path.parent / "estado_hormiga.json"),
           "BIORAG_AUTOGUARDADO_HEURISTICO": "0", "BIORAG_MCP_AUTO_PARAFRASIS": "0",
           "BIORAG_MCP_AUTO_DIMS": "0"}
    registros = []
    with patch.dict(os.environ, env), patch("time.time", return_value=RELOJ_FIJO):
        reset_cerebro()
        mcp = _build_server()
        try:
            for pos, caso in enumerate(filas, 1):
                clave = caso["concepto"].lower().replace(" ", "_").strip()
                buffer_global.limpiar()
                previa_raw, previa, previa_excepcion = None, None, None
                try:
                    previa_raw = texto_tool(await mcp.call_tool("recordar", {
                        "query": caso["concepto"], "sustantivos_clave": caso["sustantivo_busqueda_previa"],
                        "deep": False, "limite": 5,
                    }))
                    previa = parsear_mcp(previa_raw)
                except Exception as exc:
                    previa_excepcion = f"{type(exc).__name__}: {exc}"
                busco = previa_excepcion is None and previa is not None and previa.get("status") != "error" and "resultados" in previa
                duplicado = busco and any(r.get("concepto") == clave for r in previa["resultados"])
                confirmacion = bool(busco and not duplicado)
                buffer_global.limpiar()
                raw, respuesta, excepcion = None, None, None
                try:
                    raw = texto_tool(await mcp.call_tool("aprender", {
                        "concepto": caso["concepto"], "contenido": caso["contenido"],
                        "dimensiones": None, "bridges": caso["bridges"],
                        "sustantivos_clave": caso["sustantivos_guardado"],
                        "cat": "General", "busqueda_previa": confirmacion,
                    }))
                    respuesta = parsear_mcp(raw)
                except Exception as exc:
                    excepcion = f"{type(exc).__name__}: {exc}"
                cerebro = get_cerebro(str(path))
                row_cp = cerebro.conn.execute(
                    "SELECT contenido, sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,)
                ).fetchone()
                row_lp = cerebro.conn.execute(
                    "SELECT contenido, sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,)
                ).fetchone()
                guardado = bool(row_cp or row_lp)
                status_ok = respuesta is not None and respuesta.get("status") == "ok"
                consolidado = False
                consolidacion_error = None
                hub_id = f"hub_{clave}"
                puentes_guardados = cerebro.conn.execute(
                    "SELECT COUNT(*) FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,)
                ).fetchone()[0]
                actual = row_cp or row_lp
                if status_ok and guardado and row_cp:
                    try:
                        consolidado = bool(cerebro.consolidar_concepto(clave))
                    except Exception as exc:
                        consolidacion_error = f"{type(exc).__name__}: {exc}"
                elif status_ok and row_lp:
                    consolidado = True
                codigo = (respuesta or {}).get("codigo")
                if excepcion:
                    primero = "EXCEPCION_MCP"
                elif not status_ok:
                    primero = codigo or "ERROR_SIN_CODIGO"
                elif not guardado:
                    primero = "RESPUESTA_OK_SIN_REGISTRO"
                else:
                    primero = None
                registros.append({
                    "id": caso["id"], "idioma": caso["idioma"], "concepto": caso["concepto"],
                    "sustantivos_guardado_entrada": caso["sustantivos_guardado"],
                    "sustantivos_normalizados": normalizar_sustantivos_clave(caso["sustantivos_guardado"]),
                    "sustantivos_en_db": actual[1] if actual else None,
                    "sustantivo_busqueda_previa": caso["sustantivo_busqueda_previa"],
                    "busqueda_previa_ejecutada": bool(busco), "busqueda_previa_duplicado_exacto": bool(duplicado),
                    "busqueda_previa_confirmada": confirmacion, "busqueda_previa": previa,
                    "busqueda_previa_respuesta_cruda": previa_raw, "busqueda_previa_excepcion": previa_excepcion,
                    "respuesta_aprender": respuesta, "respuesta_cruda": raw, "excepcion": excepcion,
                    "primer_rechazo": primero, "guardado_en_db": guardado,
                    "confirmado_por_mcp": status_ok, "consolidado": consolidado,
                    "error_consolidacion": consolidacion_error, "puentes_guardados": puentes_guardados,
                })
                print(f"{pos:02}/{len(filas)} {caso['id']} previa={'sí' if busco else 'no'} "
                      f"guardado={'sí' if guardado else 'no'} primer_rechazo={primero}", flush=True)
            integridad = cerebro.conn.execute("PRAGMA integrity_check").fetchone()[0]
            cp = cerebro.conn.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
            lp = cerebro.conn.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
            if integridad != "ok":
                raise RuntimeError(f"Integridad de base temporal: {integridad}")
        finally:
            buffer_global.limpiar()
            reset_cerebro()
    return {"casos": registros, "integridad": integridad, "nodos_corto": cp, "nodos_largo": lp}


def resumen(registros: list[dict]) -> dict:
    resultado = {}
    for idioma in IDIOMAS:
        filas = [r for r in registros if r["idioma"] == idioma]
        resultado[idioma] = {
            "intentos": len(filas), "busquedas_previas_ejecutadas": sum(r["busqueda_previa_ejecutada"] for r in filas),
            "guardados": sum(r["guardado_en_db"] for r in filas),
            "ok_mcp_y_guardado": sum(r["guardado_en_db"] and r["confirmado_por_mcp"] for r in filas),
            "consolidados": sum(r["consolidado"] for r in filas),
            "primeros_rechazos": dict(Counter(r["primer_rechazo"] for r in filas if r["primer_rechazo"])),
            "excepciones_tras_guardado": [r["id"] for r in filas if r["guardado_en_db"] and r["excepcion"]],
        }
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--sha-write", help="SHA-256 esperado de write.py al cargar el proceso")
    parser.add_argument("--write-source", type=Path, default=ROOT / "core/mcp_server/write.py",
                        help="Copia de write.py para medir una referencia sin modificar el árbol")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    write_source = args.write_source.resolve()
    write_sha = sha256(write_source)
    if args.sha_write and write_sha != args.sha_write:
        parser.error(f"write.py no tiene la huella esperada: {write_sha}")
    if write_source != (ROOT / "core/mcp_server/write.py").resolve():
        # Referencia B1: cambiar solo el módulo cargado, no los archivos del proyecto.
        import core.mcp_server as paquete
        if "core.mcp_server.server" in sys.modules or "core.mcp_server.write" in sys.modules:
            raise RuntimeError("El servidor o write.py se cargaron antes de seleccionar la referencia")
        spec = importlib.util.spec_from_file_location("core.mcp_server.write", write_source)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"No se puede cargar {write_source}")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = modulo
        spec.loader.exec_module(modulo)
        paquete.write = modulo
    filas = cargar_entradas()
    inicio = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="biorag_e3b2_mcp_guardado_") as tmp:
        datos = asyncio.run(ejecutar(filas, Path(tmp) / "sintetica.db"))
    from core.mcp_server import write as write_medido
    if Path(write_medido.__file__).resolve() != write_source or sha256(write_source) != write_sha:
        raise RuntimeError("write.py cargado no coincide con la fuente y huella declaradas")
    salida = {
        "metadatos": {"gold_guardado_sha256": sha256(CASOS), "write_sha256": write_sha,
                      "write_source": str(write_source),
                      "estado_hormiga": "archivo temporal separado por corrida",
                      "modo": "FastMCP en proceso; sin transporte ni agente real",
                      "base": "temporal inicialmente vacía; se consolida cada escritura confirmada",
                      "puentes": "plantillas sintéticas en lengua nativa, no revisadas por hablantes",
                      "biorag_neurona": "0", "pythonhashseed": "0", "reloj_fijo_unix": RELOJ_FIJO,
                      "duracion_s": round(time.perf_counter() - inicio, 2)},
        "resumen": resumen(datos["casos"]), **datos,
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nResumen:")
    for idioma, r in salida["resumen"].items():
        print(idioma, r)
    errores = [r["id"] for r in datos["casos"] if r["excepcion"] or r["error_consolidacion"] or
               r["confirmado_por_mcp"] != r["guardado_en_db"] or (r["guardado_en_db"] and r["puentes_guardados"] != 5)]
    print("Errores operativos o de verificación:", errores)
    print("Salida:", args.salida)
    return int(bool(errores))


if __name__ == "__main__":
    raise SystemExit(main())
