"""
core/memory/recall.py
=====================
Métodos de evocación y búsqueda directa de nodos (recall clásico):
  - _buscar_en_contenido
  - _buscar_todos_en_contenido
  - buscar_recuerdo_microsegundos
  - buscar_todos_recuerdos
  - buscar_por_predicados
  - _fallback_busqueda_predicados
  - buscar_por_tokens
  - buscar_recuerdo_profundo

Extraídos de SQLiteMemoryBioRAG (memory_store.py) como parte de la
modularización progresiva. memory_store.py mantiene delegators de 1 línea.
"""
from __future__ import annotations

import re
import time


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de contenido
# ─────────────────────────────────────────────────────────────────────────────

def _buscar_en_contenido(self, query, solo_activos=True):
    """
    Busca coincidencias en el CONTENIDO (no solo en clave) usando coincidencia de tokens.
    Retorna tupla (concepto, contenido, peso, estado, asociaciones) o None.
    """
    tokens_query = set(re.findall(r'\b\w{3,}\b', query.lower()))

    if solo_activos:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE estado = 'activo'")
    else:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo")

    nodos = self.cursor.fetchall()
    mejor_puntaje = 0.0
    mejor_nodo = None

    for concepto, contenido, peso, estado, asociaciones in nodos:
        contenido_lower = contenido.lower()
        tokens_encontrados = sum(1 for t in tokens_query if t in contenido_lower)
        if tokens_encontrados > 0:
            puntaje = tokens_encontrados / len(tokens_query) * 0.8 + 0.2
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_nodo = (concepto, contenido, peso, estado, asociaciones)

    if mejor_nodo and mejor_puntaje >= 0.3:
        return mejor_nodo
    return None


def _buscar_todos_en_contenido(self, query, solo_activos=True):
    """
    Busca TODAS las coincidencias en contenido. Retorna lista de tuplas
    (concepto, contenido, peso, estado, puntaje) ordenadas por relevancia.
    """
    tokens_query = set(re.findall(r'\b\w{3,}\b', query.lower()))
    if not tokens_query:
        return []

    if solo_activos:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo WHERE estado = 'activo'")
    else:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo")

    resultados = []
    for concepto, contenido, peso, estado in self.cursor.fetchall():
        contenido_lower = contenido.lower()
        tokens_encontrados = sum(1 for t in tokens_query if t in contenido_lower)
        if tokens_encontrados > 0:
            puntaje = tokens_encontrados / len(tokens_query) * 0.8 + 0.2
            resultados.append((concepto, contenido, peso, estado, puntaje))

    resultados.sort(key=lambda r: r[4], reverse=True)
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Evocación directa
# ─────────────────────────────────────────────────────────────────────────────

