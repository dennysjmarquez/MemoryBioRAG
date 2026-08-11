import re
import time
import sqlite3
from core.stopwords import STOPWORDS

TOKENS_TECNICOS_CORTOS = {'dsl', 'api', 'mcp', 'rag', 'cpu', 'ram', 'gpu', 'cli', 'db', 'ui', 'ux', 'os', 'ai', 'vm'}

_TOKEN_PATTERN = re.compile(r'\b[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{4,}\b')
_CORTO_PATTERN = re.compile(r'\b[a-z]{2,3}\b')


def _tokenizar(texto):
    texto = texto.replace('_', ' ')
    tokens = set(_TOKEN_PATTERN.findall(texto.lower()))
    tokens |= TOKENS_TECNICOS_CORTOS & set(_CORTO_PATTERN.findall(texto.lower()))
    return tokens - STOPWORDS


def _peso_similitud(tokens_nuevos, tokens_exist, idf_map=None):
    if not tokens_nuevos or not tokens_exist:
        return 0.0
    inter = tokens_nuevos & tokens_exist
    if not inter:
        return 0.0
    idf = idf_map or {}
    peso_inter = sum(idf.get(t, 0.5) for t in inter)
    peso_union = sum(idf.get(t, 0.5) for t in tokens_nuevos | tokens_exist)
    return round(peso_inter / peso_union if peso_union > 0 else 0.0, 2)


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
    # Índice cubriente para la CTE recursiva de inferencia_transitiva:
    # WHERE peso >= X  JOIN ON origen=destino  → range scan + covering lookup sin acceder a la tabla
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_peso_cobertura ON sinapsis(peso, origen, destino)")
    cursor.connection.commit()


def _vecinos_comunes(cursor, nodo_a: str, nodo_b: str) -> int:
    """Retorna el número de vecinos sinápticos comunes entre nodo_a y nodo_b.

    Fundamento (Granovetter 1973 / Teoría de Cierre Triádico):
    Dos nodos deben conectarse sólo si ya comparten al menos un vecino común
    en el grafo — garantía matemática de que pertenecen al mismo dominio semántico.
    Sin este requisito, palabras accidentalmente compartidas entre nodos de dominios
    distintos crean puentes espurios que degradan la precisión de búsqueda a escala.
    """
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT vecino FROM (
                    SELECT destino AS vecino FROM sinapsis WHERE origen = ?
                    UNION SELECT origen AS vecino FROM sinapsis WHERE destino = ?
                ) INTERSECT
                SELECT vecino FROM (
                    SELECT destino AS vecino FROM sinapsis WHERE origen = ?
                    UNION SELECT origen AS vecino FROM sinapsis WHERE destino = ?
                )
            )
        """, (nodo_a, nodo_a, nodo_b, nodo_b))
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _dimensiones_comunes(cursor, nodo_a: str, nodo_b: str) -> int:
    """Retorna el número de dimensiones semánticas compartidas entre nodo_a y nodo_b."""
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?
                INTERSECT
                SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?
            )
        """, (nodo_a, nodo_b))
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


# v26.2: Control de Cierre Triádico — activo por defecto, apagable con BIORAG_CIERRE_TRIADICO=0
import os as _os
_CIERRE_TRIADICO = _os.getenv("BIORAG_CIERRE_TRIADICO", "1") == "1"


