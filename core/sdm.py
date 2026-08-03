"""
Sparse Distributed Memory (SDM) — BioRAG v2.0: Memoria Semántica Hebbiana
==========================================================================
Codificación binaria dispersa con semántica profunda. Los vectores capturan
relaciones semánticas reales usando clustering Hebbiano sobre co-ocurrencia
de dimensiones (principio: "lo que se activa junto, se codifica junto").

v1.0 (v19.0 legacy): Hash simple de tokens → 1 bit por token
v2.0 (actual):       Clusters Hebbianos + IDF ponderado + ventanas semánticas

Estructura del Vector SDM v2 (2048 bits = 256 bytes):
  - bits 0..511    (25%) -> Tokens de contenido (ventana de 4 bits/token)
  - bits 512..767   (12.5%) -> Tokens de concepto (ventana de 4 bits/token)
  - bits 768..1791  (50%) -> Dimensiones Hebbianas (ventana de 8-16 bits/dim, ponderada por IDF)
  - bits 1792..1919 (6.25%) -> Categoría (ventana de 8 bits)
  - bits 1920..2047 (6.25%) -> Vecinos sinápticos (ventana de 4 bits/vecino)

Sin dependencias externas (utiliza hashlib y bit_count nativo de Python).
"""

import hashlib
import json
import math
import time
import os
from pathlib import Path
from core.stemmer_es import stem

# =============================================================================
# Configuración
# =============================================================================

SDM_BITS = 2048
SDM_BYTES = 256
SDM_RADIO_DEFAULT = int(os.environ.get('BIORAG_SDM_RADIO', '400'))

# Segmentos del vector (rangos de bits)
SEGMENTO_CONTENIDO = (0, 512)       # 512 bits
SEGMENTO_CONCEPTO = (512, 768)      # 256 bits
SEGMENTO_DIMENSIONES = (768, 1792)  # 1024 bits
SEGMENTO_CATEGORIA = (1792, 1920)   # 128 bits
SEGMENTO_VECINOS = (1920, 2048)     # 128 bits

# Pesos por tipo de bit (para Jaccard ponderado)
PESO_TOKEN = 1.0
PESO_DIMENSION = 2.5    # Dimensiones pesan más (semanántica profunda)
PESO_CATEGORIA = 1.5
PESO_VECINO = 1.2

# Archivo de datos Hebbianos
_HEBBIAN_PATH = Path(__file__).parent.parent / 'db' / 'hebbian_clusters.json'

# =============================================================================
# Datos Hebbianos (cargados desde JSON pre-calculado)
# =============================================================================

_hebbian_data = None

def _cargar_hebbianos():
    """Carga clusters Hebbianos e IDF desde JSON. Se ejecuta 1 vez."""
    global _hebbian_data
    if _hebbian_data is not None:
        return _hebbian_data

    if _HEBBIAN_PATH.exists():
        with open(_HEBBIAN_PATH) as f:
            _hebbian_data = json.load(f)
    else:
        # Fallback: datos vacíos (v1 compat)
        _hebbian_data = {
            'clusters': [],
            'idf': {},
            'dim_names': {},
            'umbral': 0.25,
            'total_nodos': 0
        }
    return _hebbian_data


def _obtener_cluster_dim(dim_id):
    """Retorna el índice del cluster Hebbiano al que pertenece una dimensión."""
    data = _cargar_hebbianos()
    dim_str = str(dim_id)
    for i, cluster in enumerate(data.get('clusters', [])):
        if dim_str in [str(d) for d in cluster]:
            return i
    return -1  # Dimensión aislada (cluster propio)


def _obtener_idf_dim(dim_id):
    """Retorna el IDF de una dimensión (raro = alto, común = bajo)."""
    data = _cargar_hebbianos()
    return data.get('idf', {}).get(str(dim_id), 1.0)


