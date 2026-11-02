#!/usr/bin/env python3
"""Compara reemplazo y acumulación de etiquetas en copias sintéticas aisladas.

No abre datos del usuario: crea un esquema vacío en un TemporaryDirectory, lo
copia para cada política y usa la consolidación actual para un solo concepto.
La rama hipotética de acumulación une etiquetas únicamente dentro de esa fila
sintética. No modifica el motor ni propone alterar datos reales.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

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

# Un único recuerdo sintético recibe cinco actualizaciones. "castor" es la pista
# estable; las demás son pistas históricas distintas. Todos los términos tienen
# longitud suficiente para el tokenizer trigram de FTS5.
EPISODIOS = (
    ("castor,humedal,represa", "faceta sintética uno"),
    ("castor,ribera,madera", "faceta sintética dos"),
    ("castor,dique,corriente", "faceta sintética tres"),
    ("castor,cantera,sedimento", "faceta sintética cuatro"),
    ("castor,afluente,erosion", "faceta sintética cinco"),
)
CONCEPTO = "recuerdo_sintetico_unico"


def etiquetas(texto: str) -> tuple[str, str]:
    exactas = normalizar_sustantivos_clave_exacto(texto)
    plegadas = normalizar_sustantivos_clave(exactas)
    exactas = normalizar_sustantivos_clave_exactos_coherentes(exactas, plegadas) or ""
    return plegadas, exactas


def crear_esquema_vacio(ruta: Path) -> None:
    cerebro = SQLiteMemoryBioRAG(str(ruta))
    cerebro.cerrar_sistema()


def aplicar_politica(ruta: Path, acumular: bool) -> dict:
    cerebro = SQLiteMemoryBioRAG(str(ruta))
    categoria = cerebro._resolver_categoria_id("General")
    historial: list[str] = []
    acumuladas: list[str] = []
    try:
        for etiquetas_entrada, contenido in EPISODIOS:
            plegadas, exactas = etiquetas(etiquetas_entrada)
            historial.extend(t for t in exactas.split(",") if t)
            for term in exactas.split(","):
                if term and term not in acumuladas:
                    acumuladas.append(term)
            consolidation.fusionar_en_largo_plazo(
                cerebro, CONCEPTO, contenido, "", categoria, 0.0, plegadas, exactas
            )
            if acumular:
                # Contrafactual en esta copia de prueba: unir deduplicando con
                # orden de primera aparición; solo toca la fila sintética.
                folded, exact = etiquetas(",".join(acumuladas))
                cerebro.cursor.execute(
                    "UPDATE largo_plazo SET sustantivos_clave=?, sustantivos_clave_exactos=? WHERE concepto=?",
                    (folded, exact, CONCEPTO),
                )
            cerebro.conn.commit()

        row = cerebro.cursor.execute(
            "SELECT sustantivos_clave, sustantivos_clave_exactos FROM largo_plazo WHERE concepto=?",
            (CONCEPTO,),
        ).fetchone()
        stored = row[0].split(",") if row and row[0] else []
        # Comprueba cada pista usando exclusivamente la columna de etiquetas del
        # índice FTS5; no confunde coincidencias en contenido/concepto con tags.
        indexed = {}
        for term in dict.fromkeys(historial):
            match = cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo_fts "
                "WHERE largo_plazo_fts MATCH ?",
                (f'sustantivos_clave : "{term}"',),
            ).fetchone()[0]
            indexed[term] = bool(match)
        return {
            "policy": "accumulate" if acumular else "replace",
            "folded": row[0] or "",
            "exact": row[1] or "",
            "unique_historical_clues": list(dict.fromkeys(historial)),
            "indexed_clues": indexed,
            "stored_count": len(stored),
            "fts_integrity": cerebro.cursor.execute("PRAGMA integrity_check").fetchone()[0],
        }
    finally:
        cerebro.cerrar_sistema()


def resumen(result: dict) -> dict:
    latest = set(EPISODIOS[-1][0].split(","))
    union = set(result["unique_historical_clues"])
    returned = {term for term, hit in result["indexed_clues"].items() if hit}
    return {
        "policy": result["policy"],
        "stored_labels": result["stored_count"],
        "historical_clues_retrievable": len(returned),
        "historical_union_recall": round(len(returned & union) / len(union), 4),
        "latest_clue_recall": round(len(returned & latest) / len(latest), 4),
        "stale_clues_if_only_latest_is_relevant": len(returned - latest),
        "missing_prior_clues_if_all_facets_remain_relevant": len((union - latest) - returned),
        "fts_integrity": result["fts_integrity"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="e3_tag_policy_synthetic_") as tmp:
        root = Path(tmp)
        seed = root / "empty_schema.db"
        create_replace = root / "replace_copy.db"
        create_accumulate = root / "accumulate_copy.db"
        crear_esquema_vacio(seed)
        shutil.copy2(seed, create_replace)
        shutil.copy2(seed, create_accumulate)
        raw = [
            aplicar_politica(create_replace, False),
            aplicar_politica(create_accumulate, True),
        ]
        report = {
            "synthetic_only": True,
            "source_databases_opened": 0,
            "memories_created_per_copy": 1,
            "memory_merges_between_records": 0,
            "backfill": False,
            "engine_patches_applied": False,
            "episodes": len(EPISODIOS),
            "per_policy": raw,
            "metrics": [resumen(item) for item in raw],
            "interpretation_note": (
                "Complementarity (all historical facets remain true) and supersession "
                "(only the latest facets remain true) are separate truth assumptions, "
                "not inferred from the synthetic index hits."
            ),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
