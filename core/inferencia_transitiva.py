"""
Inferencia Transitiva Semántica (SLS) para BioRAG v19.0
======================================================
Calcula sinapsis latentes (relaciones indirectas) a través de caminos
en el grafo de sinapsis usando CTEs recursivos de SQLite, filtrados y
ponderados por coincidencia en Dimensiones Semánticas y PMI/NPMI.

Fórmula de atenuación:
  peso_latente = producto(pesos_camino) × FACTOR_DECAY^saltos × (1 + PMI_boost + Dim_boost)
  FACTOR_DECAY = 0.7, MAX_SALTOS = 3, UMBRAL_MINIMO = 0.05

Filtrado semántico — Criterio de Convergencia de Evidencia (DUAL VALIDATION):
  Basado en Pattern Separation del Dentate Gyrus hipocampal (Marr 1971, O'Reilly 1994).
  Una sinapsis latente se acepta SOLO si hay evidencia convergente de dos señales:

    ACEPTA si: PMI > UMBRAL_PMI_ALTO  (señal estadística fuerte — independiente)
    ACEPTA si: tiene_dim=1 AND PMI > UMBRAL_PMI_LATENTE  (convergencia dual)
    ACEPTA si: tiene_dim=1 AND peso_camino >= UMBRAL_PESO_DIM_SOLO  (topología fuerte)
    RECHAZA:   solo dimensión con PMI=0 y camino débil  (ruido categórico puro)

  Esto elimina el 'problema hub': dimensiones genéricas (ej. tipo:técnico) crean
  conexiones falsas entre nodos que solo comparten categoría, sin co-ocurrencia real.

Poda Top-K por nodo (Lateral Inhibition):
  Análogo biológico: inhibición lateral en el Dentate Gyrus — solo las K señales
  más fuertes de cada nodo 'ganan' y sobreviven. Previene nodos hiper-conectados
  que pierden poder discriminante al conectarse a 300+ nodos simultáneamente.
  Ref: Rolls & Treves (1990), O'Reilly & McClelland (1994).
"""

import time
import os
from collections import defaultdict
from core.pmi_semantico import score_pmi_nodo, recalcular

FACTOR_DECAY           = float(os.environ.get('BIORAG_DECAY_INFERENCIA',    '0.7'))
MAX_SALTOS_INFERENCIA  = int(os.environ.get('BIORAG_MAX_SALTOS_INFERENCIA', '3'))
UMBRAL_MINIMO_LATENTE  = float(os.environ.get('BIORAG_UMBRAL_LATENTE',      '0.05'))

# Umbrales de validación dual
UMBRAL_PMI_LATENTE     = float(os.environ.get('BIORAG_UMBRAL_PMI_LATENTE',  '0.02'))  # PMI mínimo (convergencia)
UMBRAL_PMI_ALTO        = float(os.environ.get('BIORAG_UMBRAL_PMI_ALTO',     '0.05'))  # PMI fuerte (señal sola)
UMBRAL_PESO_DIM_SOLO   = float(os.environ.get('BIORAG_UMBRAL_PESO_DIM',     '0.35'))  # Peso mínimo si solo hay dim

# Top-K poda por nodo (Pattern Separation — inhibición lateral)
MAX_LATENTES_POR_NODO  = int(os.environ.get('BIORAG_MAX_LATENTES_NODO',     '20'))


def _obtener_pares_dimension_comun(cerebro) -> set[tuple[str, str]]:
    """Devuelve un set de pares (origen, destino) que comparten al menos una dimensión semántica."""
    try:
        cur = cerebro.cursor.execute("""
            SELECT DISTINCT d1.concepto, d2.concepto
            FROM largo_plazo_dimensiones d1
            JOIN largo_plazo_dimensiones d2 ON d1.dimension_id = d2.dimension_id
            WHERE d1.concepto != d2.concepto
        """)
        pares = set()
        for r in cur.fetchall():
            pares.add((r[0], r[1]))
            pares.add((r[1], r[0]))
        return pares
    except Exception:
        return set()


