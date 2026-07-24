"""
Sparse Distributed Memory (SDM) para BioRAG v19.0
===================================================
Codificación binaria dispersa de 1024 bits (Kanerva 1988) para recuperación por
distancia Hamming. Funciona como Capa 3 en el pipeline de búsqueda cuando FTS5
no devuelve suficientes resultados exactos.

Estructura del Vector SDM (1024 bits = 128 bytes):
  - bits 0..399   (40%) -> Hash de tokens de contenido (stemmed + stopwords)
  - bits 400..599  (20%) -> Hash de tokens de concepto
  - bits 600..799  (20%) -> Hash de dimensiones semánticas
  - bits 800..899  (10%) -> Hash de categoría
  - bits 900..1023 (10%) -> Hash de vecinos sinápticos directos

Sin dependencias externas (utiliza hashlib y bit_count nativo de Python).
"""

import hashlib
import time
import os
from core.stemmer_es import stem

SDM_BITS = 1024
SDM_BYTES = 128
SDM_RADIO_DEFAULT = int(os.environ.get('BIORAG_SDM_RADIO', '250'))


def _hash_token_a_bit(token: str, min_bit: int, max_bit: int) -> int:
    """Mapea un token a una posición de bit unívoca en el rango [min_bit, max_bit)."""
    rango = max_bit - min_bit
    if rango <= 0:
        return min_bit
    h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
    return min_bit + (h % rango)


def generar_vector_sdm(concepto: str, contenido: str = "", categoria: str = "",
                       dimensiones: list[str] = None, vecinos: list[str] = None) -> bytes:
    """Genera un vector binario disperso de 1024 bits (128 bytes) para un nodo."""
    bit_array = [0] * SDM_BITS

    # 1. Concepto (bits 400..599)
    tokens_concepto = [stem(t.lower()) for t in concepto.split() if len(t) >= 2]
    for tok in tokens_concepto:
        b = _hash_token_a_bit(tok, 400, 600)
        bit_array[b] = 1

    # 2. Contenido (bits 0..399)
    if contenido:
        tokens_contenido = [stem(t.lower()) for t in contenido.split() if len(t) >= 3]
        for tok in set(tokens_contenido[:50]):  # cap 50 tokens
            b = _hash_token_a_bit(tok, 0, 400)
            bit_array[b] = 1

    # 3. Dimensiones Semánticas (bits 600..799)
    if dimensiones:
        for dim in dimensiones:
            b = _hash_token_a_bit(str(dim).lower(), 600, 800)
            bit_array[b] = 1

    # 4. Categoría (bits 800..899)
    if categoria is not None:
        b = _hash_token_a_bit(str(categoria).lower(), 800, 900)
        bit_array[b] = 1

    # 5. Vecinos sinápticos (bits 900..1023)
    if vecinos:
        for vec in vecinos:
            b = _hash_token_a_bit(str(vec).lower(), 900, 1024)
            bit_array[b] = 1

    # Empaquetar bits en bytes
    bytes_list = bytearray(SDM_BYTES)
    for i in range(SDM_BITS):
        if bit_array[i]:
            byte_idx = i // 8
            bit_idx = i % 8
            bytes_list[byte_idx] |= (1 << (7 - bit_idx))

    return bytes(bytes_list)


def distancia_hamming(vec1: bytes, vec2: bytes) -> int:
    """Calcula la distancia Hamming (bits diferentes) entre dos vectores SDM de 128 bytes."""
    if len(vec1) != SDM_BYTES or len(vec2) != SDM_BYTES:
        return SDM_BITS
    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')
    return (int1 ^ int2).bit_count()


def similitud_sdm(vec1: bytes, vec2: bytes) -> float:
    """Similitud SDM por Jaccard sobre bits activos (no Hamming).

    Analogía biológica: dos engramas se parecen cuando comparten
    NEURONAS ACTIVAS, no cuando comparten silencio. La distancia
    Hamming clásica inflaba la similitud porque 90%+ de los bits
    eran 0 en ambos vectores (esparsidad simétrica).

    Jaccard sobre bits activos:
      J = |A ∩ B| / |A ∪ B|  (solo bits encendidos)

    Esto elimina la inflación por ceros compartidos y da una
    medida real de solapamiento de representación.
    """
    if len(vec1) != SDM_BYTES or len(vec2) != SDM_BYTES:
        return 0.0
    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')
    bits_interseccion = (int1 & int2).bit_count()  # Bits 1 en AMBOS
    bits_union = (int1 | int2).bit_count()          # Bits 1 en CUALQUIERA
    if bits_union == 0:
        return 0.0
    return round(bits_interseccion / bits_union, 4)


