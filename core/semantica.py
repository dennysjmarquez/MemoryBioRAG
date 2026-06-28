"""
Semántica: expansión de queries por equivalencias léxicas.

Permite que "auto" encuentre "vehículo" sin embeddings externos.
Tabla semantica bidireccional con peso y límite de expansión.
"""

import json
import os
import re

STOPWORDS_ES = {
    'para', 'como', 'con', 'por', 'que', 'del', 'las', 'los', 'mas',
    'pero', 'esta', 'este', 'entre', 'todo', 'tiene', 'cada', 'muy',
    'era', 'han', 'sin', 'sobre', 'tambien', 'desde', 'hasta', 'cuando',
    'donde', 'ello', 'ella', 'cual', 'dicho', 'sido', 'sea', 'tanto',
    'otro', 'otros', 'ante', 'segun', 'una', 'unas', 'unos',
    'porque', 'pues', 'contra', 'durante', 'mediante',
    'parte', 'forma', 'tipo', 'tema', 'vez', 'caso', 'dentro',
    'tras', 'aquel', 'aquella', 'aquellos', 'aquellas', 'estos',
}

_TECNICOS_CORTOS = {'dsl', 'api', 'mcp', 'rag', 'cpu', 'ram', 'gpu', 'cli', 'db', 'ui', 'ux', 'os', 'ai', 'vm'}

_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{4,}\b')
_CORTO_PATTERN = re.compile(r'\b[a-z]{2,3}\b')


def _tokenizar(texto):
    texto = texto.replace('_', ' ')
    tokens = set(_TOKEN_PATTERN.findall(texto.lower()))
    tokens |= _TECNICOS_CORTOS & set(_CORTO_PATTERN.findall(texto.lower()))
    return tokens - STOPWORDS_ES


