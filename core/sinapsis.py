import re
import time
import sqlite3

STOPWORDS_ES = {
    'para', 'como', 'con', 'por', 'que', 'del', 'las', 'los', 'mas',
    'pero', 'esta', 'este', 'entre', 'todo', 'tiene', 'cada', 'muy',
    'era', 'han', 'sin', 'sobre', 'tambien', 'desde', 'hasta', 'cuando',
    'donde', 'ello', 'ella', 'cual', 'dicho', 'sido', 'sea', 'tanto',
    'otro', 'otros', 'ante', 'segun', 'una', 'una', 'unas', 'unos',
    'porque', 'pues', 'contra', 'durante', 'mediante', 'segun',
    'parte', 'forma', 'tipo', 'tema', 'vez', 'caso', 'dentro',
    'tras', 'aquel', 'aquella', 'aquellos', 'aquellas', 'estos',
}

TOKENS_TECNICOS_CORTOS = {'dsl', 'api', 'mcp', 'rag', 'cpu', 'ram', 'gpu', 'cli', 'db', 'ui', 'ux', 'os', 'ai', 'vm'}

_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{4,}\b')
_CORTO_PATTERN = re.compile(r'\b[a-z]{2,3}\b')


def _tokenizar(texto):
    texto = texto.replace('_', ' ')
    tokens = set(_TOKEN_PATTERN.findall(texto.lower()))
    tokens |= TOKENS_TECNICOS_CORTOS & set(_CORTO_PATTERN.findall(texto.lower()))
    return tokens - STOPWORDS_ES


def _peso_similitud(tokens_nuevos, tokens_exist):
    if not tokens_nuevos or not tokens_exist:
        return 0.0
    inter = tokens_nuevos & tokens_exist
    return len(inter) / min(len(tokens_nuevos), len(tokens_exist))


def init_sinapsis_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sinapsis (
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            peso REAL DEFAULT 0.5,
            tipo TEXT DEFAULT 'co_ocurrencia',
            creado_en REAL,
            PRIMARY KEY (origen, destino)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_origen ON sinapsis(origen)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_destino ON sinapsis(destino)")
    cursor.connection.commit()


def auto_vincular(cerebro, concepto, contenido, umbral=0.3):
    if not concepto and not contenido:
        return []

    init_sinapsis_table(cerebro.cursor)

    tokens_nuevos = _tokenizar(concepto + " " + contenido)
    if not tokens_nuevos or len(tokens_nuevos) < 2:
        return []

    # Buscar candidatos via FTS5 primero (indizado, BM25, rapido)
    # Solo tokens de 3+ chars para FTS5 trigram; terminos tecnicos cortos
    # (dsl, api, etc.) caen al fallback scan si es necesario
    terminos_fts = [f'"{t}"' for t in tokens_nuevos if len(t) >= 3]
    existentes = None
    if terminos_fts:
        fts_query = " OR ".join(terminos_fts)
        try:
            cerebro.cursor.execute(
                "SELECT DISTINCT l.concepto, l.contenido "
                "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' AND l.concepto != ? "
                "ORDER BY bm25(largo_plazo_fts) LIMIT 500",
                (fts_query, concepto)
            )
            existentes = cerebro.cursor.fetchall()
        except sqlite3.OperationalError:
            existentes = None

    # Fallback: scan completo si FTS5 no encontro candidatos o fallo
    if not existentes:
        cerebro.cursor.execute(
            "SELECT concepto, contenido FROM largo_plazo "
            "WHERE estado = 'activo' AND concepto != ?",
            (concepto,)
        )
        existentes = cerebro.cursor.fetchall()

    vinculados = []
    for conc_exist, cont_exist in existentes:
        tokens_exist = _tokenizar(conc_exist + " " + (cont_exist or ""))
        if not tokens_exist:
            continue

        sim = _peso_similitud(tokens_nuevos, tokens_exist)

        if sim >= umbral:
            peso = round(sim, 2)
            cerebro.cursor.execute(
                "INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, ?, 'co_ocurrencia', ?)",
                (concepto, conc_exist, peso, time.time())
            )
            vinculados.append((conc_exist, peso))

    if vinculados:
        cerebro.cursor.connection.commit()

    return vinculados


def buscar_vecinos(cerebro, concepto, profundo=False, max_vecinos=5):
    init_sinapsis_table(cerebro.cursor)

    if profundo:
        resultado = cerebro.buscar_recuerdo_profundo(concepto)
    else:
        resultado = cerebro.buscar_recuerdo_microsegundos(concepto)

    if not resultado:
        return None, []

    cerebro.cursor.execute(
        "SELECT destino, peso FROM sinapsis WHERE origen = ? "
        "UNION SELECT origen, peso FROM sinapsis WHERE destino = ? "
        "ORDER BY peso DESC LIMIT ?",
        (concepto, concepto, max_vecinos)
    )
    vecinos = []
    for vecino, peso in cerebro.cursor.fetchall():
        cerebro.cursor.execute(
            "SELECT contenido FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
            (vecino,)
        )
        fila = cerebro.cursor.fetchone()
        if fila:
            vecinos.append({
                "concepto": vecino,
                "peso_sinaptico": peso,
                "contenido": fila[0][:200]
            })

    return resultado, vecinos


def vincular_nuevo_si_existe(cerebro, concepto):
    init_sinapsis_table(cerebro.cursor)
    cerebro.cursor.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
        (concepto,)
    )
    fila = cerebro.cursor.fetchone()
    if not fila:
        return []
    return auto_vincular(cerebro, concepto, fila[0])