def indexar_nodo_sdm(cerebro, concepto: str) -> bool:
    """Genera e inserta/actualiza el vector SDM para un nodo individual."""
    try:
        # Obtener nodo
        row = cerebro.cursor.execute(
            "SELECT categoria, contenido FROM largo_plazo WHERE concepto = ?", (concepto,)
        ).fetchone()
        if not row:
            return False
        cat, cont = row[0] or "", row[1] or ""

        # Obtener dimensiones
        dims_rows = cerebro.cursor.execute(
            "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?", (concepto,)
        ).fetchall()
        dims = [r[0] for r in dims_rows]

        # Obtener vecinos sinápticos
        vecinos_rows = cerebro.cursor.execute(
            "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
            (concepto, concepto)
        ).fetchall()
        vecinos = [r[0] for r in vecinos_rows]

        vector = generar_vector_sdm(concepto, cont, cat, dims, vecinos)
        ahora = time.time()

        cerebro.cursor.execute(
            "INSERT OR REPLACE INTO nodos_sdm (concepto, vector, actualizado_en) VALUES (?, ?, ?)",
            (concepto, vector, ahora)
        )
        cerebro.conn.commit()
        return True
    except Exception:
        return False


def indexar_todos_sdm(cerebro) -> int:
    """Recalcula los vectores SDM para todos los nodos activos de largo plazo."""
    cur = cerebro.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'activo'")
    nodos = [r[0] for r in cur.fetchall()]
    count = 0
    for concepto in nodos:
        if indexar_nodo_sdm(cerebro, concepto):
            count += 1
    return count


def buscar_sdm(cerebro, query: str = "", radio_max: int = None, limite: int = 10,
               vector_fijo: bytes = None) -> list[dict]:
    """Busca nodos conceptualmente similares usando distancia Hamming en el espacio SDM.

    Modos de operación:
    1. Query por texto (vector_fijo=None): genera vector desde el query text.
    2. Query por ejemplo (vector_fijo=bytes): usa el vector proporcionado directamente.
       Esto permite "buscar nodos similares a ESTE nodo" — búsqueda semántica pura.

    Retorna lista de dicts: [{'concepto': str, 'distancia': int, 'similitud': float}]
    """
    if radio_max is None:
        radio_max = SDM_RADIO_DEFAULT

    # Determinar vector de consulta
    if vector_fijo is not None:
        query_vec = vector_fijo
    else:
        query_vec = generar_vector_sdm(concepto=query, contenido=query)

    # Cargar todos los vectores SDM
    cur = cerebro.cursor.execute("SELECT concepto, vector FROM nodos_sdm")
    filas = cur.fetchall()

    if not filas:
        indexar_todos_sdm(cerebro)
        cur = cerebro.cursor.execute("SELECT concepto, vector FROM nodos_sdm")
        filas = cur.fetchall()

    resultados = []
    for concepto, vec_blob in filas:
        dist = distancia_hamming(query_vec, vec_blob)
        if dist <= radio_max:
            sim = similitud_sdm(query_vec, vec_blob)
            resultados.append({
                'concepto': concepto,
                'distancia': dist,
                'similitud': sim
            })

    resultados.sort(key=lambda x: x['distancia'])
    return resultados[:limite]


def buscar_similares_a(cerebro, concepto_semilla: str, radio_max: int = None,
                       limite: int = 10) -> list[dict]:
    """Busca nodos similares a un nodo conocido — query-by-example.

    Toma el vector SDM del nodo semilla y busca nodos con Hamming distance baja.
    Esta es la función que convierte al SDM en una base vectorial ligera.

    Retorna lista de dicts: [{'concepto': str, 'distancia': int, 'similitud': float}]
    """
    # Obtener vector del nodo semilla
    cur = cerebro.cursor.execute(
        "SELECT vector FROM nodos_sdm WHERE concepto = ?", (concepto_semilla,)
    )
    row = cur.fetchone()
    if not row:
        return []

    vector_semilla = row[0]
    return buscar_sdm(cerebro, radio_max=radio_max, limite=limite,
                      vector_fijo=vector_semilla)
