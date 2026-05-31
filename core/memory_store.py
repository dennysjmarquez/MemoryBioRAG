import os
import sqlite3
import time
import re

class SQLiteMemoryBioRAG:
    """
    Motor de Almacenamiento Cognitivo BioRAG basado en SQLite.
    Implementa almacenamiento biomimético con persistencia de doble capa (Corto/Largo plazo),
    plasticidad sináptica (LTP/LTD), indexación por B-Tree ultrarrápida,
    búsqueda de familiaridad difusa por coincidencia de Jaccard y propagación de activación (Grafo).
    """

    def __init__(self, db_path=None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = os.environ.get('BIORAG_PATH') or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "MemoryBioRAG_Data", "memory_biorag.db"
            )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Conectar a SQLite
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.cursor = self.conn.cursor()
        self._crear_estructura_cerebral()

    def _crear_estructura_cerebral(self):
        """Inicializa las tablas que simulan la corteza permanente y la memoria de trabajo."""
        # 1. Memoria de Trabajo (Corto Plazo / RAM-Disk equivalente)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS corto_plazo (
                concepto TEXT PRIMARY KEY,
                contenido TEXT,
                timestamp REAL,
                sinonimos TEXT DEFAULT ''
            )
        """)
        # Migración segura: agregar sinonimos a corto_plazo si no existe
        try:
            self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN sinonimos TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        # Migración segura: agregar categoria a corto_plazo
        try:
            self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN categoria TEXT DEFAULT 'general'")
        except sqlite3.OperationalError:
            pass

        # 2. Corteza Cerebral (Largo Plazo / Base de datos permanente con indexación B-Tree por PK)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS largo_plazo (
                concepto TEXT PRIMARY KEY,
                categoria TEXT DEFAULT 'general',
                contenido TEXT,
                peso_sinaptico REAL DEFAULT 1.0,
                estado TEXT DEFAULT 'activo', -- 'activo' o 'dormido'
                asociaciones TEXT DEFAULT '', -- Lista de conceptos relacionados separados por comas
                ultimo_acceso REAL,
                sinonimos TEXT DEFAULT '' -- Terminos alternativos para busqueda FTS5
            )
        """)

        # Migración segura: agregar columna sinonimos si la tabla existía sin ella
        try:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN sinonimos TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Ya existe

        # Crear un índice explícito para acelerar ordenaciones por peso y último acceso (Inhibición y Poda)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_peso_acceso ON largo_plazo (peso_sinaptico, ultimo_acceso)")
        self._crear_tabla_comunicaciones()
        self._crear_tabla_fts()
        self._crear_tabla_metricas()
        self.conn.commit()

    def _calcular_jaccard(self, str1, str2):
        """Calcula la similitud de Jaccard entre dos cadenas en base a sub-palabras de 3 caracteres (Trigramas)."""
        def obtener_trigramas(texto):
            clean = re.sub(r'[^a-z0-9]', '', texto.lower())
            return set(clean[i:i+3] for i in range(len(clean) - 2)) if len(clean) >= 3 else set([clean])

        set1, set2 = obtener_trigramas(str1), obtener_trigramas(str2)
        interseccion = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return interseccion / union if union > 0 else 0.0

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
            # Buscar cada token en contenido
            tokens_encontrados = sum(1 for t in tokens_query if t in contenido_lower)
            if tokens_encontrados > 0:
                puntaje = tokens_encontrados / len(tokens_query) * 0.8 + 0.2  # base 0.2 + proporcion
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
                # Fallback: buscar en contenido
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
            nodos_vecinos = [v.strip() for v in asociaciones.split(",") if v.strip()]
            for vecino in nodos_vecinos:
                self.cursor.execute("""
                    UPDATE largo_plazo 
                    SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                        ultimo_acceso = ?
                    WHERE concepto = ? AND estado = 'activo'
                """, (time.time(), vecino))

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
            for r in pagina_resultados:
                if r[3] == "dormido":
                    nuevo_peso = min(1.0, r[2] + 0.15)
                    self.cursor.execute(
                        "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                        (nuevo_peso, time.time(), r[0]),
                    )

        self.conn.commit()
        return pagina_resultados, len(resultados_con_score)

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
                # Fallback: buscar en contenido (incluye nodos dormidos)
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

        self.conn.commit()
        fin = time.perf_counter()
        print(f"[MemoryBioRAG] Evocado exitosamente '{key}' en {(fin - inicio) * 1000000:.2f} microsegundos.")
        return contenido

    def percibir_corto_plazo(self, concepto, contenido, sinonimos="", categoria="general"):
        """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo).
        Si el concepto ya existe en corto plazo, concatena contenido y mergea sinónimos."""
        key = concepto.lower().strip()
        self.cursor.execute("SELECT contenido, sinonimos, categoria FROM corto_plazo WHERE concepto = ?", (key,))
        existente = self.cursor.fetchone()
        if existente:
            contenido_final = existente[0] + f" | Actualización: {contenido}"
            sinonimos_exist = [s.strip() for s in (existente[1] or "").split(",") if s.strip()]
            sinonimos_nuevos = [s.strip() for s in (sinonimos or "").split(",") if s.strip() and s.strip() not in sinonimos_exist]
            sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
            categoria = existente[2] or categoria
        else:
            contenido_final = contenido
            sinonimos_final = sinonimos
        self.cursor.execute("""
            INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria)
            VALUES (?, ?, ?, ?, ?)
        """, (key, contenido_final, time.time(), sinonimos_final, categoria))
        self.conn.commit()

    def ciclo_sueno_consolidacion(self, limite_energia=None):
        """
        Consolida las experiencias de Corto Plazo a Largo Plazo (Corteza Permanente).
        Aplica LTD (Depresión a Largo Plazo) mediante decaimiento pasivo (-0.05) a los nodos no usados.
        Duerme los recuerdos cuyo peso sea <= 0.1.
        Aplica Inhibición Lateral Activa si la 'energía sináptica' total de los nodos activos excede el limite_energia.
        limite_energia: si es None, se calcula dinámicamente como n_activos * 1.3 (mínimo 10.0).
        """
        print("\n--- Iniciando Ciclo de Consolidación (Sueño) ---")
        
        # Límite dinámico: n_activos * 1.3, mínimo 10.0
        if limite_energia is None:
            self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
            n_activos = self.cursor.fetchone()[0] or 0
            limite_energia = max(10.0, n_activos * 1.3)

        # 1. Transferencia y Fusión de Corto a Largo Plazo
        self.cursor.execute("SELECT concepto, contenido, sinonimos, categoria FROM corto_plazo")
        recuerdos_sesion = self.cursor.fetchall()
        
        for concepto, contenido, sinonimos, categoria in recuerdos_sesion:
            self.cursor.execute("SELECT contenido, peso_sinaptico, asociaciones, sinonimos, categoria FROM largo_plazo WHERE concepto = ?", (concepto,))
            existente = self.cursor.fetchone()
            
            if existente:
                # Fusión de información por adición semántica y subida de peso (LTP de consolidación)
                nuevo_contenido = existente[0] + f" | Actualización: {contenido}"
                nuevo_peso = min(1.0, existente[1] + 0.20)
                # Fusión de sinónimos (no duplicar)
                sinonimos_exist = [s.strip() for s in (existente[3] or "").split(",") if s.strip()]
                sinonimos_nuevos = [s.strip() for s in (sinonimos or "").split(",") if s.strip() and s.strip() not in sinonimos_exist]
                sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
                categoria = existente[4] or categoria
                self.cursor.execute("""
                    UPDATE largo_plazo 
                    SET contenido = ?, peso_sinaptico = ?, estado = 'activo', ultimo_acceso = ?, sinonimos = ?, categoria = ?
                    WHERE concepto = ?
                """, (nuevo_contenido, nuevo_peso, time.time(), sinonimos_final, categoria, concepto))
            else:
                # Creación de un nuevo nodo en el grafo con peso inicial máximo
                self.cursor.execute("""
                    INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos)
                    VALUES (?, ?, ?, 1.0, 'activo', '', ?, ?)
                """, (concepto, categoria or 'general', contenido, time.time(), sinonimos or ""))

        # 2. Decaimiento Pasivo (LTD): Reducir peso de los nodos activos no consolidados hoy
        # El decaimiento es lineal (-0.05)
        self.cursor.execute("""
            UPDATE largo_plazo 
            SET peso_sinaptico = ROUND(MAX(0.0, peso_sinaptico - 0.05), 2)
            WHERE estado = 'activo' AND concepto NOT IN (SELECT concepto FROM corto_plazo)
        """)
        
        # 3. Poda selectiva por umbral de fuerza (Dormir recuerdos <= 0.1)
        self.cursor.execute("""
            UPDATE largo_plazo 
            SET estado = 'dormido' 
            WHERE peso_sinaptico <= 0.1 AND estado = 'activo'
        """)

        # 4. Inhibición Lateral Activa (Control de Saturación de Energía)
        self.cursor.execute("SELECT SUM(peso_sinaptico) FROM largo_plazo WHERE estado = 'activo'")
        energia_total = self.cursor.fetchone()[0] or 0.0

        if energia_total > limite_energia:
            exceso = energia_total - limite_energia
            print(f"[Inhibición Lateral] Alerta: Energía sináptica activa ({energia_total:.2f}) excede el límite ({limite_energia}). Aplicando inhibición...")
            # Obtener los nodos activos ordenados de menor peso y más antiguos para apagar los más débiles
            self.cursor.execute("""
                SELECT concepto, peso_sinaptico FROM largo_plazo 
                WHERE estado = 'activo' 
                ORDER BY peso_sinaptico ASC, ultimo_acceso ASC
            """)
            nodos_activos = self.cursor.fetchall()
            
            for concepto, peso in nodos_activos:
                if exceso <= 0:
                    break
                # Forzar el apagado (dormir) del nodo para liberar energía
                self.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (concepto,))
                exceso -= peso
                print(f"[Inhibición Lateral] Recuerdo '{concepto}' puesto a dormir forzadamente para balancear la carga cortical.")

        # 5. Vaciar la memoria de corto plazo (La mente amanece despejada)
        self.cursor.execute("DELETE FROM corto_plazo")
        self.conn.commit()

        # 6. Benchmark de rendimiento post-consolidacion
        self._benchmark_rendimiento()

        print("[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.")

    def establecer_asociacion(self, concepto_a, concepto_b):
        """Crea un enlace sináptico bidireccional entre dos conceptos en el grafo de largo plazo."""
        concepto_a, concepto_b = concepto_a.lower().strip(), concepto_b.lower().strip()
        
        for a, b in [(concepto_a, concepto_b), (concepto_b, concepto_a)]:
            self.cursor.execute("SELECT asociaciones FROM largo_plazo WHERE concepto = ?", (a,))
            fila = self.cursor.fetchone()
            if fila:
                asoc = [v.strip() for v in fila[0].split(",") if v.strip()] if fila[0] else []
                if b not in asoc:
                    asoc.append(b)
                    nuevas_asoc = ",".join(asoc)
                    self.cursor.execute("UPDATE largo_plazo SET asociaciones = ? WHERE concepto = ?", (nuevas_asoc, a))
            else:
                self.cursor.execute("""
                    INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso)
                    VALUES (?, 'general', '', 1.0, 'activo', ?, ?)
                """, (a, b, time.time()))
        self.conn.commit()
        print(f"[MemoryBioRAG] Sinapsis establecida: '{concepto_a}' <--> '{concepto_b}'")

    # ─── CANAL DE COMUNICACION INTER-AGENTE ──────────────────────────────

    def _crear_tabla_comunicaciones(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS comunicaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origen TEXT NOT NULL,
                destino TEXT NOT NULL DEFAULT 'todos',
                contenido TEXT NOT NULL,
                timestamp REAL NOT NULL,
                leido INTEGER DEFAULT 0
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_destino ON comunicaciones (destino, leido)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_timestamp ON comunicaciones (timestamp)")
        self.conn.commit()

    def enviar_comunicado(self, origen, destino, contenido):
        """Escribe un mensaje en el canal compartido entre agentes."""
        if destino not in ('athena', 'artemis', 'hermes', 'todos'):
            destino = 'todos'
        self.cursor.execute("""
            INSERT INTO comunicaciones (origen, destino, contenido, timestamp, leido)
            VALUES (?, ?, ?, ?, 0)
        """, (origen.lower(), destino.lower(), contenido, time.time()))
        self.conn.commit()
        print(f"[BioRAG] Mensaje de {origen} para {destino} registrado en la corteza compartida.")

    def leer_comunicados(self, destino=None, solo_no_leidos=False, ultimos=10):
        """Lee mensajes del canal compartido."""
        if destino and destino not in ('athena', 'artemis', 'hermes', 'todos'):
            destino = None
        query = "SELECT id, origen, destino, contenido, timestamp, leido FROM comunicaciones"
        params = []
        condiciones = []

        if destino:
            condiciones.append("(destino = ? OR destino = 'todos')")
            params.append(destino.lower())
        if solo_no_leidos:
            condiciones.append("leido = 0")

        if condiciones:
            query += " WHERE " + " AND ".join(condiciones)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(ultimos)

        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def marcar_como_leido(self, ids):
        """Marca mensajes como leidos."""
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.cursor.execute(f"UPDATE comunicaciones SET leido = 1 WHERE id IN ({placeholders})", ids)
        self.conn.commit()

    # ─── FULL-TEXT SEARCH (FTS5) ─────────────────────────────────

    def _crear_tabla_fts(self):
        """Crea tabla virtual FTS5 con tokenizer trigram y columna sinonimos."""
        # Verificar si la tabla FTS ya existe con el tokenizer correcto
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='largo_plazo_fts'")
        fts_existe = self.cursor.fetchone()[0] > 0

        if fts_existe:
            # Verificar si la FTS actual usa trigram (check by testing if a simple query works with the tokenizer)
            # If it's already trigram, keep it. If porter, rebuild.
            try:
                self.cursor.execute("SELECT rowid FROM largo_plazo_fts WHERE largo_plazo_fts MATCH 'abc' LIMIT 1")
                self.cursor.fetchall()
            except sqlite3.OperationalError:
                fts_existe = False

        if fts_existe:
            # Ya existe con trigram — solo verificar sinonimos column
            try:
                self.cursor.execute("SELECT sinonimos FROM largo_plazo_fts LIMIT 0")
            except sqlite3.OperationalError:
                fts_existe = False  # Rebuild needed

        if not fts_existe:
            # Drop existing FTS if any
            self.cursor.execute("DROP TABLE IF EXISTS largo_plazo_fts")
            self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ai")
            self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ad")
            self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_au")

            # Crear nueva FTS con trigram
            self.cursor.execute("""
                CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
                    concepto,
                    categoria,
                    contenido,
                    sinonimos,
                    tokenize='trigram'
                )
            """)
            self._poblar_fts()

        # Ensure triggers are up-to-date (drop+recreate to replace stale ones)
        self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ai")
        self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ad")
        self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_au")
        self.cursor.execute("""
            CREATE TRIGGER largo_plazo_ai AFTER INSERT ON largo_plazo BEGIN
                INSERT INTO largo_plazo_fts(rowid, concepto, categoria, contenido, sinonimos)
                VALUES (new.rowid, new.concepto, new.categoria, new.contenido, new.sinonimos);
            END
        """)
        self.cursor.execute("""
            CREATE TRIGGER largo_plazo_ad AFTER DELETE ON largo_plazo BEGIN
                DELETE FROM largo_plazo_fts WHERE rowid = old.rowid;
            END
        """)
        self.cursor.execute("""
            CREATE TRIGGER largo_plazo_au AFTER UPDATE ON largo_plazo BEGIN
                DELETE FROM largo_plazo_fts WHERE rowid = old.rowid;
                INSERT INTO largo_plazo_fts(rowid, concepto, categoria, contenido, sinonimos)
                VALUES (new.rowid, new.concepto, new.categoria, new.contenido, new.sinonimos);
            END
        """)

    def _poblar_fts(self):
        """Puebla la FTS desde datos existentes, incluyendo sinonimos."""
        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo_fts")
        if self.cursor.fetchone()[0] > 0:
            return
        try:
            self.cursor.execute("SELECT rowid, concepto, categoria, contenido, sinonimos FROM largo_plazo")
        except sqlite3.OperationalError:
            self.cursor.execute("SELECT rowid, concepto, categoria, contenido, '' as sinonimos FROM largo_plazo")
        for row in self.cursor.fetchall():
            rowid, concepto, categoria, contenido = row[0], row[1], row[2], row[3]
            sinonimos = row[4] if len(row) > 4 else ""
            self.cursor.execute(
                "INSERT INTO largo_plazo_fts(rowid, concepto, categoria, contenido, sinonimos) VALUES (?, ?, ?, ?, ?)",
                (rowid, concepto or "", categoria or "", contenido or "", sinonimos or "")
            )
        self.conn.commit()

    def _crear_tabla_metricas(self):
        """Crea tabla de metricas de rendimiento para auto-evaluacion del sistema."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_rendimiento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                total_nodos INTEGER NOT NULL,
                total_dormidos INTEGER NOT NULL,
                latencia_busqueda_ms REAL NOT NULL,
                tamano_db_bytes INTEGER NOT NULL,
                nodos_activos INTEGER NOT NULL,
                energia_sinaptica REAL NOT NULL
            )
        """)
        self.conn.commit()

    def _calcular_score_hibrido(self, rank_idx, total, peso_sinaptico, asociaciones):
        """Score híbrido: 60% calidad textual (BM25 rank) + 25% peso biológico + 15% riqueza de asociaciones."""
        # Señal 1: Calidad textual — posición en ranking BM25
        if total <= 1:
            score_texto = 1.0
        else:
            score_texto = 1.0 - (rank_idx / (total - 1)) * 0.4

        # Señal 2: Peso sináptico — qué tan usado/reforzado está el nodo
        peso_normalizado = min(1.0, peso_sinaptico)

        # Señal 3: Riqueza de asociaciones — conectividad en el grafo
        if asociaciones:
            num_asoc = len([v for v in asociaciones.split(",") if v.strip()])
            score_asoc = min(1.0, num_asoc / 5.0)
        else:
            score_asoc = 0.0

        return round(0.60 * score_texto + 0.25 * peso_normalizado + 0.15 * score_asoc, 4)

    def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=3, categoria=None):
        """Busqueda hibrida: FTS5 trigram + peso sinaptico + asociaciones.

        frase: texto en lenguaje natural. Trigrams nativos de FTS5 manejan
               typos, variaciones morfologicas y palabras parciales.
        profundidad: 'activos' | 'profundo'
        categoria: filtrar por tipo de memoria (ej: 'proyecto', 'leccion')
        Retorna (resultados, total) donde resultados es lista de
        (concepto, contenido, peso, estado, score, asociaciones)
        """
        if not frase.strip():
            return [], 0

        # Limpiar la frase para FTS5 trigram
        query = frase.strip()

        # Build filter clauses
        filtros = []
        if profundidad != "profundo":
            filtros.append("l.estado = 'activo'")
        if categoria:
            filtros.append(f"l.categoria = '{categoria}'")
        clause = (" AND " + " AND ".join(filtros)) if filtros else ""

        # Construir consulta desde la frase limpia
        sql = """
            SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                   l.estado, l.asociaciones
            FROM largo_plazo_fts f
            JOIN largo_plazo l ON l.rowid = f.rowid
            WHERE largo_plazo_fts MATCH ?{filtro}
            ORDER BY bm25(largo_plazo_fts)
        """.format(filtro=clause)

        todos = None
        try:
            self.cursor.execute(sql, (query,))
            todos = self.cursor.fetchall()
        except sqlite3.OperationalError:
            pass

        # Fallback 1: substring match en contenido
        if not todos and len(query) >= 2:
            filtros_fb = []
            if profundidad != "profundo":
                filtros_fb.append("estado = 'activo'")
            if categoria:
                filtros_fb.append(f"categoria = '{categoria}'")
            where_fb = ("WHERE " + " AND ".join(filtros_fb)) if filtros_fb else ""
            try:
                self.cursor.execute(
                    f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb}"
                )
                filas = self.cursor.fetchall()
                todos = []
                for row in filas:
                    texto = f"{row[1]} {row[2]}".lower()
                    q = query.lower()
                    if q in texto:
                        todos.append((row[0], row[1], row[2], row[3], row[4], row[5]))
                todos = todos[:50]
            except sqlite3.OperationalError:
                pass

        # Fallback 2: best-word trigram similarity (typo + word-match tolerance)
        if not todos and len(query) >= 3:
            filtros_fb = []
            if profundidad != "profundo":
                filtros_fb.append("estado = 'activo'")
            if categoria:
                filtros_fb.append(f"categoria = '{categoria}'")
            where_fb = ("WHERE " + " AND ".join(filtros_fb)) if filtros_fb else ""
            try:
                self.cursor.execute(
                    f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb}"
                )
                filas = self.cursor.fetchall()
                query_words = re.findall(r'\w{3,}', query.lower())
                candidatos = []
                for row in filas:
                    texto = f"{row[1]} {row[2]}".lower()
                    text_words = re.findall(r'\w{3,}', texto)
                    total_score = 0.0
                    for qw in query_words:
                        qt = set(qw[i:i+3] for i in range(len(qw) - 2))
                        if not qt:
                            continue
                        best = max(
                            (len(qt & set(tw[i:i+3] for i in range(len(tw) - 2))) / len(qt)
                             for tw in text_words if len(tw) >= 3),
                            default=0.0
                        )
                        total_score += best
                    avg_score = total_score / len(query_words) if query_words else 0.0
                    if avg_score >= 0.5:
                        candidatos.append((avg_score, row))
                candidatos.sort(key=lambda x: x[0], reverse=True)
                todos = [r[1] for r in candidatos[:10]]
            except sqlite3.OperationalError:
                pass

        if not todos:
            return [], 0

        # Calcular score hibrido para cada resultado
        total = len(todos)
        resultados_con_hibrido = []
        for i, (rowid, concepto, contenido, peso, estado, asociaciones) in enumerate(todos):
            score_hibrido = self._calcular_score_hibrido(i, total, peso, asociaciones or "")
            resultados_con_hibrido.append(
                (concepto, contenido, peso, estado, score_hibrido, asociaciones or "")
            )

        # Reordenar por score hibrido descendente
        resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

        # Paginar
        inicio = (pagina - 1) * limite
        pagina_resultados = resultados_con_hibrido[inicio:inicio + limite]

        if profundidad == "profundo":
            for r in pagina_resultados:
                if r[3] == "dormido":
                    self.cursor.execute(
                        "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = MIN(1.0, peso_sinaptico + 0.15), ultimo_acceso = ? WHERE concepto = ?",
                        (time.time(), r[0]),
                    )
            self.conn.commit()

        return pagina_resultados, total

    # ─── AUTO-MANTENIMIENTO Y EVICCION ──────────────────────────

    def _benchmark_rendimiento(self):
        """Mide latencia de busqueda y registra metricas del sistema."""
        latencia = 0.0
        try:
            inicio = time.perf_counter()
            self.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH 'zzz'"
            )
            latencia = (time.perf_counter() - inicio) * 1000
        except sqlite3.OperationalError:
            latencia = -1.0

        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo")
        total = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'")
        dormidos = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
        activos = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado = 'activo'")
        energia = self.cursor.fetchone()[0] or 0.0
        tamano = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        self.cursor.execute("""
            INSERT INTO metricas_rendimiento
            (timestamp, total_nodos, total_dormidos, latencia_busqueda_ms,
             tamano_db_bytes, nodos_activos, energia_sinaptica)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (time.time(), total, dormidos, round(latencia, 2), tamano, activos, energia))
        self.conn.commit()

    def _candidatos_eviccion(self, limite=5):
        """Identifica nodos candidatos para eviccion (dormant — no ejecuta borrado).

        Retorna lista de (concepto, peso, ultimo_acceso, dias_sin_acceso)
        """
        now = time.time()
        self.cursor.execute("""
            SELECT concepto, peso_sinaptico, ultimo_acceso,
                   ROUND((? - ultimo_acceso) / 86400.0, 1) as dias_sin_acceso
            FROM largo_plazo
            WHERE estado = 'dormido'
              AND peso_sinaptico <= 0.1
            ORDER BY ultimo_acceso ASC
            LIMIT ?
        """, (now, limite))
        return self.cursor.fetchall()

    def _ultimo_benchmark(self):
        """Retorna la ultima latencia registrada o None si no hay metricas."""
        self.cursor.execute(
            "SELECT latencia_busqueda_ms FROM metricas_rendimiento ORDER BY id DESC LIMIT 1"
        )
        fila = self.cursor.fetchone()
        return fila[0] if fila else None

    def cerrar_sistema(self):
        """Cierra de forma segura la conexión con la base de datos SQLite."""
        self.conn.close()
