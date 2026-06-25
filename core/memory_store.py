import os
import sqlite3
import time
import re

# Auto-cargar .env.local al importar (antes de leer任何环境变量)
from config import _load_env_local
_load_env_local()

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================
# Los defaults están aquí. Para cambiar, setear la variable de entorno
# correspondiente o crear .env.local en la raíz del proyecto.
# =============================================================================

CANDIDATOS_SIMILITUD = int(os.environ.get('BIORAG_CANDIDATOS_SIMILITUD', '100'))
"""Cuántos nodos considerar como candidatos en similitud conceptual."""

MAX_SALTOS_CADENA = int(os.environ.get('BIORAG_MAX_SALTOS_CADENA', '3'))
"""Máximo de saltos (hops) en evocación por cadena."""

LIMITE_DEFAULT = int(os.environ.get('BIORAG_LIMITE_DEFAULT', '5'))
"""Límite de resultados por capa de búsqueda."""

UMBRAL_JACCARD = float(os.environ.get('BIORAG_UMBRAL_JACCARD', '0.15'))
"""Umbral Jaccard para similitud conceptual (0.0-1.0)."""

RAFTAGA_ACTIVA = os.environ.get('BIORAG_RAFTAGA_ACTIVA', 'true').lower() == 'true'
"""Activar/desactivar ráfaga de reminiscencia."""

THRESHOLD_RAFTAGA = float(os.environ.get('BIORAG_THRESHOLD_RAFTAGA', '0.5'))
"""Score mínimo para activar ráfaga automáticamente."""

LIMITE_RAFTAGA = int(os.environ.get('BIORAG_LIMITE_RAFTAGA', '5'))
"""Límite de resultados en búsqueda por ráfaga."""

LIMITE_EVOCACION = int(os.environ.get('BIORAG_LIMITE_EVOCACION', '5'))
"""Límite de resultados en evocación por cadena."""

