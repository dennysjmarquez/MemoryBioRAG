#!/usr/bin/env python3
"""Sondas E3 A: componentes, límites MCP y casos pequeños; sin tocar el motor.

PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/diagnostico_lexico_e3a.py \
  --salida docs/e3a_diagnostico_20261027.json

Las únicas bases que se crean son temporales; se borran al terminar. Las llamadas
MCP están protegidas para que una validación superada jamás abra la base real.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.evaluar_qa_multilingue_e3a import (
    RELOJ_FIJO, buscar_caso, cargar_gold, crear_base,
)


class AccesoMCPProtegido(Exception):
    pass


def _no_abrir_base(*args, **kwargs):
    raise AccesoMCPProtegido("La validación llegó al motor; se impidió abrir la base")


def _respuesta_mcp(funcion, **kwargs):
    try:
        r = json.loads(funcion(**kwargs))
        return {k: r.get(k) for k in ("status", "codigo", "termino_invalido")}
    except AccesoMCPProtegido:
        return {"status": "no_medido", "codigo": "VALIDACION_SUPERADA_BASE_PROTEGIDA"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")

    from core.fallback_simbolico import _normalizar, _tokenizar_normalizado
    from core.stemmer_es import stem
    from core.sinapsis import _tokenizar as token_sinapsis
    from core.ppmi_vectorizer import _tokenizar as token_ppmi
    from core.similitud_conceptual import _tokenizar_query as token_conceptual
    from core.lexical_learning import normalizar_expresion, ensenar_expresion
    from core.memory.catalog_methods import _normalizar_nombre_dimension
    from core.clasificador_wordnet import clasificar_palabra
    from core.concept_hub import ANGULOS_OFICIALES, validar_bridges
    from core.mcp_server import write as mcp_write, search as mcp_search
    from core.memory_store import SQLiteMemoryBioRAG

    muestras = ["ガラス", "カラス", "月亮", "月", "한국어", "русский", "всё", "все", "acción", "action"]
    componentes = [{
        "texto": s, "fallback_normalizado": _normalizar(s),
        "tokens_fallback": sorted(_tokenizar_normalizado(s)), "stem": stem(s),
        "tokens_sinapsis": sorted(token_sinapsis(s)), "tokens_ppmi": token_ppmi(s),
        "tokens_conceptuales": sorted(token_conceptual(s)),
        "expresion_aprendida": normalizar_expresion(s),
        "dimension": _normalizar_nombre_dimension(s),
        "grupos_wordnet": sorted(clasificar_palabra(s)),
    } for s in muestras]

    bridges_espaciados = [
        {"text": "alias de la herramienta aprender en el sistema biorag", "angle": "sinonimo"},
        {"text": "permite guardar informacion sin conocer el nombre tecnico aprender", "angle": "problema"},
        {"text": "redirige internamente a aprender con los mismos parametros", "angle": "solucion"},
        {"text": "agente llama guardar en lugar de aprender por convencion", "angle": "situacion"},
        {"text": "que diferencia hay entre guardar y aprender en biorag", "angle": "ingenuo"},
    ]
    textos_ja = ["透明な素材を説明する", "破れやすい容器の問題", "素材を加工する方法", "食器を選ぶ場面について", "初心者向けの簡単な説明"]
    puentes_ja = [{"text": t, "angle": a} for t, a in zip(textos_ja, ANGULOS_OFICIALES)]
    validos, rechazados = validar_bridges(puentes_ja, "ガラス")
    puente_sonda = {"puentes": puentes_ja, "validos": len(validos), "rechazos": rechazados}
    pares = {
        "zh": ("海岸灯塔", "月亮,天空"), "ja": ("海辺の灯台", "月光,夜空"),
        "ko": ("바닷가등대", "달빛,밤하늘"), "ru": ("морской_маяк", "луна,небо"),
    }
    mcp = {}
    with patch.object(mcp_write, "_get_cerebro", _no_abrir_base), \
         patch.object(mcp_search, "_get_cerebro", _no_abrir_base):
        for idioma, (concepto, sustantivos) in pares.items():
            mcp[idioma] = {
                "sustantivos": sustantivos,
                "aprender": _respuesta_mcp(
                    mcp_write._aprender_impl, concepto=concepto, contenido="Contenido de prueba.",
                    bridges=bridges_espaciados, sustantivos_clave=sustantivos, busqueda_previa=True),
                "recordar": _respuesta_mcp(
                    mcp_search._recordar_impl, query=concepto, sustantivos_clave=sustantivos,
                    limite=5, asociados=False),
            }

    gold = cargar_gold()
    por_id = {c["id"]: c for c in gold}
    with tempfile.TemporaryDirectory(prefix="biorag_e3a_sondas_") as temp, \
         patch("time.time", return_value=RELOJ_FIJO):
        carpeta = Path(temp)
        mini = [por_id[k] for k in ("zh-01", "ja-19", "ja-20", "es-01")]
        path_mini = carpeta / "mini.db"
        resumen_mini = crear_base(path_mini, mini)
        par_mini = [buscar_caso(path_mini, por_id[k], carpeta) for k in ("ja-19", "ja-20")]
        cerebro = SQLiteMemoryBioRAG(str(path_mini))
        try:
            aprendizaje_ja = ensenar_expresion(cerebro, "ガラス", "ガラス")
        finally:
            cerebro.cerrar_sistema()

        fragmentos_gold = [por_id[k] for k in ("zh-07", "ja-07", "es-07")]
        path_fts = carpeta / "fragmentos.db"
        crear_base(path_fts, fragmentos_gold)
        fts = []
        for caso in fragmentos_gold:
            # Una copia limpia por sonda, igual que la QA de 132 consultas.
            with tempfile.TemporaryDirectory(prefix="fts_", dir=carpeta) as copia_dir:
                copia = Path(copia_dir) / "copia.db"
                shutil.copyfile(path_fts, copia)
                cerebro = SQLiteMemoryBioRAG(str(copia))
                try:
                    query, concepto = caso["query"], caso["concepto"]
                    contiene, prefijo = cerebro.conn.execute(
                        "SELECT instr(contenido, ?), PALABRA_PREFIJO(?, contenido) "
                        "FROM largo_plazo WHERE concepto = ?", (query, query, concepto)).fetchone()
                    hits = [r[0] for r in cerebro.conn.execute(
                        "SELECT l.concepto FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid=f.rowid "
                        "WHERE largo_plazo_fts MATCH ?", ('"' + query.replace('"', '""') + '"',))]
                    resultados, _ = cerebro.buscar_por_frase(
                        query, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
                    fts.append({"id": caso["id"], "query": query, "concepto": concepto,
                                "posicion_subcadena": contiene, "palabra_prefijo": bool(prefijo),
                                "fts_bruto": hits,
                                "en_pool_antes_del_filtro": concepto in [r[1] for r in cerebro.last_todos],
                                "origen_antes_del_filtro": cerebro.last_origen_scores.get(concepto),
                                "resultado_final": [r[0] for r in resultados]})
                finally:
                    cerebro.cerrar_sistema()

    out = {"componentes": componentes, "puentes_japones_sin_espacios": puente_sonda,
           "mcp_validacion": mcp, "mini_base": resumen_mini,
           "mini_par_japones": par_mini, "ensenar_expresion_japonesa": aprendizaje_ja,
           "fragmentos_fts": fts}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
