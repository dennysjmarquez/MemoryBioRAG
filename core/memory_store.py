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
                timestamp REAL
            )
        """)

        # 2. Corteza Cerebral (Largo Plazo / Base de datos permanente con indexación B-Tree por PK)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS largo_plazo (
                concepto TEXT PRIMARY KEY,
                categoria TEXT DEFAULT 'general',
                contenido TEXT,
                peso_sinaptico REAL DEFAULT 1.0,
                estado TEXT DEFAULT 'activo', -- 'activo' o 'dormido'
                asociaciones TEXT DEFAULT '', -- Lista de conceptos relacionados separados por comas
                ultimo_acceso REAL
            )
        """)

        # Crear un índice explícito para acelerar ordenaciones por peso y último acceso (Inhibición y Poda)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_peso_acceso ON largo_plazo (peso_sinaptico, ultimo_acceso)")
        self._crear_tabla_comunicaciones()
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

    def buscar_recuerdo_microsegundos(self, concepto):
        """
        Evoca un recuerdo de largo plazo en microsegundos.
        Solo busca en nodos activos. Si esta dormido, no lo despierta.
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

    def buscar_recuerdo_profundo(self, concepto):
        """
        Busqueda en toda la corteza (activos + dormidos).
        Si encuentra un nodo dormido, lo despierta y aplica LTP.
        Para busqueda consciente de memorias profundas.
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

    def percibir_corto_plazo(self, concepto, contenido):
        """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo)."""
        key = concepto.lower().strip()
        self.cursor.execute("""
            INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp)
            VALUES (?, ?, ?)
        """, (key, contenido, time.time()))
        self.conn.commit()

    def ciclo_sueno_consolidacion(self, limite_energia=10.0):
        """
        Consolida las experiencias de Corto Plazo a Largo Plazo (Corteza Permanente).
        Aplica LTD (Depresión a Largo Plazo) mediante decaimiento pasivo (-0.05) a los nodos no usados.
        Duerme los recuerdos cuyo peso sea <= 0.1.
        Aplica Inhibición Lateral Activa si la 'energía sináptica' total de los nodos activos excede el limite_energia.
        """
        print("\n--- Iniciando Ciclo de Consolidación (Sueño) ---")
        
        # 1. Transferencia y Fusión de Corto a Largo Plazo
        self.cursor.execute("SELECT concepto, contenido FROM corto_plazo")
        recuerdos_sesion = self.cursor.fetchall()
        
        for concepto, contenido in recuerdos_sesion:
            self.cursor.execute("SELECT contenido, peso_sinaptico, asociaciones FROM largo_plazo WHERE concepto = ?", (concepto,))
            existente = self.cursor.fetchone()
            
            if existente:
                # Fusión de información por adición semántica y subida de peso (LTP de consolidación)
                nuevo_contenido = existente[0] + f" | Actualización: {contenido}"
                nuevo_peso = min(1.0, existente[1] + 0.20)
                self.cursor.execute("""
                    UPDATE largo_plazo 
                    SET contenido = ?, peso_sinaptico = ?, estado = 'activo', ultimo_acceso = ?
                    WHERE concepto = ?
                """, (nuevo_contenido, nuevo_peso, time.time(), concepto))
            else:
                # Creación de un nuevo nodo en el grafo con peso inicial máximo
                self.cursor.execute("""
                    INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso)
                    VALUES (?, 'general', ?, 1.0, 'activo', '', ?)
                """, (concepto, contenido, time.time()))

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

    def cerrar_sistema(self):
        """Cierra de forma segura la conexión con la base de datos SQLite."""
        self.conn.close()