# =============================================================================

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
        self.conn = sqlite3.connect(self.db_path, timeout=5)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.cursor = self.conn.cursor()
        # Función personalizada: word boundary check del lado de la DB
        def palabra_completa(token, texto):
            if not token or not texto:
                return 0
            return 1 if re.search(r'\b' + re.escape(token.lower()) + r'\b', texto.lower()) else 0
        self.conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)

        # Función personalizada: prefix word boundary check del lado de la DB
        def palabra_prefijo(token, texto):
            if not token or not texto:
                return 0
            return 1 if re.search(r'\b' + re.escape(token.lower()), texto.lower()) else 0
        self.conn.create_function("PALABRA_PREFIJO", 2, palabra_prefijo)
        self._cat_cache = {}
        self._crear_estructura_cerebral()
        self.conn.execute("PRAGMA foreign_keys = ON")

    def _resolver_categoria_id(self, nombre):
        if not self._cat_cache:
            cur = self.conn.execute("SELECT id, name FROM categories")
            for row in cur.fetchall():
                self._cat_cache[row[1]] = row[0]
        if nombre not in self._cat_cache:
            validas = ", ".join(sorted(self._cat_cache.keys()))
            raise ValueError(f"Categoria '{nombre}' no existe. Validas: {validas}")
        return self._cat_cache[nombre]

    def listar_categorias(self):
        self.cursor.execute("SELECT id, name, description FROM categories ORDER BY id")
        return self.cursor.fetchall()

    def sync_status(self):
        """Retorna categorías pendientes de sincronizar."""
        self.cursor.execute("""
            SELECT c.id, c.name, COUNT(sl.id) as cambios
            FROM sync_log sl
            JOIN categories c ON sl.categoria_id = c.id
            WHERE sl.sincronizado = 0
            GROUP BY c.id, c.name
            ORDER BY c.name
        """)
        return self.cursor.fetchall()

    def sync_marcado(self, categoria_ids):
        """Marca categorías como sincronizadas."""
        if not categoria_ids:
            return
        placeholders = ",".join("?" * len(categoria_ids))
        self.cursor.execute(
            f"UPDATE sync_log SET sincronizado = 1 WHERE categoria_id IN ({placeholders}) AND sincronizado = 0",
            categoria_ids
        )
        self.conn.commit()

    def sync_limpiar(self):
        """Limpia el log de sincronización ya procesado."""
        self.cursor.execute("DELETE FROM sync_log WHERE sincronizado = 1")
        self.conn.commit()

    def _crear_estructura_cerebral(self):
        """Inicializa las tablas que simulan la corteza permanente y la memoria de trabajo."""
        # 1. Memoria de Trabajo (Corto Plazo / RAM-Disk equivalente)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS corto_plazo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concepto TEXT UNIQUE NOT NULL,
                contenido TEXT,
                timestamp REAL,
                sinonimos TEXT DEFAULT '',
                categoria INTEGER DEFAULT 1
            )
        """)
        # Migración: si categoria es TEXT, recrear con INTEGER
        self.cursor.execute("PRAGMA table_info(corto_plazo)")
        cp_cols = {row[1]: row[2] for row in self.cursor.fetchall()}
        if cp_cols.get('categoria') == 'TEXT':
            self.cursor.execute("ALTER TABLE corto_plazo RENAME TO corto_plazo_old")
            self.cursor.execute("""
                CREATE TABLE corto_plazo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concepto TEXT UNIQUE NOT NULL,
                    contenido TEXT,
                    timestamp REAL,
                    sinonimos TEXT DEFAULT '',
                    categoria INTEGER DEFAULT 1
                )
            """)
            self.cursor.execute("""
                INSERT INTO corto_plazo (id, concepto, contenido, timestamp, sinonimos, categoria)
                SELECT id, concepto, contenido, COALESCE(timestamp, 0),
                       COALESCE(sinonimos, ''),
                       COALESCE((SELECT id FROM categories WHERE name = corto_plazo_old.categoria), 1)
                FROM corto_plazo_old
            """)
            self.cursor.execute("DROP TABLE corto_plazo_old")

        # 2. Corteza Cerebral (Largo Plazo / Base de datos permanente con indexación B-Tree por PK)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS largo_plazo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concepto TEXT UNIQUE NOT NULL,
                categoria INTEGER DEFAULT 1,
                contenido TEXT,
                peso_sinaptico REAL DEFAULT 1.0,
                estado TEXT DEFAULT 'activo',
                asociaciones TEXT DEFAULT '',
                ultimo_acceso REAL,
                sinonimos TEXT DEFAULT '',
                FOREIGN KEY (categoria) REFERENCES categories(id)
            )
        """)

        # Migración desde schema viejo (concepto TEXT PRIMARY KEY, sin id)
        self.cursor.execute("SELECT COUNT(*) FROM pragma_table_info('largo_plazo') WHERE name = 'id'")
        tiene_id = self.cursor.fetchone()[0] > 0
        if not tiene_id:
            self.cursor.execute("ALTER TABLE largo_plazo RENAME TO largo_plazo_old")
            self.cursor.execute("""
                CREATE TABLE largo_plazo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concepto TEXT UNIQUE NOT NULL,
                    categoria TEXT DEFAULT 'General',
                    contenido TEXT,
                    peso_sinaptico REAL DEFAULT 1.0,
                    estado TEXT DEFAULT 'activo',
                    asociaciones TEXT DEFAULT '',
                    ultimo_acceso REAL,
                    sinonimos TEXT DEFAULT ''
                )
            """)
            self.cursor.execute("""
                INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos)
                SELECT concepto, COALESCE(categoria, 'general'), contenido,
                       COALESCE(peso_sinaptico, 1.0), COALESCE(estado, 'activo'),
                       COALESCE(asociaciones, ''), COALESCE(ultimo_acceso, 0),
                       COALESCE(sinonimos, '')
                FROM largo_plazo_old
            """)
            self.cursor.execute("DROP TABLE largo_plazo_old")
            # Forzar recreación de FTS5 (schema viejo de largo_plazo ya no existe)
            self.cursor.execute("DROP TABLE IF EXISTS largo_plazo_fts")
        else:
            # Migración segura: agregar columna sinonimos si la tabla existía sin ella
            try:
                self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN sinonimos TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass

        # 3. Tabla de Categorías (taxonomía fija para organización de fuentes)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                decay_rate REAL DEFAULT 1.0
            )
        """)
        self.cursor.execute("""
            INSERT OR IGNORE INTO categories (name, description) VALUES
                ('System', 'Componentes base del ecosistema, infraestructura técnica, servidores, bases de datos locales, motores de indexación, protocolos de contexto, instaladores, dependencias y configuración del entorno fundamental que sostiene la operación del software'),
                ('Architecture', 'Decisiones de diseño estructural, lenguajes formales de dominio, patrones de software, estándares de seguridad y marcos organizativos que definen cómo se integran y comunican los distintos módulos del sistema'),
                ('Project', 'Iniciativas activas, frentes de trabajo en ejecución, configuraciones de soluciones específicas e integraciones con terceros que requieren seguimiento, tareas y entregables definidos'),
                ('Lesson', 'Conocimiento empírico derivado de fallos resueltos, depuración técnica, análisis de causas raíz, soluciones aplicadas a problemas operativos y aprendizajes que merecen preservarse para no repetir errores'),
                ('Profile', 'Historial profesional y académico, habilidades técnicas, certificaciones, portafolio de trabajos, empresas y proyectos realizados para acreditación y exposición de la trayectoria del usuario'),
                ('Personal', 'Datos e información del ámbito privado, preferencias, notas subjetivas, registros del entorno de trabajo y configuraciones personales que no pertenecen a la operación técnica del sistema'),
                ('Principle', 'Filosofías rectoras, axiomas de desarrollo, reglas de estilo, metodologías conceptuales y criterios de calidad que guían las decisiones y el diseño dentro del ecosistema'),
                ('Protocol', 'Secuencias operativas estandarizadas, flujos de trabajo repetibles, reglas de sincronización y procedimientos paso a paso para procesos que deben ejecutarse siempre de la misma forma'),
                ('Cognition', 'Lógica interna de los agentes inteligentes, identidad, rol, instrucciones de sistema, introspección, autoevaluación y control interno del comportamiento y la toma de decisiones'),
                ('Relation', 'Esquemas de comunicación entre entidades, dinámicas de interacción, roles, canales y protocolos de mensajería entre agentes, usuarios y sistemas externos'),
                ('General', 'Contenido no clasificado, información transversal, notas de entrada rápida y datos temporales pendientes de categorización o triaje')
        """)

        # Migración: agregar decay_rate si no existe
        cur_temp = self.conn.execute("PRAGMA table_info(categories)")
        cat_cols = [row[1] for row in cur_temp.fetchall()]
        if 'decay_rate' not in cat_cols:
            self.cursor.execute("ALTER TABLE categories ADD COLUMN decay_rate REAL DEFAULT 1.0")
            self.conn.commit()

        # Siempre asegurar decay rates correctos (CREATE TABLE usa DEFAULT 1.0)
        self.cursor.execute("UPDATE categories SET decay_rate = 0.05 WHERE name = 'Profile'")
        self.cursor.execute("UPDATE categories SET decay_rate = 0.2 WHERE name = 'Principle'")
        self.cursor.execute("UPDATE categories SET decay_rate = 0.5 WHERE name = 'Protocol'")
        self.cursor.execute("UPDATE categories SET decay_rate = 1.0 WHERE name IN ('Lesson', 'Cognition', 'Relation', 'System', 'Architecture', 'Personal')")
        self.cursor.execute("UPDATE categories SET decay_rate = 1.5 WHERE name = 'Project'")
        self.cursor.execute("UPDATE categories SET decay_rate = 2.0 WHERE name = 'General'")
        self.conn.commit()

        # Migración: agregar ultimo_uso a sinapsis si no existe
        from core.sinapsis import init_sinapsis_table
        init_sinapsis_table(self.cursor)
        sinapsis_cols = [row[1] for row in self.conn.execute("PRAGMA table_info(sinapsis)").fetchall()]
        if 'ultimo_uso' not in sinapsis_cols:
            self.cursor.execute("ALTER TABLE sinapsis ADD COLUMN ultimo_uso REAL")
            self.conn.commit()

        # 3b. Tabla semántica para expansión de queries
        from core.semantica import init_semantica_table
        init_semantica_table(self.cursor)

        # 4. Migración FK: eliminar categoria_id si existe, agregar FK en categoria→categories.name
        cur = self.cursor

        # --- corto_plazo ---
        cur.execute("PRAGMA table_info(corto_plazo)")
        cp_cols = [row[1] for row in cur.fetchall()]
        if 'categoria_id' in cp_cols:
            cur.execute("ALTER TABLE corto_plazo RENAME TO corto_plazo_old")
            cur.execute("""
                CREATE TABLE corto_plazo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concepto TEXT UNIQUE NOT NULL,
                    contenido TEXT,
                    timestamp REAL,
                    sinonimos TEXT DEFAULT '',
                    categoria TEXT DEFAULT 'General',
                    FOREIGN KEY (categoria) REFERENCES categories(name)
                )
            """)
            cur.execute("""
                INSERT INTO corto_plazo (id, concepto, contenido, timestamp, sinonimos, categoria)
                SELECT id, concepto, contenido, COALESCE(timestamp, 0),
                       COALESCE(sinonimos, ''), COALESCE(categoria, 'general')
                FROM corto_plazo_old
            """)
            cur.execute("DROP TABLE corto_plazo_old")

        # --- largo_plazo ---
        cur.execute("PRAGMA table_info(largo_plazo)")
        lp_cols = {row[1]: row[2] for row in cur.fetchall()}
        needs_recreate = False

        # Caso 1: categoria_id existe (schema viejo)
        if 'categoria_id' in lp_cols:
            needs_recreate = True
        # Caso 2: categoria es TEXT (necesita convertir a INTEGER)
        elif lp_cols.get('categoria') == 'TEXT':
            needs_recreate = True
        # Caso 3: no tiene FK constraint
        else:
            cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='largo_plazo'")
            create_sql = (cur.fetchone() or [''])[0]
            if 'FOREIGN KEY' not in create_sql:
                needs_recreate = True

        if needs_recreate:
            cur.execute("DROP TRIGGER IF EXISTS largo_plazo_ai")
            cur.execute("DROP TRIGGER IF EXISTS largo_plazo_ad")
            cur.execute("DROP TRIGGER IF EXISTS largo_plazo_au")
            cur.execute("DROP TABLE IF EXISTS largo_plazo_fts")
            cur.execute("ALTER TABLE largo_plazo RENAME TO largo_plazo_old")
            cur.execute("""
                CREATE TABLE largo_plazo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concepto TEXT UNIQUE NOT NULL,
                    categoria INTEGER DEFAULT 1,
                    contenido TEXT,
                    peso_sinaptico REAL DEFAULT 1.0,
                    estado TEXT DEFAULT 'activo',
                    asociaciones TEXT DEFAULT '',
                    ultimo_acceso REAL,
                    sinonimos TEXT DEFAULT '',
                    FOREIGN KEY (categoria) REFERENCES categories(id)
                )
            """)
            cur.execute("""
                INSERT INTO largo_plazo (id, concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos)
                SELECT id, concepto,
                       COALESCE((SELECT id FROM categories WHERE name = largo_plazo_old.categoria), 1),
                       contenido,
                       COALESCE(peso_sinaptico, 1.0), COALESCE(estado, 'activo'),
                       COALESCE(asociaciones, ''), COALESCE(ultimo_acceso, 0),
                       COALESCE(sinonimos, '')
                FROM largo_plazo_old
            """)
            cur.execute("DROP TABLE largo_plazo_old")

        # Crear un índice explícito para acelerar ordenaciones por peso y último acceso (Inhibición y Poda)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_peso_acceso ON largo_plazo (peso_sinaptico, ultimo_acceso)")
        self._crear_tabla_comunicaciones()
        self._crear_tabla_fts()
        self._crear_tabla_metricas()
        # Vistas para visualización con nombre de categoría
        self.cursor.execute("""
            CREATE VIEW IF NOT EXISTS vista_largo_plazo AS
            SELECT l.*, c.name AS categoria_name
            FROM largo_plazo l
            LEFT JOIN categories c ON l.categoria = c.id
        """)
        self.cursor.execute("""
            CREATE VIEW IF NOT EXISTS vista_corto_plazo AS
            SELECT cp.*, c.name AS categoria_name
            FROM corto_plazo cp
            LEFT JOIN categories c ON cp.categoria = c.id
        """)

        # 7. Tabla de log de sincronización (sync incremental)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria_id INTEGER NOT NULL,
                accion TEXT NOT NULL,
                concepto TEXT,
                timestamp REAL DEFAULT (strftime('%s','now')),
                sincronizado INTEGER DEFAULT 0
            )
        """)
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
            pass  # Legacy TEXT propagation removed — sinapsis table is canonical

        # Propagación vía sinapsis (fuente canónica)
        from core.sinapsis import init_sinapsis_table
        init_sinapsis_table(self.cursor)
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

        # Propagación también vía sinapsis
        from core.sinapsis import init_sinapsis_table
        init_sinapsis_table(self.cursor)
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

    def percibir_corto_plazo(self, concepto, contenido, sinonimos="", categoria="General"):
        """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo).
        Si el concepto ya existe en corto plazo, concatena contenido y mergea sinónimos."""
        key = concepto.lower().strip()
        cat_id = self._resolver_categoria_id(categoria)
        self.cursor.execute("SELECT contenido, sinonimos, categoria FROM corto_plazo WHERE concepto = ?", (key,))
        existente = self.cursor.fetchone()
        if existente:
            contenido_final = existente[0] + f" | Actualización: {contenido}"
            sinonimos_exist = [s.strip() for s in (existente[1] or "").split(",") if s.strip()]
            sinonimos_nuevos = [s.strip() for s in (sinonimos or "").split(",") if s.strip() and s.strip() not in sinonimos_exist]
            sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
            cat_id = existente[2] or cat_id
        else:
            contenido_final = contenido
            sinonimos_final = sinonimos
        self.cursor.execute("""
            INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria)
            VALUES (?, ?, ?, ?, ?)
        """, (key, contenido_final, time.time(), sinonimos_final, cat_id))
        self.conn.commit()

        # Auto-aprendizaje semántico: si hay sinónimos, crear equivalencias
        if sinonimos_final:
            from core.semantica import auto_aprender_desde_sononimos
            auto_aprender_desde_sononimos(self.cursor, key, sinonimos_final)

    def consolidar_concepto(self, concepto):
        """Mueve un concepto de corto a largo plazo directamente.
        No ejecuta LTD, inhibición lateral ni toca otros nodos.
        El trigger FTS5 se encarga del índice automáticamente."""
        key = concepto.lower().strip()
        self.cursor.execute(
            "SELECT contenido, sinonimos, categoria FROM corto_plazo WHERE concepto = ?",
            (key,),
        )
        fila = self.cursor.fetchone()
        if not fila:
            return False
        contenido, sinonimos, cat_id = fila
        self.cursor.execute(
            "INSERT OR REPLACE INTO largo_plazo "
            "(concepto, categoria, contenido, peso_sinaptico, estado, sinonimos) "
            "VALUES (?, ?, ?, 1.0, 'activo', ?)",
            (key, cat_id, contenido, sinonimos or ""),
        )
        self.cursor.execute("DELETE FROM corto_plazo WHERE concepto = ?", (key,))
        self.conn.commit()
        from core.sinapsis import auto_vincular
        auto_vincular(self, key, contenido)
        return True

    def _auto_generar_co_ocurrencia(self, recuerdos_sesion):
        """Fase 2: Auto-generar sinapsis por co-ocurrencia.
        
        Analiza dos fuentes:
        1. corto_plazo: conceptos consolidados en la misma sesión co-ocurren
        2. comunicaciones: conceptos que aparecen en el mismo mensaje co-ocurren
        
        Crea sinapsis con tipo='co_ocurrencia' y peso basado en frecuencia.
        """
        import re
        from itertools import combinations
        
        # Mapa de concepto → tokens de contenido (para matching)
        concepto_tokens = {}
        
        # 1. Co-ocurrencia en corto_plazo (conceptos de la misma sesión)
        if len(recuerdos_sesion) >= 2:
            for c1, contenido1, _, _ in recuerdos_sesion:
                if c1 not in concepto_tokens:
                    concepto_tokens[c1] = set(re.findall(r'\w{4,}', (contenido1 or "").lower()))
            
            # Para cada par de conceptos consolidados juntos
            for (c1, cont1, _, _), (c2, cont2, _, _) in combinations(recuerdos_sesion, 2):
                tokens1 = concepto_tokens.get(c1, set())
                tokens2 = concepto_tokens.get(c2, set())
                
                # Si comparten al menos 2 tokens significativos, co-ocurren
                shared = tokens1 & tokens2
                if len(shared) >= 2:
                    peso = min(0.9, 0.3 + len(shared) * 0.1)
                    self.cursor.execute(
                        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, ?, 'co_ocurrencia', ?) "
                        "ON CONFLICT(origen, destino) DO UPDATE SET "
                        "peso = MIN(0.9, peso + 0.1), ultimo_uso = ?",
                        (c1, c2, peso, time.time(), time.time())
                    )
        
        # 2. Co-ocurrencia en comunicaciones (conceptos en el mismo mensaje)
        try:
            self.cursor.execute(
                "SELECT contenido FROM comunicaciones ORDER BY timestamp DESC LIMIT 50"
            )
            mensajes = self.cursor.fetchall()
            
            if mensajes and len(recuerdos_sesion) >= 1:
                # Tokenizar todos los conceptos activos
                self.cursor.execute(
                    "SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo' LIMIT 200"
                )
                nodos_activos = self.cursor.fetchall()
                nodo_tokens = {c: set(re.findall(r'\w{4,}', (cont or "").lower())) for c, cont in nodos_activos}
                
                for (msg_contenido,) in mensajes:
                    msg_tokens = set(re.findall(r'\w{4,}', (msg_contenido or "").lower()))
                    
                    # Encontrar qué conceptos aparecen en este mensaje
                    conceptos_en_msg = []
                    for c, tokens in nodo_tokens.items():
                        if tokens and msg_tokens:
                            overlap = tokens & msg_tokens
                            if len(overlap) >= 2:
                                conceptos_en_msg.append(c)
                    
                    # Para cada par de conceptos en el mismo mensaje
                    for c1, c2 in combinations(conceptos_en_msg[:10], 2):
                        self.cursor.execute(
                            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                            "VALUES (?, ?, 0.4, 'co_ocurrencia', ?) "
                            "ON CONFLICT(origen, destino) DO UPDATE SET "
                            "peso = MIN(0.9, peso + 0.05), ultimo_uso = ?",
                            (c1, c2, time.time(), time.time())
                        )
        except Exception:
            pass  # Tabla comunicaciones puede no tener datos
        
        self.conn.commit()

    def ciclo_sueno_consolidacion(self, limite_energia=None):
        """
        Consolida las experiencias de Corto Plazo a Largo Plazo (Corteza Permanente).
        Aplica LTD (Depresión a Largo Plazo) mediante decaimiento pasivo (-0.05) a los nodos no usados.
        Duerme los recuerdos cuyo peso sea <= 0.05.
        Aplica Inhibición Lateral Activa si la 'energía sináptica' total de los nodos activos excede el limite_energia.
        limite_energia: si es None, se calcula dinámicamente como n_activos * 1.6 (mínimo 10.0).
        """
        print("\n--- Iniciando Ciclo de Consolidación (Sueño) ---")
        
        # Límite dinámico: n_activos * 1.6, mínimo 10.0
        if limite_energia is None:
            self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
            n_activos = self.cursor.fetchone()[0] or 0
            limite_energia = max(10.0, n_activos * 1.6)

        # Métricas del ciclo
        nodos_dormidos_antes = self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'").fetchone()[0]
        sinapsis_antes = self.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
        n_activos = self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'").fetchone()[0] or 0

        # 1. Transferencia y Fusión de Corto a Largo Plazo
        self.cursor.execute("SELECT concepto, contenido, sinonimos, categoria FROM corto_plazo")
        recuerdos_sesion = self.cursor.fetchall()
        
        for concepto, contenido, sinonimos, cat_id in recuerdos_sesion:
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
                cat_id = existente[4] or cat_id
                self.cursor.execute("""
                    UPDATE largo_plazo 
                    SET contenido = ?, peso_sinaptico = ?, estado = 'activo', ultimo_acceso = ?, sinonimos = ?, categoria = ?
                    WHERE concepto = ?
                """, (nuevo_contenido, nuevo_peso, time.time(), sinonimos_final, cat_id, concepto))
            else:
                # Creación de un nuevo nodo en el grafo con peso inicial máximo
                self.cursor.execute("""
                    INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos)
                    VALUES (?, ?, ?, 1.0, 'activo', '', ?, ?)
                """, (concepto, cat_id or 1, contenido, time.time(), sinonimos or ""))

            # Borrar de corto_plazo después de consolidar (para que LTD lo incluya)
            self.cursor.execute("DELETE FROM corto_plazo WHERE concepto = ?", (concepto,))

        # Auto-vincular cada concepto consolidado (aristas por solapamiento de tokens)
        from core.sinapsis import auto_vincular
        for concepto, contenido, _, _ in recuerdos_sesion:
            auto_vincular(self, concepto, contenido)

        # Fase 2: Auto-generar sinapsis por co-ocurrencia
        # Si dos conceptos aparecieron en la misma sesión (corto_plazo), co-ocurren.
        # También analiza comunicaciones para detectar co-ocurrencia en mensajes.
        self._auto_generar_co_ocurrencia(recuerdos_sesion)

        # 2. Decaimiento Pasivo (LTD): Reducir peso según decay_rate de la categoría
        # Profile/Principle decaen lento, Project/General decaen rápido
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = ROUND(MAX(0.0, peso_sinaptico - 0.05 * (
                SELECT COALESCE(c.decay_rate, 1.0) FROM categories c WHERE c.id = largo_plazo.categoria
            )), 2)
            WHERE estado = 'activo' AND concepto NOT IN (SELECT concepto FROM corto_plazo)
        """)

        # 2b. Decay Sináptico: reducir peso de conexiones no usadas en 7+ días
        self.cursor.execute("""
            UPDATE sinapsis
            SET peso = ROUND(MAX(0.0, peso * 0.95), 3)
            WHERE ultimo_uso IS NOT NULL
              AND ultimo_uso < strftime('%s', 'now') - 604800
        """)
        # Podar sinapsis muertas
        self.cursor.execute("DELETE FROM sinapsis WHERE peso < 0.05")

        # 3. Poda selectiva por umbral de fuerza (Dormir recuerdos <= 0.1)
        self.cursor.execute("""
            UPDATE largo_plazo 
            SET estado = 'dormido' 
            WHERE peso_sinaptico <= 0.05 AND estado = 'activo'
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

        # 7. Eviccion opcional (solo si BIORAG_PODAR=true)
        if os.environ.get("BIORAG_PODAR") == "true":
            eliminados = self._ejecutar_eviccion(max_borrar=10)
            if eliminados:
                print(f"[Eviccion] {eliminados} nodos dormidos eliminados permanentemente.")

        # 8. Registrar métricas cognitivas del ciclo
        nodos_dormidos_despues = self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'").fetchone()[0]
        sinapsis_despues = self.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
        cat_dom = self.cursor.execute("""
            SELECT c.name FROM largo_plazo l JOIN categories c ON l.categoria = c.id
            WHERE l.estado = 'activo' GROUP BY c.name ORDER BY COUNT(*) DESC LIMIT 1
        """).fetchone()
        self.cursor.execute("""
            INSERT INTO metricas_cognitivas
            (timestamp, nodos_consolidados, nodos_dormidos_ciclo, sinapsis_creadas, sinapsis_podadas, categoria_dominante, ratio_consolidacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            len(recuerdos_sesion),
            nodos_dormidos_despues - nodos_dormidos_antes,
            max(0, sinapsis_despues - sinapsis_antes),
            max(0, sinapsis_antes - sinapsis_despues),
            cat_dom[0] if cat_dom else None,
            round(len(recuerdos_sesion) / max(1, n_activos), 2)
        ))
        # Optimizar FTS después de consolidation para reducir fragmentación
        self.cursor.execute("INSERT INTO largo_plazo_fts(largo_plazo_fts) VALUES('optimize')")
        try:
            self.cursor.execute("INSERT INTO largo_plazo_fts_unicode(largo_plazo_fts_unicode) VALUES('optimize')")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

        print("[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.")

    def establecer_asociacion(self, concepto_a, concepto_b):
        """Crea un enlace sináptico bidireccional entre dos conceptos en el grafo de largo plazo."""
        concepto_a, concepto_b = concepto_a.lower().strip(), concepto_b.lower().strip()
        from core.sinapsis import init_sinapsis_table
        init_sinapsis_table(self.cursor)
        for a, b in [(concepto_a, concepto_b), (concepto_b, concepto_a)]:
            self.cursor.execute("SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?", (a, b))
            if not self.cursor.fetchone():
                self.cursor.execute(
                    "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, 0.5, 'manual', ?)",
                    (a, b, time.time())
                )
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
                leido INTEGER DEFAULT 0,
                tipo TEXT DEFAULT 'mensaje',
                referencia_id INTEGER DEFAULT NULL
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_destino ON comunicaciones (destino, leido)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_timestamp ON comunicaciones (timestamp)")
        # Migración: agregar columnas si no existen
        com_cols = [row[1] for row in self.conn.execute("PRAGMA table_info(comunicaciones)").fetchall()]
        if 'tipo' not in com_cols:
            self.cursor.execute("ALTER TABLE comunicaciones ADD COLUMN tipo TEXT DEFAULT 'mensaje'")
        if 'referencia_id' not in com_cols:
            self.cursor.execute("ALTER TABLE comunicaciones ADD COLUMN referencia_id INTEGER DEFAULT NULL")
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
        """Crea tablas virtuales FTS5: trigram (typos/substrings) y unicode61 (prefix matching)."""
        # ─── FTS5 trigram ───
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

            # Crear nueva FTS con trigram (sin categoria - ahora es INTEGER FK)
            self.cursor.execute("""
                CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
                    concepto,
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
                INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos)
                VALUES (new.rowid, new.concepto, new.contenido, new.sinonimos);
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
                INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos)
                VALUES (new.rowid, new.concepto, new.contenido, new.sinonimos);
            END
        """)

        # ─── FTS5 unicode61 (para prefix matching: react -> reactive) ───
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='largo_plazo_fts_unicode'")
        unicode_existe = self.cursor.fetchone()[0] > 0
        if unicode_existe:
            try:
                self.cursor.execute("SELECT sinonimos FROM largo_plazo_fts_unicode LIMIT 0")
            except sqlite3.OperationalError:
                unicode_existe = False

        if not unicode_existe:
            self.cursor.execute("DROP TABLE IF EXISTS largo_plazo_fts_unicode")
            self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_unicode_ai")
            self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_unicode_ad")
            self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_unicode_au")
            self.cursor.execute("""
                CREATE VIRTUAL TABLE largo_plazo_fts_unicode USING fts5(
                    concepto,
                    contenido,
                    sinonimos,
                    tokenize='unicode61'
                )
            """)
            self._poblar_fts_unicode()

        self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_unicode_ai")
        self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_unicode_ad")
        self.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_unicode_au")
        self.cursor.execute("""
            CREATE TRIGGER largo_plazo_unicode_ai AFTER INSERT ON largo_plazo BEGIN
                INSERT INTO largo_plazo_fts_unicode(rowid, concepto, contenido, sinonimos)
                VALUES (new.rowid, new.concepto, new.contenido, new.sinonimos);
            END
        """)
        self.cursor.execute("""
            CREATE TRIGGER largo_plazo_unicode_ad AFTER DELETE ON largo_plazo BEGIN
                DELETE FROM largo_plazo_fts_unicode WHERE rowid = old.rowid;
            END
        """)
        self.cursor.execute("""
            CREATE TRIGGER largo_plazo_unicode_au AFTER UPDATE ON largo_plazo BEGIN
                DELETE FROM largo_plazo_fts_unicode WHERE rowid = old.rowid;
                INSERT INTO largo_plazo_fts_unicode(rowid, concepto, contenido, sinonimos)
                VALUES (new.rowid, new.concepto, new.contenido, new.sinonimos);
            END
        """)

        # Triggers de sync_log: registrar cambios para export incremental
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_sync_insert")
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_sync_update")
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_sync_delete")
        self.cursor.execute("""
            CREATE TRIGGER trg_sync_insert AFTER INSERT ON largo_plazo BEGIN
                INSERT INTO sync_log (categoria_id, accion, concepto)
                VALUES (NEW.categoria, 'insert', NEW.concepto);
            END
        """)
        self.cursor.execute("""
            CREATE TRIGGER trg_sync_update AFTER UPDATE ON largo_plazo
            WHEN OLD.contenido IS NOT NEW.contenido
              OR OLD.concepto IS NOT NEW.concepto
              OR OLD.sinonimos IS NOT NEW.sinonimos
            BEGIN
                INSERT INTO sync_log (categoria_id, accion, concepto)
                VALUES (NEW.categoria, 'update', NEW.concepto);
            END
        """)
        self.cursor.execute("""
            CREATE TRIGGER trg_sync_delete AFTER DELETE ON largo_plazo BEGIN
                INSERT INTO sync_log (categoria_id, accion, concepto)
                VALUES (OLD.categoria, 'delete', OLD.concepto);
            END
        """)

        # Backup antes de DELETE: copia la fila completa a largo_plazo_backup
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS largo_plazo_backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concepto TEXT,
                categoria INTEGER,
                contenido TEXT,
                peso_sinaptico REAL,
                estado TEXT,
                asociaciones TEXT,
                sinonimos TEXT,
                deleted_at REAL DEFAULT (strftime('%s','now'))
            )
        """)
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_backup_before_delete")
        self.cursor.execute("""
            CREATE TRIGGER trg_backup_before_delete
            BEFORE DELETE ON largo_plazo
            BEGIN
                INSERT INTO largo_plazo_backup (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, sinonimos)
                VALUES (OLD.concepto, OLD.categoria, OLD.contenido, OLD.peso_sinaptico, OLD.estado, OLD.asociaciones, OLD.sinonimos);
            END
        """)

    def _poblar_fts(self):
        """Puebla la FTS desde datos existentes, incluyendo sinonimos."""
        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo_fts")
        if self.cursor.fetchone()[0] > 0:
            return
        try:
            self.cursor.execute("SELECT rowid, concepto, contenido, sinonimos FROM largo_plazo")
        except sqlite3.OperationalError:
            self.cursor.execute("SELECT rowid, concepto, contenido, '' as sinonimos FROM largo_plazo")
        for row in self.cursor.fetchall():
            rowid, concepto, contenido = row[0], row[1], row[2]
            sinonimos = row[3] if len(row) > 3 else ""
            self.cursor.execute(
                "INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos) VALUES (?, ?, ?, ?)",
                (rowid, concepto or "", contenido or "", sinonimos or "")
            )
        self.conn.commit()

    def _poblar_fts_unicode(self):
        """Puebla la FTS unicode61 desde datos existentes, incluyendo sinonimos."""
        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo_fts_unicode")
        if self.cursor.fetchone()[0] > 0:
            return
        try:
            self.cursor.execute("SELECT rowid, concepto, contenido, sinonimos FROM largo_plazo")
        except sqlite3.OperationalError:
            self.cursor.execute("SELECT rowid, concepto, contenido, '' as sinonimos FROM largo_plazo")
        for row in self.cursor.fetchall():
            rowid, concepto, contenido = row[0], row[1], row[2]
            sinonimos = row[3] if len(row) > 3 else ""
            self.cursor.execute(
                "INSERT INTO largo_plazo_fts_unicode(rowid, concepto, contenido, sinonimos) VALUES (?, ?, ?, ?)",
                (rowid, concepto or "", contenido or "", sinonimos or "")
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
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_cognitivas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                nodos_consolidados INTEGER DEFAULT 0,
                nodos_dormidos_ciclo INTEGER DEFAULT 0,
                sinapsis_creadas INTEGER DEFAULT 0,
                sinapsis_podadas INTEGER DEFAULT 0,
                categoria_dominante TEXT,
                ratio_consolidacion REAL
            )
        """)
        self.conn.commit()

    def _agregar_prefix_wildcards(self, query):
        """Agrega '*' al final de cada término para prefix matching en FTS5 unicode61.

        Preserva frases entre comillas: "react native" -> "react* native*".
        No duplica wildcards si ya existen. Términos cortos (<3 chars) no reciben
        wildcard para evitar ruido (ej: "el*" matchearía demasiadas palabras).
        """
        terms = re.findall(r'"[^"]*"|\S+', query)
        result = []
        for t in terms:
            if t.startswith('"') and t.endswith('"'):
                inner = t[1:-1]
                if len(inner) < 3:
                    result.append(t)
                else:
                    result.append(f'"{inner}*"')
            elif len(t) < 3 or t.endswith('*'):
                result.append(t)
            else:
                result.append(t + '*')
        return ' '.join(result)

    def _pesar_tokens_query(self, frase):
        """Calcula el peso de cada token según su centralidad en la red sináptica.
        
        Tokens con más conexiones en sinapsis y equivalencias en semántica
        obtienen mayor peso en el scoring. Peso base mínimo de 0.1 para que
        ningún término desaparezca del scoring.
        """
        import re
        tokens = re.findall(r'\w{3,}', frase.lower())
        if not tokens:
            return {}
        
        pesos = {}
        for token in set(tokens):
            # Buscar en concepto de sinapsis (origen/destino suelen ser nombres de nodo)
            # Usamos LIKE solo en sinapsis porque los nombres de nodo son compound
            self.cursor.execute(
                "SELECT COUNT(*) FROM sinapsis WHERE origen LIKE ? OR destino LIKE ?",
                (f'%{token}%', f'%{token}%')
            )
            conexiones = self.cursor.fetchone()[0] or 0
            
            # Buscar en semántica con match exacto (más rápido)
            self.cursor.execute(
                "SELECT COUNT(*) FROM semantica WHERE termino = ? OR equivalente = ?",
                (token, token)
            )
            equivalencias = self.cursor.fetchone()[0] or 0
            
            pesos[token] = max(0.1, conexiones + equivalencias)
        
        total = sum(pesos.values()) or 1
        return {t: p / total for t, p in pesos.items()}

    def _evocacion_por_cadena(self, semillas, max_saltos=None, limite=None):
        """Evocación por cadena: spreading activation multi-hop con decay logarítmico.
        
        Sigue aristas de sinapsis en cadena. Cada salto reduce el score
        con decay logarítmico: 1/(2^salto). Más fiel al proceso cognitivo
        humano donde el tercer salto es mucho más débil que el segundo.
        """
        if max_saltos is None:
            max_saltos = MAX_SALTOS_CADENA
        if limite is None:
            limite = LIMITE_EVOCACION
        visitados = set()
        resultados = []
        actuales = [(n, 1.0) for n in semillas]

        for salto in range(max_saltos):
            decay = 1.0 / (2 ** salto)
            siguientes = []

            for nodo, score in actuales:
                if nodo in visitados:
                    continue
                visitados.add(nodo)

                self.cursor.execute(
                    "SELECT destino, peso FROM sinapsis WHERE origen = ? "
                    "UNION "
                    "SELECT origen, peso FROM sinapsis WHERE destino = ? "
                    "ORDER BY peso DESC LIMIT 10",
                    (nodo, nodo)
                )
                for vecino, peso in self.cursor.fetchall():
                    if vecino not in visitados:
                        sv = score * (peso or 0.5) * decay
                        if sv > 0.05:
                            siguientes.append((vecino, sv))
                            resultados.append((vecino, sv, salto + 1))

            actuales = siguientes

        resultados.sort(key=lambda x: x[1], reverse=True)
        return resultados[:limite]

    def _generar_variaciones(self, query, historial_fallos=None):
        """Genera variaciones de la query basadas en el historial de fallos.
        
        Si "angular formularios" falló, probar:
        - Solo "angular" (más específico)
        - "angular" + sinónimos
        - Filtro por categoría probable
        """
        import re
        variaciones = []
        palabras = re.findall(r'\w{3,}', query.lower())
        
        # Excluir términos que ya fallaron
        palabras_filtradas = [p for p in palabras if p not in (historial_fallos or [])]
        
        # Solo la palabra más importante no fallida
        if palabras_filtradas:
            variaciones.append(palabras_filtradas[0])
        
        # Con sinónimos de la palabra más importante no fallida
        if palabras_filtradas:
            termino = palabras_filtradas[0]
            self.cursor.execute(
                "SELECT equivalente FROM semantica WHERE termino = ? LIMIT 3",
                (termino,)
            )
            syns = [row[0] for row in self.cursor.fetchall()]
            if syns:
                variaciones.append(f"{termino} {' '.join(syns[:2])}")
        
        return variaciones[:3]

    def _calcular_score_hibrido(self, rank_idx, total, peso_sinaptico, asociaciones, pesos_tokens=None, contenido="", es_latente=False, score_latente=0.0, ultimo_acceso=None):
        """Score híbrido: 60% calidad textual (BM25 rank) + 25% peso biológico + 15% riqueza de asociaciones.
        Si pesos_tokens está disponible, ajusta el score textual por centralidad del token en la red.
        Si es_latente=True y score_latente >= 0.15, usa fórmula de emergencia: 70% latente + 20% peso + 10% asociaciones.
        Si ultimo_acceso es reciente, agrega bonus temporal (Anclaje Temporal)."""
        peso_normalizado = min(1.0, peso_sinaptico)

        if asociaciones:
            num_asoc = len([v for v in asociaciones.split(",") if v.strip()])
            score_asoc = min(1.0, num_asoc / 5.0)
        else:
            score_asoc = 0.0

        # Anclaje Temporal: bonus por frescura del nodo
        score_temporal = 0.0
        if ultimo_acceso:
            import time
            dias_desde = (time.time() - ultimo_acceso) / 86400
            if dias_desde <= 7:
                score_temporal = 0.15
            elif dias_desde <= 30:
                score_temporal = 0.08
            elif dias_desde <= 90:
                score_temporal = 0.03

        if es_latente and score_latente >= 0.15:
            return round(0.70 * score_latente + 0.20 * peso_normalizado + 0.10 * score_asoc + score_temporal, 4)

        if total <= 1:
            score_texto = 1.0
        else:
            score_texto = 1.0 - (rank_idx / (total - 1)) * 0.4

        if pesos_tokens and contenido:
            import re
            tokens_en_contenido = set(re.findall(r'\w{3,}', contenido.lower()))
            peso_query = sum(peso for token, peso in pesos_tokens.items() if token in tokens_en_contenido)
            score_texto = score_texto * 0.7 + peso_query * 0.3

        return round(0.60 * score_texto + 0.25 * peso_normalizado + 0.15 * score_asoc + score_temporal, 4)

    def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=None, categoria=None, preview_chars=1500, historial_fallos=None, context_window=0):
        """Busqueda hibrida: FTS5 trigram + peso sinaptico + asociaciones.

        frase: texto en lenguaje natural. Trigrams nativos de FTS5 manejan
               typos, variaciones morfologicas y palabras parciales.
        profundidad: 'activos' | 'profundo'
        categoria: filtrar por tipo de memoria (ej: 'proyecto', 'leccion')
        preview_chars: longitud maxima del contenido retornado.
                       0 o None retorna el contenido completo.
                       El motor trunca en vez del CLI (ahorra RAM).
        historial_fallos: lista de queries anteriores que no dieron resultado.
                          Se usa para generar variaciones en caso de fallo.
        context_window: numero de vecinos por resultado a incluir como contexto.
                        0 = solo resultados principales (default).
                        Maximo 3. Vecinos se obtienen de sinapsis por peso.
        Retorna (resultados, total) donde resultados es lista de
        (concepto, contenido, peso, estado, score, asociaciones)
        """
        if limite is None:
            limite = LIMITE_DEFAULT
        if not frase.strip():
            return [], 0

        # Limpiar la frase para FTS5 trigram
        query = frase.strip()

        # Calcular pesos diferenciales de tokens por centralidad en la red
        pesos_tokens = self._pesar_tokens_query(frase)

        # Build filter clauses
        filtros = []
        if profundidad != "profundo":
            filtros.append("l.estado = 'activo'")
        if categoria:
            cat_id = self._resolver_categoria_id(categoria)
            filtros.append(f"l.categoria = {cat_id}")
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

        todos = []
        palabras = [w for w in frase.split() if len(w) >= 3]
        origen_scores = {}  # Side channel: rastrea origen de cada nodo para Dynamic Multiplicator

        # Filtro DB-side PALABRA_COMPLETA: previene falsos positivos de FTS5 trigram
        # ("culo" no debe matchear "artículos"). Aplica a contenido+concepto+sinonimos.
        # Exige que AL MENOS UNA palabra aparezca como palabra completa en alguno.
        # Sinonimos incluidos: la búsqueda por sinónimo debe seguir funcionando.
        pc_clause = ""
        pc_params = []
        if palabras:
            pc_clauses = []
            for p in palabras:
                pc_clauses.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                pc_params.extend([p, p, p])
            pc_clause = " AND (" + " OR ".join(pc_clauses) + ")"
        # Inyectar pc_clause en el WHERE después de los filtros de estado/categoría
        sql_con_pc = sql.replace("ORDER BY bm25(largo_plazo_fts)", pc_clause + " ORDER BY bm25(largo_plazo_fts)")

        # Intentar NEAR query primero (palabras cercanas entre sí)
        if len(palabras) > 1:
            near_query = f'NEAR({" ".join(palabras)}, 15)'
            try:
                self.cursor.execute(sql_con_pc, tuple([near_query]) + tuple(pc_params))
                todos = self.cursor.fetchall()
                for r in todos:
                    origen_scores[r[1]] = ("literal", 0.0)
            except sqlite3.OperationalError:
                pass

        # Fallback 1.0: FTS5 AND exacto
        if not todos:
            try:
                self.cursor.execute(sql_con_pc, (query,) + tuple(pc_params))
                todos = self.cursor.fetchall()
                for r in todos:
                    origen_scores[r[1]] = ("literal", 0.0)
            except sqlite3.OperationalError:
                pass

        # OR fallback: si AND devolvió pocos resultados y hay múltiples palabras, probar OR
        if todos and len(todos) < max(limite * 2, 5) and len(frase.split()) > 1:
            palabras = [w for w in frase.split() if len(w) >= 3]
            if len(palabras) > 1:
                query_or = " OR ".join(palabras)
                try:
                    self.cursor.execute(sql_con_pc, (query_or,) + tuple(pc_params))
                    or_results = self.cursor.fetchall()
                    seen_rowids = {r[0] for r in todos}
                    for r in or_results:
                        if r[0] not in seen_rowids:
                            todos.append(r)
                            origen_scores[r[1]] = ("literal", 0.0)
                except sqlite3.OperationalError:
                    pass

        # Fallback 1.4: FTS5 unicode61 con prefix wildcards
        # Mejora recall para palabras que comparten prefijo (react -> reactive, forms -> formularios).
        # Se ejecuta siempre que haya al menos un término buscable para enriquecer resultados.
        try:
            query_wild = self._agregar_prefix_wildcards(query)
            sql_unicode = """
                SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                       l.estado, l.asociaciones
                FROM largo_plazo_fts_unicode f
                JOIN largo_plazo l ON l.rowid = f.rowid
                WHERE largo_plazo_fts_unicode MATCH ?{filtro}
                ORDER BY bm25(largo_plazo_fts_unicode)
                LIMIT ?
            """.format(filtro=clause)
            self.cursor.execute(sql_unicode, (query_wild,) + (max(limite * 3, 10),))
            uni_results = self.cursor.fetchall()
            seen_rowids = {r[0] for r in todos}
            for r in uni_results:
                if r[0] not in seen_rowids:
                    todos.append(r)
                    origen_scores[r[1]] = ("literal", 0.0)
        except sqlite3.OperationalError:
            pass

        # Fallback 1.5: Expansión semántica
        # NO aplica PALABRA_COMPLETA: las equivalentes son palabras distintas por diseño.
        # "auto" → "vehículo" debe funcionar aunque "vehículo" no aparezca en el texto.
        # Dynamic Multiplicator: registrar como "expansion" con score 0.8 (peso default semántica)
        if not todos and len(query) >= 2:
            from core.semantica import expandir_query
            equivalentes = expandir_query(self.cursor, query)
            if equivalentes:
                query_exp = " OR ".join(equivalentes)
                try:
                    self.cursor.execute(sql, (query_exp,))
                    sem_results = self.cursor.fetchall()
                    seen_rowids = {r[0] for r in todos}
                    for r in sem_results:
                        if r[0] not in seen_rowids:
                            todos.append(r)
                            origen_scores[r[1]] = ("expansion", 0.8)
                except sqlite3.OperationalError:
                    pass

        # Fallback 1.7: Similitud conceptual latente (Jaccard vecinos + contenido)
        # Usa Jaccard sobre tokens, no requiere match literal. No aplicar PALABRA_COMPLETA.
        # Dynamic Multiplicator: registrar como "latente" con score Jaccard real
        # OPTIMIZACIÓN: Pre-cargar puentes FTS5 una vez (reduce N queries a 1)
        if not todos and len(query) >= 2:
            from core.similitud_conceptual import _tokenizar_query, score_similitud_latente, LIMITE_SIMILITUD, _cargar_grafo, _limpiar_cache
            query_tokens = _tokenizar_query(query)
            if query_tokens:
                try:
                    grafo = _cargar_grafo(self.cursor)
                    # Batch: pre-fetch puentes FTS5 una vez (1 query SQL)
                    # En vez de N queries FTS5 separadas en _similitud_red
                    filtrar = [t for t in query_tokens if len(t) >= 3]
                    nodos_cache = None
                    if filtrar:
                        fts_tokens = [f'"{t}"' for t in filtrar]
                        fts_q = " OR ".join(fts_tokens)
                        # Filtro PALABRA_COMPLETA en puentes: evita falsos positivos de trigram
                        # (ej: "culo" en "oráculo" contaminando la similitud conceptual)
                        pc_bridge_clause = " AND (" + " OR ".join(
                            ["(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)"] * len(filtrar)
                        ) + ")"
                        pc_bridge_params = tuple(p for t in filtrar for p in (t, t, t))
                        try:
                            self.cursor.execute(
                                "SELECT DISTINCT l.concepto FROM largo_plazo_fts f "
                                "JOIN largo_plazo l ON l.rowid = f.rowid "
                                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                                + pc_bridge_clause + " LIMIT 50",
                                (fts_q,) + pc_bridge_params
                            )
                            nodos_cache = {row[0] for row in self.cursor.fetchall()}
                        except sqlite3.OperationalError:
                            nodos_cache = None
                    fts_tokens = [f'"{t}"' for t in query_tokens if len(t) >= 3]
                    if fts_tokens:
                        fts_q = " OR ".join(fts_tokens)
                        self.cursor.execute(
                            "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                            "l.estado, l.asociaciones "
                            "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                            "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' LIMIT ?",
                            (fts_q, CANDIDATOS_SIMILITUD)
                        )
                        candidatos_lat = self.cursor.fetchall()
                        scored = []
                        for rowid, concepto, contenido, peso, estado, asoc in candidatos_lat:
                            s = score_similitud_latente(self.cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache)
                            if s >= 0.10:
                                scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))
                        scored.sort(key=lambda x: x[0], reverse=True)
                        for jaccard_score, row in scored[:LIMITE_SIMILITUD]:
                            todos.append(row)
                            # Solo registrar si no fue encontrado por capa literal (FTS5 tiene prioridad)
                            if row[1] not in origen_scores:
                                origen_scores[row[1]] = ("latente", jaccard_score)
                    _limpiar_cache()
                except sqlite3.OperationalError:
                    _limpiar_cache()
                    pass

        # Fallback 2.0: substring match con word boundary via PALABRA_COMPLETA
        if not todos and len(query) >= 2:
            filtros_fb = []
            if profundidad != "profundo":
                filtros_fb.append("estado = 'activo'")
            if categoria:
                cat_id_fb = self._resolver_categoria_id(categoria)
                filtros_fb.append(f"categoria = {cat_id_fb}")
            # PALABRA_COMPLETA filtra en DB: "culo" no matchea "artículo"
            filtros_fb.append("PALABRA_COMPLETA(?, contenido) = 1")
            where_fb = "WHERE " + " AND ".join(filtros_fb)
            try:
                self.cursor.execute(
                    f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb}",
                    (query.lower(),)
                )
                filas = self.cursor.fetchall()
                todos = [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in filas]
                todos = todos[:50]
            except sqlite3.OperationalError:
                pass

        # Fallback 2.5: best-word trigram similarity (typo + word-match tolerance)
        # Filtro PC: solo aplica a palabras CORTAS (<=5 chars) donde el trigrama no
        # es discriminante (ej: "culo" como substring de "artículos"). Para palabras
        # largas (>=6 chars), el trigrama ya es tolerante a typos sin generar FPs.
        if not todos and len(query) >= 3:
            sql_limit = max(200, limite * 10)
            filtros_fb = []
            if profundidad != "profundo":
                filtros_fb.append("estado = 'activo'")
            if categoria:
                cat_id_fb2 = self._resolver_categoria_id(categoria)
                filtros_fb.append(f"categoria = {cat_id_fb2}")
            where_fb = ("WHERE " + " AND ".join(filtros_fb)) if filtros_fb else ""
            try:
                self.cursor.execute(
                    f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb} LIMIT {sql_limit}"
                )
                filas = self.cursor.fetchall()
                query_words = re.findall(r'\w{3,}', query.lower())
                # Separar query_words en cortas (PC aplica) y largas (PC no aplica, tolerancia a typos)
                qw_cortas = [w for w in query_words if len(w) <= 5]
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
                    if avg_score >= 0.7:
                        # Filtro PC solo para palabras cortas: rechaza matches donde el
                        # token solo es substring de otra palabra. Palabras largas ya son
                        # discriminantes vía trigrama.
                        texto_full = f"{row[1]} {row[2] or ''}"
                        if qw_cortas:
                            match_legitimo = any(
                                re.search(r'\b' + re.escape(qw) + r'\b', texto_full, re.IGNORECASE)
                                for qw in qw_cortas
                            )
                            if not match_legitimo:
                                continue
                        candidatos.append((avg_score, row))
                candidatos.sort(key=lambda x: x[0], reverse=True)
                for score_typo, row in candidatos[:max(limite * 3, 10)]:
                    todos.append(row)
                    if row[1] not in origen_scores:
                        origen_scores[row[1]] = ("typo", score_typo)
            except sqlite3.OperationalError:
                pass

        # Fallback 1.8: Snap reciente (últimos 7 días)
        if not todos and len(query) >= 2:
            limite_tiempo = time.time() - (7 * 86400)
            # sql_con_pc ya incluye el filtro PALABRA_COMPLETA — previene falsos positivos
            sql_snap = sql_con_pc.replace("ORDER BY bm25(largo_plazo_fts)",
                                          "AND l.ultimo_acceso > ? ORDER BY bm25(largo_plazo_fts) LIMIT 5")
            try:
                self.cursor.execute(sql_snap, (query,) + tuple(pc_params) + (limite_tiempo,))
                snap_r = self.cursor.fetchall()
                if snap_r:
                    print(f"[TRACE] 1.8 Snap: {len(snap_r)} → {[r[1] for r in snap_r[:3]]}")
                todos = snap_r
            except sqlite3.OperationalError:
                pass

        # Fallback 1.9: Evocación por cadena (multi-hop con decay logarítmico)
        # Dynamic Multiplicator: registrar como "cadena" con score de decay
        if not todos and len(query) >= 2:
            tokens_query = re.findall(r'\w{3,}', query.lower())
            if tokens_query:
                fts_tokens = [f'"{t}"' for t in tokens_query if len(t) >= 3]
                if fts_tokens:
                    fts_q = " OR ".join(fts_tokens)
                    # Filtro PALABRA_COMPLETA en semillas: evita que la cadena evoque desde
                    # falsos positivos de trigram (ej: "culo" → "artículos" → cadena contaminada)
                    pc_seed_clause = " AND (" + " OR ".join(
                        ["(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1)"] * len(fts_tokens)
                    ) + ")"
                    pc_seed_params = tuple(p for t in fts_tokens for p in (t.strip('"'), t.strip('"')))
                    try:
                        self.cursor.execute(
                            "SELECT l.concepto FROM largo_plazo_fts f "
                            "JOIN largo_plazo l ON l.rowid = f.rowid "
                            "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                            + pc_seed_clause + " LIMIT 5",
                            (fts_q,) + pc_seed_params
                        )
                        semillas = [row[0] for row in self.cursor.fetchall()]
                        if semillas:
                            evocados = self._evocacion_por_cadena(semillas)
                            for concepto_ev, decay_score, _ in evocados:
                                self.cursor.execute(
                                    "SELECT rowid, concepto, contenido, peso_sinaptico, "
                                    "estado, asociaciones FROM largo_plazo "
                                    "WHERE concepto = ? AND estado = 'activo'",
                                    (concepto_ev,)
                                )
                                row = self.cursor.fetchone()
                                if row and row[1] not in {r[1] for r in todos}:
                                    todos.append(row)
                                    # Solo registrar si no fue encontrado por capa anterior
                                    if row[1] not in origen_scores:
                                        origen_scores[row[1]] = ("cadena", decay_score)
                    except sqlite3.OperationalError:
                        pass

        if not todos:
            return [], 0

        # Calcular score hibrido para cada resultado
        # Dynamic Multiplicator: consultar origen_scores para activar fórmula de emergencia
        total = len(todos)
        resultados_con_hibrido = []
        for i, (rowid, concepto, contenido, peso, estado, asociaciones) in enumerate(todos):
            origen, score_capa = origen_scores.get(concepto, ("literal", 0.0))
            es_latente = origen in ("latente", "cadena", "expansion") and score_capa >= 0.15
            score_hibrido = self._calcular_score_hibrido(
                i, total, peso, asociaciones or "", pesos_tokens, contenido or "",
                es_latente=es_latente, score_latente=score_capa
            )
            resultados_con_hibrido.append(
                (concepto, contenido, peso, estado, score_hibrido, asociaciones or "")
            )

        # Reordenar por score hibrido descendente
        resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

        # Filtro final con PALABRA_PREFIJO: para queries de una palabra,
        # exigir que aparezca como prefijo de palabra en contenido (del lado de la DB).
        # Esto permite "react" -> "reactive" mientras sigue bloqueando falsos positivos de substring
        # ("culo" no es prefijo de "artículos").
        # Solo aplica a resultados de capas literales (AND/OR/NEAR/unicode/snap/substring).
        # Resultados de capas no literales (typo, expansión, latente, cadena) se preservan
        # para no romper tolerancia a typos ni búsqueda semántica/conceptual.
        query_words = re.findall(r'\w{3,}', query.lower())
        if len(query_words) == 1 and resultados_con_hibrido:
            token = query_words[0]
            literal_results = [
                r for r in resultados_con_hibrido
                if origen_scores.get(r[0], ("literal", 0.0))[0] == "literal"
            ]
            non_literal_results = [r for r in resultados_con_hibrido if r not in literal_results]
            if literal_results:
                conceptos_literal = [r[0] for r in literal_results if r[0] is not None]
                placeholders = ",".join("?" * len(conceptos_literal))
                self.cursor.execute(
                    f"SELECT concepto FROM largo_plazo WHERE "
                    f"(PALABRA_PREFIJO(?, concepto) = 1 OR PALABRA_PREFIJO(?, contenido) = 1 OR PALABRA_PREFIJO(?, COALESCE(sinonimos, '')) = 1) "
                    f"AND concepto IN ({placeholders})",
                    (token, token, token) + tuple(conceptos_literal)
                )
                validos = {row[0] for row in self.cursor.fetchall()}
                resultados_con_hibrido = [r for r in literal_results if r[0] in validos] + non_literal_results

        # Paginar (sin truncar aun; se necesita contenido completo para context window)
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

        # Context window: expandir cada resultado con vecinos por sinapsis
        if context_window and context_window > 0 and pagina_resultados:
            context_window = min(int(context_window), 3)
            expandidos = list(pagina_resultados)
            vistos = {r[0] for r in pagina_resultados}
            contextos = []
            filtro_estado = " AND l.estado = 'activo'" if profundidad != "profundo" else ""
            for r in pagina_resultados:
                concepto = r[0]
                score_principal = r[4]
                self.cursor.execute(f"""
                    SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
                    FROM sinapsis s
                    JOIN largo_plazo l ON l.concepto = s.destino
                    WHERE s.origen = ?{filtro_estado}
                    UNION
                    SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
                    FROM sinapsis s
                    JOIN largo_plazo l ON l.concepto = s.origen
                    WHERE s.destino = ?{filtro_estado}
                    ORDER BY s.peso DESC
                """, (concepto, concepto))
                agregados = 0
                for row in self.cursor.fetchall():
                    if agregados >= context_window:
                        break
                    if row[0] in vistos:
                        continue
                    score_contexto = round(min(1.0, score_principal * 0.6 + min(row[5], 1.0) * 0.2), 4)
                    contextos.append((row[0], row[1], row[2], row[3], score_contexto, row[4]))
                    vistos.add(row[0])
                    agregados += 1
            contextos.sort(key=lambda x: x[4], reverse=True)
            pagina_resultados = expandidos + contextos

        # Truncar preview a nivel de motor (ahorra RAM en CLI/MCP)
        if preview_chars and preview_chars > 0:
            pagina_resultados = [
                (r[0], (r[1] or "")[:preview_chars] + ("..." if len(r[1] or "") > preview_chars else ""), r[2], r[3], r[4], r[5])
                for r in pagina_resultados
            ]

        # Búsqueda iterativa: si no hay resultados y hay historial, generar variaciones
        if not pagina_resultados and historial_fallos is not None:
            variaciones = self._generar_variaciones(query, historial_fallos)
            for var in variaciones:
                resultados_var, total_var = self.buscar_por_frase(
                    var, profundidad, pagina, limite, categoria, preview_chars,
                    historial_fallos=None, context_window=context_window
                )
                if resultados_var:
                    return resultados_var, total_var

        return pagina_resultados, total

    def validar_rafaga(self, rafaga_palabras):
        """Valida palabras de ráfaga contra FTS5 y prioriza por frecuencia.
        
        Retorna lista de palabras (strings) ordenada por relevancia.
        Solo retorna palabras que existen en al menos un nodo de la DB.
        """
        if not rafaga_palabras:
            return []
        
        validadas = []
        for palabra in rafaga_palabras:
            if len(palabra) < 3:
                continue
            try:
                self.cursor.execute(
                    "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
                    (f'"{palabra}"',)
                )
                count = self.cursor.fetchone()[0]
                if count > 0:
                    validadas.append((palabra, count))
            except sqlite3.OperationalError:
                pass
        
        validadas.sort(key=lambda x: x[1], reverse=True)
        return [palabra for palabra, _ in validadas]

    def buscar_por_rafaga(self, query, rafaga_palabras, limite=None):
        """Búsqueda por ráfaga de reminiscencia: emula el proceso humano de recordar.
        
        Cuando la búsqueda normal falla, usa palabras asociadas al azar para encontrar
        nodos dormidos o aislados. Si encuentra un match, crea sinapsis automáticamente
        y despierta el nodo.
        
        Retorna (resultados, total) y lista de sinapsis creadas.
        """
        if limite is None:
            limite = LIMITE_RAFTAGA
        import re
        from itertools import combinations
        
        if not rafaga_palabras:
            return [], 0, []
        
        # Fase 0: Verificar errores previos de interpretación
        errores_previos = set()
        try:
            self.cursor.execute(
                "SELECT concepto, contenido FROM largo_plazo "
                "WHERE concepto LIKE 'error_interpretacion_%' AND estado = 'activo'"
            )
            for c, contenido in self.cursor.fetchall():
                for palabra in rafaga_palabras:
                    if palabra in (contenido or ""):
                        errores_previos.add(palabra)
        except Exception:
            pass
        
        rafaga_limpia = [p for p in rafaga_palabras if p not in errores_previos]
        
        if not rafaga_limpia:
            return [], 0, []
        
        todos = []
        palabra_ganadora = None
        seen_rowids = set()

        # Filtrar palabras válidas (>= 3 chars, sin comillas dobles)
        palabras_validas = [p for p in rafaga_limpia if len(p) >= 3 and '"' not in p]
        if not palabras_validas:
            return [], 0, []

        # Construir query FTS5 con OR — un solo MATCH para todas las palabras.
        # Esto elimina el cuello de botella de variables SQL y permite
        # cantidad ilimitada de términos en la ráfaga.
        fts_terms = " OR ".join(f'"{p}"' for p in palabras_validas)
        limite_batch = max(limite * len(palabras_validas), 50)

        # Buscar en activos — query único
        try:
            self.cursor.execute(
                "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                "l.estado, l.asociaciones "
                "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' LIMIT ?",
                (fts_terms, limite_batch)
            )
            resultados = self.cursor.fetchall()
            for r in resultados:
                if r[0] not in seen_rowids:
                    todos.append(r)
                    seen_rowids.add(r[0])
            if resultados and not palabra_ganadora:
                texto = f"{resultados[0][1] or ''} {resultados[0][2] or ''}".lower()
                for p in palabras_validas:
                    if p.lower() in texto:
                        palabra_ganadora = p
                        break
                if not palabra_ganadora:
                    palabra_ganadora = palabras_validas[0]
        except sqlite3.OperationalError:
            pass

        # SIEMPRE buscar en dormidos también (la ráfaga rescata del olvido)
        try:
            self.cursor.execute(
                "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                "l.estado, l.asociaciones "
                "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'dormido' LIMIT ?",
                (fts_terms, limite_batch)
            )
            resultados = self.cursor.fetchall()
            for r in resultados:
                if r[0] not in seen_rowids:
                    todos.append(r)
                    seen_rowids.add(r[0])
            if resultados and not palabra_ganadora:
                texto = f"{resultados[0][1] or ''} {resultados[0][2] or ''}".lower()
                for p in palabras_validas:
                    if p.lower() in texto:
                        palabra_ganadora = p
                        break
                if not palabra_ganadora:
                    palabra_ganadora = palabras_validas[0]
        except sqlite3.OperationalError:
            pass
        
        if not todos:
            return [], 0, []
        
        # Fase 2: Calcular score y ordenar
        total = len(todos)
        scored = []
        for i, (rowid, concepto, contenido, peso, estado, asoc) in enumerate(todos):
            score = self._calcular_score_hibrido(i, total, peso, asoc or "", None, contenido or "")
            scored.append((concepto, contenido, peso, estado, score, asoc or ""))
        
        scored.sort(key=lambda r: r[4], reverse=True)
        
        # Fase 3: Auto-sinapsis y despertar TODOS los nodos dormidos encontrados
        sinapsis_creadas = []
        query_tokens = set(re.findall(r'\w{4,}', query.lower()))
        
        # Primero: despertar TODOS los nodos dormidos (sin límite)
        for concepto, contenido, peso, estado, score, asoc in scored:
            if estado == 'dormido':
                self.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'activo', "
                    "peso_sinaptico = MIN(1.0, peso_sinaptico + 0.3), "
                    "ultimo_acceso = ? WHERE concepto = ?",
                    (time.time(), concepto)
                )
        
        # Segundo: crear sinapsis solo para los top resultados
        for concepto, contenido, peso, estado, score, asoc in scored[:limite]:
            
            # Crear sinapsis entre query y nodo encontrado
            if palabra_ganadora and query_tokens:
                for qt in query_tokens:
                    if qt != concepto and len(qt) >= 4:
                        # Verificar si ya existe la sinapsis
                        self.cursor.execute(
                            "SELECT peso FROM sinapsis WHERE "
                            "(origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                            (qt, concepto, concepto, qt)
                        )
                        existente = self.cursor.fetchone()
                        
                        if not existente:
                            self.cursor.execute(
                                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                                "VALUES (?, ?, 0.6, 'rafaga_rememb', ?)",
                                (qt, concepto, time.time())
                            )
                            sinapsis_creadas.append((qt, concepto, 0.6))
                        else:
                            # Reforzar sinapsis existente
                            nuevo_peso = min(0.95, existente[0] + 0.1)
                            self.cursor.execute(
                                "UPDATE sinapsis SET peso = ?, ultimo_uso = ? "
                                "WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                                (nuevo_peso, time.time(), qt, concepto, concepto, qt)
                            )
        
        self.conn.commit()
        
        # Fase 4: Métricas de ráfaga
        import sys
        if sinapsis_creadas:
            print(f"[Ráfaga] Palabra ganadora: '{palabra_ganadora}'", file=sys.stderr)
            print(f"[Ráfaga] Sinapsis creadas: {len(sinapsis_creadas)}", file=sys.stderr)
            for origen, destino, peso in sinapsis_creadas:
                print(f"  {origen} → {destino} (peso: {peso})", file=sys.stderr)
        
        return scored[:limite], len(scored), sinapsis_creadas

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

    def _ejecutar_eviccion(self, max_borrar=10):
        """Borra nodos dormidos abandonados para liberar espacio en la corteza.

        Solo se activa cuando la env var BIORAG_PODAR=true.
        Elimina hasta `max_borrar` nodos que cumplan:
          - estado = 'dormido'
          - peso_sinaptico <= 0.01
        Ordenados por ultimo_acceso ASC (los mas viejos primero).

        USO (solo via env var, no hay flag CLI):
          export BIORAG_PODAR=true
          python3 biorag.py sueno

        Sin BIORAG_PODAR=true esto nunca se ejecuta.
        Los datos borrados no se pueden recuperar — usar con criterio.
        """
        self.cursor.execute("""
            SELECT concepto FROM largo_plazo
            WHERE estado = 'dormido'
              AND peso_sinaptico <= 0.01
            ORDER BY ultimo_acceso ASC
            LIMIT ?
        """, (max_borrar,))
        candidatos = [row[0] for row in self.cursor.fetchall()]
        if not candidatos:
            return 0
        placeholders = ",".join("?" for _ in candidatos)
        self.cursor.execute(
            f"DELETE FROM largo_plazo WHERE concepto IN ({placeholders})", candidatos
        )
        # FTS cleanup via trigger largo_plazo_ad (no manual DELETE needed)
        self.conn.commit()
        return len(candidatos)

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
