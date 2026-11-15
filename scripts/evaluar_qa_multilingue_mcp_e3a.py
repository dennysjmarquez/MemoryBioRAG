#!/usr/bin/env python3
"""E3A: medir recordar MCP con sustantivos nativos, en bases temporales.

PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_mcp_e3a.py \
  --verificar-orden --salida docs/e3a_mcp_resultados_20261027.json

Brazo A: los mismos 120 recuerdos de la QA directa, sin sustantivos guardados.
Brazo B: 40 recuerdos inglés/español creados por _aprender_impl con sustantivos,
cinco puentes sintéticos y consolidación explícita. Los otros cuatro idiomas no
se fingen guardados: sus ejemplos MCP son rechazados por el validador actual.
En ambos brazos se llama realmente a _recordar_impl para las 132 preguntas y se
usa una copia limpia por consulta. _get_cerebro se dirige exclusivamente a esa
copia; no se altera el código ni el cálculo del motor. Las bases se destruyen.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluar_qa_multilingue_e3a import IDIOMAS, RELOJ_FIJO, cargar_gold, crear_base, sha256

LABELS = ROOT / "scripts" / "casos_qa_multilingue_sustantivos_e3a.jsonl"


def cargar_sustantivos(casos: list[dict], path: Path = LABELS) -> dict[str, dict]:
    """Exige un registro por caso y términos de búsqueda visibles en la consulta."""
    labels = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(set(x) != {"id", "sustantivos_busqueda", "sustantivos_guardado"} for x in labels):
        raise ValueError("Campos incorrectos en sustantivos")
    by_id = {x["id"]: x for x in labels}
    if len(labels) != len(by_id) or set(by_id) != {c["id"] for c in casos}:
        raise ValueError("Los sustantivos deben cubrir cada caso una sola vez")
    for caso in casos:
        row = by_id[caso["id"]]
        q_terms = row["sustantivos_busqueda"].split(",")
        if not q_terms or any(not t or t.lower() not in caso["query"].lower() for t in q_terms):
            raise ValueError(f"{caso['id']}: los términos de búsqueda no salen de la pregunta")
        sk_write = row["sustantivos_guardado"]
        requiere_write = caso["concepto"] is not None and caso["idioma"] in ("en", "es")
        if bool(sk_write) != requiere_write:
            raise ValueError(f"{caso['id']}: sustantivos de guardado inconsistentes")
        if sk_write:
            texto = (caso["concepto"] + " " + caso["contenido"]).lower()
            if any(not t or t.lower() not in texto for t in sk_write.split(",")):
                raise ValueError(f"{caso['id']}: términos de guardado no salen del recuerdo")
    return by_id


def parsear_mcp(texto: str) -> dict:
    """La función MCP antepone advertencias en texto al objeto JSON final."""
    starts = [0] if texto.startswith("{") else []
    starts += [i + 2 for i in range(len(texto)) if texto.startswith("\n\n{", i)]
    for start in reversed(starts):
        try:
            obj = json.loads(texto[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Respuesta MCP sin objeto JSON final: {texto[:300]}")


def puentes_sinteticos(caso: dict) -> list[dict]:
    """Cinco plantillas por nodo; cumplen validación, no son puentes humanos."""
    nombre = caso["concepto"]
    if caso["idioma"] == "en":
        textos = [f"definition reference for {nombre}", f"forgotten detail about {nombre}",
                  f"restore information about {nombre}", f"later question about {nombre}",
                  f"simple guide for {nombre}"]
    else:
        textos = [f"significado recuerdo {nombre}", f"olvido informacion relacionada {nombre}",
                  f"conservar informacion acerca {nombre}", f"consulta posterior contexto {nombre}",
                  f"explicacion sencilla sobre {nombre}"]
    return [{"angle": a, "text": t} for a, t in zip(
        ("sinonimo", "problema", "solucion", "situacion", "ingenuo"), textos)]


def crear_base_mcp(path: Path, casos: list[dict], labels: dict[str, dict]) -> dict:
    """Guarda 40 nodos mediante MCP y los consolida en la base temporal.

    Hace búsqueda previa real para cada entrada. No trata los puentes de plantilla
    como cobertura semántica evaluada: pueden influir en los resultados.
    """
    from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave
    from core.mcp_server import write as mcp_write, search as mcp_search
    from middleware.auto_guardado import buffer_global

    if path.exists():
        raise FileExistsError(path)
    cerebro = SQLiteMemoryBioRAG(str(path))
    # Igual que el singleton MCP: los cierres al final de cada tool son no-op.
    cerebro._persistente = True
    escrituras = []
    try:
        with patch.object(mcp_write, "_get_cerebro", return_value=cerebro), \
             patch.object(mcp_search, "_get_cerebro", return_value=cerebro):
            for caso in casos:
                sk = labels[caso["id"]]["sustantivos_guardado"]
                if not sk:
                    continue
                buffer_global.limpiar()
                previa_raw = mcp_search._recordar_impl(
                    query=caso["concepto"], sustantivos_clave=sk, deep=False, limite=5)
                previa = parsear_mcp(previa_raw)
                if previa.get("status") == "error":
                    raise RuntimeError(f"{caso['id']}: búsqueda previa MCP rechazada: {previa}")
                clave = caso["concepto"].lower().replace(" ", "_")
                if any(r.get("concepto") == clave for r in previa.get("resultados", [])):
                    raise RuntimeError(f"{caso['id']}: búsqueda previa halló un duplicado exacto")
                buffer_global.limpiar()
                raw = mcp_write._aprender_impl(
                    concepto=caso["concepto"], contenido=caso["contenido"],
                    bridges=puentes_sinteticos(caso), sustantivos_clave=sk,
                    cat="General", busqueda_previa=True)
                respuesta = parsear_mcp(raw)
                registro = {"id": caso["id"], "idioma": caso["idioma"],
                            "sustantivos_guardado": sk, "busqueda_previa_ejecutada": True,
                            "resultados_busqueda_previa": [r["concepto"] for r in previa.get("resultados", [])],
                            "respuesta_aprender": respuesta, "respuesta_cruda": raw}
                escrituras.append(registro)
                if respuesta.get("status") != "ok" or respuesta.get("concepto") != clave:
                    raise RuntimeError(f"{caso['id']}: escritura MCP falló: {respuesta}")
                if not cerebro.consolidar_concepto(clave):
                    raise RuntimeError(f"{caso['id']}: no se consolidó el recuerdo MCP")
                row = cerebro.conn.execute(
                    "SELECT contenido, estado, sustantivos_clave FROM largo_plazo WHERE concepto = ?",
                    (clave,)).fetchone()
                if row != (caso["contenido"], "activo", normalizar_sustantivos_clave(sk)):
                    raise RuntimeError(f"{caso['id']}: memoria consolidada incorrecta: {row}")
        total = cerebro.conn.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
        integridad = cerebro.conn.execute("PRAGMA integrity_check").fetchone()[0]
        if total != 40 or integridad != "ok":
            raise RuntimeError(f"Base MCP inválida: {total} recuerdos; integridad={integridad}")
        cerebro.conn.commit()
        if cerebro.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
            raise RuntimeError("No fue posible consolidar el WAL de la base MCP")
    finally:
        buffer_global.limpiar()
        cerebro._persistente = False
        cerebro.cerrar_sistema()
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError("WAL no vacío en base MCP")
    return {"nodos": total, "integridad": integridad, "sha256_sqlite": sha256(path),
            "escrituras": escrituras}


def buscar_mcp(origen: Path, caso: dict, labels: dict[str, dict], carpeta: Path,
               base_mcp: bool = False) -> dict:
    """Llama _recordar_impl sin alterar su scoring, en una copia efímera."""
    from core.memory_store import SQLiteMemoryBioRAG
    from core.mcp_server import search as mcp_search
    from middleware.auto_guardado import buffer_global

    with tempfile.TemporaryDirectory(prefix="mcp_caso_", dir=carpeta) as tmp:
        copia = Path(tmp) / "copia.db"
        shutil.copyfile(origen, copia)
        abiertos = []

        def cerebro_temporal():
            # Si algún acceso extra intenta llegar a la base, solo se abre la copia.
            cerebro = SQLiteMemoryBioRAG(str(copia))
            abiertos.append(cerebro)
            return cerebro

        buffer_global.limpiar()
        with patch.object(mcp_search, "_get_cerebro", side_effect=cerebro_temporal):
            raw = mcp_search._recordar_impl(
                query=caso["query"], sustantivos_clave=labels[caso["id"]]["sustantivos_busqueda"],
                deep=False, limite=5)
        buffer_global.limpiar()
        respuesta = parsear_mcp(raw)
        if len(abiertos) > 1:
            raise RuntimeError(f"{caso['id']}: se abrieron varias instancias inesperadamente")
        for cerebro in abiertos:
            cerebro.cerrar_sistema()
    error = respuesta.get("status") == "error"
    if error and abiertos:
        raise RuntimeError(f"{caso['id']}: error con base abierta inesperadamente")
    resultados = [{"concepto": r["concepto"], "score": r["score_hibrido"],
                   "score_base": r.get("score_hibrido_base", r["score_hibrido"])}
                  for r in respuesta.get("resultados", [])]
    if len(resultados) > 5:
        raise RuntimeError(f"{caso['id']}: más de cinco resultados")
    esperado = caso["concepto"]
    if esperado is not None and base_mcp:
        esperado = esperado.lower().replace(" ", "_")
    nombres = [r["concepto"] for r in resultados]
    rango = nombres.index(esperado) + 1 if esperado in nombres else None
    return {"id": caso["id"], "idioma": caso["idioma"], "tipo": caso["tipo"],
            "query": caso["query"],
            "sustantivos_clave": labels[caso["id"]]["sustantivos_busqueda"],
            "esperado": esperado, "rango": rango, "resultados": resultados,
            "error": respuesta.get("codigo") if error else None,
            "termino_invalido": respuesta.get("termino_invalido") if error else None,
            "busqueda_ejecutada": bool(abiertos),
            "umbral_conforme_presente": bool(abiertos[0]._umbral_conforme) if abiertos else None,
            "falso_positivo": bool(resultados) if esperado is None and not error else None,
            "respuesta_cruda_mcp": raw}


def estadisticas(casos: list[dict]) -> dict:
    pos = [c for c in casos if c["esperado"] is not None]
    neg = [c for c in casos if c["esperado"] is None]
    neg_ejecutados = [c for c in neg if c["busqueda_ejecutada"]]
    return {"positivos": len(pos), "ejecutados_positivos": sum(c["busqueda_ejecutada"] for c in pos),
            "rechazos_positivos": sum(bool(c["error"]) for c in pos),
            "aciertos_r1": sum(c["rango"] == 1 for c in pos),
            "aciertos_r5": sum(c["rango"] is not None for c in pos),
            "negativos": len(neg), "negativos_ejecutados": len(neg_ejecutados),
            "rechazos_negativos": sum(bool(c["error"]) for c in neg),
            "falsos_positivos": sum(bool(c["falso_positivo"]) for c in neg_ejecutados),
            "codigos_error": dict(Counter(c["error"] for c in casos if c["error"]))}


def ejecutar_brazo(path: Path, casos: list[dict], labels: dict[str, dict], carpeta: Path,
                    base_mcp: bool, verificar_orden: bool) -> dict:
    hash_inicial = sha256(path)
    resultados = [buscar_mcp(path, c, labels, carpeta, base_mcp) for c in casos]
    diferentes = []
    if verificar_orden:
        primero = {r["id"]: r for r in resultados}
        for c in reversed(casos):
            if buscar_mcp(path, c, labels, carpeta, base_mcp) != primero[c["id"]]:
                diferentes.append(c["id"])
    if sha256(path) != hash_inicial:
        raise RuntimeError("La base fuente cambió durante las consultas")
    return {"sha256_fuente": hash_inicial,
            "metricas": {lang: estadisticas([c for c in resultados if c["idioma"] == lang])
                         for lang in IDIOMAS},
            "global": estadisticas(resultados),
            "verificacion_orden": {"casos_comparados": len(casos) if verificar_orden else 0,
                                    "diferentes": diferentes},
            "casos": resultados}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--verificar-orden", action="store_true")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    casos = cargar_gold()
    labels = cargar_sustantivos(casos)
    inicio = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="biorag_e3a_mcp_") as tmp:
        carpeta = Path(tmp)
        # Falla cerrada: cualquier acceso auxiliar no previsto apunta al directorio temporal.
        env = {"BIORAG_PATH": str(carpeta / "acceso_auxiliar.db"),
               "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
               "BIORAG_MCP_AUTO_PARAFRASIS": "0", "BIORAG_MCP_AUTO_DIMS": "0"}
        with patch.dict(os.environ, env), patch("time.time", return_value=RELOJ_FIJO):
            directa = carpeta / "base_directa.db"
            base_directa = crear_base(directa, casos)
            print("Brazo A: 120 recuerdos guardados por API directa, sin sustantivos en nodos.", flush=True)
            resultados_a = ejecutar_brazo(directa, casos, labels, carpeta, False, args.verificar_orden)
            mcp = carpeta / "base_aprender_mcp.db"
            base_mcp = crear_base_mcp(mcp, casos, labels)
            print("Brazo B: 40 recuerdos EN/ES guardados por MCP con sustantivos y puentes de plantilla.", flush=True)
            resultados_b = ejecutar_brazo(mcp, casos, labels, carpeta, True, args.verificar_orden)
        salida = {
            "metadatos": {"gold_sha256": sha256(ROOT / "scripts" / "casos_qa_multilingue_e3a.jsonl"),
                          "sustantivos_sha256": sha256(LABELS), "reloj_fijo_unix": RELOJ_FIJO,
                          "pythonhashseed": "0", "biorag_neurona": "0",
                          "profundidad": "activos", "limite_publico": 5, "limite_interno_mcp": 15,
                          "ignore_peso_sinaptico": "no expuesto por recordar; usa el default del motor",
                          "aislamiento": "base temporal; copia nueva por consulta; buffer limpio",
                          "sin_parafrasis_ni_rafaga_ni_dimensiones": True,
                          "duracion_s": round(time.perf_counter() - inicio, 2)},
            "base_directa": base_directa, "base_mcp": base_mcp,
            "recordar_sobre_base_directa": resultados_a,
            "recordar_sobre_base_mcp_en_es": resultados_b,
        }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nombre, brazo in (("base directa", resultados_a), ("base MCP EN/ES", resultados_b)):
        print(f"\n{nombre}: idioma | ejecutados positivos | R@5 | R@1 | errores | FP/negativos ejecutados")
        for lang, s in brazo["metricas"].items():
            print(f"{lang:6} | {s['ejecutados_positivos']:2}/{s['positivos']} | "
                  f"{s['aciertos_r5']:2}/{s['positivos']} | {s['aciertos_r1']:2}/{s['positivos']} | "
                  f"{s['rechazos_positivos']:2} | {s['falsos_positivos']}/{s['negativos_ejecutados']}")
        print("Orden inverso, casos diferentes:", len(brazo["verificacion_orden"]["diferentes"]))
    print(f"\nSalida: {args.salida}")
    if any(b["verificacion_orden"]["diferentes"] for b in (resultados_a, resultados_b)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