def buscar_recuerdo_microsegundos(self, concepto):
    """
    Evoca un recuerdo de largo plazo en microsegundos.
    Solo busca en nodos activos. Si esta dormido, no lo despierta.
    Busca en clave y en contenido.
    """
    key = concepto.lower().strip()
    inicio = time.perf_counter()

    self.cursor.execute("""
        SELECT contenido, peso_sinaptico, estado, asociaciones 
        FROM largo_plazo WHERE concepto = ?
    """, (key,))
    fila = self.cursor.fetchone()

    if not fila:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE estado = 'activo'")
        activos = self.cursor.fetchall()
        mejor_similitud = 0.0
        mejor_coincidencia = None

        for concepto_db, contenido_db, peso_db, estado_db, asociadas_db in activos:
            similitud = self._calcular_jaccard(key, concepto_db)
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_coincidencia = (concepto_db, contenido_db, peso_db, estado_db, asociadas_db)

        if mejor_similitud >= 0.55 and mejor_coincidencia:
            print(f"[MemoryBioRAG] Coincidencia exacta fallida. Familiaridad difusa activada: '{concepto}' se asocia con '{mejor_coincidencia[0]}' (Similitud: {mejor_similitud:.2f})")
            key = mejor_coincidencia[0]
            fila = mejor_coincidencia[1:5]
        else:
            contenido_match = self._buscar_en_contenido(concepto, solo_activos=True)
            if contenido_match:
                print(f"[MemoryBioRAG] Sin coincidencia en clave. Busqueda en contenido activada: '{concepto}' hallado en '{contenido_match[0]}'")
                key = contenido_match[0]
                fila = contenido_match[1:5]
            else:
                return None
    else:
        fila = (fila[0], fila[1], fila[2], fila[3])

    contenido, peso, estado, asociaciones = fila

    if estado == "dormido":
        return None

    nuevo_peso = min(1.0, peso + 0.15)
    self.cursor.execute("""
        UPDATE largo_plazo 
        SET peso_sinaptico = ?, ultimo_acceso = ? 
        WHERE concepto = ?
    """, (nuevo_peso, time.time(), key))

    if asociaciones:
        pass  # Legacy TEXT propagation removed — sinapsis table is canonical

    # Propagación vía sinapsis (fuente canónica)
    self.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (key, key)
    )
    ahora = time.time()
    for (vecino,) in self.cursor.fetchall():
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                ultimo_acceso = ?
            WHERE concepto = ? AND estado = 'activo'
        """, (ahora, vecino))
        self.cursor.execute(
            "UPDATE sinapsis SET ultimo_uso = ? WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
            (ahora, key, vecino, vecino, key)
        )

    self.conn.commit()
    fin = time.perf_counter()
    print(f"[MemoryBioRAG] Evocado exitosamente '{key}' en {(fin - inicio) * 1000000:.2f} microsegundos.")
    return contenido


def buscar_todos_recuerdos(self, concepto):
    """
    Busca TODOS los recuerdos relacionados con un concepto (clave + contenido).
    Devuelve lista de resultados ordenados por relevancia.
    Combina coincidencias de clave exacta, Jaccard en clave y busqueda en contenido.
    """
    key = concepto.lower().strip()
    resultados = []

    # 1. Coincidencia exacta
    self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo WHERE concepto = ? AND estado = 'activo'", (key,))
    fila = self.cursor.fetchone()
    if fila:
        resultados.append((fila[0], fila[1], fila[2], fila[3], 1.0))

    # 2. Jaccard en claves activas
    self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo WHERE estado = 'activo'")
    for concepto_db, contenido_db, peso_db, estado_db in self.cursor.fetchall():
        if concepto_db == key:
            continue
        sim = self._calcular_jaccard(key, concepto_db)
        if sim >= 0.55:
            resultados.append((concepto_db, contenido_db, peso_db, estado_db, sim))

    # 3. Contenido (incluye activos ya capturados, se filtran duplicados despues)
    contenidos = self._buscar_todos_en_contenido(concepto, solo_activos=True)
    existentes = {r[0] for r in resultados}
    for concepto_db, contenido_db, peso_db, estado_db, puntaje in contenidos:
        if concepto_db not in existentes:
            resultados.append((concepto_db, contenido_db, peso_db, estado_db, puntaje))

    resultados.sort(key=lambda r: r[4], reverse=True)
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda por predicados SRL
# ─────────────────────────────────────────────────────────────────────────────

def buscar_por_predicados(self, sujeto=None, accion=None, objeto=None, contexto=None, limite=10):
    """Búsqueda por roles semánticos (SRL v16.0).
    Filtra la tabla predicados por sujeto, acción, objeto y/o contexto.
    Retorna lista de (concepto, contenido, peso, estado, score, asociaciones)."""
    condiciones = []
    params = []
    if sujeto:
        condiciones.append("p.sujeto LIKE ?")
        params.append(f"%{sujeto}%")
    if accion:
        condiciones.append("p.accion LIKE ?")
        params.append(f"%{accion}%")
    if objeto:
        condiciones.append("p.objeto LIKE ?")
        params.append(f"%{objeto}%")
    if contexto:
        condiciones.append("p.contexto LIKE ?")
        params.append(f"%{contexto}%")

    if not condiciones:
        return []

    where = " AND ".join(condiciones)
    params.append(limite)
    self.cursor.execute(f"""
        SELECT DISTINCT l.concepto, l.contenido, l.peso_sinaptico, l.estado,
               l.peso_sinaptico AS score, l.asociaciones
        FROM predicados p
        JOIN largo_plazo l ON l.concepto = p.concepto
        WHERE {where} AND l.estado = 'activo'
        ORDER BY l.peso_sinaptico DESC
        LIMIT ?
    """, tuple(params))

    return [(r[0], r[1], r[2], r[3], r[4], r[5] or "") for r in self.cursor.fetchall()]


def _fallback_busqueda_predicados(self, frase, limite=10):
    """
    Fallback Causal SRL v1.0.
    Se ejecuta cuando la búsqueda tradicional por 8 señales arroja 0 candidatos o score < 0.35.
    Extrae o tokeniza la query y busca coincidencias por roles semánticos en la tabla predicados.
    """
    if not frase or len(frase.strip()) < 3:
        return []

    from core.srl_extractor import extraerte_normalizado, VERBOS_CANONICOS
    tokens = [extraerte_normalizado(w) for w in re.findall(r'\w{3,}', frase)]
    if not tokens:
        return []

    acciones = {VERBOS_CANONICOS.get(t, t) for t in tokens}

    placeholders = " OR ".join([
        "(PALABRA_PREFIJO(?, COALESCE(p.sujeto, '')) = 1 OR PALABRA_PREFIJO(?, COALESCE(p.accion, '')) = 1 OR PALABRA_PREFIJO(?, COALESCE(p.objeto, '')) = 1 OR PALABRA_PREFIJO(?, COALESCE(p.contexto, '')) = 1)"
    ] * len(tokens))
    params = []
    for t in tokens:
        params.extend([t, t, t, t])

    sql = f"""
        SELECT DISTINCT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones,
                        p.sujeto, p.accion, p.objeto, p.contexto
        FROM predicados p
        JOIN largo_plazo l ON l.concepto = p.concepto
        WHERE ({placeholders}) AND l.estado = 'activo'
        LIMIT ?
    """
    params.append(limite)

    try:
        self.cursor.execute(sql, tuple(params))
        rows = self.cursor.fetchall()
    except Exception:
        return []

    resultados = []
    for r in rows:
        conc, cont, peso, est, asoc, suj, acc, obj, ctx = r
        match_bonus = 0.50
        if acc and extraerte_normalizado(acc) in acciones:
            match_bonus = 0.65
        score = round(min(0.85, match_bonus + (peso or 0.5) * 0.10), 4)
        resultados.append((conc, cont, peso or 0.5, est, score, asoc or ""))

    resultados.sort(key=lambda x: x[4], reverse=True)
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda multi-token
# ─────────────────────────────────────────────────────────────────────────────

def buscar_por_tokens(self, tokens, modo="relaxed", profundidad="activos", limite=3, pagina=1):
    """Busqueda multi-token con Soft AND.

    tokens: lista de raices (stems) para buscar en concepto y contenido
    modo: 'strict' (score=1.0) | 'relaxed' (al menos 1 token coincide)
    profundidad: 'activos' | 'profundo'
    limite: resultados por pagina
    pagina: numero de pagina (1-indexed)
    Retorna lista de (concepto, contenido, peso, estado, score)
    """
    if not tokens:
        return []

    total_tokens = len(tokens)
    resultados_con_score = []

    if profundidad == "profundo":
        self.cursor.execute(
            "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo"
        )
    else:
        self.cursor.execute(
            "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE estado = 'activo'"
        )

    for concepto, contenido, peso, estado, asociaciones in self.cursor.fetchall():
        texto_concepto = concepto.lower()
        texto_contenido = (contenido or "").lower()
        matches = 0
        en_concepto = False

        for t in tokens:
            t_lower = t.lower().strip()
            if t_lower in texto_concepto:
                matches += 1
                en_concepto = True
            elif t_lower in texto_contenido:
                matches += 1

        if matches == 0:
            continue

        score = matches / total_tokens
        if en_concepto:
            score = min(1.0, score + 0.1)

        if modo == "strict" and score < 1.0:
            continue

        resultados_con_score.append(
            (concepto, contenido, peso, estado, round(score, 2), asociaciones or "")
        )

    if not resultados_con_score:
        return [], 0

    resultados_con_score.sort(key=lambda r: (r[4], r[2]), reverse=True)

    inicio = (pagina - 1) * limite
    fin = inicio + limite
    pagina_resultados = resultados_con_score[inicio:fin]

    if profundidad == "profundo":
        pagina_resultados_actualizada = []
        for r in pagina_resultados:
            if r[3] == "dormido":
                nuevo_peso = min(1.0, r[2] + 0.15)
                self.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                    (nuevo_peso, time.time(), r[0]),
                )
                pagina_resultados_actualizada.append(
                    (r[0], r[1], nuevo_peso, "activo", r[4], r[5])
                )
            else:
                pagina_resultados_actualizada.append(r)
        pagina_resultados = pagina_resultados_actualizada
        self.conn.commit()
        pagina_resultados.sort(key=lambda r: (r[4], r[2]), reverse=True)
    else:
        self.conn.commit()
    return pagina_resultados, len(resultados_con_score)


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda profunda (activos + dormidos)
# ─────────────────────────────────────────────────────────────────────────────

def buscar_recuerdo_profundo(self, concepto):
    """
    Busqueda en toda la corteza (activos + dormidos).
    Si encuentra un nodo dormido, lo despierta y aplica LTP.
    Busca en clave y en contenido.
    """
    key = concepto.lower().strip()
    inicio = time.perf_counter()

    self.cursor.execute("""
        SELECT contenido, peso_sinaptico, estado, asociaciones 
        FROM largo_plazo WHERE concepto = ?
    """, (key,))
    fila = self.cursor.fetchone()

    if not fila:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo")
        todos = self.cursor.fetchall()
        mejor_similitud = 0.0
        mejor_coincidencia = None

        for concepto_db, contenido_db, peso_db, estado_db, asociadas_db in todos:
            similitud = self._calcular_jaccard(key, concepto_db)
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_coincidencia = (concepto_db, contenido_db, peso_db, estado_db, asociadas_db)

        if mejor_similitud >= 0.4 and mejor_coincidencia:
            print(f"[MemoryBioRAG] Busqueda profunda: '{concepto}' coincide con '{mejor_coincidencia[0]}' (Similitud: {mejor_similitud:.2f})")
            key = mejor_coincidencia[0]
            fila = mejor_coincidencia[1:5]
        else:
            contenido_match = self._buscar_en_contenido(concepto, solo_activos=False)
            if contenido_match:
                print(f"[MemoryBioRAG] Sin coincidencia en clave. Busqueda en contenido activada: '{concepto}' hallado en '{contenido_match[0]}'")
                key = contenido_match[0]
                fila = contenido_match[1:5]
            else:
                return None
    else:
        fila = (fila[0], fila[1], fila[2], fila[3])

    contenido, peso, estado, asociaciones = fila

    # Despertar el nodo si estaba dormido y aplicar LTP
    nuevo_peso = min(1.0, peso + 0.15)
    self.cursor.execute("""
        UPDATE largo_plazo 
        SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? 
        WHERE concepto = ?
    """, (nuevo_peso, time.time(), key))
    if estado == "dormido":
        print(f"[MemoryBioRAG] Recuerdo '{key}' despertado de la memoria profunda.")

    if asociaciones:
        nodos_vecinos = [v.strip() for v in asociaciones.split(",") if v.strip()]
        for vecino in nodos_vecinos:
            self.cursor.execute("""
                UPDATE largo_plazo 
                SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                    ultimo_acceso = ?
                WHERE concepto = ? AND estado = 'activo'
            """, (time.time(), vecino))

    # Propagación también vía sinapsis
    self.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (key, key)
    )
    ahora = time.time()
    for (vecino,) in self.cursor.fetchall():
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                ultimo_acceso = ?
            WHERE concepto = ? AND estado = 'activo'
        """, (ahora, vecino))
        self.cursor.execute(
            "UPDATE sinapsis SET ultimo_uso = ? WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
            (ahora, key, vecino, vecino, key)
        )

    self.conn.commit()
    fin = time.perf_counter()
    print(f"[MemoryBioRAG] Evocado exitosamente '{key}' en {(fin - inicio) * 1000000:.2f} microsegundos.")
    return contenido