def _calcular_rango_cluster(cluster_idx, total_clusters):
    """Calcula el rango de bits asignado a un cluster Hebbiano."""
    inicio, fin = SEGMENTO_DIMENSIONES
    tamano_total = fin - inicio
    tamano_cluster = tamano_total // max(total_clusters, 1)
    inicio_cluster = inicio + (cluster_idx * tamano_cluster)
    fin_cluster = min(inicio_cluster + tamano_cluster, fin)
    return (inicio_cluster, fin_cluster)


# =============================================================================
# Funciones de hashing
# =============================================================================

def _hash_token_a_bit(token: str, min_bit: int, max_bit: int, seed: int = 0) -> int:
    """Mapea un token a una posición de bit en el rango [min_bit, max_bit).

    seed=0 mantiene el comportamiento histórico (md5(token)) para compatibilidad
    de tests e imports externos. seed>0 produce una proyección INDEPENDIENTE
    (md5(f"{seed}:{token}")) — usada por _activar_proyecciones para multi-hashing.
    """
    rango = max_bit - min_bit
    if rango <= 0:
        return min_bit
    entrada = f"{seed}:{token}" if seed else token
    h = int(hashlib.md5(entrada.encode('utf-8')).hexdigest(), 16)
    return min_bit + (h % rango)


def _activar_proyecciones(bit_array, token: str, rango_inicio: int, rango_fin: int, k: int):
    """Activa k posiciones INDEPENDIENTES por token (multi-proyección).

    Cada seed produce un hash distinto del token → k bits pseudoaleatorios en
    [rango_inicio, rango_fin). Con k proyecciones, la colisión exacta entre dos
    tokens distintos cae de 1/rango a (1/rango)^k — elimina la paradoja de
    cumpleaños del md5%512 para strings de un solo token (concepto==contenido),
    preservando la densidad de bits activos (k bits/token, igual que la ventana
    contigua histórica). Los bits independientes además eliminan el solapamiento
    espurio que la ventana contigua causaba entre tokens con bases cercanas.
    """
    for seed in range(k):
        pos = _hash_token_a_bit(token, rango_inicio, rango_fin, seed=seed)
        if 0 <= pos < len(bit_array):
            bit_array[pos] = 1


def _activar_ventana(bit_array, pos_base, rango_inicio, rango_fin, n_bits):
    """Activa una ventana de n_bits alrededor de pos_base dentro del rango."""
    rango_tam = rango_fin - rango_inicio
    if rango_tam <= 0:
        return
    for i in range(n_bits):
        pos = rango_inicio + ((pos_base + i) % rango_tam)
        if 0 <= pos < len(bit_array):
            bit_array[pos] = 1


# =============================================================================
# Generación de vectores
# =============================================================================