def vincular_por_sinonimos(cerebro, concepto, sinonimos, peso=0.9):
    """Crea aristas en sinapsis para sinonimos explicitos declarados por el usuario."""
    init_sinapsis_table(cerebro.cursor)

    terminos = [s.strip().lower() for s in sinonimos.split(",") if s.strip()]
    if not terminos:
        return []

    vinculados = []
    for termino in terminos:
        cerebro.cursor.execute(
            "SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo' AND concepto != ? "
            "AND (concepto LIKE ? OR contenido LIKE ?)",
            (concepto, f"%{termino}%", f"%{termino}%")
        )
        for conc_exist, cont_exist in cerebro.cursor.fetchall():
            cerebro.cursor.execute(
                "INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, ?, 'sinonimo_explicito', ?)",
                (concepto, conc_exist, peso, time.time())
            )
            vinculados.append((conc_exist, peso))

    if vinculados:
        cerebro.cursor.connection.commit()
    return vinculados


def vincular_existentes(cerebro, umbral=0.3):
    """Ejecuta auto-linking retroactivo entre todos los pares de nodos existentes en largo_plazo.
    Puebla el grafo sináptico con aristas faltantes. Se ejecuta una sola vez como migración."""
    init_sinapsis_table(cerebro.cursor)
    cerebro.cursor.execute(
        "SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo'"
    )
    todos = cerebro.cursor.fetchall()
    total_enlaces = 0
    for concepto, contenido in todos:
        enlaces = auto_vincular(cerebro, concepto, contenido, umbral)
        total_enlaces += len(enlaces)
    return total_enlaces


def migrar_desde_csv(cerebro):
    init_sinapsis_table(cerebro.cursor)

    cerebro.cursor.execute(
        "SELECT concepto, asociaciones FROM largo_plazo "
        "WHERE asociaciones IS NOT NULL AND asociaciones != ''"
    )
    nodos_con_asociaciones = cerebro.cursor.fetchall()

    contador = 0
    for concepto, csv_asoc in nodos_con_asociaciones:
        for destino in csv_asoc.split(","):
            destino = destino.strip()
            if not destino:
                continue
            cerebro.cursor.execute(
                "INSERT OR IGNORE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, 0.8, 'legacy_csv', ?)",
                (concepto, destino, time.time())
            )
            contador += 1

    if contador:
        cerebro.cursor.connection.commit()
    return contador