def auto_vincular(cerebro, concepto, contenido, umbral=0.4):
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

    MAX_FANOUT = 30  # Límite de sinapsis por nodo en una sola pasada
    vinculados = []
    dirty = set()  # Reindex SDM selectivo: extremos de sinapsis NUEVAS
    for conc_exist, cont_exist in existentes:
        if len(vinculados) >= MAX_FANOUT:
            break
        tokens_exist = _tokenizar(conc_exist + " " + (cont_exist or ""))
        if not tokens_exist:
            continue

        # Similitud Jaccard ponderada por IDF (con fallback uniforme a 0.5):
        # auto_vincular llama a _peso_similitud con idf_map=None para evitar escanear la base de datos
        sim = _peso_similitud(tokens_nuevos, tokens_exist, idf_map=None)

        if sim >= umbral:
            # v26.2: Cierre Triádico — sólo conectar si comparten vecino/dimensión común,
            # o si el grafo del nodo nuevo está vacío (bootstrap). Previene puentes espurios
            # entre nodos de dominios distintos causados por tokens compartidos accidentalmente.
            if _CIERRE_TRIADICO:
                vec_comunes = _vecinos_comunes(cerebro.cursor, concepto, conc_exist)
                dim_comunes = _dimensiones_comunes(cerebro.cursor, concepto, conc_exist) if vec_comunes == 0 else 1
                # Permitir la conexión si: (1) hay vecinos comunes, (2) hay dims semánticas comunes,
                # o (3) el nodo nuevo no tiene aún ninguna sinapsis (bootstrap necesario)
                cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?", (concepto, concepto))
                sinap_existentes = cerebro.cursor.fetchone()[0]
                if vec_comunes == 0 and dim_comunes == 0 and sinap_existentes > 5:
                    continue  # Rechazar: puente espurio entre dominios distintos

            peso = sim
            # Reindex SDM selectivo: marcar dirty solo si la sinapsis es NUEVA
            # (el ON CONFLICT DO UPDATE no distingue insert de update)
            cerebro.cursor.execute(
                "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                (concepto, conc_exist)
            )
            es_nueva = cerebro.cursor.fetchone() is None
            cerebro.cursor.execute(
                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, ?, 'co_ocurrencia', ?) "
                "ON CONFLICT(origen, destino) DO UPDATE SET "
                "peso = MAX(sinapsis.peso, excluded.peso), "
                "tipo = CASE WHEN sinapsis.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test') THEN sinapsis.tipo ELSE excluded.tipo END, "
                "ultimo_uso = COALESCE(sinapsis.ultimo_uso, excluded.creado_en)",
                (concepto, conc_exist, peso, time.time())
            )
            if es_nueva:
                dirty.add(concepto)
                dirty.add(conc_exist)
            vinculados.append((conc_exist, peso))

    # ─── Pasada 2: vincular por nombre de concepto (LIKE + PALABRA_COMPLETA) ───
    # Conecta nodos que comparten palabras clave en el nombre aunque su
    # contenido use vocabulario distinto. No requiere FTS5 — usa LIKE directo.
    # Usamos OR para capturar cualquier candidato que comparta al menos una
    # palabra, luego filtramos por overlap ≥ 30% en Python.
    palabras_nombre = [w for w in re.findall(r'[a-zA-Záéíóúñ]{4,}', concepto.lower().replace('_', ' ').replace('-', ' ')) if w not in STOPWORDS]
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
                f"WHERE l.estado = 'activo' AND l.concepto != ? AND ({like_conds}) "
                f"ORDER BY l.peso_sinaptico DESC LIMIT 500",
                (concepto,) + tuple(like_params)
            )
            count_name = 0
            for conc_exist, cont_exist, peso_exist in cerebro.cursor.fetchall():
                if count_name >= 30: # Límite de fan-out para vinculación por nombre
                    break
                if conc_exist in ya_vinculados:
                    continue
                nombre_overlap = sum(1 for w in palabras_nombre if w in conc_exist.lower()) / len(palabras_nombre)
                if nombre_overlap >= 0.3:
                    peso_link = round(min(1.0, nombre_overlap * 0.7 + peso_exist * 0.3), 2)
                    cerebro.cursor.execute(
                        "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                        (concepto, conc_exist)
                    )
                    es_nueva = cerebro.cursor.fetchone() is None
                    cerebro.cursor.execute(
                        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, ?, 'co_nombre', ?) "
                        "ON CONFLICT(origen, destino) DO UPDATE SET "
                        "peso = MAX(sinapsis.peso, excluded.peso), "
                        "tipo = CASE WHEN sinapsis.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test') THEN sinapsis.tipo ELSE excluded.tipo END, "
                        "ultimo_uso = COALESCE(sinapsis.ultimo_uso, excluded.creado_en)",
                        (concepto, conc_exist, peso_link, time.time())
                    )
                    if es_nueva:
                        dirty.add(concepto)
                        dirty.add(conc_exist)
                    vinculados.append((conc_exist, peso_link))
                    count_name += 1
            # commit al final de todas las pasadas
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
                    f"WHERE l.estado = 'activo' AND l.concepto != ? AND ({sin_conds}) "
                    f"ORDER BY l.peso_sinaptico DESC LIMIT 500",
                    (concepto,) + tuple(sin_params)
                )
                count_syn = 0
                for conc_exist, sin_exist, peso_exist in cerebro.cursor.fetchall():
                    if count_syn >= 30: # Límite de fan-out para vinculación por sinónimos
                        break
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
                                "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                                (concepto, conc_exist)
                            )
                            es_nueva = cerebro.cursor.fetchone() is None
                            cerebro.cursor.execute(
                                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                                "VALUES (?, ?, ?, 'co_semantica', ?) "
                                "ON CONFLICT(origen, destino) DO UPDATE SET "
                                "peso = MAX(sinapsis.peso, excluded.peso), "
                                "tipo = CASE WHEN sinapsis.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test') THEN sinapsis.tipo ELSE excluded.tipo END, "
                                "ultimo_uso = COALESCE(sinapsis.ultimo_uso, excluded.creado_en)",
                                (concepto, conc_exist, peso_link, time.time())
                            )
                            if es_nueva:
                                dirty.add(concepto)
                                dirty.add(conc_exist)
                            vinculados.append((conc_exist, peso_link))
                            count_syn += 1
            except sqlite3.OperationalError:
                pass

    # ─── Pasada 4: Resonancia PMI Hebbiana (pmi_hebbiano) ───
    # Conecta el nodo a conceptos emergentes que tienen alto PMI con sus tokens,
    # resolviendo la categorización implícita (ej. Angular → Frontend).
    try:
        from core.pmi_semantico import pares_fuertes
        from core.stemmer_es import stem

        stems_nuevos = set(stem(t) for t in tokens_nuevos if len(t) >= 3)
        tokens_pmi = {}  # {tok_asoc: max_npmi}
        for s in stems_nuevos:
            fuertes = pares_fuertes(cerebro.cursor, s, top_n=20)
            for tok_asoc, npmi in fuertes:
                if npmi >= 0.35 and tok_asoc not in stems_nuevos:
                    if npmi > tokens_pmi.get(tok_asoc, 0.0):
                        tokens_pmi[tok_asoc] = npmi

        if tokens_pmi:
            ya_vinculados = {v[0] for v in vinculados}
            fts_tokens = [f'"{t}"' for t in tokens_pmi.keys() if len(t) >= 3]
            if fts_tokens:
                fts_q = " OR ".join(fts_tokens)
                cerebro.cursor.execute(
                    "SELECT DISTINCT l.concepto, l.contenido, l.peso_sinaptico "
                    "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                    "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' AND l.concepto != ? "
                    "ORDER BY l.peso_sinaptico DESC LIMIT 50",
                    (fts_q, concepto)
                )
                count_pmi = 0
                for conc_exist, cont_exist, peso_exist in cerebro.cursor.fetchall():
                    if count_pmi >= 15:
                        break
                    if conc_exist in ya_vinculados:
                        continue

                    # Calcular fuerza hebbiana basada en PMI
                    tokens_dest = set(stem(t) for t in _tokenizar(conc_exist + " " + (cont_exist or "")) if len(t) >= 3)
                    pmi_matches = [tokens_pmi[t] for t in tokens_pmi if t in tokens_dest]
                    if pmi_matches:
                        avg_pmi = sum(pmi_matches) / len(pmi_matches)
                        peso_link = round(min(1.0, avg_pmi * 0.75 + peso_exist * 0.25), 2)
                        if peso_link >= 0.35:
                            cerebro.cursor.execute(
                                "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                                (concepto, conc_exist)
                            )
                            es_nueva = cerebro.cursor.fetchone() is None
                            cerebro.cursor.execute(
                                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                                "VALUES (?, ?, ?, 'pmi_hebbiano', ?) "
                                "ON CONFLICT(origen, destino) DO UPDATE SET "
                                "peso = MAX(sinapsis.peso, excluded.peso), "
                                "tipo = CASE WHEN sinapsis.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test') THEN sinapsis.tipo ELSE excluded.tipo END, "
                                "ultimo_uso = COALESCE(sinapsis.ultimo_uso, excluded.creado_en)",
                                (concepto, conc_exist, peso_link, time.time())
                            )
                            if es_nueva:
                                dirty.add(concepto)
                                dirty.add(conc_exist)
                            vinculados.append((conc_exist, peso_link))
                            count_pmi += 1
    except Exception:
        pass

    if vinculados:
        _sincronizar_asociaciones(cerebro, concepto)
        for conc_exist, _ in vinculados:
            _sincronizar_asociaciones(cerebro, conc_exist)
        cerebro.cursor.connection.commit()  # Único commit de todas las pasadas

    # Reindex SDM selectivo: marcar dirty los extremos de sinapsis nuevas
    if dirty:
        try:
            from core.sdm import marcar_sdm_dirty
            marcar_sdm_dirty(cerebro, dirty)
        except Exception:
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
    dirty = set()  # Reindex SDM selectivo: extremos de sinapsis NUEVAS
    for termino in terminos:
        # ponytail: solo buscar en concepto y sinonimos, NO en contenido
        # Evita falsos positivos cuando el término aparece de pasada en el contenido
        cerebro.cursor.execute(
            "SELECT concepto FROM largo_plazo WHERE estado = 'activo' AND concepto != ? "
            "AND (concepto LIKE ? OR sinonimos LIKE ?)",
            (concepto, f"%{termino}%", f"%{termino}%")
        )
        for (conc_exist,) in cerebro.cursor.fetchall():
            cerebro.cursor.execute(
                "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                (concepto, conc_exist)
            )
            es_nueva = cerebro.cursor.fetchone() is None
            cerebro.cursor.execute(
                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, ?, 'sinonimo_explicito', ?) "
                "ON CONFLICT(origen, destino) DO UPDATE SET "
                "peso = MAX(sinapsis.peso, excluded.peso), "
                "tipo = CASE WHEN sinapsis.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test') THEN sinapsis.tipo ELSE excluded.tipo END, "
                "ultimo_uso = COALESCE(sinapsis.ultimo_uso, excluded.creado_en)",
                (concepto, conc_exist, peso, time.time())
            )
            if es_nueva:
                dirty.add(concepto)
                dirty.add(conc_exist)
            vinculados.append((conc_exist, peso))

    if vinculados:
        _sincronizar_asociaciones(cerebro, concepto)
        for conc_exist, _ in vinculados:
            _sincronizar_asociaciones(cerebro, conc_exist)
        cerebro.cursor.connection.commit()

    if dirty:
        try:
            from core.sdm import marcar_sdm_dirty
            marcar_sdm_dirty(cerebro, dirty)
        except Exception:
            pass
    return vinculados


