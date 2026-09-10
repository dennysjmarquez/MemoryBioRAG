"""Servicio único de lectura/escritura para MCP, CLI y dashboard.

POR QUÉ (Fase A): el dashboard escribía LIKE/INSERT crudo y se saltaba
buscar_por_frase, consolidación, dirty-set SDM y procedencia. Este módulo
no cambia la inteligencia: solo cablea las mismas primitivas del motor.

`sinapsis` es la fuente canónica del grafo. `largo_plazo.asociaciones` es
espejo histórico (core.sinapsis._sincronizar_asociaciones), no se muta
directamente desde este servicio.
"""
from __future__ import annotations

from typing import Optional

from core.paths import resolve_db_path


def get_cerebro(db_path: Optional[str] = None):
    """Instancia SQLiteMemoryBioRAG sobre el DB_PATH canónico."""
    from core.memory_store import SQLiteMemoryBioRAG

    path = resolve_db_path(db_path)
    return SQLiteMemoryBioRAG(path)


def buscar(cerebro, frase: str, **kwargs):
    """Recuperación híbrida común. Siempre pasa por buscar_por_frase()."""
    return cerebro.buscar_por_frase(frase, **kwargs)


def aprender(
    cerebro,
    concepto: str,
    contenido: str,
    sinonimos: str = "",
    categoria: str = "General",
    dimensiones=None,
    predicados=None,
    consolidar: bool = True,
):
    """Escritura canónica: corto plazo → (opcional) consolidar_concepto.

    POR QUÉ consolidar por defecto: una interfaz que «aprende» debe dejar el
    nodo recuperable por FTS/SDM/PPMI, no solo en RAM de trabajo.
    """
    cerebro.percibir_corto_plazo(
        concepto, contenido, sinonimos or "", categoria, dimensiones, predicados
    )
    if consolidar:
        cerebro.consolidar_concepto(concepto)
    return {"ok": True, "concepto": concepto.lower().strip(), "consolidado": consolidar}


def ensenar_lexico(cerebro, expression_surface: str, canonical_concept: str, **kwargs):
    """Enseñanza léxica atómica (Fase B)."""
    from core.lexical_learning import ensenar_expresion

    return ensenar_expresion(cerebro, expression_surface, canonical_concept, **kwargs)


def consolidar_ciclo(cerebro):
    """Sueño completo. Todas las interfaces deben llamar esto, no SQL suelto."""
    return cerebro.ciclo_sueno_consolidacion()
