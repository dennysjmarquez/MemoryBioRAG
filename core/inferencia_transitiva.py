"""
Inferencia Transitiva para BioRAG v16.0
Calcula sinapsis latentes (relaciones indirectas) a través de caminos
en el grafo de sinapsis usando CTEs recursivos de SQLite.

Fórmula de atenuación:
  peso_latente = producto(pesos_camino) × FACTOR_DECAY^saltos
  FACTOR_DECAY = 0.7, MAX_SALTOS = 3, UMBRAL_MINIMO = 0.05
"""

import time
import os

FACTOR_DECAY = float(os.environ.get('BIORAG_DECAY_INFERENCIA', '0.7'))
MAX_SALTOS_INFERENCIA = int(os.environ.get('BIORAG_MAX_SALTOS_INFERENCIA', '2'))
UMBRAL_MINIMO_LATENTE = float(os.environ.get('BIORAG_UMBRAL_LATENTE', '0.05'))


def calcular_sinapsis_latentes(cerebro, max_saltos=None, factor_decay=None, umbral=None):
    """Recorre el grafo de sinapsis con una CTE recursiva hasta max_saltos.
    Calcula peso_atenuado para cada par (origen, destino) no directamente conectado.
    Pobla la tabla sinapsis_latentes (reemplaza el contenido anterior).

    Retorna: número de sinapsis latentes generadas.
    """
    if max_saltos is None:
        max_saltos = MAX_SALTOS_INFERENCIA
    if factor_decay is None:
        factor_decay = FACTOR_DECAY
    if umbral is None:
        umbral = UMBRAL_MINIMO_LATENTE

    max_saltos = min(max_saltos, 3)  # Hard cap para proteger rendimiento

    ahora = time.time()

    # Vaciar caché anterior
    cerebro.cursor.execute("DELETE FROM sinapsis_latentes")

    # CTE recursiva: encontrar caminos transitivos con poda temprana
    cerebro.cursor.execute(f"""
        WITH RECURSIVE caminos(origen, destino, peso_acum, saltos) AS (
            -- Caso base: sinapsis directas con peso significativo
            SELECT origen, destino, ROUND(peso * {factor_decay}, 4), 1
            FROM sinapsis
            WHERE peso >= 0.1

            UNION ALL

            -- Caso recursivo: extender caminos
            SELECT c.origen, s.destino,
                   ROUND(c.peso_acum * s.peso * {factor_decay}, 4),
                   c.saltos + 1
            FROM caminos c
            JOIN sinapsis s ON s.origen = c.destino
            WHERE c.saltos < {max_saltos}
              AND s.destino != c.origen
              AND c.peso_acum * s.peso * {factor_decay} >= {umbral}
        ),
        caminos_unicos AS (
            SELECT origen, destino, MAX(peso_acum) AS peso_max, MIN(saltos) AS saltos_min
            FROM caminos
            WHERE origen != destino
            GROUP BY origen, destino
        )
        INSERT INTO sinapsis_latentes (origen, destino, peso_atenuado, saltos, calculado_en)
        SELECT cu.origen, cu.destino, cu.peso_max, cu.saltos_min, {ahora}
        FROM caminos_unicos cu
        LEFT JOIN sinapsis s ON s.origen = cu.origen AND s.destino = cu.destino
        WHERE s.origen IS NULL
    """)

    count = cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis_latentes").fetchone()[0]
    cerebro.conn.commit()
    return count


def obtener_vecinos_latentes(cerebro, concepto, limite=5):
    """Consulta sinapsis_latentes para un concepto dado.
    Retorna lista de (destino, peso_atenuado, saltos).
    Busca en ambas direcciones (origen y destino)."""
    cerebro.cursor.execute("""
        SELECT destino, peso_atenuado, saltos FROM sinapsis_latentes
        WHERE origen = ?
        UNION
        SELECT origen, peso_atenuado, saltos FROM sinapsis_latentes
        WHERE destino = ?
        ORDER BY peso_atenuado DESC
        LIMIT ?
    """, (concepto, concepto, limite))
    return cerebro.cursor.fetchall()


def obtener_score_latente(cerebro, concepto_query_tokens, concepto_candidato):
    """Calcula un score de inferencia transitiva entre los tokens del query
    y un candidato específico. Busca si algún token del query tiene una
    sinapsis latente con el candidato.

    Retorna: float entre 0.0 y 1.0 (máximo peso latente encontrado)."""
    if not concepto_query_tokens:
        return 0.0

    # Buscar si el candidato tiene sinapsis latentes con algún nodo
    # que comparta tokens con el query
    cerebro.cursor.execute("""
        SELECT MAX(sl.peso_atenuado)
        FROM sinapsis_latentes sl
        WHERE sl.destino = ?
          AND sl.origen IN (
              SELECT concepto FROM largo_plazo
              WHERE estado = 'activo'
              AND concepto IN ({})
          )
    """.format(",".join("?" * len(concepto_query_tokens))),
        (concepto_candidato, *concepto_query_tokens))

    row = cerebro.cursor.fetchone()
    if row and row[0]:
        return min(1.0, row[0])

    # Dirección inversa
    cerebro.cursor.execute("""
        SELECT MAX(sl.peso_atenuado)
        FROM sinapsis_latentes sl
        WHERE sl.origen = ?
          AND sl.destino IN (
              SELECT concepto FROM largo_plazo
              WHERE estado = 'activo'
              AND concepto IN ({})
          )
    """.format(",".join("?" * len(concepto_query_tokens))),
        (concepto_candidato, *concepto_query_tokens))

    row = cerebro.cursor.fetchone()
    if row and row[0]:
        return min(1.0, row[0])

    return 0.0
