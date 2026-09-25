"""
Módulo de contexto epistémico y coherencia dimensional.

Extraído de SQLiteMemoryBioRAG (Paso 3.4c - T17).
"""

import logging

logger = logging.getLogger("BioRAG.MemoryStore")


def _epistemico_coherencia_dimensional(self, top_conceptos):
    """Fraccion del top-k (sin top-1) que comparte >=1 dimension con top-1."""
    if not top_conceptos or len(top_conceptos) < 2:
        return 0.0
    try:
        ph = ",".join("?" for _ in top_conceptos)
        dims = {}
        for concepto, dim_id in self.cursor.execute(
                "SELECT concepto, dimension_id FROM largo_plazo_dimensiones WHERE concepto IN (%s)" % ph,
                tuple(top_conceptos)):
            dims.setdefault(concepto, set()).add(dim_id)
        base = dims.get(top_conceptos[0]) or set()
        if not base:
            return 0.0
        resto = top_conceptos[1:]
        return sum(1 for c in resto if (dims.get(c) or set()) & base) / len(resto)
    except Exception as e:
        logger.warning("epistemico: coherencia_dimensional fallo, coh=0 (%s: %s)", type(e).__name__, e)
        return 0.0


def _epistemico_evaluar(self, pagina_resultados):
    """Ce = 0.5*top1 + 0.3*densidad_top5 + 0.2*coherencia_dim. Solo lectura."""
    top = list(pagina_resultados or [])[:self.EPISTEMICO_TOP_K]
    if not top:
        return {"estado_epistemico": "vacio_cognitivo", "Ce": 0.0,
                "top1_score": 0.0, "densidad_pool": 0.0,
                "coherencia_dimensional": 0.0}

    def _clip(x):
        try:
            return max(0.0, min(1.0, float(x or 0.0)))
        except Exception as e:
            logger.warning("epistemico: clip score fallo, score=0 (%s: %s)", type(e).__name__, e)
            return 0.0

    scores = [_clip(r[4]) for r in top]
    s1 = scores[0]
    densidad = sum(scores) / len(scores)
    dim_coh = self._epistemico_coherencia_dimensional([r[0] for r in top])
    ce = round(0.5 * s1 + 0.3 * densidad + 0.2 * dim_coh, 4)
    if ce >= self.EPISTEMICO_UMBRAL_CONOCIDO:
        estado = "conocido"
    elif ce >= self.EPISTEMICO_UMBRAL_INCERTIDUMBRE:
        estado = "incertidumbre_parcial"
    else:
        estado = "vacio_cognitivo"
    return {"estado_epistemico": estado, "Ce": ce,
            "top1_score": round(s1, 4), "densidad_pool": round(densidad, 4),
            "coherencia_dimensional": round(dim_coh, 4)}


def _epistemico_publicar(self, frase, pagina_resultados, total):
    """Hook de cola: merge metadatos en last_estado_epistemico + encola vacios.
    JAMAS muta pagina_resultados. Devuelve None."""
    try:
        info = self._epistemico_evaluar(pagina_resultados)
    except Exception as e:
        logger.warning("epistemico: evaluar fallo, sin metadatos (%s: %s)", type(e).__name__, e)
        return
    try:
        base = getattr(self, "last_estado_epistemico", {}) or {}
        if not isinstance(base, dict):
            base = {}
        merged = dict(base)
        merged.update(info)
        merged["epistemico_n_resultados"] = len(pagina_resultados or [])
        self.last_estado_epistemico = merged
    except Exception as e:
        logger.warning("epistemico: merge metadatos fallo (%s: %s)", type(e).__name__, e)
    if info.get("estado_epistemico") == "vacio_cognitivo":
        self._epistemico_encolar_vacio(frase, info.get("Ce", 0.0))


def _epistemico_publicar_sin_consulta(self):
    """Early-exit (query vacia/basura): no hubo busqueda, no es vacio."""
    try:
        base = getattr(self, "last_estado_epistemico", {}) or {}
        if not isinstance(base, dict):
            base = {}
        merged = dict(base)
        merged.update({"estado_epistemico": "sin_consulta", "Ce": 0.0,
                       "epistemico_n_resultados": 0})
        self.last_estado_epistemico = merged
    except Exception as e:
        logger.warning("epistemico: sin_consulta fallo (%s: %s)", type(e).__name__, e)


def _epistemico_encolar_vacio(self, frase, ce):
    """Encola termino no resuelto en estado_hormiga.json (vacios_cognitivos).
    Best-effort con dedup exacto y cap FIFO: jamas rompe la busqueda."""
    try:
        termino = (frase or "").strip()[:200]
        if not termino:
            return
        from core.dmn_reflexion import _cargar_estado, _guardar_estado
        import time as _t
        estado = _cargar_estado()
        cola = estado.get("vacios_cognitivos")
        if not isinstance(cola, list):
            cola = []
        if any(isinstance(e, dict) and e.get("termino") == termino for e in cola):
            return
        cola.append({"termino": termino, "Ce": float(ce or 0.0), "ts": _t.time()})
        estado["vacios_cognitivos"] = cola[-self.EPISTEMICO_VACIOS_CAP:]
        _guardar_estado(estado)
    except Exception as e:
        logger.warning("epistemico: encolar vacio DMN fallo (%s: %s)", type(e).__name__, e)
