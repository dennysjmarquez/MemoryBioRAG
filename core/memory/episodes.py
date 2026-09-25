"""core/memory/episodes.py - Módulo de memoria episódica y afinidad temporal.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro (recibe instancia de SQLiteMemoryBioRAG).
- Mantiene compatibilidad y acceso a cursores/estado de la base de datos.
"""

from core.memory import constants


def _ts_nodo(self, concepto):
    """Epoch de vivencia: creado_en, sino ultimo_acceso."""
    try:
        self.cursor.execute(
            "SELECT COALESCE(NULLIF(creado_en, 0), ultimo_acceso, 0) "
            "FROM largo_plazo WHERE concepto = ?",
            (concepto,),
        )
        row = self.cursor.fetchone()
        return float(row[0] or 0.0) if row else 0.0
    except Exception:
        return 0.0


def _expandir_episodio_temporal(self, nodo_ancla, ventana_horas=None, limite_episodio=None):
    """F2: nodos cronologicamente adyacentes al ancla (misma categoria o dim)."""
    if not nodo_ancla:
        return []
    vh = float(ventana_horas if ventana_horas is not None else constants.EPISODIO_VENTANA_HORAS)
    lim = int(limite_episodio if limite_episodio is not None else constants.EPISODIO_LIMITE)
    ts = self._ts_nodo(nodo_ancla)
    if ts <= 0:
        return []
    delta = max(1.0, vh) * 3600.0
    lo, hi = ts - delta, ts + delta
    try:
        self.cursor.execute(
            "SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, "
            "COALESCE(NULLIF(l.creado_en, 0), l.ultimo_acceso, 0) AS ts "
            "FROM largo_plazo l WHERE l.concepto != ? AND l.estado = 'activo' "
            "AND COALESCE(NULLIF(l.creado_en, 0), l.ultimo_acceso, 0) BETWEEN ? AND ? "
            "ORDER BY ABS(COALESCE(NULLIF(l.creado_en, 0), l.ultimo_acceso, 0) - ?) "
            "LIMIT ?",
            (nodo_ancla, lo, hi, ts, max(lim * 4, 20)),
        )
        cands = self.cursor.fetchall()
    except Exception:
        return []
    cat_a = None
    dims_a = set()
    try:
        self.cursor.execute("SELECT categoria FROM largo_plazo WHERE concepto = ?", (nodo_ancla,))
        r = self.cursor.fetchone()
        cat_a = r[0] if r else None
        self.cursor.execute(
            "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?",
            (nodo_ancla,),
        )
        dims_a = {row[0] for row in self.cursor.fetchall()}
    except Exception:
        pass
    out = []
    for conc, cont, peso, est, asoc, cts in cands:
        ok = False
        try:
            self.cursor.execute("SELECT categoria FROM largo_plazo WHERE concepto = ?", (conc,))
            rc = self.cursor.fetchone()
            if cat_a is not None and rc and rc[0] == cat_a:
                ok = True
            if not ok and dims_a:
                self.cursor.execute(
                    "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?",
                    (conc,),
                )
                if dims_a & {row[0] for row in self.cursor.fetchall()}:
                    ok = True
        except Exception:
            ok = True
        if not ok:
            continue
        out.append({
            "concepto": conc,
            "contenido": cont,
            "peso": peso,
            "estado": est,
            "asociaciones": asoc or "",
            "ts": float(cts or 0.0),
        })
        if len(out) >= lim:
            break
    return out


def _afinidad_temporal_pool(self, conceptos):
    """F2: 1.0 si comparte bucket dia/sesion con otro del pool. O(k)."""
    if constants.EPISODIO_TEMPORAL_PESO <= 0 or not conceptos:
        return {}
    uniq = [c for c in conceptos if c]
    if len(uniq) < 2:
        return {c: 0.0 for c in uniq}
    ph = ",".join("?" * len(uniq))
    ts_map = {}
    try:
        self.cursor.execute(
            f"SELECT concepto, COALESCE(NULLIF(creado_en, 0), ultimo_acceso, 0) "
            f"FROM largo_plazo WHERE concepto IN ({ph})",
            uniq,
        )
        for conc, ts in self.cursor.fetchall():
            ts_map[conc] = float(ts or 0.0)
    except Exception:
        return {c: 0.0 for c in uniq}
    buck = constants.EPISODIO_BUCKET_SEG if constants.EPISODIO_BUCKET_SEG > 0 else 86400.0
    counts = {}
    for c in uniq:
        t = ts_map.get(c, 0.0)
        if t <= 0:
            continue
        b = int(t // buck)
        counts[b] = counts.get(b, 0) + 1
    out = {}
    for c in uniq:
        t = ts_map.get(c, 0.0)
        if t <= 0:
            out[c] = 0.0
            continue
        out[c] = 1.0 if counts.get(int(t // buck), 0) >= 2 else 0.0
    return out