def calcular_sinapsis_latentes(cerebro, max_saltos=None, factor_decay=None, umbral=None):
    """Recorre el grafo de sinapsis con una CTE recursiva hasta max_saltos.
    Aplica filtro SLS (Sinapsis Latentes Semánticas): valida coincidencia en dimensiones
    semánticas o PMI semántico positivo para eliminar ruido de las sinapsis latentes.

    Pobla la tabla sinapsis_latentes con pmi_score y tiene_dim_comun.
    Retorna: número de sinapsis latentes válidas generadas.
    """
    if max_saltos is None:
        max_saltos = MAX_SALTOS_INFERENCIA
    if factor_decay is None:
        factor_decay = FACTOR_DECAY
    if umbral is None:
        umbral = UMBRAL_MINIMO_LATENTE

    max_saltos = min(max_saltos, 3)  # Hard cap para proteger rendimiento

    ahora = time.time()

    # Asegurar que el PMI esté cargado/recalculado
    try:
        recalcular(cerebro)
    except Exception:
        pass

    # Obtener pares que comparten dimensión semántica
    pares_dim = _obtener_pares_dimension_comun(cerebro)

    # Vaciar caché anterior de latentes
    cerebro.cursor.execute("DELETE FROM sinapsis_latentes")

    # CTE recursiva: encontrar caminos transitivos candidatos
    query_cte = f"""
        WITH RECURSIVE caminos(origen, destino, peso_acum, saltos, ruta, tipo_camino) AS (
            -- Caso base: sinapsis directas con peso significativo
            SELECT origen, destino, ROUND(peso * {factor_decay}, 4), 1,
                   origen || ',' || destino, tipo
            FROM sinapsis
            WHERE peso >= 0.1

            UNION ALL

            -- Caso recursivo: extender caminos
            SELECT c.origen, s.destino,
                   ROUND(c.peso_acum * s.peso * {factor_decay}, 4),
                   c.saltos + 1,
                   c.ruta || ',' || s.destino,
                   s.tipo
            FROM caminos c
            JOIN sinapsis s ON s.origen = c.destino
            WHERE c.saltos < {max_saltos}
              AND c.ruta NOT LIKE '%' || s.destino || '%'
              AND (
                  c.tipo_camino IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test')
                  OR s.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test')
                  OR (c.tipo_camino = 'co_semantica' AND s.tipo = 'co_semantica')
                  OR (c.tipo_camino = 'co_nombre' AND s.tipo = 'co_nombre')
                  OR (c.tipo_camino = 'co_semantica' AND s.tipo = 'co_nombre')
                  OR (c.tipo_camino = 'co_nombre' AND s.tipo = 'co_semantica')
              )
              AND c.peso_acum * s.peso * {factor_decay} >= {umbral}
        ),
        caminos_unicos(origen, destino, peso_max, saltos_min) AS (
            SELECT origen, destino, MAX(peso_acum), MIN(saltos)
            FROM caminos
            WHERE origen != destino
            GROUP BY origen, destino
        )
        SELECT cu.origen, cu.destino, cu.peso_max, cu.saltos_min
        FROM caminos_unicos cu
        LEFT JOIN sinapsis s ON s.origen = cu.origen AND s.destino = cu.destino
        WHERE s.origen IS NULL
    """

    candidatos = cerebro.cursor.execute(query_cte).fetchall()

    # ─────────────────────────────────────────────────────────────────────
    # FILTRADO BIOLÓGICO — Atenuación Sináptica Inmadura
    # ─────────────────────────────────────────────────────────────────────
    # Basado en Sinaptogénesis (McClelland & O'Reilly, 1995):
    #   - El cerebro NO elimina sinapsis débiles inmediatamente.
    #   - Las ATENÚA: las deja existir con peso casi invisible.
    #   - Si se refuerzan por co-acceso real → LTP las fortalece.
    #   - Si nunca se activan juntas → LTD las poda eventualmente.
    #
    # Niveles de madurez sináptica:
    #   MADURA:   PMI >= UMBRAL_PMI_ALTO → peso completo (evidencia fuerte)
    #   JOVEN:    dim + PMI >= UMBRAL_PMI_LATENTE → peso completo (convergencia)
    #   INMADURA: dim + PMI=0 → peso × FACTOR_INMADUREZ (existe pero invisible)
    #   RECHAZA:  sin dim Y sin PMI → no hay evidencia de ningún tipo
    #
    # FACTOR_INMADUREZ = 0.15 (la sinapsis existe al 15% de su potencial)
    # Puede crecer a 100% si PMI se desarrolla con co-acceso futuro.
    FACTOR_INMADUREZ = 0.15

    latentes_validas = []
    for origen, destino, peso_max, saltos_min in candidatos:
        tiene_dim = 1 if (origen, destino) in pares_dim else 0
        pmi_val   = score_pmi_nodo(origen, destino)

        # Clasificación por madurez sináptica
        pmi_fuerte = pmi_val >= UMBRAL_PMI_ALTO
        pmi_minimo = pmi_val >= UMBRAL_PMI_LATENTE

        if pmi_fuerte:
            # MADURA: señal estadística fuerte, peso completo
            factor_madurez = 1.0
        elif tiene_dim == 1 and pmi_minimo:
            # JOVEN: convergencia dual real, peso completo
            factor_madurez = 1.0
        elif tiene_dim == 1:
            # INMADURA: solo dimensión, sin evidencia estadística
            # No la matamos — la atenuamos. Puede crecer con LTP.
            factor_madurez = FACTOR_INMADUREZ
        else:
            # Sin dimensión Y sin PMI → no hay evidencia de ningún tipo
            continue

        pmi_boost  = max(0.0, pmi_val) * 0.5
        dim_boost  = 0.1 if tiene_dim == 1 else 0.0
        peso_final = round(min(1.0, peso_max * (1.0 + pmi_boost + dim_boost) * factor_madurez), 4)

        latentes_validas.append((
            origen,
            destino,
            peso_final,
            saltos_min,
            ahora,
            round(pmi_val, 4),
            tiene_dim
        ))

    # ─────────────────────────────────────────────────────────────────────
    # TOP-K PODA POR NODO (Inhibición Lateral — Rolls & Treves 1990)
    # ─────────────────────────────────────────────────────────────────────
    # Cada nodo puede tener como máximo MAX_LATENTES_POR_NODO conexiones
    # latentes salientes. Se mantienen las de mayor peso_final.
    # Esto previene nodos 'hub' que se conectan a 300+ nodos y pierden
    # toda capacidad discriminante.
    por_nodo = defaultdict(list)
    for item in latentes_validas:
        por_nodo[item[0]].append(item)  # Agrupar por origen

    latentes_podadas = []
    for origen, items in por_nodo.items():
        # Ordenar por peso_final descendente, conservar Top-K
        items_sorted = sorted(items, key=lambda x: x[2], reverse=True)
        latentes_podadas.extend(items_sorted[:MAX_LATENTES_POR_NODO])

    if latentes_podadas:
        cerebro.cursor.executemany("""
            INSERT OR REPLACE INTO sinapsis_latentes (
                origen, destino, peso_atenuado, saltos, calculado_en, pmi_score, tiene_dim_comun
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, latentes_podadas)

    count = len(latentes_podadas)
    cerebro.conn.commit()
    return count


def obtener_vecinos_latentes(cerebro, concepto, limite=5):
    """Consulta sinapsis_latentes para un concepto dado.
    Retorna lista de (destino, peso_atenuado, saltos, pmi_score, tiene_dim_comun).
    Busca en ambas direcciones (origen y destino)."""
    cerebro.cursor.execute("""
        SELECT destino, peso_atenuado, saltos, pmi_score, tiene_dim_comun FROM sinapsis_latentes
        WHERE origen = ?
        UNION
        SELECT origen, peso_atenuado, saltos, pmi_score, tiene_dim_comun FROM sinapsis_latentes
        WHERE destino = ?
        ORDER BY peso_atenuado DESC
        LIMIT ?
    """, (concepto, concepto, limite))
    return cerebro.cursor.fetchall()


def obtener_score_latente(cursor_or_cerebro, concepto_query_tokens, concepto_candidato):
    """Calcula un score de inferencia transitiva entre los tokens del query
    y un candidato específico. Soporta recibir objeto cerebro o cursor SQLite."""
    if not concepto_query_tokens:
        return 0.0

    cursor = cursor_or_cerebro.cursor if hasattr(cursor_or_cerebro, 'cursor') else cursor_or_cerebro
    tokens_list = list(concepto_query_tokens)
    ph = ",".join("?" * len(tokens_list))

    cursor.execute(f"""
        SELECT MAX(sl.peso_atenuado)
        FROM sinapsis_latentes sl
        WHERE sl.destino = ?
          AND sl.origen IN (
              SELECT concepto FROM largo_plazo
              WHERE estado = 'activo'
              AND concepto IN ({ph})
          )
    """, (concepto_candidato, *tokens_list))

    row = cursor.fetchone()
    if row and row[0]:
        return min(1.0, row[0])

    # Dirección inversa
    cursor.execute(f"""
        SELECT MAX(sl.peso_atenuado)
        FROM sinapsis_latentes sl
        WHERE sl.origen = ?
          AND sl.destino IN (
              SELECT concepto FROM largo_plazo
              WHERE estado = 'activo'
              AND concepto IN ({ph})
          )
    """, (concepto_candidato, *tokens_list))

    row = cursor.fetchone()
    if row and row[0]:
        return min(1.0, row[0])

    return 0.0