def _sincronizar_asociaciones(cerebro, concepto):
    """Sincroniza el campo CSV 'asociaciones' en largo_plazo con el estado real de sinapsis."""
    cerebro.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? "
        "UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (concepto, concepto)
    )
    vecinos = [r[0] for r in cerebro.cursor.fetchall()]
    cerebro.cursor.execute(
        "UPDATE largo_plazo SET asociaciones = ? WHERE concepto = ?",
        (",".join(vecinos), concepto)
    )


def desvincular(cerebro, a, b, autor=None, query=None):
    """Elimina la sinapsis bidireccional entre dos conceptos.
    Plasticidad negativa: cuando un falso positivo aparece, se borra la conexión
    para que no vuelva a traerse en búsquedas futuras."""
    cerebro.cursor.execute(
        "DELETE FROM sinapsis WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
        (a, b, b, a)
    )
    eliminadas = cerebro.cursor.rowcount
    _sincronizar_asociaciones(cerebro, a)
    _sincronizar_asociaciones(cerebro, b)
    cerebro.cursor.connection.commit()
    return eliminadas


def calcular_idf_corpus(cerebro):
    """Calcula el IDF de todos los tokens relevantes del corpus activo, UNA sola vez.
    Retorna un dict {token: idf_normalizado}. Usar una vez por ciclo de consolidación,
    no una vez por par de sinapsis."""
    import math
    cerebro.cursor.execute("SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo'")
    filas = cerebro.cursor.fetchall()
    total_nodos = max(1, len(filas))

    doc_freq = {}
    for concepto, contenido in filas:
        tokens_nodo = _tokenizar((concepto or "") + " " + (contenido or ""))
        for t in tokens_nodo:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    idf_map = {}
    for token, df in doc_freq.items():
        if len(token) < 3:
            idf_map[token] = 1.0
            continue
        idf_map[token] = min(1.0, math.log(total_nodos / max(1, df)) / math.log(max(total_nodos, 2)))
    return idf_map


