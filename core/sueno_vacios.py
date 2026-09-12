"""Consolidacion de vacios epistemicos en el ciclo de sueno (Mision c).

Lee la cola `vacios_cognitivos` de estado_hormiga.json (producida por
OPT-NUEVA-5 en modo metadata) y consolida hipotesis de sueno entre los
nodos candidatos con afinidad lexica (FTS5) al termino no resuelto:

  - `sinapsis` tipo='hipotesis_sueno', peso prudente (canal topologico;
    cf. precedente 'latente_confirmada').
  - `sinapsis_latentes` con peso_atenuado minimo (canal de scoring v16.0:
    boost por inferencia transitiva en buscar_por_frase).

100% local: FTS5 + dimensiones + tokens. Sin APIs, sin red, sin embeddings.
NUNCA se ejecuta en la ruta de busqueda en vivo: solo via sleep_cycle.py.

Orden de persistencia: commit DB primero, cola despues. Si el commit falla,
la cola queda intacta (reintento limpio proximo ciclo); si falla el guardado
de estado tras el commit, el proximo ciclo reprocesa con dedup (0 nuevas).
"""

import logging
import re
import time

logger = logging.getLogger("BioRAG.SuenoVacios")

SUENO_TIPO = "hipotesis_sueno"
# HIPOTESIS documentada (sin set calibrado): sobrevive la poda de sueno
# (DELETE peso<0.05) pero << promedio observado en sinapsis (0.68).
SUENO_PESO_SINAPSIS = 0.08
# = UMBRAL_MINIMO documentado del SLS v19.0 (core/inferencia_transitiva.py).
SUENO_PESO_LATENTE = 0.05
# Convencion observada en snapshot: 100% latentes con saltos=2.
SUENO_SALTOS = 2
SUENO_MAX_VACIOS = 50
SUENO_TOP_CANDIDATOS = 3
SUENO_PROCESADOS_CAP = 200
# HIPOTESIS provisional v2: umbral coseno PPMI para rescate semantico.
# Se calibra contra la distribucion real de la cola antes de consolidar.
SUENO_PPMI_UMBRAL = 0.25

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _tokens(termino):
    return [t.lower() for t in _TOKEN_RE.findall(termino or "") if len(t) > 2]


def afinidad_candidatos(cerebro, termino, k=SUENO_TOP_CANDIDATOS):
    """Nodos activos con afinidad lexica FTS5 al termino. Huerfanos primero.

    Determinista: rank FTS5, desempate estable huerfano(grado 0 en sinapsis)
    antes que conectado. Solo lectura.
    """
    toks = _tokens(termino)
    if not toks:
        return []
    q = " OR ".join(toks[:12])
    try:
        rows = cerebro.cursor.execute(
            "SELECT concepto FROM largo_plazo_fts"
            " WHERE largo_plazo_fts MATCH ? ORDER BY rank LIMIT ?",
            (q, max(k * 2, 6)),
        ).fetchall()
    except Exception as e:
        logger.warning("sueno: FTS afinidad fallo (%s: %s)", type(e).__name__, e)
        return []
    conceptos = [r[0] for r in rows]
    if not conceptos:
        return []
    ph = ",".join("?" * len(conceptos))
    try:
        activos = {
            r[0]
            for r in cerebro.cursor.execute(
                "SELECT concepto FROM largo_plazo"
                " WHERE concepto IN (%s) AND estado='activo'" % ph,
                tuple(conceptos),
            )
        }
    except Exception as e:
        logger.warning("sueno: filtro activos fallo (%s: %s)", type(e).__name__, e)
        return []
    cand = [c for c in conceptos if c in activos]
    grados = {}
    for c in cand:
        try:
            grados[c] = cerebro.cursor.execute(
                "SELECT COUNT(*) FROM sinapsis WHERE origen=? OR destino=?",
                (c, c),
            ).fetchone()[0]
        except Exception:
            grados[c] = 1
    cand.sort(key=lambda c: (0 if grados[c] == 0 else 1,))
    return cand[:k]


_LAT_VAL_FIJO = ("origen", "destino", "peso_atenuado", "saltos", "calculado_en")
_LAT_VAL_OPT = ("pmi_score", "tiene_dim_comun", "strikes")


def _latentes_have(cursor):
    """Columnas reales de sinapsis_latentes (DBs viejas carecen de strikes)."""
    try:
        return {r[1] for r in cursor.execute("PRAGMA table_info(sinapsis_latentes)")}
    except Exception:
        return set(_LAT_VAL_FIJO)