def init_semantica_table(cursor):
    """Crea la tabla semantica si no existe."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantica (
            termino TEXT NOT NULL,
            equivalente TEXT NOT NULL,
            peso REAL DEFAULT 0.8,
            PRIMARY KEY (termino, equivalente)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sem_term ON semantica(termino)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sem_equiv ON semantica(equivalente)")
    cursor.connection.commit()


def expandir_query(cursor, termino, max_equivalentes=5):
    """
    Expande un término a sus equivalentes semánticos.
    Busca en ambas direcciones: auto→vehículo y vehículo→auto.
    Retorna lista de equivalentes ordenados por peso.
    """
    init_semantica_table(cursor)
    termino = termino.lower().strip()
    cursor.execute(
        "SELECT equivalente, peso FROM semantica WHERE termino = ? "
        "UNION "
        "SELECT termino, peso FROM semantica WHERE equivalente = ? "
        "ORDER BY peso DESC LIMIT ?",
        (termino, termino, max_equivalentes)
    )
    return [row[0] for row in cursor.fetchall()]


def agregar_equivalencia(cursor, termino, equivalente, peso=0.8):
    """
    Agrega una equivalencia semántica bidireccional.
    Inserta ambos sentidos: termino→equivalente y equivalente→termino.
    """
    init_semantica_table(cursor)
    termino = termino.lower().strip()
    equivalente = equivalente.lower().strip()
    if termino == equivalente:
        return
    cursor.execute(
        "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, ?)",
        (termino, equivalente, peso)
    )
    cursor.execute(
        "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, ?)",
        (equivalente, termino, peso)
    )
    cursor.connection.commit()


def eliminar_equivalencia(cursor, termino, equivalente):
    """Elimina una equivalencia semántica (ambos sentidos)."""
    init_semantica_table(cursor)
    termino = termino.lower().strip()
    equivalente = equivalente.lower().strip()
    cursor.execute(
        "DELETE FROM semantica WHERE (termino = ? AND equivalente = ?) OR (termino = ? AND equivalente = ?)",
        (termino, equivalente, equivalente, termino)
    )
    cursor.connection.commit()


def listar_equivalencias(cursor, termino=None):
    """
    Lista equivalencias semánticas.
    Si termino es None, retorna todas.
    """
    init_semantica_table(cursor)
    if termino:
        termino = termino.lower().strip()
        cursor.execute(
            "SELECT termino, equivalente, peso FROM semantica WHERE termino = ? OR equivalente = ? ORDER BY peso DESC",
            (termino, termino)
        )
    else:
        cursor.execute("SELECT termino, equivalente, peso FROM semantica ORDER BY peso DESC")
    return cursor.fetchall()


def tabla_vacia(cursor):
    """Verifica si la tabla semántica está vacía."""
    init_semantica_table(cursor)
    cursor.execute("SELECT COUNT(*) FROM semantica")
    return cursor.fetchone()[0] == 0


def cargar_vocabulario(cursor, vocabulario_dict):
    """
    Carga vocabulario desde un diccionario.
    Estructura: {"categoria": {"term": ["equiv1", "equiv2"], ...}}
    Inserta bidireccionalmente.
    """
    init_semantica_table(cursor)
    count = 0
    for categoria, terminos in vocabulario_dict.items():
        for term, equivalentes in terminos.items():
            for equiv in equivalentes:
                agregar_equivalencia(cursor, term, equiv, 0.85)
                count += 1
    return count


def cargar_vocabulario_desde_archivo(cursor, ruta_archivo):
    """Carga vocabulario desde un archivo JSON."""
    if not os.path.exists(ruta_archivo):
        return 0
    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        vocabulario = json.load(f)
    return cargar_vocabulario(cursor, vocabulario)


def auto_aprender_desde_sinonimos(cursor, concepto, sinonimos):
    """
    Aprende equivalencias semánticas desde los sinónimos de un nodo.
    Llamar cuando se guarda un nodo con sinónimos explícitos.
    """
    if not sinonimos:
        return 0
    init_semantica_table(cursor)
    concepto = concepto.lower().strip()
    sinonimos_list = [s.strip().lower() for s in sinonimos.split(",") if s.strip()]
    count = 0
    for sinonimo in sinonimos_list:
        if sinonimo != concepto and len(sinonimo) >= 2:
            agregar_equivalencia(cursor, concepto, sinonimo, 0.85)
            count += 1
    return count


def inferir_equivalencias_desde_sinapsis(
    cursor,
    umbral_sinapsis=0.6,
    umbral_jaccard=0.5,
    frecuencia_minima=2,
    peso_base=0.3,
    auto_guardar=False,
):
    """
    Infiere candidatos de equivalencia semántica leyendo pares sinápticos fuertes.

    Lee pares de nodos con sinapsis >= umbral_sinapsis. Tokeniza el contenido
    de ambos nodos. Si comparten suficiente vocabulario (Jaccard >=
    umbral_jaccard), infiere que los tokens exclusivos de cada nodo son
    posibles equivalentes.

    Los pares de tokens que co-ocurren en >= frecuencia_minima pares
    sinápticos distintos se retornan como candidatos.

    Si auto_guardar=True, guarda directamente en tabla semantica.
    Si auto_guardar=False (default), solo retorna la lista de candidatos
    para revisión manual — no modifica la BD.

    Retorna dict con:
      - candidatos: lista de (token_a, token_b, freq_co_ocurrencia, peso_inferido)
      - total_candidatos: int
      - pares_procesados: int
      - guardados: int (0 si auto_guardar=False)
    """
    init_semantica_table(cursor)

    cursor.execute(
        "SELECT s.origen, s.destino, l1.contenido, l2.contenido "
        "FROM sinapsis s "
        "JOIN largo_plazo l1 ON l1.concepto = s.origen "
        "JOIN largo_plazo l2 ON l2.concepto = s.destino "
        "WHERE s.peso >= ? AND l1.estado = 'activo' AND l2.estado = 'activo'",
        (umbral_sinapsis,)
    )
    pares = cursor.fetchall()
    total_pares = len(pares)

    if not pares:
        return {
            "candidatos": [],
            "total_candidatos": 0,
            "pares_procesados": 0,
            "guardados": 0,
        }

    co_ocurrencias = {}

    for origen, destino, cont_a, cont_b in pares:
        tokens_a = _tokenizar(origen + " " + (cont_a or ""))
        tokens_b = _tokenizar(destino + " " + (cont_b or ""))

        if not tokens_a or not tokens_b:
            continue

        compartidos = tokens_a & tokens_b
        if len(compartidos) / min(len(tokens_a), len(tokens_b)) < umbral_jaccard:
            continue

        exclusivos_a = tokens_a - tokens_b
        exclusivos_b = tokens_b - tokens_a

        for ta in exclusivos_a:
            for tb in exclusivos_b:
                key = tuple(sorted([ta, tb]))
                co_ocurrencias[key] = co_ocurrencias.get(key, 0) + 1

    candidatos_ordenados = []
    for (ta, tb), freq in co_ocurrencias.items():
        peso = round(min(peso_base + 0.1 * freq, 0.7), 3)
        candidatos_ordenados.append((ta, tb, freq, peso))

    candidatos_ordenados.sort(key=lambda x: x[3], reverse=True)

    guardados = 0
    if auto_guardar:
        for ta, tb, freq, peso in candidatos_ordenados:
            if freq >= frecuencia_minima:
                agregar_equivalencia(cursor, ta, tb, peso)
                guardados += 1

    return {
        "candidatos": candidatos_ordenados,
        "total_candidatos": len(candidatos_ordenados),
        "pares_procesados": total_pares,
        "guardados": guardados,
    }


def poda_tesauro_confianza(cursor, ciclos_sin_uso=3, peso_minimo=0.1):
    """
    Poda equivalencias no usadas en N ciclos de sueño.
    
    Decae el peso de cada equivalencia en 10% por cada ciclo sin uso.
    Elimina equivalencias con peso < peso_minimo.
    
    Retorna (eliminadas, decadas) como tupla.
    """
    init_semantica_table(cursor)
    
    # Buscar todas las equivalencias
    cursor.execute("SELECT termino, equivalente, peso FROM semantica")
    equivalencias = cursor.fetchall()
    
    eliminadas = 0
    decadas = 0
    
    for termino, equivalente, peso in equivalencias:
        # Verificar si la equivalencia fue usada recientemente
        # (buscar en sinapsis de co_ocurrencia o en búsquedas)
        cursor.execute("""
            SELECT COUNT(*) FROM sinapsis 
            WHERE tipo = 'co_ocurrencia' 
            AND (origen = ? OR destino = ? OR origen = ? OR destino = ?)
            AND ultimo_uso > strftime('%s', 'now') - (604800 * ?)
        """, (termino, termino, equivalente, equivalente, ciclos_sin_uso))
        usos_recientes = cursor.fetchone()[0]
        
        if usos_recientes == 0:
            # No se usó en los últimos N ciclos → decayer
            nuevo_peso = round(peso * 0.9, 3)
            if nuevo_peso < peso_minimo:
                # Eliminar equivalencia débil
                cursor.execute(
                    "DELETE FROM semantica WHERE (termino = ? AND equivalente = ?) OR (termino = ? AND equivalente = ?)",
                    (termino, equivalente, equivalente, termino)
                )
                eliminadas += 1
            else:
                # Decayer peso
                cursor.execute(
                    "UPDATE semantica SET peso = ? WHERE (termino = ? AND equivalente = ?) OR (termino = ? AND equivalente = ?)",
                    (nuevo_peso, termino, equivalente, equivalente, termino)
                )
                decadas += 1
    
    cursor.connection.commit()
    return eliminadas, decadas
