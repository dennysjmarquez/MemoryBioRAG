#!/usr/bin/env python3
"""A/B no destructivo del re-ranking multicampo para el caso de versión BioRAG.

La DB indicada se abre en modo solo lectura y se clona con SQLite backup para
cada variante; ninguna búsqueda ni migración toca el archivo original. Por
omisión se reproducen la query transformada y las paráfrasis del caso MCP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# El smoke no debe contaminar telemetría ni crear síntesis asociativas.
os.environ["BIORAG_NO_LOG"] = "1"
os.environ.setdefault("BIORAG_DMN_SINTESIS_ACTIVA", "0")

from core.fallback_simbolico import _tokenizar_normalizado  # noqa: E402
from core.memory import constants  # noqa: E402
from core.memory.evidence_convergence import (  # noqa: E402
    calcular_bono_convergencia,
    evidencia_multicampo,
)
from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402

QUERY_CASES = (
    {
        "nombre": "mcp_transformada",
        "query": "biorag version actual ultima",
        "parafrasis": (
            "version biorag",
            "version actual biorag",
            "ultima version biorag",
            "biorag v version",
        ),
    },
    {
        "nombre": "spec_006_normalizada",
        "query": "version actual biorag",
        "parafrasis": (),
    },
)
CONCEPTO_OBJETIVO = "version_actual_biorag"
CONCEPTO_INCIDENTAL = "reindex_selectivo_dirty"


def _sha256(ruta: Path) -> str:
    sha = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()


def _copia_solo_lectura(origen: Path, destino: Path) -> None:
    """Clona de forma consistente una DB, incluyendo transacciones confirmadas."""
    uri = origen.resolve().as_uri() + "?mode=ro"
    src = sqlite3.connect(uri, uri=True)
    dst = sqlite3.connect(str(destino))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _buscar_ab(origen: Path, query: str, parafrasis: tuple[str, ...], activo: bool,
               limite: int, limite_publico: int,
               ignore_peso_sinaptico: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="biorag_convergencia_smoke_") as temp_dir:
        db_path = Path(temp_dir) / "copia.db"
        _copia_solo_lectura(origen, db_path)
        constants.CONVERGENCIA_EVIDENCIA_ACTIVA = activo
        cerebro = SQLiteMemoryBioRAG(db_path=str(db_path))
        try:
            filas, total = cerebro.buscar_por_frase(
                query,
                profundidad="activos",
                pagina=1,
                limite=limite,
                preview_chars=0,
                context_window=0,
                parafrasis_list=list(parafrasis) or None,
                ignore_peso_sinaptico=ignore_peso_sinaptico,
                ordenar_por="relevancia",
                convergencia_limite=limite_publico,
            )
            top = []
            for posicion, fila in enumerate(filas[:5], start=1):
                concepto = fila[0]
                score_base = cerebro.last_score_base_map.get(concepto, fila[4])
                top.append({
                    "posicion": posicion,
                    "concepto": concepto,
                    "score_ranking": round(float(fila[4]), 4),
                    "score_base": round(float(score_base), 4),
                    "bonus_multicampo": round(
                        float(cerebro.last_score_bonus_map.get(concepto, 0.0)), 4
                    ),
                    "origen": (cerebro.last_origen_scores.get(concepto) or ("", 0.0))[0],
                })
            conceptos = [fila[0] for fila in filas]
            posiciones = {concepto: index + 1 for index, concepto in enumerate(conceptos)}
            query_sets = [
                frozenset(_tokenizar_normalizado(texto))
                for texto in (query, *parafrasis)
                if _tokenizar_normalizado(texto)
            ]
            query_size = max((len(tokens) for tokens in query_sets), default=0)
            evidencia_campos = {}
            for concepto in (CONCEPTO_OBJETIVO, CONCEPTO_INCIDENTAL):
                cerebro.cursor.execute(
                    "SELECT concepto, COALESCE(sinonimos, ''), "
                    "COALESCE(sustantivos_clave, ''), COALESCE(contenido, '') "
                    "FROM largo_plazo WHERE concepto = ?",
                    (concepto,),
                )
                campos = cerebro.cursor.fetchone()
                if campos:
                    evidencia = evidencia_multicampo(query_sets, *campos)
                    evidencia_campos[concepto] = {
                        "cobertura_directa_por_campo": evidencia,
                        "bonus_estimado_sin_ratios_base": calcular_bono_convergencia(
                            evidencia,
                            max_bonus=constants.CONVERGENCIA_EVIDENCIA_MAX_BONUS,
                            query_size=query_size,
                        ),
                    }
                else:
                    evidencia_campos[concepto] = None
            return {
                "total": total,
                "ids_pagina_base": conceptos,
                "top_5": top,
                "pos_objetivo": posiciones.get(CONCEPTO_OBJETIVO),
                "pos_incidental": posiciones.get(CONCEPTO_INCIDENTAL),
                "evidencia_campos": evidencia_campos,
            }
        finally:
            cerebro.cerrar_sistema()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=os.environ.get("BIORAG_PATH", str(ROOT / "MemoryBioRAG_Data" / "memory_biorag.db")),
        help="DB de origen (solo lectura); default: DB local canónica.",
    )
    parser.add_argument(
        "--limite-interno", type=int, default=15,
        help="Pool que replica MCP (límite público 5 × 3).",
    )
    parser.add_argument(
        "--limite-publico", type=int, default=5,
        help="Top-k visible; la convergencia no cambia su membresía. Default: 5.",
    )
    parser.add_argument(
        "--qa-parity", action="store_true",
        help="Ignora peso sináptico para comparar con evaluar_qa.py; por omisión replica MCP.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Falla si version_actual_biorag no queda top-1 con convergencia activa.",
    )
    args = parser.parse_args()
    origen = Path(args.db).expanduser().resolve()
    if not origen.is_file():
        parser.error(f"No existe la DB de origen: {origen}")
    if args.limite_interno < 1:
        parser.error("--limite-interno debe ser mayor que cero")
    if args.limite_publico < 1:
        parser.error("--limite-publico debe ser mayor que cero")

    reporte = {
        "db_origen": str(origen),
        "db_sha256": None,
        "copia_original_solo_lectura": True,
        "ignore_peso_sinaptico": args.qa_parity,
        "casos": [],
    }
    reporte["db_sha256"] = _sha256(origen)

    fallos_objetivo = []
    fallos_membresia = []
    for caso in QUERY_CASES:
        off = _buscar_ab(
            origen, caso["query"], caso["parafrasis"], False,
            args.limite_interno, args.limite_publico, args.qa_parity,
        )
        on = _buscar_ab(
            origen, caso["query"], caso["parafrasis"], True,
            args.limite_interno, args.limite_publico, args.qa_parity,
        )
        misma_membresia = set(off["ids_pagina_base"]) == set(on["ids_pagina_base"])
        misma_membresia_top_k = (
            set(off["ids_pagina_base"][:args.limite_publico])
            == set(on["ids_pagina_base"][:args.limite_publico])
        )
        resultado = {
            "caso": caso["nombre"],
            "query": caso["query"],
            "parafrasis": list(caso["parafrasis"]),
            "top_5_sin_convergencia": off["top_5"],
            "top_5_con_convergencia": on["top_5"],
            "pos_objetivo_off": off["pos_objetivo"],
            "pos_objetivo_on": on["pos_objetivo"],
            "pos_incidental_off": off["pos_incidental"],
            "pos_incidental_on": on["pos_incidental"],
            "cobertura_de_campos": on["evidencia_campos"],
            "membresia_top_k_igual": misma_membresia_top_k,
            "membresia_pool_interno_igual": misma_membresia,
        }
        reporte["casos"].append(resultado)
        if on["pos_objetivo"] != 1:
            fallos_objetivo.append(caso["nombre"])
        if not misma_membresia_top_k or not misma_membresia:
            fallos_membresia.append(caso["nombre"])

    reporte["db_origen_sin_cambios"] = _sha256(origen) == reporte["db_sha256"]
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    if not reporte["db_origen_sin_cambios"]:
        print("ERROR: el hash de la DB de origen cambió durante el smoke.", file=sys.stderr)
        return 2
    if args.strict and (fallos_objetivo or fallos_membresia):
        if fallos_objetivo:
            print(
                "No pasó el smoke: version_actual_biorag no quedó TOP-1 en "
                + ", ".join(fallos_objetivo),
                file=sys.stderr,
            )
        if fallos_membresia:
            print(
                "No pasó el smoke: cambió la membresía top-k/pool en "
                + ", ".join(fallos_membresia),
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