def afinidad_semantica(cerebro, termino, k=SUENO_TOP_CANDIDATOS,
                       umbral=SUENO_PPMI_UMBRAL, idx=None, activos=None):
    """Fallback PPMI v2: Top-k nodos activos por coseno query-vector.

    Solo lectura. Determinista (desempate por nombre). Solo se invoca
    cuando FTS5 devuelve <2 candidatos. Devuelve [(concepto, coseno)].
    `idx` permite inyectar vectores en tests (patron F3 aprobado).
    """
    try:
        from core.ppmi_hybrid_search import IndicesBioRAG, _coseno, _tokenizar
    except Exception as e:
        logger.warning("sueno: import ppmi fallo (%s: %s)", type(e).__name__, e)
        return []
    try:
        if idx is None:
            idx = IndicesBioRAG(cerebro.conn)
        toks = [t for t in _tokenizar(termino or "")]
        if not toks:
            return []
        vq = idx.vector_query(toks)
        if float((vq * vq).sum()) < 1e-12:
            return []  # sin tokens conocidos: sin info semantica
        if activos is None:
            activos = {
                r[0]
                for r in cerebro.cursor.execute(
                    "SELECT concepto FROM largo_plazo WHERE estado='activo'"
                )
            }
        cand = []
        for c in idx.todos_los_conceptos:
            if c not in activos:
                continue
            v = idx.vecs.get(c)
            if v is None or float((v * v).sum()) < 1e-12:
                continue
            cos = float(_coseno(vq, v))
            if cos >= umbral:
                cand.append((c, round(cos, 4)))
        cand.sort(key=lambda item: (-item[1], item[0]))
        return cand[:k]
    except Exception as e:
        logger.warning("sueno: afinidad semantica fallo (%s: %s)", type(e).__name__, e)
        return []


def _dim_comun(cursor, a, b):
    try:
        row = cursor.execute(
            "SELECT 1 FROM largo_plazo_dimensiones A"
            " JOIN largo_plazo_dimensiones B ON A.dimension_id=B.dimension_id"
            " WHERE A.concepto=? AND B.concepto=? LIMIT 1",
            (a, b),
        ).fetchone()
        return 1 if row else 0
    except Exception:
        return 0


def _existe(cursor, tabla, a, b):
    """Dedup fail-closed: si no puedo verificar, asumo que existe."""
    try:
        return (
            cursor.execute(
                "SELECT 1 FROM %s WHERE (origen=? AND destino=?)"
                " OR (origen=? AND destino=?) LIMIT 1" % tabla,
                (a, b, b, a),
            ).fetchone()
            is not None
        )
    except Exception as e:
        logger.warning(
            "sueno: dedup %s fallo (%s: %s)", tabla, type(e).__name__, e
        )
        return True


