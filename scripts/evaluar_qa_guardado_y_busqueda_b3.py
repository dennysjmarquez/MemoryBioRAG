#!/usr/bin/env python3
"""E3B3: guardar los 80 casos congelados y buscarlos realmente por FastMCP.

No abre ni modifica la base viva ni el snapshot. El módulo del hub se carga
explícitamente antes de importar el servidor: permite ejecutar el mismo arnés
con el archivo B2 extraído de Git y con el candidato B3. Cada búsqueda ON/OFF
parte de copias byte a byte de UNA misma semilla SQLite.

El puente completo contiene el nombre: su hallazgo no demuestra recuperación
independiente del nombre. Los fragmentos sin nombre son genéricos y repetidos
entre casos de cada idioma; no son preguntas humanas ni pistas distintivas.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import unicodedata
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASOS = ROOT / "scripts" / "casos_qa_guardado_nativo_e3b2.jsonl"
CASOS_SHA256 = "fed44d525fe037a4ffd596a5b5bda24129ca22727474518b5425dd805954c35c"
FRAGMENTOS = {
    "zh": ("是什么意思", "是什么意思"),
    "ja": ("とは何ですか", "とは何ですか"),
    "ko": ("다른 말로 무엇인가요", "다른,말로"),
    "ru": ("другое название", "другое,название"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _termino_valido(s: str) -> bool:
    s = unicodedata.normalize("NFC", s)
    return 2 <= len(s) <= 15 and all(unicodedata.category(c)[0] in "LMN" or c == "_" for c in s)


def consultas_de_caso(caso: dict) -> dict[str, dict]:
    """Construye tres vistas y jamás introduce el nombre en el fragmento.

    Las etiquetas se extraen del propio texto. En nombre/puente se usan las
    palabras válidas del concepto; en fragmento se usan SOLO palabras visibles
    en el fragmento. No se modifica el corpus congelado.
    """
    nombre = caso["concepto"]
    puente = caso["bridges"][0]["text"]
    if puente.count(nombre) != 1:
        raise ValueError(f"{caso['id']}: el puente no contiene exactamente una vez el nombre")
    fragmento = puente.replace(nombre, "", 1).strip(" \t\r\n.,;:!?？。！：，、")
    if not fragmento or nombre.lower() in fragmento.lower():
        raise ValueError(f"{caso['id']}: fragmento sin nombre inválido")

    palabras_nombre = [w for w in nombre.split() if _termino_valido(w)]
    if not palabras_nombre:
        raise ValueError(f"{caso['id']}: no hay sustantivo válido en el nombre")
    consulta_fragmento, sustantivos_fragmento = FRAGMENTOS[caso["idioma"]]
    if consulta_fragmento not in fragmento:
        raise ValueError(f"{caso['id']}: la consulta no proviene del fragmento")
    for palabra in sustantivos_fragmento.split(","):
        if not _termino_valido(palabra) or palabra.lower() not in consulta_fragmento.lower():
            raise ValueError(f"{caso['id']}: sustantivo ajeno o inválido en fragmento")
    sk_nombre = ",".join(palabras_nombre)
    return {
        "nombre": {"query": nombre, "sustantivos_clave": sk_nombre, "contiene_nombre": True},
        "puente_completo": {"query": puente, "sustantivos_clave": sk_nombre, "contiene_nombre": True},
        "fragmento_sin_nombre": {"query": consulta_fragmento, "sustantivos_clave": sustantivos_fragmento,
                                  "contiene_nombre": False, "fragmento_completo": fragmento},
    }


def instalar_hub(path: Path, esperado: str):
    path = path.resolve(strict=True)
    actual = sha256(path)
    if actual != esperado:
        raise ValueError(f"SHA del hub incorrecto: {actual} != {esperado}")
    if "core.concept_hub" in sys.modules:
        raise RuntimeError("El hub fue importado antes de instalar la versión solicitada")
    import core
    spec = importlib.util.spec_from_file_location("core.concept_hub", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se puede cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["core.concept_hub"] = module
    spec.loader.exec_module(module)
    core.concept_hub = module
    if Path(module.__file__).resolve() != path:
        raise RuntimeError("Hub instalado desde una ruta incorrecta")
    return module


def guardar_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_name(path.name + ".tmp")
    temporal.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(path)


def hacer_semilla(origen: Path, destino: Path) -> dict:
    if destino.exists():
        raise FileExistsError(f"La semilla ya existe; no se sobrescribe: {destino}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{origen.resolve()}?mode=ro", uri=True) as src:
        with sqlite3.connect(destino) as dst:
            src.backup(dst)
    with sqlite3.connect(f"file:{destino.resolve()}?mode=ro&immutable=1", uri=True) as con:
        integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
        corto = con.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
        largo = con.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
        hubs = con.execute("SELECT COUNT(*) FROM concept_hubs").fetchone()[0]
        puentes = con.execute("SELECT COUNT(*) FROM concept_hub_bridges").fetchone()[0]
    if integridad != "ok":
        raise RuntimeError(f"Semilla corrupta: {integridad}")
    return {"sha256": sha256(destino), "integridad": integridad,
            "corto_plazo": corto, "largo_plazo": largo, "hubs": hubs, "puentes": puentes}


def validar_guardados(data: dict) -> None:
    if data["integridad"] != "ok" or len(data["casos"]) != 80:
        raise RuntimeError("Integridad o número de guardados incorrecto")
    for row in data["casos"]:
        if not row["busqueda_previa_ejecutada"] or row["excepcion"] or row["error_consolidacion"]:
            raise RuntimeError(f"Fallo operativo en {row['id']}")
        if row["confirmado_por_mcp"] != row["guardado_en_db"]:
            raise RuntimeError(f"MCP y SQL discrepan: {row['id']}")
        if row["guardado_en_db"] and not (row["consolidado"] and row["puentes_guardados"] == 5):
            raise RuntimeError(f"Guardado sin confirmación completa: {row['id']}")


def comparar_guardados_referencia(actual: dict, referencia: dict) -> None:
    campos = ("busqueda_previa_ejecutada", "busqueda_previa_confirmada", "primer_rechazo",
              "guardado_en_db", "confirmado_por_mcp", "consolidado", "puentes_guardados")
    por_id = {r["id"]: r for r in referencia["casos"]}
    if len(por_id) != 80 or set(por_id) != {r["id"] for r in actual["casos"]}:
        raise RuntimeError("El control de guardados tiene casos diferentes")
    diferencias = [f"{r['id']}:{c}" for r in actual["casos"] for c in campos if r[c] != por_id[r["id"]][c]]
    if diferencias:
        raise RuntimeError("Los guardados no reproducen el control: " + ", ".join(diferencias))


def _a_json(value):
    # Los metadatos del motor usan listas, dicts y números. Si un backend añade
    # un set, se conserva ordenado en vez de ocultar el dato.
    def convertir(obj):
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(f"No serializable: {type(obj).__name__}")
    return json.loads(json.dumps(value, ensure_ascii=False, default=convertir))


async def recordar(mcp, caso: dict, consulta: dict, modo: str, semilla: Path,
                   destino: Path, estado: Path) -> dict:
    from core import memory_service
    from middleware.auto_guardado import buffer_global
    from scripts.evaluar_qa_guardado_nativo_b2 import texto_tool
    from scripts.evaluar_qa_multilingue_mcp_e3a import parsear_mcp

    shutil.copyfile(semilla, destino)
    if sha256(destino) != sha256(semilla):
        raise RuntimeError("Copia de búsqueda distinta de la semilla")
    env = {
        "BIORAG_PATH": str(destino), "BIORAG_HUB_ENABLED": "1" if modo == "on" else "0",
        "BIORAG_DMN_ESTADO_PATH": str(estado), "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
        "BIORAG_MCP_AUTO_PARAFRASIS": "0", "BIORAG_MCP_AUTO_DIMS": "0",
    }
    memory_service.reset_cerebro()
    buffer_global.limpiar()
    try:
        with patch.dict(os.environ, env):
            raw = texto_tool(await mcp.call_tool("recordar", {
                "query": consulta["query"], "sustantivos_clave": consulta["sustantivos_clave"],
                "limite": 5, "asociados": False,
            }))
            respuesta = parsear_mcp(raw)
            cerebro = memory_service._cerebro
            hub = _a_json(getattr(cerebro, "last_hub_expansion", None)) if cerebro else None
            origenes = _a_json(getattr(cerebro, "last_origen_scores", {})) if cerebro else {}
            ultima_query = getattr(cerebro, "last_query", None) if cerebro else None
        if respuesta.get("status") == "error":
            raise RuntimeError(f"{caso['id']} {modo}: error MCP {respuesta.get('codigo') or respuesta}")
        resultados = respuesta.get("resultados", [])
        if not isinstance(resultados, list):
            raise RuntimeError(f"{caso['id']} {modo}: resultados no son lista")
        conceptos = [r.get("concepto") for r in resultados if isinstance(r, dict)]
        esperado = caso["concepto"].lower().replace(" ", "_").strip()
        orden = next((i + 1 for i, c in enumerate(conceptos) if c == esperado), None)
        return {
            "top5": conceptos, "posicion_esperado": orden, "acierto_r5": orden is not None,
            "acierto_r1": orden == 1, "respuesta": respuesta, "respuesta_cruda": raw,
            "last_hub_expansion": hub, "last_query_motor": ultima_query,
            "origen_esperado": origenes.get(esperado), "origenes": origenes,
        }
    finally:
        memory_service.reset_cerebro()
        buffer_global.limpiar()
        destino.unlink(missing_ok=True)
        for sufijo in ("-wal", "-shm"):
            Path(str(destino) + sufijo).unlink(missing_ok=True)


async def buscar_todos(casos: list[dict], guardados: dict, semilla: Path,
                       carpeta: Path, ids: set[str] | None) -> tuple[list[dict], dict]:
    from mcp.server.fastmcp import FastMCP
    from core.mcp_server.write import register as register_write
    from core.mcp_server.search import register as register_search
    from scripts.evaluar_qa_guardado_nativo_b2 import RELOJ_FIJO

    mcp = FastMCP("E3B3-consultas")
    register_write(mcp)
    register_search(mcp)
    exitosos = {r["id"] for r in guardados["casos"] if r["guardado_en_db"]}
    if ids is not None:
        exitosos &= ids
    filas = []
    inicio = time.perf_counter()
    consulta_numero = 0
    with patch("time.time", return_value=RELOJ_FIJO):
        for caso in casos:
            if caso["id"] not in exitosos:
                continue
            for tipo, consulta in consultas_de_caso(caso).items():
                row = {"id": caso["id"], "idioma": caso["idioma"], "concepto": caso["concepto"],
                       "tipo": tipo, **consulta}
                for modo in ("on", "off"):
                    consulta_numero += 1
                    prefijo = f"q_{consulta_numero:04d}"
                    row[modo] = await recordar(mcp, caso, consulta, modo, semilla,
                                              carpeta / f"{prefijo}.db", carpeta / f"{prefijo}.json")
                row["hallado_solo_con_hub"] = row["on"]["acierto_r5"] and not row["off"]["acierto_r5"]
                row["hallado_solo_sin_hub"] = row["off"]["acierto_r5"] and not row["on"]["acierto_r5"]
                filas.append(row)
            print(f"Búsqueda {len(filas)//3}/{len(exitosos)}: {caso['id']}", flush=True)
    resumen = {}
    for idioma in ("zh", "ja", "ko", "ru"):
        resumen[idioma] = {}
        for tipo in ("nombre", "puente_completo", "fragmento_sin_nombre"):
            grupo = [r for r in filas if r["idioma"] == idioma and r["tipo"] == tipo]
            resumen[idioma][tipo] = {
                "casos": len(grupo),
                "on_r5": sum(r["on"]["acierto_r5"] for r in grupo),
                "off_r5": sum(r["off"]["acierto_r5"] for r in grupo),
                "on_r1": sum(r["on"]["acierto_r1"] for r in grupo),
                "off_r1": sum(r["off"]["acierto_r1"] for r in grupo),
                "on_expansion_alguna": sum(bool(r["on"]["last_hub_expansion"]) for r in grupo),
                "solo_on": sum(r["hallado_solo_con_hub"] for r in grupo),
                "solo_off": sum(r["hallado_solo_sin_hub"] for r in grupo),
            }
    return filas, {"por_idioma": resumen, "consultas_mcp": consulta_numero,
                   "duracion_s": round(time.perf_counter() - inicio, 2)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub-source", type=Path, required=True)
    parser.add_argument("--hub-sha256", required=True)
    parser.add_argument("--semilla", type=Path, required=True)
    parser.add_argument("--guardados", type=Path, required=True)
    parser.add_argument("--crear-semilla", action="store_true")
    parser.add_argument("--control-guardados", type=Path,
                        help="Referencia de 80 guardados ya medida, obligatoria al crear semilla")
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--ids", help="Solo para piloto: IDs separados por coma")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    if sha256(CASOS) != CASOS_SHA256:
        parser.error("Cambió el corpus congelado de 80 casos")
    if args.crear_semilla and not args.control_guardados:
        parser.error("Al crear la semilla se requiere un control de los 80 guardados")
    instalar_hub(args.hub_source, args.hub_sha256)
    from scripts.evaluar_qa_guardado_nativo_b2 import cargar_entradas, ejecutar, RELOJ_FIJO

    casos = cargar_entradas(CASOS)
    with tempfile.TemporaryDirectory(prefix="biorag_e3b3_busquedas_") as tmp:
        carpeta = Path(tmp)
        if args.crear_semilla:
            guardados = asyncio.run(ejecutar(casos, carpeta / "guardados.db"))
            validar_guardados(guardados)
            comparar_guardados_referencia(guardados, json.loads(args.control_guardados.read_text(encoding="utf-8")))
            metadata_semilla = hacer_semilla(carpeta / "guardados.db", args.semilla)
            guardados["semilla"] = metadata_semilla
            guardar_json(args.guardados, guardados)
        else:
            guardados = json.loads(args.guardados.read_text(encoding="utf-8"))
            validar_guardados(guardados)
            metadata_semilla = guardados["semilla"]
            if sha256(args.semilla) != metadata_semilla["sha256"]:
                raise RuntimeError("La semilla no coincide con el registro de guardados")
        ids = set(args.ids.split(",")) if args.ids else None
        filas, resumen = asyncio.run(buscar_todos(casos, guardados, args.semilla, carpeta, ids))
        salida = {
            "metadatos": {
                "hub_source": str(args.hub_source.resolve()), "hub_sha256": args.hub_sha256,
                "corpus_sha256": CASOS_SHA256, "semilla": metadata_semilla,
                "reloj_fijo_unix": RELOJ_FIJO, "pythonhashseed": "0", "biorag_neurona": "0",
                "ruta": "FastMCP en proceso, tool recordar", "profundidad": "activos",
                "limite_publico": 5, "limite_interno_mcp": 15,
                "ignore_peso_sinaptico": "no expuesto por recordar; usa el valor predeterminado",
                "aislamiento": "una copia idéntica de la semilla y estado auxiliar propio por consulta",
                "control_hub": "BIORAG_HUB_ENABLED=1 frente a 0",
                "limites": "puente completo contiene nombre; fragmentos son genéricos y repetidos por idioma",
                "solo_ids": sorted(ids) if ids is not None else None,
            },
            "resumen": resumen, "casos": filas,
        }
        guardar_json(args.salida, salida)
    print("Consultas MCP:", resumen["consultas_mcp"], "duración:", resumen["duracion_s"], "s")
    print("Salida:", args.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
