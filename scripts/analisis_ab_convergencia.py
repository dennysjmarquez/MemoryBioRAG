#!/usr/bin/env python3
"""
Análisis Forense A/B para Convergencia Multi-Campo (Spec-006).
Compara detalladamente las consultas representativas entre BIORAG_CONVERGENCIA_ACTIVA=0 y =1
sobre el snapshot congelado, registrando para el esperado y el top-5:
origen, match_exacto, score base, máscara de campos, score post-convergencia, posición y estado QCR.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SNAPSHOT_PATH = ROOT / "snapshots" / "qa_escape_qcr_20260811.db"
CASOS_TARGET = [
    {"id": "0516", "cat": "por_tema", "query": "real más sistemas", "expected": "dennys-identidad-profunda"},
    {"id": "0514", "cat": "sinonimo", "query": "perfil", "expected": "dennys-identidad-profunda"},
    {"id": "0489", "cat": "typo", "query": "oracle custom prompt arsitecura que fuciona", "expected": "oracle_custom_prompt_arsitecura_que_funciona"},
    {"id": "0518", "cat": "variante_gramatical", "query": "cuando usado dimensione biorags", "expected": "cuando_usar_dimensiones_biorag"},
    {"id": "0564", "cat": "pregunta_natural", "query": "¿Dónde encuentro la info de memoria v5 1 optimizaciones?", "expected": "memoria_v5_1_optimizaciones"},
    {"id": "0594", "cat": "sinonimo", "query": "arquitectura", "expected": "arquitectura_memoria_biorag"},
    {"id": "0638", "cat": "sinonimo", "query": "memoria compartida", "expected": "mentalidad_biorag_para_agentes"},
]


def _crear_copia_snapshot():
    fd, tmp = tempfile.mkstemp(suffix="_ab_eval.db")
    os.close(fd)
    src = sqlite3.connect(f"file:{SNAPSHOT_PATH}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.close()
    src.close()
    return tmp


def analizar_caso(db_path, caso, convergencia_activa):
    from core.fallback_simbolico import _tokenizar_normalizado
    from core.memory import constants
    from core.memory_store import SQLiteMemoryBioRAG

    constants.CONVERGENCIA_ACTIVA = convergencia_activa
    os.environ["BIORAG_CONVERGENCIA_ACTIVA"] = "1" if convergencia_activa else "0"
    os.environ["BIORAG_DMN_SINTESIS_ACTIVA"] = "0"
    os.environ["BIORAG_NO_LOG"] = "1"

    cerebro = SQLiteMemoryBioRAG(db_path=db_path)
    query = caso["query"]
    expected = caso["expected"]

    # Ejecutar búsqueda estándar
    res, total = cerebro.buscar_por_frase(query, limite=5, preview_chars=120)
    top_5_conceptos = [r[0] for r in res]

    # Reconstruir trazas de candidatos evaluados
    origenes = getattr(cerebro, "last_origen_scores", {}) or {}
    todos_conceptos = set(top_5_conceptos)
    if expected:
        todos_conceptos.add(expected)

    # Obtener campos de los nodos
    campos_map = {}
    ph = ",".join("?" * len(todos_conceptos))
    for r in cerebro.cursor.execute(
        f"SELECT concepto, contenido, COALESCE(sinonimos, ''), COALESCE(sustantivos_clave, '') FROM largo_plazo WHERE concepto IN ({ph})",
        list(todos_conceptos)
    ):
        campos_map[r[0]] = {
            "contenido": r[1] or "",
            "sinonimos": r[2] or "",
            "sustantivos": r[3] or ""
        }

    # Analizar tokens y canales
    tokens_query = _tokenizar_normalizado(query)
    q_set = set(tokens_query) if tokens_query else set()

    def _campo_activo(texto: str) -> int:
        if not texto or not q_set:
            return 0
        return 1 if q_set & set(_tokenizar_normalizado(texto)) else 0

    detalles_nodos = {}
    for conc in todos_conceptos:
        c_data = campos_map.get(conc, {"contenido": "", "sinonimos": "", "sustantivos": ""})
        c_conc = _campo_activo(conc)
        c_sin = _campo_activo(c_data["sinonimos"])
        c_sus = _campo_activo(c_data["sustantivos"])
        c_cont = _campo_activo(c_data["contenido"])
        canales_activos = c_conc + c_sin + c_sus + c_cont
        convergencia = canales_activos / 4.0
        alpha = constants.CONVERGENCIA_ALPHA
        multiplicador = alpha + (1.0 - alpha) * convergencia

        origen_info = origenes.get(conc, ("desconocido", 0.0))
        origen_tipo = origen_info[0] if isinstance(origen_info, (tuple, list)) else "desconocido"
        origen_score = origen_info[1] if isinstance(origen_info, (tuple, list)) else 0.0

        _q_norm = query.lower().replace(" ", "_").replace("-", "_")
        _c_norm = (conc or "").lower().replace(" ", "_").replace("-", "_")
        match_exacto = (_q_norm == _c_norm) or (bool(tokens_query) and tokens_query == _tokenizar_normalizado(conc))

        # Posición en resultado
        pos = (top_5_conceptos.index(conc) + 1) if conc in top_5_conceptos else (">5" if conc in [r[0] for r in res] else "NO_RECUPERADO")
        score_final = next((r[4] for r in res if r[0] == conc), None)

        detalles_nodos[conc] = {
            "posicion": pos,
            "score_final": score_final,
            "origen": origen_tipo,
            "origen_score_capa": origen_score,
            "match_exacto": match_exacto,
            "mascara_canales": {
                "concepto": c_conc,
                "sinonimos": c_sin,
                "sustantivos": c_sus,
                "contenido": c_cont,
                "total_canales": canales_activos,
            },
            "multiplicador": multiplicador
        }

    cerebro.cerrar_sistema()

    return {
        "id": caso["id"],
        "cat": caso["cat"],
        "query": query,
        "expected": expected,
        "total_encontrados": total,
        "top_5": [
            {
                "pos": i + 1,
                "concepto": r[0],
                "score": r[4],
                "detalle": detalles_nodos.get(r[0])
            }
            for i, r in enumerate(res[:5])
        ],
        "detalle_esperado": detalles_nodos.get(expected)
    }


def main():
    tmp_db = _crear_copia_snapshot()
    try:
        reporte_off = []
        reporte_on = []

        print("Analizando casos con BIORAG_CONVERGENCIA_ACTIVA=0 (OFF)...")
        for caso in CASOS_TARGET:
            reporte_off.append(analizar_caso(tmp_db, caso, convergencia_activa=False))

        print("Analizando casos con BIORAG_CONVERGENCIA_ACTIVA=1 (ON)...")
        for caso in CASOS_TARGET:
            reporte_on.append(analizar_caso(tmp_db, caso, convergencia_activa=True))

        out_path = ROOT / "scripts" / "analisis_ab_convergencia_reporte.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "snapshot": str(SNAPSHOT_PATH),
                "casos_evaluados": len(CASOS_TARGET),
                "off": reporte_off,
                "on": reporte_on
            }, f, indent=2, ensure_ascii=False)

        print(f"\nReporte JSON generado en: {out_path}")
        print("\n" + "="*80)
        print(f"{'ID':<6} | {'CAT':<18} | {'EXPECTED':<35} | {'POS OFF':<8} | {'POS ON':<8} | {'CANALES EXP':<12}")
        print("="*80)
        for c_off, c_on in zip(reporte_off, reporte_on):
            exp = c_off["expected"]
            pos_off = str(c_off["detalle_esperado"]["posicion"]) if c_off["detalle_esperado"] else "N/A"
            pos_on = str(c_on["detalle_esperado"]["posicion"]) if c_on["detalle_esperado"] else "N/A"
            canales = f"{c_on['detalle_esperado']['mascara_canales']['total_canales']}/4" if c_on["detalle_esperado"] else "N/A"
            print(f"{c_off['id']:<6} | {c_off['cat']:<18} | {exp:<35} | {pos_off:<8} | {pos_on:<8} | {canales:<12}")

    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)


if __name__ == "__main__":
    main()
