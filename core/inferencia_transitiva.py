"""
Inferencia Transitiva Semántica (SLS) para BioRAG v19.0
======================================================
Calcula sinapsis latentes (relaciones indirectas) a través de caminos
en el grafo de sinapsis usando CTEs recursivos de SQLite, filtrados y
ponderados por coincidencia en Dimensiones Semánticas y PMI/NPMI.

Fórmula de atenuación:
  peso_latente = producto(pesos_camino) × FACTOR_DECAY^saltos × (1 + PMI_boost + Dim_boost)
  FACTOR_DECAY = 0.7, MAX_SALTOS = 3, UMBRAL_MINIMO = 0.05
"""

import time
import os
from core.pmi_semantico import score_pmi_nodo, recalcular

FACTOR_DECAY = float(os.environ.get('BIORAG_DECAY_INFERENCIA', '0.7'))
MAX_SALTOS_INFERENCIA = int(os.environ.get('BIORAG_MAX_SALTOS_INFERENCIA', '2'))
UMBRAL_MINIMO_LATENTE = float(os.environ.get('BIORAG_UMBRAL_LATENTE', '0.05'))
UMBRAL_PMI_LATENTE = float(os.environ.get('BIORAG_UMBRAL_PMI_LATENTE', '0.02'))


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

    # Filtrar candidatos con validación semántica SLS (Dimensiones O PMI)
    latentes_validas = []
    for origen, destino, peso_max, saltos_min in candidatos:
        tiene_dim = 1 if (origen, destino) in pares_dim else 0
        pmi_val = score_pmi_nodo(origen, destino)

        # Criterio de aceptación SLS: dimensión común O PMI > UMBRAL
        if tiene_dim == 1 or pmi_val >= UMBRAL_PMI_LATENTE:
            pmi_boost = max(0.0, pmi_val) * 0.5
            dim_boost = 0.1 if tiene_dim == 1 else 0.0
            peso_final = round(min(1.0, peso_max * (1.0 + pmi_boost + dim_boost)), 4)

            latentes_validas.append((
                origen,
                destino,
                peso_final,
                saltos_min,
                ahora,
                round(pmi_val, 4),
                tiene_dim
            ))

    if latentes_validas:
        cerebro.cursor.executemany("""
            INSERT OR REPLACE INTO sinapsis_latentes (
                origen, destino, peso_atenuado, saltos, calculado_en, pmi_score, tiene_dim_comun
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, latentes_validas)

    count = len(latentes_validas)
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