def recalcular_similitud_sinapsis(cerebro, a, b, idf_map=None):
    """Recalcula la similitud Jaccard ponderada por IDF entre dos conceptos.
    Útil para auditoría y depuración (pruning) de sinapsis stale/heredadas.
    idf_map: dict precalculado por calcular_idf_corpus(). Si no se provee,
    se usa peso uniforme 0.5 para todos los tokens."""
    cerebro.cursor.execute(
        "SELECT tipo, peso FROM sinapsis WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
        (a, b, b, a)
    )
    row = cerebro.cursor.fetchone()
    if row and row[0] in ('manual', 'manual_v7', 'sinonimo_explicito', 'test'):
        return row[1]

    cerebro.cursor.execute("SELECT contenido FROM largo_plazo WHERE concepto = ? AND estado = 'activo'", (a,))
    res_a = cerebro.cursor.fetchone()
    cerebro.cursor.execute("SELECT contenido FROM largo_plazo WHERE concepto = ? AND estado = 'activo'", (b,))
    res_b = cerebro.cursor.fetchone()
    if not res_a or not res_b:
        return 0.0

    t_a = _tokenizar(a + " " + (res_a[0] or ""))
    t_b = _tokenizar(b + " " + (res_b[0] or ""))

    inter = t_a & t_b
    if not inter:
        return 0.0

    idf = idf_map or {}
    peso_inter = sum(idf.get(t, 0.5) for t in inter)
    peso_union = sum(idf.get(t, 0.5) for t in t_a | t_b)

    return round(peso_inter / peso_union if peso_union > 0 else 0.0, 2)

