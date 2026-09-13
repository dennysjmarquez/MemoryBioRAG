"""Servicio único de lectura/escritura para MCP, CLI y dashboard.

POR QUÉ (Fase A): el dashboard escribía LIKE/INSERT crudo y se saltaba
buscar_por_frase, consolidación, dirty-set SDM y procedencia. Este módulo
no cambia la inteligencia: solo cablea las mismas primitivas del motor.

`sinapsis` es la fuente canónica del grafo. `largo_plazo.asociaciones` es
espejo histórico (core.sinapsis._sincronizar_asociaciones), no se muta
directamente desde este servicio.

Singleton: Kilo/VS Code dispara tools en paralelo. Reconstruir
SQLiteMemoryBioRAG en cada tool (~6–11s) causa MCP -32001 timeout.
Una instancia por db_path; cerrar_sistema() es no-op en ella.
"""
from __future__ import annotations

import threading
from typing import Optional

from core.paths import resolve_db_path

_lock = threading.RLock()
_cerebro = None
_path = None


def reset_cerebro():
    """Tests / cambio de BIORAG_PATH: suelta el singleton."""
    global _cerebro, _path
    with _lock:
        if _cerebro is not None:
            try:
                _cerebro._persistente = False
                _cerebro.cerrar_sistema()
            except Exception:
                pass
        _cerebro = None
        _path = None


def get_cerebro(db_path: Optional[str] = None):
    """Instancia persistente de SQLiteMemoryBioRAG (thread-safe)."""
    global _cerebro, _path
    from core.memory_store import SQLiteMemoryBioRAG

    path = resolve_db_path(db_path)
    with _lock:
        if _cerebro is not None and _path == path:
            return _cerebro
        if _cerebro is not None:
            try:
                _cerebro._persistente = False
                _cerebro.cerrar_sistema()
            except Exception:
                pass
        _cerebro = SQLiteMemoryBioRAG(path)
        _cerebro._persistente = True
        _path = path
        return _cerebro


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


def resolver_analogia(cerebro, a: str, b: str, c: str, limite: int = 5):
    """F3: A:B :: C:? por álgebra PPMI local (Plan Maestro, INVENCIÓN 5)."""
    from core.ppmi_hybrid_search import resolver_analogia_simbolica

    return resolver_analogia_simbolica(cerebro, a, b, c, limite=limite)
