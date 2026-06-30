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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grupos_semanticos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raiz TEXT UNIQUE NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grupo_terminos (
            termino TEXT PRIMARY KEY,
            grupo_id INTEGER NOT NULL,
            FOREIGN KEY (grupo_id) REFERENCES grupos_semanticos(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gr_term_grupo ON grupo_terminos(grupo_id)")
    cursor.connection.commit()
    
    # Auto-inicializar si las tablas de grupos están vacías pero la semántica no
    cursor.execute("SELECT COUNT(*) FROM grupos_semanticos")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT COUNT(*) FROM semantica")
        if cursor.fetchone()[0] > 0:
            reconstruir_grupos_semanticos(cursor)

    # Sembrar equivalencias emocionales iniciales si no existen
    cursor.execute("SELECT COUNT(*) FROM semantica WHERE equivalente = 'emocion_afecto' AND termino = 'quiero'")
    if cursor.fetchone()[0] == 0:
        emociones_dict = {
            "cariño": ["afecto", "aprecio", "amor", "emocion_afecto", "quiero", "querer"],
            "afecto": ["cariño", "aprecio", "amor", "emocion_afecto", "quiero", "querer"],
            "aprecio": ["cariño", "afecto", "amor", "emocion_afecto", "quiero", "querer"],
            "amor": ["cariño", "afecto", "aprecio", "emocion_afecto", "quiero", "querer"],
            "quiero": ["cariño", "afecto", "aprecio", "amor", "emocion_afecto"],
            "querer": ["cariño", "afecto", "aprecio", "amor", "emocion_afecto"],
            
            "frustracion": ["enojo", "molesto", "rabia", "frustrado", "emocion_frustracion"],
            "frustrado": ["enojo", "molesto", "rabia", "frustracion", "emocion_frustracion"],
            "molesto": ["enojo", "frustrado", "rabia", "frustracion", "emocion_frustracion"],
            "enojo": ["molesto", "frustrado", "rabia", "frustracion", "emocion_frustracion"],
            "rabia": ["molesto", "frustrado", "enojo", "frustracion", "emocion_frustracion"],
            "error": ["emocion_frustracion"],
            "fallo": ["emocion_frustracion"],
            "problema": ["emocion_frustracion"],
            "mal": ["emocion_frustracion"],
            
            "satisfaccion": ["alegria", "exito", "bien", "genial", "emocion_satisfaccion"],
            "alegria": ["satisfaccion", "exito", "bien", "genial", "emocion_satisfaccion"],
            "exito": ["satisfaccion", "alegria", "bien", "genial", "emocion_satisfaccion"],
            "excelente": ["emocion_satisfaccion"],
            "logro": ["emocion_satisfaccion"],
            "bien": ["emocion_satisfaccion"],
            "genial": ["emocion_satisfaccion"],
            
            "preocupacion": ["duda", "riesgo", "alerta", "preocupado", "emocion_preocupacion"],
            "preocupado": ["preocupacion", "duda", "riesgo", "alerta", "emocion_preocupacion"],
            "duda": ["preocupacion", "preocupado", "riesgo", "alerta", "emocion_preocupacion"],
            "riesgo": ["emocion_preocupacion"],
            "alerta": ["emocion_preocupacion"],
        }
        for term, equivs in emociones_dict.items():
            for eq in equivs:
                term_val = term.lower().strip()
                equiv_val = eq.lower().strip()
                if term_val != equiv_val:
                    cursor.execute(
                        "INSERT OR IGNORE INTO semantica (termino, equivalente, peso) VALUES (?, ?, 0.85)",
                        (term_val, equiv_val)
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO semantica (termino, equivalente, peso) VALUES (?, ?, 0.85)",
                        (equiv_val, term_val)
                    )
        cursor.connection.commit()
        reconstruir_grupos_semanticos(cursor)



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


def expandir_query_por_tokens(cursor, query, max_equivalentes=3):
    """
    Tokeniza la query y expande cada token individual a sus equivalentes semánticos.
    Une las expansiones de cada token con AND.
    Ej: "modo dios" -> "(modo OR nivel OR forma) AND (dios)"
    Retorna la query de FTS5 construida, o None si no hay expansiones viables.
    """
    init_semantica_table(cursor)
    tokens = list(_tokenizar(query))
    if not tokens:
        return None
    
    parts = []
    has_expansion = False
    
    for token in tokens:
        # Buscar equivalentes para este token
        cursor.execute(
            "SELECT equivalente, peso FROM semantica WHERE termino = ? "
            "UNION "
            "SELECT termino, peso FROM semantica WHERE equivalente = ? "
            "ORDER BY peso DESC LIMIT ?",
            (token, token, max_equivalentes)
        )
        equivalentes = [row[0] for row in cursor.fetchall()]
        
        if equivalentes:
            has_expansion = True
            # Formar el subgrupo con el token original más sus equivalentes
            opciones = [token] + [eq.strip() for eq in equivalentes if eq.strip() and eq.strip() != token]
            parts.append(f"({' OR '.join(opciones)})")
        else:
            parts.append(f"({token})")
            
    # Solo retornamos si al menos un token fue expandido
    if not has_expansion:
        return None
        
    return " AND ".join(parts)



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
    reconstruir_grupos_semanticos(cursor)


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
    reconstruir_grupos_semanticos(cursor)


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
                term_val = term.lower().strip()
                equiv_val = equiv.lower().strip()
                if term_val != equiv_val:
                    cursor.execute(
                        "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, 0.85)",
                        (term_val, equiv_val)
                    )
                    cursor.execute(
                        "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, 0.85)",
                        (equiv_val, term_val)
                    )
                    count += 1
    cursor.connection.commit()
    reconstruir_grupos_semanticos(cursor)
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
            cursor.execute(
                "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, 0.85)",
                (concepto, sinonimo)
            )
            cursor.execute(
                "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, 0.85)",
                (sinonimo, concepto)
            )
            count += 1
    if count > 0:
        cursor.connection.commit()
        reconstruir_grupos_semanticos(cursor)
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
                cursor.execute(
                    "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, ?)",
                    (ta, tb, peso)
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, ?)",
                    (tb, ta, peso)
                )
                guardados += 1
        if guardados > 0:
            cursor.connection.commit()
            reconstruir_grupos_semanticos(cursor)

    return {
        "candidatos": candidatos_ordenados,
        "total_candidatos": len(candidatos_ordenados),
        "pares_procesados": total_pares,
        "guardados": guardados,
    }


def reconstruir_grupos_semanticos(cursor):
    """Reconstruye los grupos semánticos disjuntos usando Union-Find."""
    cursor.execute("SELECT termino, equivalente FROM semantica")
    filas = cursor.fetchall()
    
    parent = {}
    
    def find(i):
        path = []
        while parent[i] != i:
            path.append(i)
            i = parent[i]
        for node in path:
            parent[node] = i
        return i
        
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_j] = root_i

    for term, equiv in filas:
        if term not in parent:
            parent[term] = term
        if equiv not in parent:
            parent[equiv] = equiv
            
    for term, equiv in filas:
        union(term, equiv)
        
    grupos = {}
    for term in parent:
        raiz = find(term)
        grupos.setdefault(raiz, set()).add(term)
        
    cursor.execute("DELETE FROM grupo_terminos")
    cursor.execute("DELETE FROM grupos_semanticos")
    
    for raiz, terminos in grupos.items():
        cursor.execute("INSERT INTO grupos_semanticos (raiz) VALUES (?)", (raiz,))
        grupo_id = cursor.lastrowid
        cursor.executemany(
            "INSERT OR REPLACE INTO grupo_terminos (termino, grupo_id) VALUES (?, ?)",
            [(t, grupo_id) for t in terminos]
        )
            
    cursor.connection.commit()
