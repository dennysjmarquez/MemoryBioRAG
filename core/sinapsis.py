import re
import time
import sqlite3

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
            ultimo_uso REAL,
            PRIMARY KEY (origen, destino)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_origen ON sinapsis(origen)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_destino ON sinapsis(destino)")
    cursor.connection.commit()


def auto_vincular(cerebro, concepto, contenido, umbral=0.3):
    if not concepto and not contenido:
        return []

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
                "ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico) LIMIT 500",
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

    # ─── Pasada 2: vincular por nombre de concepto (LIKE + PALABRA_COMPLETA) ───
    # Conecta nodos que comparten palabras clave en el nombre aunque su
    # contenido use vocabulario distinto. No requiere FTS5 — usa LIKE directo.
    # Usamos OR para capturar cualquier candidato que comparta al menos una
    # palabra, luego filtramos por overlap ≥ 30% en Python.
    palabras_nombre = [w for w in re.findall(r'[a-zA-Záéíóúñ]{4,}', concepto.lower().replace('_', ' ').replace('-', ' ')) if w not in STOPWORDS_ES]
    if len(palabras_nombre) >= 2:
        ya_vinculados = {v[0] for v in vinculados}
        like_conds = " OR ".join([
            "(l.concepto LIKE '%' || ? || '%' AND "
            "(PALABRA_COMPLETA(?, l.concepto) = 1 OR length(?) >= 5))"
            for _ in palabras_nombre
        ])
        like_params = []
        for w in palabras_nombre:
            like_params.extend([w, w, w])
        try:
            cerebro.cursor.execute(
                f"SELECT l.concepto, l.contenido, l.peso_sinaptico "
                f"FROM largo_plazo l "
                f"WHERE l.estado = 'activo' AND l.concepto != ? AND ({like_conds})",
                (concepto,) + tuple(like_params)
            )
            for conc_exist, cont_exist, peso_exist in cerebro.cursor.fetchall():
                if conc_exist in ya_vinculados:
                    continue
                nombre_overlap = sum(1 for w in palabras_nombre if w in conc_exist.lower()) / len(palabras_nombre)
                if nombre_overlap >= 0.3:
                    peso_link = round(min(1.0, nombre_overlap * 0.7 + peso_exist * 0.3), 2)
                    cerebro.cursor.execute(
                        "INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, ?, 'co_nombre', ?)",
                        (concepto, conc_exist, peso_link, time.time())
                    )
                    vinculados.append((conc_exist, peso_link))
            if any(v not in ya_vinculados for v in vinculados):
                cerebro.cursor.connection.commit()
        except sqlite3.OperationalError:
            pass

    # ─── Pasada 3: vincular por sinónimos (co_semantica) ───
    # Lee sinónimos del nodo activo desde la BD (columna que ya existe) y busca
    # nodos cuyos sinónimos contengan solapamiento léxico. Conecta nodos que
    # hablan del mismo tema con vocabulario distinto en contenido y nombre.
    try:
        cerebro.cursor.execute("SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,))
        fila_sin = cerebro.cursor.fetchone()
    except sqlite3.OperationalError:
        fila_sin = None

    if fila_sin and fila_sin[0]:
        tokens_sin = _tokenizar(fila_sin[0])
        if len(tokens_sin) >= 1:
            ya_vinculados = {v[0] for v in vinculados}
            sin_conds = " OR ".join(["l.sinonimos LIKE '%' || ? || '%'" for _ in tokens_sin])
            sin_params = list(tokens_sin)
            try:
                cerebro.cursor.execute(
                    f"SELECT l.concepto, l.sinonimos, l.peso_sinaptico "
                    f"FROM largo_plazo l "
                    f"WHERE l.estado = 'activo' AND l.concepto != ? AND ({sin_conds})",
                    (concepto,) + tuple(sin_params)
                )
                for conc_exist, sin_exist, peso_exist in cerebro.cursor.fetchall():
                    if conc_exist in ya_vinculados:
                        continue
                    tokens_exist_sin = _tokenizar(sin_exist or "")
                    if not tokens_exist_sin:
                        continue
                    inter = tokens_sin & tokens_exist_sin
                    if len(inter) >= 1:
                        overlap = len(inter) / min(len(tokens_sin), len(tokens_exist_sin))
                        if overlap >= umbral:
                            peso_link = round(min(1.0, overlap * 0.6 + peso_exist * 0.4), 2)
                            cerebro.cursor.execute(
                                "INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                                "VALUES (?, ?, ?, 'co_semantica', ?)",
                                (concepto, conc_exist, peso_link, time.time())
                            )
                            vinculados.append((conc_exist, peso_link))
                if any(v not in ya_vinculados for v in vinculados):
                    cerebro.cursor.connection.commit()
            except sqlite3.OperationalError:
                pass

    return vinculados


def buscar_vecinos(cerebro, concepto, profundo=False, max_vecinos=5):
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
    rows = cerebro.cursor.fetchall()

    # Actualizar ultimo_uso de las sinapsis consultadas
    ahora = time.time()
    cerebro.cursor.execute(
        "UPDATE sinapsis SET ultimo_uso = ? WHERE origen = ? OR destino = ?",
        (ahora, concepto, concepto)
    )
    cerebro.conn.commit()

    vecinos = []
    for vecino, peso in rows:
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