def generar_vector_sdm(concepto: str, contenido: str = "", categoria: str = "",
                       dimensiones: list = None, vecinos: list = None) -> bytes:
    """Genera un vector binario disperso v2 con semántica Hebbiana.

    Dimensiones: lista de dimension_id (int o str).
    """
    bit_array = [0] * SDM_BITS
    data = _cargar_hebbianos()
    clusters = data.get('clusters', [])
    total_clusters = len(clusters)

    # 1. Tokens de contenido (bits 0..511, 4 proyecciones independientes/token)
    if contenido:
        tokens_contenido = [stem(t.lower()) for t in contenido.split() if len(t) >= 3]
        for tok in set(tokens_contenido[:50]):
            _activar_proyecciones(bit_array, tok, *SEGMENTO_CONTENIDO, 4)

    # 2. Tokens de concepto (bits 512..767, 4 proyecciones independientes/token)
    tokens_concepto = [stem(t.lower()) for t in concepto.split() if len(t) >= 2]
    for tok in tokens_concepto:
        _activar_proyecciones(bit_array, tok, *SEGMENTO_CONCEPTO, 4)

    # 3. Dimensiones Hebbianas (bits 768..1792, ponderadas por IDF)
    if dimensiones and total_clusters > 0:
        for dim_id in dimensiones:
            cluster_idx = _obtener_cluster_dim(dim_id)
            idf = _obtener_idf_dim(dim_id)

            # Calcular bits a activar según IDF
            if idf > 3.0:
                n_bits = 16  # Dimensión muy rara → más bits (más peso)
            elif idf > 1.5:
                n_bits = 12  # Dimensión rara
            elif idf > 0.5:
                n_bits = 8   # Dimensión normal
            else:
                n_bits = 4   # Dimensión común → menos bits

            if cluster_idx >= 0:
                rango = _calcular_rango_cluster(cluster_idx, total_clusters)
            else:
                # Dimensión aislada: usar rango proporcional al hash
                rango = SEGMENTO_DIMENSIONES

            pos = _hash_token_a_bit(str(dim_id), *rango)
            _activar_ventana(bit_array, pos, *rango, n_bits)

    # 4. Categoría (bits 1792..1920, 8 proyecciones independientes)
    if categoria is not None:
        _activar_proyecciones(bit_array, str(categoria).lower(), *SEGMENTO_CATEGORIA, 8)

    # 5. Vecinos sinápticos (bits 1920..2047, 4 proyecciones independientes/vecino)
    if vecinos:
        for vec in vecinos:
            _activar_proyecciones(bit_array, str(vec).lower(), *SEGMENTO_VECINOS, 4)

    # Empaquetar bits en bytes
    bytes_list = bytearray(SDM_BYTES)
    for i in range(SDM_BITS):
        if bit_array[i]:
            byte_idx = i // 8
            bit_idx = i % 8
            bytes_list[byte_idx] |= (1 << (7 - bit_idx))

    return bytes(bytes_list)


# =============================================================================
# Similitud
# =============================================================================

def _obtener_peso_bit(pos_bit):
    """Retorna el peso de un bit según su posición (segmento)."""
    if pos_bit < SEGMENTO_CONTENIDO[1]:
        return PESO_TOKEN
    elif pos_bit < SEGMENTO_CONCEPTO[1]:
        return PESO_TOKEN
    elif pos_bit < SEGMENTO_DIMENSIONES[1]:
        return PESO_DIMENSION
    elif pos_bit < SEGMENTO_CATEGORIA[1]:
        return PESO_CATEGORIA
    else:
        return PESO_VECINO


def distancia_hamming(vec1: bytes, vec2: bytes) -> int:
    """Calcula la distancia Hamming (bits diferentes) entre dos vectores."""
    if len(vec1) != len(vec2):
        return SDM_BITS
    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')
    return (int1 ^ int2).bit_count()


def similitud_sdm(vec1: bytes, vec2: bytes) -> float:
    """Jaccard PONDERADO sobre bits activos.

    Cada bit tiene un peso según su tipo:
      - Tokens: 1.0
      - Dimensiones Hebbianas: 2.5 (semántica profunda)
      - Categoría: 1.5
      - Vecinos: 1.2

    Fórmula:
      J_ponderado = Σ(peso_i × b1_i × b2_i) / Σ(peso_i × (b1_i OR b2_i))

    Esto hace que coincidir en dimensiones semánticas sea 2.5x más
    importante que coincidir en tokens de texto.
    """
    if len(vec1) != len(vec2):
        return 0.0

    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')

    interseccion_ponderada = 0.0
    union_ponderada = 0.0

    # Iterar por bytes para eficiencia
    for byte_idx in range(len(vec1)):
        b1 = vec1[byte_idx]
        b2 = vec2[byte_idx]

        if b1 == 0 and b2 == 0:
            continue

        for bit_idx in range(8):
            mask = 1 << (7 - bit_idx)
            bit_pos = byte_idx * 8 + bit_idx

            b1_active = bool(b1 & mask)
            b2_active = bool(b2 & mask)

            if b1_active or b2_active:
                peso = _obtener_peso_bit(bit_pos)
                union_ponderada += peso
                if b1_active and b2_active:
                    interseccion_ponderada += peso

    if union_ponderada == 0:
        return 0.0

    return round(interseccion_ponderada / union_ponderada, 4)