def consolidar_vacios(cerebro, max_vacios=None, idx_sem=None):
    """Consume la cola vacios_cognitivos y consolida hipotesis. Nunca lanza.

    Devuelve resumen dict con atendidos/omitidos/sin_pares/sinapsis_nuevas/
    latentes_nuevas/elapsed_s.
    """
    t0 = time.time()
    resumen = {
        "atendidos": 0,
        "omitidos": 0,
        "sin_pares": 0,
        "sinapsis_nuevas": 0,
        "latentes_nuevas": 0,
        "elapsed_s": 0.0,
    }
    max_vacios = SUENO_MAX_VACIOS if max_vacios is None else max_vacios
    try:
        from core.dmn_reflexion import _cargar_estado, _guardar_estado

        estado = _cargar_estado()
    except Exception as e:
        logger.warning("sueno: estado hormiga ilegible (%s: %s)", type(e).__name__, e)
        return resumen
    cola = estado.get("vacios_cognitivos")
    if not isinstance(cola, list):
        cola = []
    if not cola:
        return resumen
    procesados = estado.get("vacios_procesados")
    if not isinstance(procesados, list):
        procesados = []
    ahora = time.time()
    lat_have = _latentes_have(cerebro.cursor)
    idx_shared = idx_sem  # seam tests (vectores inyectados patron F3)
    activos_sem = None
    ppmi_roto = False
    lote = cola[:max_vacios]
    resto = cola[max_vacios:]
    for item in lote:
        termino = item.get("termino", "") if isinstance(item, dict) else ""
        termino = (termino or "").strip()[:200]
        if not termino:
            resumen["omitidos"] += 1
            continue
        try:
            cands = afinidad_candidatos(cerebro, termino, SUENO_TOP_CANDIDATOS)
        except Exception as e:
            logger.warning(
                "sueno: afinidad '%s' fallo (%s: %s)",
                termino[:60],
                type(e).__name__,
                e,
            )
            resumen["omitidos"] += 1
            continue
        # v2: fallback semantico PPMI si FTS aporta <k (complementa, no reemplaza)
        via = "lexica"
        if len(cands) < SUENO_TOP_CANDIDATOS and not ppmi_roto:
            try:
                if idx_shared is None:
                    from core.ppmi_hybrid_search import IndicesBioRAG

                    idx_shared = IndicesBioRAG(cerebro.conn)
                if activos_sem is None:
                    activos_sem = {
                        r[0]
                        for r in cerebro.cursor.execute(
                            "SELECT concepto FROM largo_plazo WHERE estado='activo'"
                        )
                    }
                faltan = SUENO_TOP_CANDIDATOS - len(cands)
                sem = afinidad_semantica(
                    cerebro, termino, faltan, SUENO_PPMI_UMBRAL,
                    idx=idx_shared, activos=activos_sem,
                )
                n_prev = len(cands)
                nuevos = [c for c, _ in sem if c not in cands][:faltan]
                cands = cands + nuevos
                if nuevos:
                    via = "mixta" if n_prev > 0 else "semantica"
            except Exception as e:
                logger.warning("sueno: fallback ppmi deshabilitado (%s: %s)",
                               type(e).__name__, e)
                ppmi_roto = True
        nuevas_s, nuevas_l, pares = 0, 0, []
        if len(cands) >= 2:
            for i in range(len(cands)):
                for j in range(i + 1, len(cands)):
                    a, b = sorted((cands[i], cands[j]))
                    if a == b:
                        continue
                    try:
                        if not _existe(cerebro.cursor, "sinapsis", a, b):
                            cerebro.cursor.execute(
                                "INSERT INTO sinapsis"
                                " (origen, destino, peso, tipo, creado_en, ultimo_uso)"
                                " VALUES (?, ?, ?, ?, ?, ?)",
                                (
                                    a,
                                    b,
                                    SUENO_PESO_SINAPSIS,
                                    SUENO_TIPO,
                                    ahora,
                                    ahora,
                                ),
                            )
                            nuevas_s += 1
                        if not _existe(cerebro.cursor, "sinapsis_latentes", a, b):
                            dimc = _dim_comun(cerebro.cursor, a, b)
                            vals = {
                                "origen": a,
                                "destino": b,
                                "peso_atenuado": SUENO_PESO_LATENTE,
                                "saltos": SUENO_SALTOS,
                                "calculado_en": ahora,
                                "pmi_score": 0.0,
                                "tiene_dim_comun": dimc,
                                "strikes": 0,
                            }
                            cols = [c for c in vals if c in lat_have]
                            cerebro.cursor.execute(
                                "INSERT INTO sinapsis_latentes (%s) VALUES (%s)"
                                % (",".join(cols), ",".join("?" * len(cols))),
                                tuple(vals[c] for c in cols),
                            )
                            nuevas_l += 1
                        pares.append(a + "<>" + b)
                    except Exception as e:
                        logger.warning(
                            "sueno: par %s<>%s fallo (%s: %s)",
                            a,
                            b,
                            type(e).__name__,
                            e,
                        )
        else:
            resumen["sin_pares"] += 1
        resumen["sinapsis_nuevas"] += nuevas_s
        resumen["latentes_nuevas"] += nuevas_l
        resumen["atendidos"] += 1
        procesados.append(
            {
                "termino": termino,
                "Ce": item.get("Ce", 0.0) if isinstance(item, dict) else 0.0,
                "ts": ahora,
                "candidatos": cands,
                "pares": pares,
                "sinapsis_nuevas": nuevas_s,
                "latentes_nuevas": nuevas_l,
                "via": via,
            }
        )
    # Items venenosos (vacíos/corruptos) se descartan: jamás atascan la cola.
    estado["vacios_cognitivos"] = resto
    estado["vacios_procesados"] = procesados[-SUENO_PROCESADOS_CAP:]
    try:
        cerebro.conn.commit()
    except Exception as e:
        logger.warning("sueno: commit fallo (%s: %s)", type(e).__name__, e)
        try:
            cerebro.conn.rollback()
        except Exception:
            pass
        return resumen
    try:
        _guardar_estado(estado)
    except Exception as e:
        logger.warning("sueno: guardar estado fallo (%s: %s)", type(e).__name__, e)
    resumen["elapsed_s"] = round(time.time() - t0, 2)
    return resumen