def similitud_sdm_legacy(vec1: bytes, vec2: bytes) -> float:
    """Jaccard simple (sin ponderación) — para compatibilidad v1."""
    if len(vec1) != len(vec2):
        return 0.0
    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')
    inter = (int1 & int2).bit_count()
    union = (int1 | int2).bit_count()
    return round(inter / union, 4) if union > 0 else 0.0


# =============================================================================
# Indexación
# =============================================================================

def indexar_nodo_sdm(cerebro, concepto: str) -> bool:
    """Genera e inserta/actualiza el vector SDM v2 para un nodo individual."""
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


# =============================================================================
# Búsqueda
# =============================================================================

def buscar_sdm(cerebro, query: str = "", radio_max: int = None, limite: int = 10,
               vector_fijo: bytes = None) -> list:
    """Busca nodos conceptualmente similares usando Jaccard ponderado.

    Modos de operación:
    1. Query por texto (vector_fijo=None): genera vector desde el query text.
    2. Query por ejemplo (vector_fijo=bytes): usa el vector proporcionado directamente.

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
        sim = similitud_sdm(query_vec, vec_blob)
        # Usar 1-sim como "distancia" para ordenar (mayor sim = mejor)
        dist = int((1.0 - sim) * SDM_BITS)
        if dist <= radio_max:
            resultados.append({
                'concepto': concepto,
                'distancia': dist,
                'similitud': sim
            })

    resultados.sort(key=lambda x: x['similitud'], reverse=True)
    return resultados[:limite]


def buscar_similares_a(cerebro, concepto_semilla: str, radio_max: int = None,
                       limite: int = 10) -> list:
    """Busca nodos similares a un nodo conocido — query-by-example.

    Toma el vector SDM del nodo semilla y busca nodos con mayor similitud.

    Retorna lista de dicts: [{'concepto': str, 'distancia': int, 'similitud': float}]
    """
    cur = cerebro.cursor.execute(
        "SELECT vector FROM nodos_sdm WHERE concepto = ?", (concepto_semilla,)
    )
    row = cur.fetchone()
    if not row:
        return []

    vector_semilla = row[0]
    return buscar_sdm(cerebro, radio_max=radio_max, limite=limite,
                      vector_fijo=vector_semilla)


# =============================================================================
# Info / Diagnóstico
# =============================================================================

def sdm_info():
    """Retorna información sobre la configuración actual de SDM."""
    data = _cargar_hebbianos()
    clusters = data.get('clusters', [])
    idf = data.get('idf', {})

    cluster_info = []
    for i, c in enumerate(clusters[:10]):
        dims = [data.get('dim_names', {}).get(str(d), f'dim_{d}') for d in c[:5]]
        cluster_info.append({
            'idx': i,
            'size': len(c),
            'dims': dims,
            'bits': _calcular_rango_cluster(i, len(clusters))
        })

    return {
        'version': '2.0',
        'bits': SDM_BITS,
        'bytes': SDM_BYTES,
        'clusters_hebbianos': len(clusters),
        'dimensiones_con_idf': len(idf),
        'segmentos': {
            'contenido': SEGMENTO_CONTENIDO,
            'concepto': SEGMENTO_CONCEPTO,
            'dimensiones': SEGMENTO_DIMENSIONES,
            'categoria': SEGMENTO_CATEGORIA,
            'vecinos': SEGMENTO_VECINOS,
        },
        'pesos': {
            'token': PESO_TOKEN,
            'dimension': PESO_DIMENSION,
            'categoria': PESO_CATEGORIA,
            'vecino': PESO_VECINO,
        },
        'top_clusters': cluster_info,
    }
