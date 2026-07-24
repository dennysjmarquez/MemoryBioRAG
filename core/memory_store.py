import os
import sqlite3
import time
import re
import sys
from collections import deque

# Auto-cargar .env.local al importar (antes de leer cualquier variable de entorno)
from config import _load_env_local
_load_env_local()

# Pre-cargar WordNet al importar para evitar latencia de 3s en primera consulta semántica
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    obtener_lexnames_query("test")  # Trigger NLTK/WordNet lazy load
except Exception:
    pass  # WordNet opcional, ignorar si falla

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
        self.conn = sqlite3.connect(self.db_path, timeout=60)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.cursor = self.conn.cursor()
        # Función personalizada: word boundary check del lado de la DB
        def palabra_completa(token, texto):
            if not token or not texto:
                return 0
            token_norm = token.lower().replace('_', ' ').replace('-', ' ')
            texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
            return 1 if re.search(r'\b' + re.escape(token_norm) + r'\b', texto_norm) else 0
        self.conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)

        # Función personalizada: prefix word boundary check del lado de la DB
        def palabra_prefijo(token, texto):
            if not token or not texto:
                return 0
            token_norm = token.lower().replace('_', ' ').replace('-', ' ')
            texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
            return 1 if re.search(r'\b' + re.escape(token_norm), texto_norm) else 0
        self.conn.create_function("PALABRA_PREFIJO", 2, palabra_prefijo)
        self._cat_cache = {}
        # Evitar inicialización redundante de DDL si el esquema ya está creado
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='largo_plazo'")
        if not self.cursor.fetchone():
            self._crear_estructura_cerebral()
        else:
            # Schema exists but ensure new tables (like log_busquedas) are created
            self._crear_tablas_nuevas_si_faltan()
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Trazaabilidad: datos de la última búsqueda para mcp_server.py
        self.last_todos = []
        self.last_origen_scores = {}
        # Buffer circular de memoria de trabajo (v19.0 Context Window)
        self._context_window = deque(maxlen=10)
        self.dmn = None

    def notificar_actividad_usuario(self):
        """Notifica actividad del usuario al motor DMN si está activo."""
        if hasattr(self, 'dmn') and self.dmn is not None:
            self.dmn.notificar_actividad_usuario()

    def iniciar_dmn(self, idle_seconds=300):
        """Inicia el motor DMN de curiosidad espontánea."""
        from core.dmn_engine import DMNEngine
        if self.dmn is None:
            self.dmn = DMNEngine(self, idle_seconds=idle_seconds)
        self.dmn.start()
        return self.dmn

    def detener_dmn(self):
        """Detiene el motor DMN."""
        if hasattr(self, 'dmn') and self.dmn is not None:
            self.dmn.stop()

    def registrar_acceso_contexto(self, concepto: str):
        """Registra un concepto accedido recientemente en la memoria de trabajo."""
        if concepto and concepto not in self._context_window:
            self._context_window.append(concepto)

    def obtener_bonus_contexto(self, concepto: str) -> float:
        """Devuelve bonus de atención (+0.05) si el concepto o sus tokens coinciden con la memoria de trabajo."""
        if not self._context_window or not concepto:
            return 0.0
        if concepto in self._context_window:
            return 0.05
        # Coincidencia por tokens con items en la ventana
        tokens_concepto = set(concepto.lower().split())
        for ctx_item in self._context_window:
            if tokens_concepto.intersection(set(ctx_item.lower().split())):
                return 0.03
        return 0.0

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

    def _resolver_dimension_ids(self, tipo_nombre, valores_str):
        """Convierte nombres de dimensiones de un eje específico a lista de IDs.
        Retorna (ids_validos, nombres_invalidos)."""
        nombres = [v.strip().lower() for v in valores_str.split(",") if v.strip()]
        if not nombres:
            return [], []
        ph = ",".join("?" * len(nombres))
        self.cursor.execute(
            f"SELECT id, name FROM dimensiones_semanticas "
            f"WHERE tipo_id = (SELECT id FROM tipos_dimension WHERE nombre = ?) "
            f"AND name IN ({ph})",
            [tipo_nombre] + nombres,
        )
        rows = self.cursor.fetchall()
        encontrados = {row[1]: row[0] for row in rows}
        ids_validos = [encontrados[n] for n in nombres if n in encontrados]
        invalidos = [n for n in nombres if n not in encontrados]
        return ids_validos, invalidos

    def _obtener_arbol_dimensiones(self):
        """Retorna el catálogo completo de dimensiones formateado como string.
        Se usa para inyectar el catálogo vivo en la descripción de la tool aprender."""
        self.cursor.execute("""
            SELECT t.nombre, t.description, d.name, d.description
            FROM tipos_dimension t
            LEFT JOIN dimensiones_semanticas d ON d.tipo_id = t.id
            ORDER BY t.id, d.id
        """)
        filas = self.cursor.fetchall()
        arbol = {}
        for tipo_nombre, tipo_desc, dim_nombre, dim_desc in filas:
            if tipo_nombre not in arbol:
                arbol[tipo_nombre] = {"desc": tipo_desc, "dims": []}
            if dim_nombre:
                arbol[tipo_nombre]["dims"].append(f"{dim_nombre}: {dim_desc or '(sin descripción)'}")

        lineas = []
        for tipo_nombre, data in arbol.items():
            dims_str = "; ".join(data["dims"]) if data["dims"] else "(vacío)"
            lineas.append(f"  {tipo_nombre}: {dims_str}")
        return "\n".join(lineas)

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
                creado_en REAL DEFAULT 0,
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

            # ponytail: creado_en — registros antiguos heredan ultimo_acceso
            try:
                self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN creado_en REAL DEFAULT 0")
                self.cursor.execute(
                    "UPDATE largo_plazo SET creado_en = COALESCE(ultimo_acceso, 0) "
                    "WHERE creado_en = 0 OR creado_en IS NULL"
                )
                self.conn.commit()
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

        # 3b. Catálogo de tipos de dimensión (5 ejes)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tipos_dimension (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT ''
            )
        """)
        self.cursor.execute("""
            INSERT OR IGNORE INTO tipos_dimension (id, nombre, description) VALUES
                (1, 'emocion', '(El "Sentir"): La carga emocional o la reacción subjetiva ante la experiencia (ej. alegría, frustración, sorpresa)'),
                (2, 'entidad', '(El "Qué"): Cualquier tipo de ente, objeto o concepto que existe como unidad identificable — personas, agentes de IA, dispositivos, software, organizaciones o ideas abstractas (ej. usuario, servidor, empresa, fiesta, base de datos).'),
                (3, 'accion', '(El "Hacer" o "Estar"): Verbos, transiciones, procesos físicos y cognitivos (ej. disfrutar, copiar, recordar)'),
                (4, 'cualidad', '(El "Cómo"): Propiedades, descripciones, tamaños y valoraciones de las cosas (ej. bueno, comprimido, malformado)'),
                (5, 'coordenada', '(Espacio y Tiempo): La ubicación física, las relaciones de distancia y la cronología (ej. ayer, vida, dentro, después)'),
                (6, 'intencion', '(El "Por Qué"): Propósito o razón por la que se guardó el nodo. Captura la intención del autor al momento de guardar.'),
                (7, 'dominio', '(El "Dónde"): Área de vida o campo de aplicación del conocimiento. Captura dónde se aplica el contenido del nodo.')
        """)

        # 3d. Tabla de dimensiones semánticas (39 valores en 5 ejes)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dimensiones_semanticas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                tipo_id INTEGER NOT NULL,
                FOREIGN KEY (tipo_id) REFERENCES tipos_dimension(id)
            )
        """)
        self.cursor.execute("""
            INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
                -- EMOCION (tipo_id=1): 12 valores
                (1, 'afecto', 'Cariño, aprecio, gratitud, amor hacia personas o agentes', 1),
                (2, 'alegria', 'Satisfacción, logro, orgullo, entusiasmo', 1),
                (3, 'frustracion', 'Molestia, rabia, arrechera, enojo con algo o alguien', 1),
                (4, 'tristeza', 'Pérdida, decepción, nostalgia', 1),
                (5, 'preocupacion', 'Duda, alerta, ansiedad, incertidumbre', 1),
                (6, 'confusion', 'Desorientación, falta de claridad, no entender', 1),
                (7, 'sorpresa', 'Asombro, descubrimiento inesperado, impacto', 1),
                (87, 'miedo', 'Temor, susto, sensación de amenaza o peligro ante algo', 1),
                (88, 'alivio', 'Sensación de calma después de resolver algo o soltar tensión', 1),
                (89, 'apatia', 'Falta de interés, motivación o energía. Desgano, indiferencia', 1),
                (90, 'culpa', 'Sensación de haber hecho algo malo o de deber algo. Arrepentimiento', 1),
                (91, 'satisfaccion', 'Placer por completar algo, aprender algo nuevo o ver resultados positivos', 1),
                -- ENTIDAD (tipo_id=2): 11 valores
                (8, 'identidad_individual', 'El ser humano en su plano personal, biológico y psicológico', 2),
                (9, 'identidad_social_legal', 'Vinculación de personas a nivel de cultura, idioma, etnia y estatus legal', 2),
                (10, 'identidad_organizacional', 'Colectivos, instituciones o agrupaciones de personas estructuradas bajo un fin', 2),
                (11, 'identidad_digital', 'El rastro, cuentas de usuario, correos electrónicos y representaciones virtuales', 2),
                (12, 'identidad_artificial', 'Elementos lógicos y de software autónomos, agentes inteligentes de IA, algoritmos', 2),
                (13, 'identidad_fisica_hardware', 'Dispositivos computacionales físicos, servidores, infraestructura de red', 2),
                (14, 'identidad_natural', 'Organismos biológicos no humanos, animales, plantas, microorganismos', 2),
                (92, 'identidad_concepto', 'Ideas, teorías, principios, modelos mentales. Sin forma física', 2),
                (93, 'identidad_institucion', 'Organizaciones, empresas, universidades, gobiernos. Estructuras formales', 2),
                (94, 'identidad_evento', 'Reuniones, conferencias, lanzamientos. Occurrences puntuales con fecha', 2),
                (95, 'identidad_vinculo', 'Personas con las que tengo vínculo emocional: familia, amigos, pareja', 2),
                -- ACCION (tipo_id=3): 11 valores
                (15, 'accion_fisica', 'Movimientos y desplazamientos del cuerpo o de objetos en el espacio', 3),
                (16, 'accion_transformacion_material', 'Construir, destruir, modificar o alterar objetos físicos o materiales', 3),
                (17, 'accion_persistencia_computacion', 'Guardar, procesar, consultar o transmitir información digital', 3),
                (18, 'accion_rutina_automatica', 'Procesos cíclicos, repetitivos o automatizados sin intervención activa', 3),
                (19, 'accion_comunicacion', 'Enviar, informar, reportar o transferir información entre agentes', 3),
                (20, 'accion_interaccion_social', 'Acciones entre personas o agentes con propósito relacional', 3),
                (21, 'accion_cognitiva', 'Procesos de pensamiento, aprendizaje, decisión o inferencia', 3),
                (22, 'accion_estado_ser', 'Estados de existencia o permanencia sin acción activa', 3),
                (96, 'accion_evaluar', 'Analizar, juzgar, comparar o valorar algo. Proceso de decisión', 3),
                (97, 'accion_observar', 'Presenciar, notar o registrar algo sin actuar directamente', 3),
                (98, 'accion_fallar', 'Algo falló, se rompió o dejó de funcionar. Error, crash', 3),
                -- CUALIDAD (tipo_id=4): 11 valores
                (23, 'cualidad_dimension_fisica', 'Tamaño, forma, cantidad, peso, medida', 4),
                (24, 'cualidad_estado_condicion', 'Condición física o funcional de algo, íntegro o dañado', 4),
                (25, 'cualidad_valoracion', 'Juicio de calidad o mérito, bueno/malo, correcto/incorrecto', 4),
                (74, 'cualidad_sensorial', 'Percepciones captadas por los sentidos: color, textura, sonido, sabor', 4),
                (75, 'cualidad_material_composicion', 'De qué está hecho o compuesto algo: metálico, digital, orgánico', 4),
                (76, 'cualidad_temporal_duracion', 'Propiedades de duración o permanencia de algo', 4),
                (77, 'cualidad_relacional_comparativa', 'Propiedades que solo existen en comparación con otra cosa', 4),
                (78, 'cualidad_abstracta_conceptual', 'Propiedades no físicas de ideas o sistemas: complejo, simple, lógico', 4),
                (99, 'cualidad_economica', 'Relacionado con dinero, costos, presupuesto, inversión o finanzas', 4),
                (100, 'cualidad_urgente', 'Requiere acción inmediata. Tiene fecha límite o consecuencias', 4),
                (101, 'cualidad_autentica', 'Vivencia real, genuina. No teórico ni hipotético. Experiencia personal', 4),
                -- COORDENADA (tipo_id=5): 10 valores
                (79, 'coordenada_cronologia_absoluta', 'Fechas o momentos específicos y objetivos', 5),
                (80, 'coordenada_anclaje_deictico', 'Referencias temporales relativas al momento del habla', 5),
                (81, 'coordenada_secuencia_relativa', 'Orden entre eventos, sin fecha fija', 5),
                (82, 'coordenada_ciclo_periodico', 'Repetición regular en el tiempo: diario, semanal, anual', 5),
                (83, 'coordenada_inclusion_topologica', 'Contención o pertenencia a un espacio', 5),
                (84, 'coordenada_distancia_proximal', 'Cercanía o lejanía entre puntos', 5),
                (85, 'coordenada_vector_direccional', 'Dirección u orientación: arriba, abajo, norte', 5),
                (86, 'coordenada_trayectoria_limite', 'Movimiento entre puntos o fronteras: desde, hacia, a través de', 5),
                (102, 'coordenada_etapa', 'Corresponde a una etapa de vida: infancia, juventud, adultez, vejez', 5),
                (103, 'coordenada_hito', 'Marca un momento significativo: nacimiento, muerte, cambio de trabajo', 5),
                -- INTENCION (tipo_id=6): 8 valores
                (104, 'intencion_aprender', 'Guardo para aprender o recordar algo que estoy estudiando', 6),
                (105, 'intencion_decidir', 'Guardo para tomar una decisión o tener contexto para decidir', 6),
                (106, 'intencion_reflexionar', 'Guardo para pensar sobre algo, meditar o sacar conclusiones', 6),
                (107, 'intencion_resolver', 'Guardo porque algo falló o hay un obstáculo que superar', 6),
                (108, 'intencion_solucionar', 'Guardo la solución a un problema que ya resolví. Referencia futura', 6),
                (109, 'intencion_documentar', 'Guardo para tener un registro formal o referencia duradera', 6),
                (110, 'intencion_desahogar', 'Guardo para expresar lo que siento, sin buscar solución', 6),
                (111, 'intencion_registrar', 'Guardo para marcar que algo pasó, sin juicio ni propósito específico', 6),
                -- DOMINIO (tipo_id=7): 10 valores
                (112, 'dominio_tecnico', 'Programación, infraestructura, herramientas de desarrollo, software', 7),
                (113, 'dominio_personal', 'Vida privada, familia, relaciones personales, hogar', 7),
                (114, 'dominio_profesional', 'Trabajo, carrera, crecimiento profesional, oficina', 7),
                (115, 'dominio_academico', 'Estudios, cursos, investigación, aprendizaje formal, universidad', 7),
                (116, 'dominio_salud', 'Salud física, mental, bienestar, cuidado del cuerpo, medicina', 7),
                (117, 'dominio_finanzas', 'Dinero, inversiones, presupuesto, deudas, planificación financiera', 7),
                (118, 'dominio_ambiental', 'Naturaleza, clima, medio ambiente, ecología, sustentabilidad', 7),
                (119, 'dominio_social', 'Relaciones sociales, comunidad, política, sociedad, cultura', 7),
                (120, 'dominio_creativo', 'Arte, música, escritura, diseño, expresión creativa', 7),
                (121, 'dominio_espiritual', 'Valores, propósito, sentido de vida, creencias, filosofía', 7)
        """)

        # 3e. Tablas puente para dimensiones en corto y largo plazo
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS corto_plazo_dimensiones (
                concepto     TEXT    NOT NULL,
                dimension_id INTEGER NOT NULL,
                PRIMARY KEY (concepto, dimension_id),
                FOREIGN KEY (concepto)     REFERENCES corto_plazo(concepto) ON DELETE CASCADE,
                FOREIGN KEY (dimension_id) REFERENCES dimensiones_semanticas(id)
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_cpd_dimension ON corto_plazo_dimensiones(dimension_id)"
        )
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS largo_plazo_dimensiones (
                concepto     TEXT    NOT NULL,
                dimension_id INTEGER NOT NULL,
                PRIMARY KEY (concepto, dimension_id),
                FOREIGN KEY (concepto)     REFERENCES largo_plazo(concepto) ON DELETE CASCADE,
                FOREIGN KEY (dimension_id) REFERENCES dimensiones_semanticas(id)
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_lpd_dimension ON largo_plazo_dimensiones(dimension_id)"
        )

        # 3f. Tablas de clasificación simbólica WordNet (lexnames)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS grupos_semanticos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                fuente TEXT DEFAULT 'wordnet',
                descripcion TEXT DEFAULT ''
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodo_grupos_semanticos (
                concepto TEXT NOT NULL,
                palabra TEXT NOT NULL,
                grupo_id INTEGER NOT NULL,
                PRIMARY KEY (concepto, palabra, grupo_id),
                FOREIGN KEY (grupo_id) REFERENCES grupos_semanticos(id),
                FOREIGN KEY (concepto) REFERENCES largo_plazo(concepto) ON DELETE CASCADE
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ngs_grupo ON nodo_grupos_semanticos(grupo_id)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ngs_concepto ON nodo_grupos_semanticos(concepto)"
        )

        # 3g. Tabla de sinapsis latentes (caché de inferencia transitiva v19.0 SLS)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sinapsis_latentes (
                origen TEXT NOT NULL,
                destino TEXT NOT NULL,
                peso_atenuado REAL NOT NULL,
                saltos INTEGER NOT NULL,
                calculado_en REAL NOT NULL,
                pmi_score REAL DEFAULT 0.0,
                tiene_dim_comun INTEGER DEFAULT 0,
                PRIMARY KEY (origen, destino)
            )
        """)
        # Migración v19.0: añadir columnas si no existen
        sl_info = [r[1] for r in self.conn.execute("PRAGMA table_info(sinapsis_latentes)").fetchall()]
        if 'pmi_score' not in sl_info:
            self.cursor.execute("ALTER TABLE sinapsis_latentes ADD COLUMN pmi_score REAL DEFAULT 0.0")
        if 'tiene_dim_comun' not in sl_info:
            self.cursor.execute("ALTER TABLE sinapsis_latentes ADD COLUMN tiene_dim_comun INTEGER DEFAULT 0")

        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sl_origen ON sinapsis_latentes(origen)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sl_destino ON sinapsis_latentes(destino)"
        )

        # 3h. Tabla de predicados SRL (Etiquetado de Roles Semánticos v16.0)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS predicados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concepto TEXT NOT NULL,
                sujeto TEXT,
                accion TEXT,
                objeto TEXT,
                contexto TEXT,
                creado_en REAL,
                FOREIGN KEY (concepto) REFERENCES largo_plazo(concepto) ON DELETE CASCADE
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pred_concepto ON predicados(concepto)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pred_sujeto ON predicados(sujeto)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pred_accion ON predicados(accion)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pred_objeto ON predicados(objeto)"
        )

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS corto_plazo_predicados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concepto TEXT NOT NULL,
                sujeto TEXT,
                accion TEXT,
                objeto TEXT,
                contexto TEXT,
                creado_en REAL,
                FOREIGN KEY (concepto) REFERENCES corto_plazo(concepto) ON DELETE CASCADE
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_cp_pred_concepto ON corto_plazo_predicados(concepto)"
        )

        self.conn.commit()

        # 4. Migración FK: eliminar categoria_id si existe, agregar FK en categoria→categories.name
        cur = self.cursor

        # --- dimensiones_semanticas (v16.0 auto-clustering) ---
        cur.execute("PRAGMA table_info(dimensiones_semanticas)")
        ds_cols = [row[1] for row in cur.fetchall()]
        if 'auto_generada' not in ds_cols:
            cur.execute("ALTER TABLE dimensiones_semanticas ADD COLUMN auto_generada INTEGER DEFAULT 0")
        if 'confianza' not in ds_cols:
            cur.execute("ALTER TABLE dimensiones_semanticas ADD COLUMN confianza REAL DEFAULT 1.0")
        if 'generado_en' not in ds_cols:
            cur.execute("ALTER TABLE dimensiones_semanticas ADD COLUMN generado_en REAL")

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

        if 'valencia_somatica' not in cp_cols:
            cur.execute("ALTER TABLE corto_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")

        # --- largo_plazo ---
        cur.execute("PRAGMA table_info(largo_plazo)")
        lp_cols = {row[1]: row[2] for row in cur.fetchall()}
        if 'valencia_somatica' not in lp_cols:
            cur.execute("ALTER TABLE largo_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")
        if 'exitos_dopamina' not in lp_cols:
            cur.execute("ALTER TABLE largo_plazo ADD COLUMN exitos_dopamina INTEGER DEFAULT 0")
        if 'fallos_dopamina' not in lp_cols:
            cur.execute("ALTER TABLE largo_plazo ADD COLUMN fallos_dopamina INTEGER DEFAULT 0")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lp_valencia ON largo_plazo (valencia_somatica)")
        self.conn.commit()

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
                    creado_en REAL DEFAULT 0,
                    FOREIGN KEY (categoria) REFERENCES categories(id)
                )
            """)
            cur.execute(f"""
                INSERT INTO largo_plazo (id, concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos, creado_en)
                SELECT id, concepto,
                       COALESCE((SELECT id FROM categories WHERE name = largo_plazo_old.categoria), 1),
                       contenido,
                       COALESCE(peso_sinaptico, 1.0), COALESCE(estado, 'activo'),
                       COALESCE(asociaciones, ''), COALESCE(ultimo_acceso, 0),
                       COALESCE(sinonimos, ''),
                       COALESCE(creado_en, ultimo_acceso, 0)
                FROM largo_plazo_old
            """)
            cur.execute("DROP TABLE largo_plazo_old")

        # Crear un índice explícito para acelerar ordenaciones por peso y último acceso (Inhibición y Poda)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_peso_acceso ON largo_plazo (peso_sinaptico, ultimo_acceso)")
        # v13: índices para queries rápidos por estado y fecha
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_estado ON largo_plazo (estado)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_creado_en ON largo_plazo (creado_en)")
        # --- Migración v20.0 (Valencia Somática y Dopamina RPE) ---
        self.cursor.execute("PRAGMA table_info(largo_plazo)")
        lp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
        if 'valencia_somatica' not in lp_cols_v20:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")
        if 'exitos_dopamina' not in lp_cols_v20:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN exitos_dopamina INTEGER DEFAULT 0")
        if 'fallos_dopamina' not in lp_cols_v20:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN fallos_dopamina INTEGER DEFAULT 0")

        self.cursor.execute("PRAGMA table_info(corto_plazo)")
        cp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
        if 'valencia_somatica' not in cp_cols_v20:
            self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")

        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_valencia ON largo_plazo (valencia_somatica)")

        self._crear_tabla_comunicaciones()
        self._crear_tabla_fts()
        self._crear_tabla_metricas()

        # Vistas para visualización con nombre de categoría (drop & recreate para reflejar cambios de esquema)
        self.cursor.execute("DROP VIEW IF EXISTS vista_largo_plazo")
        self.cursor.execute("""
            CREATE VIEW vista_largo_plazo AS
            SELECT l.*, c.name AS categoria_name
            FROM largo_plazo l
            LEFT JOIN categories c ON l.categoria = c.id
        """)
        self.cursor.execute("DROP VIEW IF EXISTS vista_corto_plazo")
        self.cursor.execute("""
            CREATE VIEW vista_corto_plazo AS
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
        # 8. Tabla de log de búsquedas (Phase 2D Telemetría)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_busquedas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                resultados_count INTEGER NOT NULL,
                top_score REAL,
                creado_en REAL NOT NULL,
                util INTEGER DEFAULT NULL,
                params_json TEXT
            )
        """)
        self.conn.commit()

    def _crear_tablas_nuevas_si_faltan(self):
        """Crea tablas nuevas (Phase 2D) si no existen en esquemas existentes."""
        # --- Migración v20.0 (Valencia Somática y Dopamina RPE) ---
        self.cursor.execute("PRAGMA table_info(largo_plazo)")
        lp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
        if 'valencia_somatica' not in lp_cols_v20:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")
        if 'exitos_dopamina' not in lp_cols_v20:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN exitos_dopamina INTEGER DEFAULT 0")
        if 'fallos_dopamina' not in lp_cols_v20:
            self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN fallos_dopamina INTEGER DEFAULT 0")

        self.cursor.execute("PRAGMA table_info(corto_plazo)")
        cp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
        if 'valencia_somatica' not in cp_cols_v20:
            self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")

        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_valencia ON largo_plazo (valencia_somatica)")
        self.conn.commit()

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_busquedas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                resultados_count INTEGER NOT NULL,
                top_score REAL,
                creado_en REAL NOT NULL,
                util INTEGER DEFAULT NULL,
                params_json TEXT
            )
        """)
        # Migración: agregar params_json si falta
        try:
            self.cursor.execute("ALTER TABLE log_busquedas ADD COLUMN params_json TEXT")
        except:
            pass  # ya existe
        # Tabla puente: historial forense de acciones por ciclo de consolidación
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_cognitivas_nodos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metrica_id INTEGER NOT NULL,
                largo_plazo_id INTEGER,
                accion TEXT NOT NULL CHECK(accion IN ('nuevo', 'actualizado', 'dormido', 'eliminado')),
                contenido_preview TEXT,
                peso_anterior REAL,
                peso_nuevo REAL,
                razon TEXT,
                contexto TEXT,
                anomalo INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (metrica_id) REFERENCES metricas_cognitivas(id) ON DELETE CASCADE,
                FOREIGN KEY (largo_plazo_id) REFERENCES largo_plazo(id) ON DELETE CASCADE
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_metrica ON metricas_cognitivas_nodos(metrica_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_largo_plazo_id ON metricas_cognitivas_nodos(largo_plazo_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_accion ON metricas_cognitivas_nodos(accion)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_anomalo ON metricas_cognitivas_nodos(anomalo)")

        # Migración v19.0 SLS para sinapsis_latentes
        sl_info = [r[1] for r in self.conn.execute("PRAGMA table_info(sinapsis_latentes)").fetchall()]
        if 'pmi_score' not in sl_info:
            self.cursor.execute("ALTER TABLE sinapsis_latentes ADD COLUMN pmi_score REAL DEFAULT 0.0")
        if 'tiene_dim_comun' not in sl_info:
            self.cursor.execute("ALTER TABLE sinapsis_latentes ADD COLUMN tiene_dim_comun INTEGER DEFAULT 0")

        # Tabla nodos_sdm para Sparse Distributed Memory (v19.0)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodos_sdm (
                concepto TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                actualizado_en REAL NOT NULL
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

    def percibir_corto_plazo(self, concepto, contenido, sinonimos="", categoria="General", dimensiones=None, predicados=None, valencia_somatica=0.0):
        """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo).
        Si el concepto ya existe en corto plazo, concatena contenido y mergea sinónimos.
        dimensiones: dict {tipo_nombre: [valores]} para indexación de 5 ejes.
        predicados: list[dict] con {sujeto, accion, objeto, contexto} para SRL v16.0.
        valencia_somatica: float [0.0, 1.0] para marcadores somáticos (v20.0)."""
        key = concepto.lower().strip()
        cat_id = self._resolver_categoria_id(categoria)
        
        # Auto-asignar valencia somática máxima si la categoría es Principle o Protocol
        if isinstance(categoria, str) and categoria.lower() in ('principle', 'protocol'):
            valencia_somatica = 1.0

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
            INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria, valencia_somatica)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (key, contenido_final, time.time(), sinonimos_final, cat_id, float(valencia_somatica or 0.0)))

        # SRL v16.0: Almacenar predicados en corto_plazo_predicados (se propagan al consolidar)
        if predicados:
            ahora = time.time()
            for pred in predicados:
                if not isinstance(pred, dict):
                    continue
                self.cursor.execute(
                    "INSERT INTO corto_plazo_predicados (concepto, sujeto, accion, objeto, contexto, creado_en) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (key, pred.get('sujeto'), pred.get('accion'),
                     pred.get('objeto'), pred.get('contexto'), ahora)
                )

        # Insertar dimensiones en tabla puente
        # Si dimensiones ya es dict de IDs (de _resolver_dimensiones), usar directamente
        # Si es dict de nombres (legacy), resolver IDs
        dim_dict = dimensiones or {}
        for tipo_nombre, valores in dim_dict.items():
            if not valores:
                continue
            # Si los valores son ints, ya son IDs resueltos
            if isinstance(valores[0], int):
                ids_validos = valores
            else:
                ids_validos, _ = self._resolver_dimension_ids(
                    tipo_nombre, ",".join(valores) if isinstance(valores, list) else valores
                )
            for eid in ids_validos:
                self.cursor.execute(
                    "INSERT OR IGNORE INTO corto_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                    (key, eid)
                )

        self.conn.commit()

        # ponytail: removed semantic table expansion — agent passes synonyms directly

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
            "(concepto, categoria, contenido, peso_sinaptico, estado, sinonimos, creado_en) "
            "VALUES (?, ?, ?, 1.0, 'activo', ?, ?)",
            (key, cat_id, contenido, sinonimos or "", time.time()),
        )
        # ponytail: ultimo_acceso se actualiza en cada acceso, creado_en es el timestamp de consolidación
        # Propagar dimensiones de corto → largo plazo
        self.cursor.execute("""
            INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id)
            SELECT concepto, dimension_id FROM corto_plazo_dimensiones WHERE concepto = ?
        """, (key,))
        self.cursor.execute(
            "DELETE FROM corto_plazo_dimensiones WHERE concepto = ?", (key,)
        )
        self.cursor.execute("DELETE FROM corto_plazo WHERE concepto = ?", (key,))
        self.conn.commit()
        from core.sinapsis import auto_vincular
        auto_vincular(self, key, contenido)
        # Clasificación simbólica: WordNet lexnames
        self._clasificar_nodo_wordnet(key, contenido, sinonimos or "")
        # SDM v19.0: Indexar vector binario para recuperación por similitud estructural
        try:
            from core.sdm import indexar_nodo_sdm
            indexar_nodo_sdm(self, key)
        except Exception:
            pass
        # SRL v16.0: Propagar predicados de corto → largo plazo
        self.cursor.execute("""
            INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en)
            SELECT concepto, sujeto, accion, objeto, contexto, creado_en FROM corto_plazo_predicados WHERE concepto = ?
        """, (key,))
        self.cursor.execute(
            "DELETE FROM corto_plazo_predicados WHERE concepto = ?", (key,)
        )
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
            for item in recuerdos_sesion:
                c1, contenido1 = item[0], item[1]
                if c1 not in concepto_tokens:
                    concepto_tokens[c1] = set(re.findall(r'\w{4,}', (contenido1 or "").lower()))
            
            # Para cada par de conceptos consolidados juntos
            for item1, item2 in combinations(recuerdos_sesion, 2):
                c1, cont1 = item1[0], item1[1]
                c2, cont2 = item2[0], item2[1]
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

    def _clasificar_nodo_wordnet(self, concepto, contenido, sinonimos=""):
        """Clasifica las palabras del nodo por grupo semántico WordNet.
        Almacena en tabla puente nodo_grupos_semanticos."""
        try:
            from core.clasificador_wordnet import clasificar_texto
        except ImportError:
            return  # WordNet no disponible — fallback silencioso

        texto = f"{concepto} {contenido} {sinonimos}".replace("_", " ")
        clasificado = clasificar_texto(texto)

        for palabra, lexnames in clasificado.items():
            for ln in lexnames:
                # Obtener o crear grupo
                self.cursor.execute(
                    "SELECT id FROM grupos_semanticos WHERE nombre = ?", (ln,)
                )
                row = self.cursor.fetchone()
                if row:
                    grupo_id = row[0]
                else:
                    self.cursor.execute(
                        "INSERT INTO grupos_semanticos (nombre) VALUES (?)", (ln,)
                    )
                    grupo_id = self.cursor.lastrowid

                self.cursor.execute(
                    "INSERT OR IGNORE INTO nodo_grupos_semanticos "
                    "(concepto, palabra, grupo_id) VALUES (?, ?, ?)",
                    (concepto, palabra, grupo_id)
                )
        self.conn.commit()

    def _crear_tabla_historial_si_falta(self):
        """Crea la tabla de historial forense si no existe (para DBs nuevas o tests)."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_cognitivas_nodos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metrica_id INTEGER NOT NULL,
                largo_plazo_id INTEGER,
                accion TEXT NOT NULL CHECK(accion IN ('nuevo', 'actualizado', 'dormido', 'eliminado')),
                contenido_preview TEXT,
                peso_anterior REAL,
                peso_nuevo REAL,
                razon TEXT,
                contexto TEXT,
                anomalo INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (metrica_id) REFERENCES metricas_cognitivas(id) ON DELETE CASCADE,
                FOREIGN KEY (largo_plazo_id) REFERENCES largo_plazo(id) ON DELETE CASCADE
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_metrica ON metricas_cognitivas_nodos(metrica_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_largo_plazo_id ON metricas_cognitivas_nodos(largo_plazo_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_accion ON metricas_cognitivas_nodos(accion)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_nodos_anomalo ON metricas_cognitivas_nodos(anomalo)")

    def ciclo_sueno_consolidacion(self):
        """
        Consolida las experiencias de Corto Plazo a Largo Plazo (Corteza Permanente).
        Aplica LTD (Depresión a Largo Plazo) mediante decaimiento pasivo (-0.05) a los nodos no usados.
        Duerme los recuerdos cuyo peso sea <= 0.05.
        Aplica Inhibición Lateral Activa de forma 100% automática según la carga cortical (n_activos * 1.0).
        """
        print("\n--- Iniciando Ciclo de Consolidación (Sueño) ---")
        
        # Asegurar que existe la tabla de historial forense
        self._crear_tabla_historial_si_falta()
        
        # ══════════════════════════════════════════════════════════════
        # SNAPSHOT INICIAL: capturar estado ANTES de cualquier cambio
        # ══════════════════════════════════════════════════════════════
        self.cursor.execute("SELECT concepto, peso_sinaptico, estado FROM largo_plazo")
        snapshot_inicial = {row[0]: {'peso': row[1], 'estado': row[2]} for row in self.cursor.fetchall()}
        
        # Métricas del ciclo
        nodos_dormidos_antes = sum(1 for n in snapshot_inicial.values() if n['estado'] == 'dormido')
        sinapsis_antes = self.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
        n_activos = sum(1 for n in snapshot_inicial.values() if n['estado'] == 'activo') or 0

        # Lista para tracking de acciones del ciclo
        acciones_ciclo = []

        # 1. Transferencia y Fusión de Corto a Largo Plazo
        self.cursor.execute("SELECT concepto, contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0) FROM corto_plazo")
        recuerdos_sesion = self.cursor.fetchall()
        
        for concepto, contenido, sinonimos, cat_id, val_somatica in recuerdos_sesion:
            existente = snapshot_inicial.get(concepto)
            
            # Si categoria es Principle o Protocol, forzar valencia_somatica = 1.0
            cat_name = ""
            if cat_id:
                res_cat = self.cursor.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
                if res_cat:
                    cat_name = res_cat[0]
            if cat_name in ('Principle', 'Protocol'):
                val_somatica = 1.0

            if existente:
                # Fusión de información por adición semántica y subida de peso (LTP de consolidación)
                peso_anterior = existente['peso']
                nuevo_peso = min(1.0, existente['peso'] + 0.20)
                
                self.cursor.execute("SELECT contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0) FROM largo_plazo WHERE concepto = ?", (concepto,))
                datos_actuales = self.cursor.fetchone()
                nuevo_contenido = datos_actuales[0] + f" | Actualización: {contenido}"
                sinonimos_exist = [s.strip() for s in (datos_actuales[1] or "").split(",") if s.strip()]
                sinonimos_nuevos = [s.strip() for s in (sinonimos or "").split(",") if s.strip() and s.strip() not in sinonimos_exist]
                sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
                cat_id = datos_actuales[2] or cat_id
                val_final = max(datos_actuales[3], val_somatica)
                
                self.cursor.execute("""
                    UPDATE largo_plazo 
                    SET contenido = ?, peso_sinaptico = ?, estado = 'activo', ultimo_acceso = ?, sinonimos = ?, categoria = ?, valencia_somatica = ?
                    WHERE concepto = ?
                """, (nuevo_contenido, nuevo_peso, time.time(), sinonimos_final, cat_id, val_final, concepto))
                
                acciones_ciclo.append({
                    'concepto': concepto, 'accion': 'actualizado',
                    'contenido_preview': (contenido or '')[:100],
                    'peso_anterior': peso_anterior, 'peso_nuevo': nuevo_peso,
                    'razon': f'Fusion: existia con peso {peso_anterior:.2f}, se actualizo contenido y peso +0.20',
                    'contexto': f'peso_antes={peso_anterior:.2f}, peso_despues={nuevo_peso:.2f}, estado=activo',
                    'anomalo': 0
                })
            else:
                # Creación de un nuevo nodo en el grafo con peso inicial máximo
                ahora = time.time()
                self.cursor.execute("""
                    INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos, creado_en, valencia_somatica)
                    VALUES (?, ?, ?, 1.0, 'activo', '', ?, ?, ?, ?)
                """, (concepto, cat_id or 1, contenido, ahora, sinonimos or "", ahora, val_somatica))
                
                acciones_ciclo.append({
                    'concepto': concepto, 'accion': 'nuevo',
                    'contenido_preview': (contenido or '')[:100],
                    'peso_anterior': 0.0, 'peso_nuevo': 1.0,
                    'razon': 'Nodo nuevo: no existia en largo_plazo, creado desde corto_plazo',
                    'contexto': f'categoria={cat_id or 1}, peso_inicial=1.0, estado=activo',
                    'anomalo': 0
                })

            # Propagar dimensiones de corto → largo plazo
            self.cursor.execute("""
                INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id)
                SELECT concepto, dimension_id FROM corto_plazo_dimensiones WHERE concepto = ?
            """, (concepto,))
            self.cursor.execute(
                "DELETE FROM corto_plazo_dimensiones WHERE concepto = ?", (concepto,)
            )
            
            # SRL v16.0: Propagar predicados de corto → largo plazo
            self.cursor.execute("""
                INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en)
                SELECT concepto, sujeto, accion, objeto, contexto, creado_en FROM corto_plazo_predicados WHERE concepto = ?
            """, (concepto,))
            self.cursor.execute(
                "DELETE FROM corto_plazo_predicados WHERE concepto = ?", (concepto,)
            )

        # Auto-vincular cada concepto consolidado (aristas por solapamiento de tokens)
        from core.sinapsis import auto_vincular
        for concepto, contenido, _, _, _ in recuerdos_sesion:
            auto_vincular(self, concepto, contenido)

        # Clasificación simbólica: WordNet lexnames para cada nodo consolidado
        for concepto, contenido, sinonimos, _, _ in recuerdos_sesion:
            self._clasificar_nodo_wordnet(concepto, contenido, sinonimos or "")

        # Fase 2: Auto-generar sinapsis por co-ocurrencia
        # Si dos conceptos aparecieron en la misma sesión (corto_plazo), co-ocurren.
        # También analiza comunicaciones para detectar co-ocurrencia en mensajes.
        self._auto_generar_co_ocurrencia(recuerdos_sesion)

        # Inferencia transitiva: recalcular sinapsis latentes (v16.0)
        try:
            from core.inferencia_transitiva import calcular_sinapsis_latentes
            n_latentes = calcular_sinapsis_latentes(self)
            if n_latentes:
                print(f"[Inferencia Transitiva] {n_latentes} sinapsis latentes calculadas.")
        except Exception as e:
            print(f"[Inferencia Transitiva] Fallback silencioso: {e}")

        # 2. Decaimiento Pasivo (LTD): Reducir peso según decay_rate de la categoría
        # Nodos protegidos (valencia_somatica >= 0.8 o categoria Principle/Protocol) son inmunes a LTD pasivo
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = ROUND(MAX(0.0, peso_sinaptico - 0.05 * (
                SELECT COALESCE(c.decay_rate, 1.0) FROM categories c WHERE c.id = largo_plazo.categoria
            )), 2)
            WHERE estado = 'activo' 
              AND concepto NOT IN (SELECT concepto FROM corto_plazo)
              AND COALESCE(valencia_somatica, 0.0) < 0.80
              AND categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol'))
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

        # 3. Poda selectiva por umbral de fuerza (Dormir recuerdos <= 0.05)
        # Snapshot ANTES de dormir (para detectar quiénes se duermen)
        self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'activo'")
        activos_antes_dormir = set(row[0] for row in self.cursor.fetchall())
        
        self.cursor.execute("""
            UPDATE largo_plazo 
            SET estado = 'dormido' 
            WHERE peso_sinaptico <= 0.05 
              AND estado = 'activo'
              AND COALESCE(valencia_somatica, 0.0) < 0.80
              AND categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol'))
        """)
        
        # Detectar quiénes se durmieron POR LTD (solo los que estaban activos y ahora son dormidos)
        self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'dormido'")
        dormidos_after_ltd = set(row[0] for row in self.cursor.fetchall())
        nodos_dormidos_ltd = activos_antes_dormir & dormidos_after_ltd  # intersección: estaban activos Y ahora son dormidos

        # 4. Inhibición Lateral Activa (Control de Saturación de Energía)
        self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
        n_activos = self.cursor.fetchone()[0] or 0
        limite_energia = max(10.0, n_activos * 0.8)

        self.cursor.execute("SELECT SUM(peso_sinaptico) FROM largo_plazo WHERE estado = 'activo'")
        energia_total = self.cursor.fetchone()[0] or 0.0

        nodos_inhibicion_lateral = []
        nodos_a_dormir = []
        if energia_total > limite_energia:
            exceso = energia_total - limite_energia
            print(f"[Inhibición Lateral] Alerta: Energía sináptica activa ({energia_total:.2f}) excede el límite ({limite_energia}). Aplicando inhibición...")
            # Obtener los nodos activos ordenados de menor peso y más antiguos (excluyendo inmunes)
            self.cursor.execute("""
                SELECT concepto, peso_sinaptico FROM largo_plazo 
                WHERE estado = 'activo' 
                  AND COALESCE(valencia_somatica, 0.0) < 0.80
                  AND categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol'))
                ORDER BY peso_sinaptico ASC, ultimo_acceso ASC
            """)
            nodos_activos = self.cursor.fetchall()
            
            for concepto, peso in nodos_activos:
                if exceso <= 0:
                    break
                nodos_a_dormir.append((concepto, peso))
                exceso -= peso

            if nodos_a_dormir:
                nodos_inhibicion_lateral = [n[0] for n in nodos_a_dormir]
                for i in range(0, len(nodos_a_dormir), 900):
                    lote = [n[0] for n in nodos_a_dormir[i:i+900]]
                    placeholders = ",".join("?" for _ in lote)
                    self.cursor.execute(f"UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = MAX(0.05, ROUND(peso_sinaptico * 0.9, 2)) WHERE concepto IN ({placeholders})", lote)
                
                if len(nodos_a_dormir) <= 10:
                    for concepto, peso in nodos_a_dormir:
                        print(f"[Inhibición Lateral] Recuerdo '{concepto}' puesto a dormir forzadamente para balancear la carga cortical.")
                else:
                    print(f"[Inhibición Lateral] Puestos a dormir {len(nodos_a_dormir)} recuerdos débiles para liberar energía (Consolidación en lote exitosa).")

        # 4b. Escalado Sináptico Homeostático (Synaptic Scaling - Turrigiano 2008)
        # Si el peso medio activo excede 0.70, aplica normalización multiplicativa (x0.98) a nodos no inmunes
        self.cursor.execute("SELECT AVG(peso_sinaptico) FROM largo_plazo WHERE estado = 'activo'")
        peso_medio_activo = self.cursor.fetchone()[0] or 0.0
        if peso_medio_activo > 0.70:
            self.cursor.execute("""
                UPDATE largo_plazo
                SET peso_sinaptico = ROUND(peso_sinaptico * 0.98, 2)
                WHERE estado = 'activo'
                  AND COALESCE(valencia_somatica, 0.0) < 0.80
                  AND categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol'))
            """)
        
        # Registrar dormidos (LTD + inhibición lateral)
        # Obtener pesos REALES de nodos dormidos desde la DB (snapshot_inicial puede estar vacío si nodos venían de corto_plazo)
        nodos_dormidos_total = nodos_dormidos_ltd | set(nodos_inhibicion_lateral)
        pesos_dormidos = {}
        if nodos_dormidos_total:
            placeholders = ",".join("?" for _ in nodos_dormidos_total)
            for row in self.cursor.execute(
                f"SELECT concepto, peso_sinaptico FROM largo_plazo WHERE concepto IN ({placeholders})",
                list(nodos_dormidos_total)
            ).fetchall():
                pesos_dormidos[row[0]] = row[1]
        
        for concepto in nodos_dormidos_total:
            peso = pesos_dormidos.get(concepto, snapshot_inicial.get(concepto, {}).get('peso', 0))
            if concepto in nodos_dormidos_ltd:
                razon = f'LTD: peso {peso:.2f} <= umbral 0.05'
                contexto = f'peso={peso:.2f}, umbral=0.05, razon=ltd_decaimiento'
            else:
                razon = f'Inhibicion lateral: energia excedia limite'
                contexto = f'peso={peso:.2f}, energia_total={energia_total:.2f}, limite={limite_energia:.2f}'
            acciones_ciclo.append({
                'concepto': concepto, 'accion': 'dormido',
                'contenido_preview': '', 'peso_anterior': peso, 'peso_nuevo': 0.0,
                'razon': razon, 'contexto': contexto, 'anomalo': 0
            })

        # Auto-clustering (v16.0)
        try:
            from core.auto_clustering import detectar_comunidades, asignar_dimensiones_emergentes
            comunidades = detectar_comunidades(self)
            if comunidades:
                asignar_dimensiones_emergentes(self, comunidades)
                print(f"[Auto-Clustering] Detectadas y asignadas {len(comunidades)} dimensiones emergentes.")
        except Exception as e:
            print(f"[Auto-Clustering] Fallback silencioso: {e}")

        # 5. Vaciar la memoria de corto plazo (La mente amanece despejada)
        self.cursor.execute("DELETE FROM corto_plazo")
        # Transacción se mantiene abierta para commit atómico final con métricas

        # 6. Benchmark de rendimiento post-consolidacion
        self._benchmark_rendimiento()

        # 7. Eviccion opcional (solo si BIORAG_PODAR=true)
        # Snapshot ANTES de evicción
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico FROM largo_plazo WHERE estado = 'dormido'")
        dormidos_antes_eviccion = {row[0]: {'contenido': row[1], 'peso': row[2]} for row in self.cursor.fetchall()}
        
        eliminados_count = 0
        if os.environ.get("BIORAG_PODAR") == "true":
            eliminados_count = self._ejecutar_eviccion(max_borrar=10)
            if eliminados_count:
                print(f"[Eviccion] {eliminados_count} nodos dormidos eliminados permanentemente.")
        
        # Detectar quiénes fueron eliminados
        self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'dormido'")
        dormidos_despues_eviccion = set(row[0] for row in self.cursor.fetchall())
        nodos_elimidos = dormidos_antes_eviccion.keys() - dormidos_despues_eviccion
        
        for concepto in nodos_elimidos:
            info = dormidos_antes_eviccion[concepto]
            acciones_ciclo.append({
                'concepto': concepto, 'accion': 'eliminado',
                'contenido_preview': (info['contenido'] or '')[:100],
                'peso_anterior': info['peso'], 'peso_nuevo': 0.0,
                'razon': f'Eviccion: nodo dormido con peso {info["peso"]:.3f} <= 0.01',
                'contexto': f'peso={info["peso"]:.3f}, umbral_eviccion=0.01, BIORAG_PODAR=true',
                'anomalo': 0
            })

        # 8. Registrar métricas cognitivas del ciclo
        nodos_dormidos_despues = self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'").fetchone()[0]
        sinapsis_despues = self.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
        # Contar categorías de nodos consolidados EN ESTE CICLO (no en toda la base)
        cats_ciclo = {}
        if recuerdos_sesion:
            cat_ids_unicos = list(set(r[3] for r in recuerdos_sesion if len(r) > 3 and r[3]))
            if cat_ids_unicos:
                placeholders = ",".join("?" for _ in cat_ids_unicos)
                cats_map = {}
                for row in self.cursor.execute(
                    f"SELECT id, name FROM categories WHERE id IN ({placeholders})",
                    cat_ids_unicos
                ):
                    cats_map[row[0]] = row[1]
                for r in recuerdos_sesion:
                    cat_id = r[3]
                    if cat_id and cat_id in cats_map:
                        nombre = cats_map[cat_id]
                        cats_ciclo[nombre] = cats_ciclo.get(nombre, 0) + 1

        # En caso de empate en cantidad de nodos por categoría, gana la primera
        # categoría según el orden de iteración de recuerdos_sesion (no es aleatorio,
        # pero tampoco tiene un criterio de desempate más allá de eso).
        cat_dom_name = max(cats_ciclo, key=cats_ciclo.get) if cats_ciclo else None
        
        # Convertir nombre de categoría a ID para FK
        cat_dom_id = None
        if cat_dom_name:
            self.cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_dom_name,))
            cat_row = self.cursor.fetchone()
            cat_dom_id = cat_row[0] if cat_row else None
        
        self.cursor.execute("""
            INSERT INTO metricas_cognitivas
            (timestamp, nodos_consolidados, nodos_dormidos_ciclo, sinapsis_creadas, sinapsis_podadas, categoria_dominante_id, ratio_consolidacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            len(recuerdos_sesion),
            nodos_dormidos_despues - nodos_dormidos_antes,
            max(0, sinapsis_despues - sinapsis_antes),
            max(0, sinapsis_antes - sinapsis_despues),
            cat_dom_id,
            round(len(recuerdos_sesion) / max(1, n_activos), 2)
        ))
        
        # ── Guardar historial forense completo en tabla puente ──
        metrica_id = self.cursor.lastrowid
        now = time.time()
        for accion in acciones_ciclo:
            # Lookup largo_plazo_id from concepto
            self.cursor.execute("SELECT id FROM largo_plazo WHERE concepto = ?", (accion['concepto'],))
            lp_row = self.cursor.fetchone()
            largo_plazo_id = lp_row[0] if lp_row else None
            
            self.cursor.execute("""
                INSERT INTO metricas_cognitivas_nodos 
                (metrica_id, largo_plazo_id, accion, contenido_preview, peso_anterior, peso_nuevo, razon, contexto, anomalo, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrica_id,
                largo_plazo_id,
                accion['accion'],
                accion['contenido_preview'],
                accion['peso_anterior'],
                accion['peso_nuevo'],
                accion['razon'],
                accion['contexto'],
                accion.get('anomalo', 0),
                now
            ))
        
        # Optimizar FTS después de consolidation para reducir fragmentación
        self.cursor.execute("INSERT INTO largo_plazo_fts(largo_plazo_fts) VALUES('optimize')")
        try:
            self.cursor.execute("INSERT INTO largo_plazo_fts_unicode(largo_plazo_fts_unicode) VALUES('optimize')")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

        # SDM v19.0: Reindexar vectores binarios tras consolidation para mantener cobertura
        try:
            from core.sdm import indexar_todos_sdm
            n_sdm = indexar_todos_sdm(self)
            if n_sdm:
                print(f"[SDM] {n_sdm} vectores reindexados tras consolidación.")
        except Exception:
            pass

        print("[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.")

    def aplicar_refuerzo_dopaminergico(self, concepto: str, exito: bool, motivo: str = None) -> bool:
        """
        Refuerzo Dopaminérgico por Error de Predicción de Recompensa (RPE v20.0 - Schultz 1997).
        Aplica el Factor de Inercia Sináptica (Dopaminergic Inertia):
        - Éxito: Delta W = +0.15 * (1.0 - peso_actual * 0.3)
        - Fallo: Delta W = -0.10 / (1.0 + ln(1 + exitos_previos))
        """
        key = concepto.lower().strip()
        self.cursor.execute(
            "SELECT peso_sinaptico, COALESCE(exitos_dopamina, 0), COALESCE(fallos_dopamina, 0) "
            "FROM largo_plazo WHERE concepto = ?", (key,)
        )
        row = self.cursor.fetchone()
        if not row:
            return False

        peso_actual, exitos, fallos = row[0] or 0.5, row[1], row[2]
        import math, time

        if exito:
            delta = 0.15 * (1.0 - peso_actual * 0.3)
            nuevo_peso = min(1.0, round(peso_actual + delta, 2))
            nuevos_exitos = exitos + 1
            self.cursor.execute("""
                UPDATE largo_plazo
                SET peso_sinaptico = ?, exitos_dopamina = ?, ultimo_acceso = ?, estado = 'activo'
                WHERE concepto = ?
            """, (nuevo_peso, nuevos_exitos, time.time(), key))
        else:
            inercia = 1.0 + math.log(1.0 + exitos)
            delta = -0.10 / inercia
            nuevo_peso = max(0.05, round(peso_actual + delta, 2))
            nuevos_fallos = fallos + 1
            nuevo_estado = 'dormido' if nuevo_peso <= 0.05 else 'activo'
            self.cursor.execute("""
                UPDATE largo_plazo
                SET peso_sinaptico = ?, fallos_dopamina = ?, estado = ?
                WHERE concepto = ?
            """, (nuevo_peso, nuevos_fallos, nuevo_estado, key))

        self.conn.commit()
        return True

    def establecer_asociacion(self, concepto_a, concepto_b):
        """Crea un enlace sináptico bidireccional entre dos conceptos en el grafo de largo plazo."""
        concepto_a, concepto_b = concepto_a.lower().strip(), concepto_b.lower().strip()
        for a, b in [(concepto_a, concepto_b), (concepto_b, concepto_a)]:
            self.cursor.execute("SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?", (a, b))
            if not self.cursor.fetchone():
                self.cursor.execute(
                    "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, 0.5, 'manual', ?)",
                    (a, b, time.time())
                )
        from core.sinapsis import _sincronizar_asociaciones
        _sincronizar_asociaciones(self, concepto_a)
        _sincronizar_asociaciones(self, concepto_b)
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
        # Migración: agregar columna leido_por si no existe
        if 'leido_por' not in com_cols:
            self.cursor.execute("ALTER TABLE comunicaciones ADD COLUMN leido_por TEXT DEFAULT ''")
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

    def leer_comunicados(self, destino=None, solo_no_leidos=False, ultimos=10, agente=None):
        """Lee mensajes del canal compartido."""
        if destino and destino not in ('athena', 'artemis', 'hermes', 'todos'):
            destino = None

        # Inferencia de agente si no se pasa explícitamente
        if not agente:
            if destino in ('athena', 'artemis', 'hermes'):
                agente = destino
            else:
                agente = os.environ.get('AGENT_NAME', 'desconocido')
        agente = agente.lower()

        query = "SELECT id, origen, destino, contenido, timestamp, leido, leido_por FROM comunicaciones"
        params = []
        condiciones = []

        if destino:
            condiciones.append("(destino = ? OR destino = 'todos')")
            params.append(destino.lower())

        if solo_no_leidos:
            if agente:
                condiciones.append(
                    "((destino != 'todos' AND leido = 0) OR (destino = 'todos' AND (leido_por IS NULL OR leido_por NOT LIKE '%,' || ? || ',%')))"
                )
                params.append(agente)
            else:
                condiciones.append("leido = 0")

        if condiciones:
            query += " WHERE " + " AND ".join(condiciones)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(ultimos)

        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def marcar_como_leido(self, ids, agente=None):
        """Marca mensajes como leidos. Para 'todos' usa leido_por, personales usa leido."""
        if not ids:
            return
        if not agente:
            agente = os.environ.get('AGENT_NAME', 'desconocido')
        agente = agente.lower()
        for msg_id in ids:
            # Verificar si es mensaje "todos"
            self.cursor.execute("SELECT destino FROM comunicaciones WHERE id = ?", (msg_id,))
            row = self.cursor.fetchone()
            if not row:
                continue
            destino = row[0]
            if destino == 'todos':
                # Para "todos": agregar agente a leido_por
                self.cursor.execute("SELECT leido_por FROM comunicaciones WHERE id = ?", (msg_id,))
                actual = self.cursor.fetchone()[0] or ''
                if not actual:
                    actual = ','
                if f",{agente}," not in actual:
                    nuevo = actual + f"{agente},"
                    self.cursor.execute("UPDATE comunicaciones SET leido_por = ? WHERE id = ?", (nuevo, msg_id))
            else:
                # Para personales: marcar leido=1 (como antes)
                self.cursor.execute("UPDATE comunicaciones SET leido = 1 WHERE id = ?", (msg_id,))
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
        # Cascade delete: cuando se borra un nodo de largo_plazo, limpiar bridge records
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_cleanup_bridge_after_delete")
        self.cursor.execute("""
            CREATE TRIGGER trg_cleanup_bridge_after_delete
            AFTER DELETE ON largo_plazo
            BEGIN
                DELETE FROM metricas_cognitivas_nodos WHERE largo_plazo_id = OLD.id;
            END
        """)
        # Cascade delete SDM: limpiar vectores binarios huérfanos
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_cleanup_sdm_after_delete")
        self.cursor.execute("""
            CREATE TRIGGER trg_cleanup_sdm_after_delete
            AFTER DELETE ON largo_plazo
            BEGIN
                DELETE FROM nodos_sdm WHERE concepto = OLD.concepto;
            END
        """)
        # Cascade delete sinapsis latentes: limpiar conexiones huérfanas
        self.cursor.execute("DROP TRIGGER IF EXISTS trg_cleanup_sinapsis_after_delete")
        self.cursor.execute("""
            CREATE TRIGGER trg_cleanup_sinapsis_after_delete
            AFTER DELETE ON largo_plazo
            BEGIN
                DELETE FROM sinapsis_latentes WHERE origen = OLD.concepto OR destino = OLD.concepto;
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
                categoria_dominante_id INTEGER,
                ratio_consolidacion REAL,
                FOREIGN KEY (categoria_dominante_id) REFERENCES categories(id) ON DELETE SET NULL
            )
        """)
        self._crear_tabla_historial_si_falta()
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
            
            pesos[token] = max(0.1, conexiones)
        
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
        
        # ponytail: removed semantica table lookup — agent provides synonyms via parafrasis_list
        
        return variaciones[:3]

    def _calcular_score_hibrido(self, bm25_norm=0.0, dim_score=0.0,
                                peso_sinaptico=0.0, concepto_ratio=0.0,
                                sinonimos_ratio=0.0, score_latente=0.0,
                                score_cadena=0.0, temporal=0.0,
                                asoc_count=0, match_exacto=False,
                                grupo_score=0.0):
        """Score híbrido unificado: 9 señales ortogonales que suman 1.0.
        grupo_score: similitud por grupo semántico WordNet (coseno binario).
        match_exacto: preserva precisión en búsquedas por nombre exacto (floor 0.5)."""
        asoc_norm = min(1.0, asoc_count / 20.0)
        peso_norm = min(1.0, peso_sinaptico)

        score = (
            0.15 * bm25_norm +          # FTS5 BM25 (was 0.20)
            0.15 * dim_score +           # Dimensiones semánticas (remains 0.15)
            0.175 * concepto_ratio +     # Match en concepto (was 0.15)
            0.125 * sinonimos_ratio +    # Match en sinónimos (was 0.10)
            0.10 * peso_norm +           # Peso sináptico
            0.10 * max(score_latente, score_cadena) +  # Jaccard/cadena
            0.10 * grupo_score +         # Grupo semántico WordNet
            0.05 * temporal +            # Recencia
            0.05 * asoc_norm             # Asociaciones
        )

        if match_exacto:
            score = max(0.95, score)
        elif sinonimos_ratio >= 0.95:
            score = max(0.65, score)

        return round(min(1.0, score), 4)

    def expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        """Realiza una búsqueda BFS real en la red sináptica hasta una profundidad 'depth'.
        Atenúa recursivamente los scores de los vecinos encontrados.
        Deduplica nodos de forma estricta.
        """
        if not depth or depth <= 0 or not pagina_resultados:
            return pagina_resultados

        depth = min(int(depth), 3)
        vistos = {}  # concepto -> item
        for r in pagina_resultados:
            vistos[r[0]] = r

        frontera = list(pagina_resultados)
        contextos = []
        filtro_estado = " AND l.estado = 'activo'" if profundidad != "profundo" else ""

        for nivel in range(1, depth + 1):
            siguiente_frontera = []
            for r in frontera:
                concepto = r[0]
                score_actual = r[4]
                
                # Recuperar vecinos directos de la base de datos
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
                # Límite local para evitar explosión combinatoria (máximo 3 vecinos con mayor peso por nodo)
                for row in self.cursor.fetchall():
                    if agregados >= 3:
                        break
                    vecino_concepto = row[0]
                    if vecino_concepto in vistos:
                        continue
                    
                    # Atenuación del score híbrido según la distancia
                    score_contexto = round(min(1.0, score_actual * 0.6 + min(row[5], 1.0) * 0.2), 4)
                    
                    # Limitar caracteres del contenido de los vecinos si preview_chars está definido
                    vecino_contenido = row[1] or ""
                    if preview_chars and preview_chars > 0:
                        if len(vecino_contenido) > preview_chars:
                            vecino_contenido = vecino_contenido[:preview_chars] + "..."
                            
                    new_item = (vecino_concepto, vecino_contenido, row[2], row[3], score_contexto, row[4] or "")
                    contextos.append(new_item)
                    vistos[vecino_concepto] = new_item
                    siguiente_frontera.append(new_item)
                    agregados += 1
                    
            frontera = siguiente_frontera
            if not frontera:
                break

        # Ordenar contextos por score descendente
        contextos.sort(key=lambda x: x[4], reverse=True)
        return list(pagina_resultados) + contextos

    def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=None, categoria=None, preview_chars=1500, historial_fallos=None, context_window=0, dimensiones_dict=None, dimensiones_ids=None, parafrasis_list=None, desde_ts=None, hasta_ts=None, modo_estricto=False, usar_inferencia=True, buscar_por_rol=None):
        """Busqueda hibrida: FTS5 trigram + peso sinaptico + asociaciones + scoring dimensional.

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
        dimensiones_dict: dict de {eje: [ids]} para scoring dimensional.
                          Batch query post-merge → coseno binario → dim_score.
        dimensiones_ids: flat list de todos los IDs (para batch query SQL).
        desde_ts: timestamp Unix mínimo para filtro temporal PRE-hoc (creado_en).
        hasta_ts: timestamp Unix máximo para filtro temporal PRE-hoc (creado_en).
        buscar_por_rol: string con filtro por roles semánticos (ej: 'sujeto:Dennys')
        Retorna (resultados, total) donde resultados es lista de
        (concepto, contenido, peso, estado, score, asociaciones)
        """
        self.notificar_actividad_usuario()
        # SRL v16.0: Filtrado por roles semánticos (buscar_por_rol)
        conceptos_validos_rol = None
        if buscar_por_rol:
            filtros_rol = {}
            for parte in buscar_por_rol.split(","):
                if ":" in parte:
                    k, v = parte.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k in ("sujeto", "accion", "objeto", "contexto"):
                        filtros_rol[k] = v
            if filtros_rol:
                conceptos_validos_rol = set()
                # Consultar predicados en largo plazo
                sql_rol = "SELECT DISTINCT concepto FROM predicados WHERE 1=1"
                params_rol = []
                for col, val in filtros_rol.items():
                    sql_rol += f" AND {col} = ?"
                    params_rol.append(val)
                self.cursor.execute(sql_rol, tuple(params_rol))
                for row in self.cursor.fetchall():
                    conceptos_validos_rol.add(row[0].lower().strip())
                # Consultar predicados en corto plazo
                sql_rol_cp = "SELECT DISTINCT concepto FROM corto_plazo_predicados WHERE 1=1"
                for col in filtros_rol.keys():
                    sql_rol_cp += f" AND {col} = ?"
                self.cursor.execute(sql_rol_cp, tuple(params_rol))
                for row in self.cursor.fetchall():
                    conceptos_validos_rol.add(row[0].lower().strip())

        if pagina < 1:
            pagina = 1
        if limite is None:
            limite = LIMITE_DEFAULT
        # Si no hay frase Y no hay dimensiones Y no hay rol, retornar vacío
        # PERO si hay dimensiones o rol (aunque no haya frase), continuar
        if not frase.strip() and not dimensiones_ids and not buscar_por_rol:
            return [], 0

        # Parsear términos entre comillas dobles ("CV", "IA") para bypass de trigram
        protected_terms = re.findall(r'"([^"]+)"', frase)
        frase_limpia = re.sub(r'"[^"]+"', '', frase).strip()
        frase_limpia = re.sub(r'\s+', ' ', frase_limpia).strip()
        solo_protegidos = bool(protected_terms) and not frase_limpia

        # Filtrar stopwords de la frase_limpia
        from core.stopwords import _STOPWORDS_QUERY
        import unicodedata

        def strip_accents(text):
            return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

        stopwords_normalized = {strip_accents(w) for w in _STOPWORDS_QUERY}

        clean_phrase_tokens = []
        if frase_limpia.strip():
            clean_p = re.sub(r'[^\w\s_-]', ' ', frase_limpia.lower())
            for w in clean_p.split():
                w_clean = strip_accents(w)
                if w_clean not in stopwords_normalized and len(w) >= 2:
                    clean_phrase_tokens.append(w)

        if clean_phrase_tokens:
            frase_limpia_filtrada = " ".join(clean_phrase_tokens)
        else:
            frase_limpia_filtrada = re.sub(r'[^\w\s_-]', ' ', frase_limpia.lower()).strip()

        frase = frase_limpia_filtrada
        query = frase_limpia_filtrada if not solo_protegidos else ""

# Filtrar stopwords de la lista de paráfrasis
        parafrasis_filtradas = []
        if parafrasis_list:
            for p in parafrasis_list:
                p_clean = re.sub(r'[^\w\s_-]', ' ', p.lower())
                p_words = [w for w in p_clean.split() if strip_accents(w) not in stopwords_normalized and len(w) >= 2]
                if p_words:
                    parafrasis_filtradas.append(" ".join(p_words))

        # EARLY-EXIT: Detectar queries adversarias/basura que cascadearían por todos los fallbacks
        # Si la query limpia no tiene tokens válidos (>=2 chars, no stopwords) Y no hay términos protegidos,
        # NO entrar en la cascada de fallbacks costosos → retornar vacío inmediato
        tokens_validos = [w for w in frase.split() if len(w) >= 2 and strip_accents(w) not in stopwords_normalized]
        tiene_parafrasis_validas = any(len(p.split()) > 0 for p in parafrasis_filtradas)
        
        # Query es basura si: no tiene tokens válidos, no tiene términos protegidos, no tiene paráfrasis válidas
        # Y es muy larga (>200 chars) o tiene alta entropía (solo ruido) → evita DoS por cascada
        es_basura = (
            not tokens_validos and 
            not protected_terms and 
            not tiene_parafrasis_validas and
            (len(frase) > 200 or len(set(frase.lower())) > 50)  # largo o alta diversidad de chars = ruido
        )
        
        if es_basura:
            # Log para auditoría
            # print(f"[EARLY-EXIT] Query basura detectada, saltando cascada fallbacks: '{frase[:50]}...'")
            return [], 0

        # Calcular pesos diferenciales de tokens por centralidad en la red
        pesos_tokens = self._pesar_tokens_query(frase)

        # Build filter clauses
        filtros = []
        temporal_params = []
        if profundidad != "profundo":
            filtros.append("l.estado = 'activo'")
        if categoria:
            cat_id = self._resolver_categoria_id(categoria)
            filtros.append(f"l.categoria = {cat_id}")
        # v13: filtro temporal PRE-hoc (aplicar en SQL, no post-hoc)
        if desde_ts is not None:
            filtros.append("l.creado_en >= ?")
            temporal_params.append(desde_ts)
        if hasta_ts is not None:
            filtros.append("l.creado_en <= ?")
            temporal_params.append(hasta_ts)
        clause = (" AND " + " AND ".join(filtros)) if filtros else ""

        # ponytail: no semantic expansion table — agent passes synonyms as parafrasis_list directly
        if modo_estricto:
            if parafrasis_list:
                fts_match = " OR ".join(f"({' AND '.join(v.split())})" for v in [frase] + parafrasis_list)
            elif len(frase.split()) > 1:
                fts_match = " AND ".join(frase.split())
            else:
                fts_match = frase
        elif parafrasis_list:
            fts_variantes = [f'"{frase}"'] + [f'"{p}"' for p in parafrasis_list]
            fts_match = " OR ".join(fts_variantes)
        elif len(frase.split()) > 1:
            fts_match = " OR ".join(frase.split())
        else:
            fts_match = frase
        sql = """
            SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                   l.estado, l.asociaciones,
                   bm25(largo_plazo_fts, 5.0, 1.0, 2.0) AS bm25_val
            FROM largo_plazo_fts f
            CROSS JOIN largo_plazo l ON l.rowid = f.rowid
            WHERE largo_plazo_fts MATCH ?{filtro}
            ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico)
        """.format(filtro=clause)

        todos = []
        bm25_raw = {}  # concepto -> raw BM25 from FTS5
        palabras = [w for w in frase.split() if len(w) >= 2]
        origen_scores = {}  # Side channel: rastrea origen de cada nodo para Dynamic Multiplicator

        # SRL v16.0: si no hay frase pero hay roles, popular todos directamente
        if not frase.strip() and conceptos_validos_rol:
            placeholders = ",".join(["?" for _ in conceptos_validos_rol])
            sql_rol_all = f"""
                SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones
                FROM largo_plazo
                WHERE concepto IN ({placeholders})
            """
            fb_rol_filtros = []
            fb_rol_params = list(conceptos_validos_rol)
            if profundidad != "profundo":
                fb_rol_filtros.append("estado = 'activo'")
            if categoria:
                cat_id = self._resolver_categoria_id(categoria)
                fb_rol_filtros.append(f"categoria = {cat_id}")
            if fb_rol_filtros:
                sql_rol_all += " AND " + " AND ".join(fb_rol_filtros)
            
            try:
                self.cursor.execute(sql_rol_all, tuple(fb_rol_params))
                for row in self.cursor.fetchall():
                    todos.append(row)
                    origen_scores[row[1]] = ("literal", 0.0)
            except sqlite3.OperationalError:
                pass

        # ─── Capa 2: LIKE en concepto (siempre activa) ───
        # Busca coincidencia por substring en el nombre del concepto.
        # Complementa a FTS5: maneja guiones, puntos y caracteres especiales
        # que FTS5 trigram no tokeniza bien como palabras completas.
        palabras_like = [w for w in frase.split() if len(w) >= 2]
        resultados_concepto = {}
        if palabras_like:
            like_clauses = []
            like_params = []
            for w in palabras_like:
                like_clauses.append(
                    "(l.concepto LIKE '%' || ? || '%' AND "
                    "(PALABRA_COMPLETA(?, l.concepto) = 1 OR length(?) >= 5))"
                )
                like_params.extend([w, w, w])
            like_where = " AND ".join(like_clauses)
            clause_like = clause.replace("l.", "") if clause else ""
            sql_like = f"""
                SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                       l.estado, l.asociaciones
                FROM largo_plazo l
                WHERE {like_where}{clause_like}
            """
            try:
                self.cursor.execute(sql_like, like_params + temporal_params)
                for r in self.cursor.fetchall():
                    match_ratio = sum(1 for w in palabras_like if w.lower() in r[1].lower()) / len(palabras_like)
                    resultados_concepto[r[1]] = match_ratio
                    origen_scores[r[1]] = ("concepto", match_ratio)
            except sqlite3.OperationalError:
                pass

        # Filtro DB-side PALABRA_COMPLETA: previene falsos positivos de FTS5 trigram
        # ("culo" no debe matchear "artículos"). Aplica a contenido+concepto+sinonimos.
        # Exige que AL MENOS UNA palabra aparezca como palabra completa en alguno.
        # Relajación: solo se exige PALABRA_COMPLETA para palabras cortas (longitud <= 4).
        palabras_pc = [w for w in palabras if len(w) <= 4]
        pc_clause = ""
        pc_params = []
        if palabras_pc:
            pc_clauses = []
            for p in palabras_pc:
                pc_clauses.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                pc_params.extend([p, p, p])
            pc_clause = " AND (" + " OR ".join(pc_clauses) + ")"
        # Inyectar pc_clause en el WHERE después de los filtros de estado/categoría
        sql_con_pc = sql.replace("ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico)", pc_clause + " ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico)")

        # Intentar NEAR query primero (palabras cercanas entre sí)
        if not solo_protegidos and len(palabras) > 1:
            near_query = f'NEAR({" ".join(palabras)}, 15)'
            try:
                self.cursor.execute(sql_con_pc, tuple([near_query]) + tuple(temporal_params) + tuple(pc_params))
                _raw = self.cursor.fetchall()
                todos = []
                for r in _raw:
                    todos.append(r[:6])
                    bm25_raw[r[1]] = r[6]
                    origen_scores[r[1]] = ("literal", 0.0)
            except sqlite3.OperationalError:
                pass

        # Fallback 1.0: FTS5 AND exacto (usar fts_match si hay paráfrasis)
        if not solo_protegidos and not todos:
            try:
                self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))
                _raw = self.cursor.fetchall()
                todos = []
                for r in _raw:
                    todos.append(r[:6])
                    bm25_raw[r[1]] = r[6]
                    origen_scores[r[1]] = ("literal", 0.0)
            except sqlite3.OperationalError:
                pass

        # ─── Términos protegidos: búsqueda exacta contra unicode61 + PALABRA_COMPLETA ───
        # Los términos entre comillas dobles ("CV", "IA") bypassan trigram y se buscan
        # como palabras completas en el índice unicode61.
        if protected_terms:
            pc_prot_conds = []
            pc_prot_params = []
            for pt in protected_terms:
                pc_prot_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                pc_prot_params.extend([pt, pt, pt])
            pc_prot_clause = " AND (" + " OR ".join(pc_prot_conds) + ")"
            fts_protected = " OR ".join(f'"{t}"' for t in protected_terms)
            try:
                self.cursor.execute(
                    f"SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                    f"l.estado, l.asociaciones, "
                    f"bm25(largo_plazo_fts_unicode) AS bm25_val "
                    f"FROM largo_plazo_fts_unicode f "
                    f"CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                    f"WHERE largo_plazo_fts_unicode MATCH ?"
                    f"{clause}{pc_prot_clause} "
                    f"ORDER BY bm25(largo_plazo_fts_unicode) "
                    f"LIMIT ?",
                    (fts_protected,) + tuple(temporal_params) + tuple(pc_prot_params) + (limite * 3,)
                )
                prot_results = self.cursor.fetchall()
                seen_rowids = {r[0] for r in todos}
                for r in prot_results:
                    if r[0] not in seen_rowids:
                        todos.append(r[:6])
                        bm25_raw[r[1]] = r[6]
                        origen_scores[r[1]] = ("protegido", 1.0)
                        seen_rowids.add(r[0])
            except sqlite3.OperationalError:
                pass

        # OR fallback: si AND devolvió pocos resultados (o ninguno), probar OR
        # Usar fts_match directamente cuando hay paráfrasis (ya es una expresión OR válida)
        # SIEMPRE usar sql_con_pc (con PALABRA_COMPLETA) para evitar falsos positivos.
        if not modo_estricto and (not todos or len(todos) < max(limite * 2, 5)) and len(frase.split()) > 1:
            if not todos and fts_match != frase:
                # Si hay paráfrasis y no se encontró nada, usar fts_match directamente
                try:
                    self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))
                    or_results = self.cursor.fetchall()
                    seen_rowids = {r[0] for r in todos}
                    for r in or_results:
                        if r[0] not in seen_rowids:
                            origen_scores[r[1]] = ("parafrasis", 0.0)
                            todos.append(r[:6])
                            bm25_raw[r[1]] = r[6]
                except sqlite3.OperationalError:
                    pass

        # Fallback 1.4: FTS5 unicode61 con prefix wildcards
        # Mejora recall para palabras que comparten prefijo (react -> reactive, forms -> formularios).
        # Último recurso: corre si la búsqueda literal arrojó menos de 3 resultados.
        if not modo_estricto and len(todos) < 3:
            try:
                query_wild = self._agregar_prefix_wildcards(query)
                sql_unicode = """
                    SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                           l.estado, l.asociaciones,
                           bm25(largo_plazo_fts_unicode) AS bm25_val
                    FROM largo_plazo_fts_unicode f
                    CROSS JOIN largo_plazo l ON l.rowid = f.rowid
                    WHERE largo_plazo_fts_unicode MATCH ?{filtro}
                    ORDER BY bm25(largo_plazo_fts_unicode)
                    LIMIT ?
                """.format(filtro=clause)
                self.cursor.execute(sql_unicode, (query_wild,) + tuple(temporal_params) + (max(limite * 3, 10),))
                uni_results = self.cursor.fetchall()
                seen_rowids = {r[0] for r in todos}
                for r in uni_results:
                    if r[0] not in seen_rowids:
                        todos.append(r[:6])
                        bm25_raw[r[1]] = r[6]
                        origen_scores[r[1]] = ("unicode", 0.0)
            except sqlite3.OperationalError:
                pass

        # ponytail: removed semantic expansion fallback — agent passes synonyms directly

        # Fallback 1.7: best-word trigram similarity (typo + word-match tolerance)
        # Filtro PC: solo aplica a palabras CORTAS (<=5 chars) donde el trigrama no
        # es discriminante (ej: "culo" como substring de "artículos"). Para palabras
        # largas (>=6 chars), el trigrama ya es tolerante a typos sin generar FPs.
        if not modo_estricto and len(todos) < 3 and len(query) >= 3:
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
                query_words_filtradas = [w for w in query_words if len(w) >= 4]
                if not query_words_filtradas:
                    query_words_filtradas = [w for w in query_words if len(w) >= 4]
                qw_cortas = [w for w in query_words_filtradas if len(w) <= 5]
                candidatos = []
                for row in filas:
                    texto = f"{row[1]} {row[2]}".lower()
                    text_words = re.findall(r'\w{3,}', texto)
                    total_score = 0.0
                    for qw in query_words_filtradas:
                        qt = set(qw[i:i+3] for i in range(len(qw) - 2))
                        if not qt:
                            continue
                        best = max(
                            (len(qt & set(tw[i:i+3] for i in range(len(tw) - 2))) / len(qt)
                             for tw in text_words if len(tw) >= 3),
                            default=0.0
                        )
                        total_score += best
                    avg_score = total_score / len(query_words_filtradas) if query_words_filtradas else 0.0
                    if avg_score >= 0.7:
                        texto_full = f"{row[1]} {row[2] or ''}".replace('_', ' ').replace('-', ' ')
                        if qw_cortas:
                            match_legitimo = any(
                                re.search(r'\b' + re.escape(qw) + r'\b', texto_full, re.IGNORECASE)
                                for qw in qw_cortas
                            )
                            if not match_legitimo:
                                continue
                        candidatos.append((avg_score, row))
                candidatos.sort(key=lambda x: x[0], reverse=True)
                seen_rowids = {r[0] for r in todos}
                for score_typo, row in candidatos[:max(limite * 3, 10)]:
                    if row[0] not in seen_rowids:
                        todos.append(row)
                        if row[1] not in origen_scores:
                            origen_scores[row[1]] = ("typo", score_typo)
            except sqlite3.OperationalError:
                pass

        # Fallback 1.8: Similitud conceptual latente (Jaccard vecinos + contenido)
        # Usa Jaccard sobre tokens, no requiere match literal. No aplicar PALABRA_COMPLETA.
        # Dynamic Multiplicator: registrar como "latente" con score Jaccard real
        # OPTIMIZACIÓN: Pre-cargar puentes FTS5 una vez (reduce N queries a 1)
        # PROTECCIÓN DoS: Early-exit para queries adversarias + subgraph bounding
        if not modo_estricto and len(todos) < 3 and len(query) >= 2:
            # Early-exit: queries muy largas o con alta entropía (probablemente basura/adversarial)
            # no justifican el costo O(N^1.6) de similitud latente
            if len(query) > 200:
                pass  # Skip latent similarity for adversarial-length queries
            else:
                from core.similitud_conceptual import _tokenizar_query, score_similitud_latente, LIMITE_SIMILITUD, _cargar_grafo, _limpiar_cache
                query_tokens = _tokenizar_query(query)
                if query_tokens:
                    try:
                        try:
                            grafo = _cargar_grafo(self.cursor)
                            # Batch: pre-fetch puentes FTS5 una vez (1 query SQL)
                            # En vez de N queries FTS5 separadas en _similitud_red
                            filtrar = [t for t in query_tokens if len(t) >= 2]
                            nodos_cache = None
                            if filtrar:
                                fts_tokens = [f'"{t}"' for t in filtrar]
                                fts_q = " OR ".join(fts_tokens)
                                # Filtro PALABRA_COMPLETA en puentes: evita falsos positivos de trigram
                                # Relajación: solo se exige PALABRA_COMPLETA para palabras cortas (longitud <= 4)
                                pc_bridge_conds = []
                                pc_bridge_params_list = []
                                for t in filtrar:
                                    if len(t) <= 4:
                                        pc_bridge_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                                        pc_bridge_params_list.extend([t, t, t])
                                    else:
                                        pc_bridge_conds.append("(1 = 1)")
                                pc_bridge_clause = " AND (" + " AND ".join(pc_bridge_conds) + ")"
                                pc_bridge_params = tuple(pc_bridge_params_list)
                                try:
                                    bridge_filter = " AND l.estado = 'activo'"
                                    self.cursor.execute(
                                        "SELECT DISTINCT l.concepto FROM largo_plazo_fts f "
                                        "CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                                        "WHERE largo_plazo_fts MATCH ? " + bridge_filter
                                        + pc_bridge_clause + " LIMIT 50",
                                        (fts_q,) + pc_bridge_params
                                    )
                                    nodos_cache = {row[0] for row in self.cursor.fetchall()}
                                except sqlite3.OperationalError:
                                    nodos_cache = None
                            fts_tokens = [f'"{t}"' for t in query_tokens if len(t) >= 2]
                            if fts_tokens:
                                fts_q = " OR ".join(fts_tokens)
                                lat_clause = " AND l.estado = 'activo'"
                                # Filtro PALABRA_COMPLETA en candidatos: evita falsos positivos de trigram
                                # Relajación: solo se exige PALABRA_COMPLETA para palabras cortas (longitud <= 4)
                                pc_lat_clause = ""
                                pc_lat_params = ()
                                filtrar_lat = [t for t in query_tokens if len(t) >= 2]
                                if filtrar_lat:
                                    pc_lat_conds = []
                                    pc_lat_params_list = []
                                    for t in filtrar_lat:
                                        if len(t) <= 4:
                                            pc_lat_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                                            pc_lat_params_list.extend([t, t, t])
                                        else:
                                            pc_lat_conds.append("(1 = 1)")
                                    pc_lat_clause = " AND (" + " AND ".join(pc_lat_conds) + ")"
                                    pc_lat_params = tuple(pc_lat_params_list)
                                self.cursor.execute(
                                    "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                                    "l.estado, l.asociaciones "
                                    "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                                    "WHERE largo_plazo_fts MATCH ?" + lat_clause + pc_lat_clause + " LIMIT ?",
                                    (fts_q,) + pc_lat_params + (CANDIDATOS_SIMILITUD,)
                                )
                                candidatos_lat = self.cursor.fetchall()
                                
                                # SUBGRAPH BOUNDING: Solo procesar candidatos con grado mínimo en el grafo
                                # Evita recorrer nodos aislados que solo añaden ruido y costo
                                if grafo:
                                    candidatos_lat = [
                                        c for c in candidatos_lat
                                        if len(grafo.get(c[1], {})) >= 2  # min degree = 2
                                    ]
                                
                                scored = []
                                seen_rowids = {r[0] for r in todos}
                                for rowid, concepto, contenido, peso, estado, asoc in candidatos_lat:
                                    if rowid in seen_rowids:
                                        continue
                                    s = score_similitud_latente(self.cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache)
                                    if s >= 0.15:
                                        scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))
                                scored.sort(key=lambda x: x[0], reverse=True)
                                for jaccard_score, row in scored[:LIMITE_SIMILITUD]:
                                    todos.append(row)
                                    # Solo registrar si no fue encontrado por capa literal (FTS5 tiene prioridad)
                                    if row[1] not in origen_scores:
                                        origen_scores[row[1]] = ("latente", jaccard_score)
                        finally:
                            _limpiar_cache()
                    except sqlite3.OperationalError:
                        pass
        # Fallback 2.0: substring match con word boundary via PALABRA_COMPLETA
        if not modo_estricto and len(todos) < 3 and len(query) >= 2:
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
                seen_rowids = {r[0] for r in todos}
                for row in filas:
                    if row[0] not in seen_rowids:
                        todos.append(row)
                todos = todos[:50]
            except sqlite3.OperationalError:
                pass

        # Fallback 1.8: Snap reciente (últimos 7 días)
        if not modo_estricto and len(todos) < 3 and len(query) >= 2:
            limite_tiempo = time.time() - (7 * 86400)
            # sql_con_pc ya incluye el filtro PALABRA_COMPLETA — previene falsos positivos
            sql_snap = sql_con_pc.replace("ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico)",
                                          "AND l.ultimo_acceso > ? ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0) * (0.5 + 0.5 * l.peso_sinaptico) LIMIT 5")
            try:
                self.cursor.execute(sql_snap, (query,) + tuple(temporal_params) + tuple(pc_params) + (limite_tiempo,))
                snap_r = self.cursor.fetchall()
                if snap_r:
                    print(f"[TRACE] 1.8 Snap: {len(snap_r)} → {[r[1] for r in snap_r[:3]]}")
                seen_rowids = {r[0] for r in todos}
                for r in snap_r:
                    if r[0] not in seen_rowids:
                        todos.append(r[:6])
                        bm25_raw[r[1]] = r[6]
            except sqlite3.OperationalError:
                pass

        # Fallback 1.9: Evocación por cadena (multi-hop con decay logarítmico)
        # Dynamic Multiplicator: registrar como "cadena" con score de decay
        if not modo_estricto and len(todos) < 3 and len(query) >= 2:
            tokens_query = re.findall(r'\w{3,}', query.lower())
            if tokens_query:
                fts_tokens = [f'"{t}"' for t in tokens_query if len(t) >= 3]
                if fts_tokens:
                    fts_q = " OR ".join(fts_tokens)
                    # Filtro PALABRA_COMPLETA en semillas: evita que la cadena evoque desde
                    # falsos positivos de trigram. Relajación: longitud <= 4.
                    pc_seed_conds = []
                    pc_seed_params_list = []
                    for t in fts_tokens:
                        clean_t = t.strip('"')
                        if len(clean_t) <= 4:
                            pc_seed_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1)")
                            pc_seed_params_list.extend([clean_t, clean_t])
                        else:
                            pc_seed_conds.append("(1 = 1)")
                    pc_seed_clause = " AND (" + " AND ".join(pc_seed_conds) + ")"
                    pc_seed_params = tuple(pc_seed_params_list)
                    try:
                        self.cursor.execute(
                            "SELECT l.concepto FROM largo_plazo_fts f "
                            "CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                            "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                            + pc_seed_clause + " LIMIT 5",
                            (fts_q,) + pc_seed_params
                        )
                        semillas = [row[0] for row in self.cursor.fetchall()]
                        if semillas:
                            evocados = self._evocacion_por_cadena(semillas)
                            for concepto_ev, decay_score, _ in evocados:
                                ev_sql = (
                                    "SELECT rowid, concepto, contenido, peso_sinaptico, "
                                    "estado, asociaciones FROM largo_plazo "
                                    "WHERE concepto = ? AND estado = 'activo'"
                                )
                                self.cursor.execute(ev_sql, (concepto_ev,))
                                row = self.cursor.fetchone()
                                if row and row[1] not in {r[1] for r in todos} and row[2]:
                                    # Filtro PALABRA_COMPLETA: el nodo evocado debe contener
                                    # al menos 2 palabras de la query como palabras completas.
                                    # Previene que la cadena traiga nodos no relacionados
                                    # (ej: "receta de paella" → nodo con solo "receta" en contenido).
                                    _contenido_ev = (row[2] or "").lower().replace('_', ' ').replace('-', ' ')
                                    _concepto_ev = row[1].lower().replace('_', ' ').replace('-', ' ')
                                    _matches_ev = 0
                                    for _pw in palabras:
                                        _patron_ev = r'\b' + re.escape(_pw.lower()) + r'\b'
                                        if re.search(_patron_ev, _contenido_ev) or re.search(_patron_ev, _concepto_ev):
                                            _matches_ev += 1
                                            if _matches_ev >= 2:
                                                break
                                    if _matches_ev < 2:
                                        continue
                                    todos.append(row)
                                    if row[1] not in origen_scores:
                                        origen_scores[row[1]] = ("cadena", decay_score)
                    except sqlite3.OperationalError:
                        pass

        # ─── Fallback 2.1: Simbólico (Levenshtein + WordNet + Traducción) ───
        # Solo cuando todas las capas anteriores devuelven < 3 resultados y no es modo_estricto.
        if not modo_estricto and len(todos) < 3 and len(query) >= 3:
            try:
                from core.fallback_simbolico import buscar_fallback_simbolico
                estado_filter = "WHERE estado = 'activo'" if profundidad != "profundo" else ""
                cat_filter = ""
                if categoria:
                    cat_id_fb = self._resolver_categoria_id(categoria)
                    cat_filter = f" AND categoria = {cat_id_fb}" if estado_filter else f"WHERE categoria = {cat_id_fb}"
                
                self.cursor.execute(
                    f"SELECT rowid, concepto, contenido, peso_sinaptico, "
                    f"estado, asociaciones, sinonimos "
                    f"FROM largo_plazo {estado_filter}{cat_filter} "
                    f"LIMIT 1000"
                )
                candidatos_fb = self.cursor.fetchall()
                if candidatos_fb:
                    fb_results = buscar_fallback_simbolico(
                        query,
                        candidatos_fb,
                        umbral=0.60,
                        top_k=10
                    )
                    seen_rowids = {r[0] for r in todos}
                    for score_fb, rowid, conc, cont, peso, est, asoc in fb_results:
                        if rowid not in seen_rowids:
                            todos.append((rowid, conc, cont, peso, est, asoc or ""))
                            seen_rowids.add(rowid)
                            if conc not in origen_scores:
                                origen_scores[conc] = ("simbolico", score_fb)
            except ImportError:
                pass
            except Exception:
                pass

        # ─── Merge: inyectar resultados de concepto no encontrados por FTS5 ───

        if resultados_concepto:
            seen = {r[1] for r in todos}
            for concepto, match_ratio in resultados_concepto.items():
                umbral_ratio = 1.0 if modo_estricto else 0.3
                if concepto not in seen and match_ratio >= umbral_ratio:
                    merge_sql = (
                        "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                        "FROM largo_plazo WHERE concepto = ?"
                    )
                    self.cursor.execute(merge_sql, (concepto,))
                    row = self.cursor.fetchone()
                    if row and (profundidad == "profundo" or row[4] == "activo"):
                        todos.append(row)

        # ─── Capa 4: inyectar resultados de sinónimos no encontrados por capas anteriores ───
        resultados_semantica = {}
        if palabras_like:
            palabras_sin = [w for w in palabras_like]
            if palabras_sin:
                sin_conds = " OR ".join(["l.sinonimos LIKE '%' || ? || '%'" for _ in palabras_sin])
                sin_params = list(palabras_sin)
            try:
                sin_where = f"l.sinonimos IS NOT NULL AND l.sinonimos != '' AND l.estado = 'activo' AND ({sin_conds})"
                self.cursor.execute(
                    f"SELECT l.concepto, l.sinonimos, l.peso_sinaptico "
                    f"FROM largo_plazo l "
                    f"WHERE {sin_where}",
                    sin_params
                )
                for conc, sin_text, _ in self.cursor.fetchall():
                    if conc not in {r[1] for r in todos}:
                        match_ratio = sum(1 for w in palabras_like if w.lower() in (sin_text or "").lower()) / len(palabras_like)
                        umbral_sin = 1.0 if modo_estricto else 0.1
                        if match_ratio >= umbral_sin:
                            resultados_semantica[conc] = match_ratio
            except (sqlite3.OperationalError, sqlite3.ProgrammingError):
                pass
        if resultados_semantica:
            seen = {r[1] for r in todos}
            for concepto, match_ratio in resultados_semantica.items():
                if concepto not in seen:
                    merge_sql = (
                        "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                        "FROM largo_plazo WHERE concepto = ?"
                    )
                    self.cursor.execute(merge_sql, (concepto,))
                    row = self.cursor.fetchone()
                    if row and (profundidad == "profundo" or row[4] == "activo"):
                        todos.append(row)
                        origen_scores[concepto] = ("semantica", match_ratio)

        # ─── Batch query: dimensiones de todos los conceptos ───
        # Una sola query en vez de N queries individuales (rendimiento)
        dim_scores_map = {}
        if dimensiones_ids and len(dimensiones_ids) > 0:
            conceptos_todos = [r[1] for r in todos if r[1]]
            if conceptos_todos:
                placeholders = ",".join(["?" for _ in conceptos_todos])
                dim_ids_str = ",".join([str(d) for d in dimensiones_ids])
                dim_sql = f"""
                    SELECT concepto, dimension_id
                    FROM largo_plazo_dimensiones
                    WHERE concepto IN ({placeholders})
                    AND dimension_id IN ({dim_ids_str})
                """
                try:
                    self.cursor.execute(dim_sql, conceptos_todos)
                    # Agrupar IDs por concepto
                    concepto_dim_ids = {}
                    for concepto, dim_id in self.cursor.fetchall():
                        if concepto not in concepto_dim_ids:
                            concepto_dim_ids[concepto] = []
                        concepto_dim_ids[concepto].append(dim_id)
                    # Coseno binario / ponderado (v16.0 auto-clustering)
                    import math
                    query_dim_set = set(dimensiones_ids)
                    
                    # Cargar pesos (confianzas) de las dimensiones de la query
                    w_map = {}
                    try:
                        self.cursor.execute(f"SELECT id, auto_generada, confianza FROM dimensiones_semanticas WHERE id IN ({dim_ids_str})")
                        for d_id, auto_gen, conf in self.cursor.fetchall():
                            w_map[d_id] = conf if auto_gen else 1.0
                    except Exception:
                        pass
                    for d_id in query_dim_set:
                        if d_id not in w_map:
                            w_map[d_id] = 1.0
                            
                    sum_q2 = sum(w_map[d_id]**2 for d_id in query_dim_set)
                    for concepto, doc_ids in concepto_dim_ids.items():
                        doc_set = set(doc_ids)
                        sum_d2 = sum(w_map[d_id]**2 for d_id in doc_set if d_id in w_map)
                        if sum_d2 > 0 and sum_q2 > 0:
                            dim_scores_map[concepto] = math.sqrt(sum_d2) / math.sqrt(sum_q2)
                except sqlite3.OperationalError:
                    dim_scores_map = {}

        # ─── Fallback dimensional CON UMBRAL: dimensiones empujan solo si hay conexión real ───
        # "Buscar sin palabras": si FTS5 no encontró nada pero hay dimensiones,
        # traer nodos que compartan AL MENOS UMBRAL_DIMENSIONES dimensiones.
        # Umbral 3: si 3 de 7 dimensiones coinciden, hay conexión semántica real.
        # PERO: si NO hay resultados de texto (todos vacío), bajar umbral a 1 para permitir "buscar solo por dimensión"
        UMBRAL_DIMENSIONES = 3
        umbral_efectivo = 1 if len(todos) == 0 else UMBRAL_DIMENSIONES
        if dimensiones_ids and len(dimensiones_ids) >= umbral_efectivo:
            conceptos_existentes = {r[1] for r in todos if r[1]}
            dim_ids_str = ",".join([str(d) for d in dimensiones_ids])
            fb_filtros_extra = []
            fb_filtros_params = []
            if categoria:
                cat_id_fb = self._resolver_categoria_id(categoria)
                fb_filtros_extra.append("l.categoria = ?")
                fb_filtros_params.append(cat_id_fb)
            if profundidad != "profundo":
                fb_filtros_extra.append("l.estado = 'activo'")
            fb_where_extra = (" AND " + " AND ".join(fb_filtros_extra)) if fb_filtros_extra else ""
            fallback_sql = f"""
                SELECT d.concepto, d.dimension_id
                FROM largo_plazo_dimensiones d
                JOIN largo_plazo l ON l.concepto = d.concepto
                WHERE d.dimension_id IN ({dim_ids_str}){fb_where_extra}
                LIMIT 500
            """
            try:
                self.cursor.execute(fallback_sql, tuple(fb_filtros_params))
                concepto_fb_ids = {}
                for concepto, dim_id in self.cursor.fetchall():
                    if concepto not in concepto_fb_ids:
                        concepto_fb_ids[concepto] = []
                    concepto_fb_ids[concepto].append(dim_id)
                if len(concepto_fb_ids) > 50:
                    # Ordenar por cantidad de dimensiones compartidas (top 50)
                    from collections import Counter
                    dim_counts = Counter({c: len(ds) for c, ds in concepto_fb_ids.items()})
                    top = dict(dim_counts.most_common(50))
                    concepto_fb_ids = {c: concepto_fb_ids[c] for c in top}
                # Calcular coseno ponderado y agregar nodos nuevos SOLO si superan umbral
                import math
                query_dim_set = set(dimensiones_ids)
                
                # Cargar pesos para fallback
                w_map_fb = {}
                try:
                    self.cursor.execute(f"SELECT id, auto_generada, confianza FROM dimensiones_semanticas WHERE id IN ({dim_ids_str})")
                    for d_id, auto_gen, conf in self.cursor.fetchall():
                        w_map_fb[d_id] = conf if auto_gen else 1.0
                except Exception:
                    pass
                for d_id in query_dim_set:
                    if d_id not in w_map_fb:
                        w_map_fb[d_id] = 1.0
                sum_q2_fb = sum(w_map_fb[d_id]**2 for d_id in query_dim_set)
                
                for concepto, doc_ids in concepto_fb_ids.items():
                    if concepto in conceptos_existentes:
                        continue
                    doc_set = set(doc_ids)
                    shared = len(query_dim_set & doc_set)
                    if shared >= umbral_efectivo:
                        sum_d2 = sum(w_map_fb[d_id]**2 for d_id in doc_set if d_id in w_map_fb)
                        coseno = math.sqrt(sum_d2) / math.sqrt(sum_q2_fb) if sum_q2_fb > 0 else 0.0
                        try:
                            self.cursor.execute(
                                "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                                "FROM largo_plazo WHERE concepto = ?",
                                (concepto,)
                            )
                            row = self.cursor.fetchone()
                            if row and (profundidad == "profundo" or row[4] == "activo"):
                                todos.append(row)
                                origen_scores[concepto] = ("dimensional_fallback", coseno)
                                dim_scores_map[concepto] = coseno
                                conceptos_existentes.add(concepto)
                        except sqlite3.OperationalError:
                            pass
            except sqlite3.OperationalError:
                pass

        # Normalizar BM25 con fórmula estable abs/(abs+1) para que la escala sea
        # consistente entre buscar_por_frase y buscar_por_rafaga (misma que línea ~2693).
        # No usa min-max porque al mezclar resultados de ambas funciones en biorag_recordar
        # las escalas relativas no son comparables entre sí.
        bm25_norm_map = {}
        for concepto, raw_bm25 in bm25_raw.items():
            bm25_norm_map[concepto] = abs(raw_bm25) / (abs(raw_bm25) + 3.0)

        # ─── Capa 5: Score por grupo semántico (WordNet lexnames) ───
        grupo_scores_map = {}
        # Skip WordNet for very short queries (< 3 chars) or very long (> 100 chars, likely garbage/adversarial)
        # NLTK load takes ~3s on first run, and long queries are not legitimate semantic queries
        if 3 <= len(frase) <= 100:
            try:
                from core.clasificador_wordnet import obtener_lexnames_query
                query_lexnames = obtener_lexnames_query(frase, parafrasis_list)
                if query_lexnames:
                    # Obtener IDs de los grupos del query
                    placeholders_ln = ",".join("?" * len(query_lexnames))
                    self.cursor.execute(
                        f"SELECT id FROM grupos_semanticos WHERE nombre IN ({placeholders_ln})",
                        tuple(query_lexnames)
                    )
                    query_grupo_ids = set(r[0] for r in self.cursor.fetchall())

                    if query_grupo_ids:
                        conceptos_todos = [r[1] for r in todos if r[1]]
                        if conceptos_todos:
                            ph_conceptos = ",".join("?" * len(conceptos_todos))
                            ph_grupos = ",".join(str(g) for g in query_grupo_ids)
                            self.cursor.execute(
                                f"SELECT concepto, grupo_id FROM nodo_grupos_semanticos "
                                f"WHERE concepto IN ({ph_conceptos}) "
                                f"AND grupo_id IN ({ph_grupos})",
                                tuple(conceptos_todos)
                            )
                            # Coseno binario: shared / sqrt(|query| × |doc|)
                            import math
                            concepto_grupo_ids = {}
                            for concepto, gid in self.cursor.fetchall():
                                concepto_grupo_ids.setdefault(concepto, set()).add(gid)

                            q_len = len(query_grupo_ids)
                            for concepto, doc_gids in concepto_grupo_ids.items():
                                shared = len(query_grupo_ids & doc_gids)
                                if shared > 0:
                                    grupo_scores_map[concepto] = shared / math.sqrt(
                                        q_len * len(doc_gids)
                                    )
            except ImportError:
                pass  # WordNet no disponible

        # SRL v16.0: Filtrar todos los candidatos por roles semánticos si se especificó buscar_por_rol
        if conceptos_validos_rol is not None:
            todos = [r for r in todos if r[1].lower().strip() in conceptos_validos_rol]

        # Batch fetch synonyms for all retrieved candidates before the final scoring loop
        conceptos_todos = [r[1] for r in todos if r[1]]
        concepto_sinonimos_map = {}
        if conceptos_todos:
            placeholders = ",".join(["?" for _ in conceptos_todos])
            try:
                self.cursor.execute(
                    f"SELECT concepto, sinonimos FROM largo_plazo WHERE concepto IN ({placeholders})",
                    conceptos_todos
                )
                for conc, sinonimos in self.cursor.fetchall():
                    concepto_sinonimos_map[conc] = sinonimos or ""
            except Exception:
                pass

        # Prepare normalized query tokens for symbolic scoring
        from core.fallback_simbolico import _tokenizar_normalizado, score_simbolico_concepto, score_simbolico_sinonimos
        tokens_query = _tokenizar_normalizado(query)

        # Calcular score hibrido para cada resultado (fórmula única 9 señales)
        total = len(todos)
        resultados_con_hibrido = []
        for _, (rowid, concepto, contenido, peso, estado, asociaciones) in enumerate(todos):
            origen, score_capa = origen_scores.get(concepto, ("literal", 0.0))
            dim_score = dim_scores_map.get(concepto, 0.0)
            _q_norm = query.lower().replace(" ", "_").replace("-", "_")
            _c_norm = (concepto or "").lower().replace(" ", "_").replace("-", "_")
            match_exacto = (_q_norm == _c_norm) or (bool(tokens_query) and tokens_query == _tokenizar_normalizado(concepto))
            score_latente = score_capa if origen in ("latente", "expansion") else 0.0
            # v16.0: Boost por inferencia transitiva (sinapsis latentes)
            if usar_inferencia:
                try:
                    self.cursor.execute("""
                        SELECT MAX(peso_atenuado) FROM sinapsis_latentes
                        WHERE (origen = ? OR destino = ?)
                    """, (concepto, concepto))
                    row_lat = self.cursor.fetchone()
                    if row_lat and row_lat[0] and row_lat[0] > score_latente:
                        score_latente = max(score_latente, row_lat[0])
                except Exception:
                    pass
            score_cadena = score_capa if origen == "cadena" else 0.0
            
            # Calculate symbolic similarity for concept name and synonyms, and update ratios
            concepto_s_score = score_simbolico_concepto(tokens_query, concepto)
            concepto_ratio = max(resultados_concepto.get(concepto, 0.0), concepto_s_score)
            
            sinonimos_str = concepto_sinonimos_map.get(concepto, "")
            sinonimos_s_score = score_simbolico_sinonimos(tokens_query, sinonimos_str)
            sinonimos_ratio = max(resultados_semantica.get(concepto, 0.0), sinonimos_s_score)

            score_hibrido = self._calcular_score_hibrido(
                bm25_norm=bm25_norm_map.get(concepto, 0.0),
                dim_score=dim_score,
                peso_sinaptico=peso,
                concepto_ratio=concepto_ratio,
                sinonimos_ratio=sinonimos_ratio,
                score_latente=score_latente,
                score_cadena=score_cadena,
                asoc_count=len([v for v in (asociaciones or "").split(",") if v.strip()]),
                match_exacto=match_exacto,
                grupo_score=grupo_scores_map.get(concepto, 0.0)
            )

            resultados_con_hibrido.append(
                (concepto, contenido, peso, estado, score_hibrido, asociaciones or "")
            )

        # Reordenar por score hibrido descendente
        resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

        # v20.0 Inhibición Lateral GABA en Tiempo Real (Edelman 1987)
        # Si el candidato Top-1 es un atractor fuerte (score >= 0.80),
        # atenúa activamente a los competidores secundarios del mismo nicho (x0.60)
        if resultados_con_hibrido and resultados_con_hibrido[0][4] >= 0.80:
            top_score = resultados_con_hibrido[0][4]
            gaba_resultados = [resultados_con_hibrido[0]]
            for conc, cont, peso, est, sc, asoc in resultados_con_hibrido[1:]:
                if sc < top_score * 0.70:
                    sc = round(sc * 0.60, 4)
                gaba_resultados.append((conc, cont, peso, est, sc, asoc))
            gaba_resultados.sort(key=lambda r: r[4], reverse=True)
            resultados_con_hibrido = gaba_resultados

        # Filtro final con PALABRA_PREFIJO: para queries de una palabra,
        # exigir que aparezca como prefijo de palabra en contenido (del lado de la DB).
        # Esto permite "react" -> "reactive" mientras sigue bloqueando falsos positivos de substring
        # ("culo" no es prefijo de "artículos").
        # Solo aplica a resultados de capas literales (AND/OR/NEAR/unicode/snap/substring).
        # Resultados de capas no literales se preservan para no romper tolerancia a typos,
        # búsqueda semántica/conceptual, ni el fallback simbólico (que normaliza acentos).
        _ORIGENES_NO_LITERALES = {"typo", "expansion", "latente", "cadena", "simbolico", "dimensional_fallback", "semantica", "unicode"}
        query_words = re.findall(r'\w{3,}', query.lower())
        if len(query_words) == 1 and resultados_con_hibrido:
            token = query_words[0]
            literal_results = [
                r for r in resultados_con_hibrido
                if origen_scores.get(r[0], ("literal", 0.0))[0] not in _ORIGENES_NO_LITERALES
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
            pagina_resultados_actualizada = []
            for r in pagina_resultados:
                if r[3] == "dormido":
                    nuevo_peso = min(1.0, r[2] + 0.15)
                    self.cursor.execute(
                        "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                        (nuevo_peso, time.time(), r[0]),
                    )
                    score_nuevo = round(min(1.0, r[4] + 0.10 * (nuevo_peso - r[2])), 4)
                    pagina_resultados_actualizada.append(
                        (r[0], r[1], nuevo_peso, "activo", score_nuevo, r[5])
                    )
                else:
                    pagina_resultados_actualizada.append(r)
            pagina_resultados = pagina_resultados_actualizada
            self.conn.commit()
            pagina_resultados.sort(key=lambda r: r[4], reverse=True)

        # Context window: expandir cada resultado con vecinos por sinapsis
        if context_window and context_window > 0 and pagina_resultados:
            pagina_resultados = self.expandir_contexto_vecinos(
                pagina_resultados,
                depth=context_window,
                profundidad=profundidad,
                preview_chars=preview_chars
            )

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

        # Guardar trazabilidad para mcp_server.py
        self.last_todos = todos
        self.last_origen_scores = origen_scores

        # Phase 2D: Telemetría de búsquedas (non-blocking)
        try:
            top_score = pagina_resultados[0][4] if pagina_resultados else None
            self.cursor.execute(
                "INSERT INTO log_busquedas (query, resultados_count, top_score, creado_en) VALUES (?, ?, ?, ?)",
                (query, total, top_score, time.time())
            )
            self.last_log_id = self.cursor.lastrowid
            self.conn.commit()
        except Exception:
            self.last_log_id = None
            pass

        return pagina_resultados, total

    def actualizar_log_busqueda(self, params_json: str):
        """Actualiza el último log de búsqueda con los params completos de recordar."""
        if not hasattr(self, 'last_log_id') or self.last_log_id is None:
            return
        try:
            self.cursor.execute(
                "UPDATE log_busquedas SET params_json = ? WHERE id = ?",
                (params_json, self.last_log_id)
            )
            self.conn.commit()
        except Exception:
            pass

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

    def buscar_por_rafaga(self, query, rafaga_palabras, pagina=1, limite=None, dimensiones_ids=None):
        """Búsqueda por ráfaga de reminiscencia: emula el proceso humano de recordar.
        
        Cuando la búsqueda normal falla, usa palabras asociadas al azar para encontrar
        nodos dormidos o aislados. Si encuentra un match, crea sinapsis automáticamente
        y despierta el nodo.
        
        Retorna (resultados, total) y lista de sinapsis creadas.
        """
        if pagina < 1:
            pagina = 1
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
            pass  # ponytail: historial_fallos puede estar vacío o malformado
        
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

        # Filtro PALABRA_COMPLETA: previene falsos positivos de FTS5 trigram.
        # "raro" no debe matchear "increíblemente" vía trigram parcial.
        pc_rafaga_clauses = []
        pc_rafaga_params = []
        for p in palabras_validas:
            pc_rafaga_clauses.append(
                "(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)"
            )
            pc_rafaga_params.extend([p, p, p])
        pc_rafaga_clause = " AND (" + " OR ".join(pc_rafaga_clauses) + ")"

        # Buscar en activos — query único con PALABRA_COMPLETA
        try:
            self.cursor.execute(
                "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                "l.estado, l.asociaciones, "
                "bm25(largo_plazo_fts, 5.0, 1.0, 2.0) AS bm25_val "
                "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                + pc_rafaga_clause + " LIMIT ?",
                (fts_terms,) + tuple(pc_rafaga_params) + (limite_batch,)
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
                "l.estado, l.asociaciones, "
                "bm25(largo_plazo_fts, 5.0, 1.0, 2.0) AS bm25_val "
                "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'dormido' "
                + pc_rafaga_clause + " LIMIT ?",
                (fts_terms,) + tuple(pc_rafaga_params) + (limite_batch,)
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
        
        # Fase 2: Calcular score por densidad de coincidencia y boost de dimensiones
        dim_scores_map = {}
        if dimensiones_ids and len(dimensiones_ids) > 0:
            conceptos_todos = [r[1] for r in todos if r[1]]
            if conceptos_todos:
                placeholders = ",".join(["?" for _ in conceptos_todos])
                dim_ids_str = ",".join([str(d) for d in dimensiones_ids])
                dim_sql = f"""
                    SELECT concepto, dimension_id
                    FROM largo_plazo_dimensiones
                    WHERE concepto IN ({placeholders})
                    AND dimension_id IN ({dim_ids_str})
                """
                try:
                    self.cursor.execute(dim_sql, conceptos_todos)
                    # Agrupar IDs por concepto
                    concepto_dim_ids = {}
                    for concepto, dim_id in self.cursor.fetchall():
                        if concepto not in concepto_dim_ids:
                            concepto_dim_ids[concepto] = []
                        concepto_dim_ids[concepto].append(dim_id)
                    # Coseno binario: shared / sqrt(|query| × |doc|)
                    import math
                    query_dim_set = set(dimensiones_ids)
                    query_len = len(query_dim_set)
                    for concepto, doc_ids in concepto_dim_ids.items():
                        doc_set = set(doc_ids)
                        shared = len(query_dim_set & doc_set)
                        if shared > 0:
                            dim_scores_map[concepto] = shared / math.sqrt(query_len * len(doc_set))
                except Exception:
                    dim_scores_map = {}  # ponytail: fallback a scores vacíos si falla el batch dimensional

        # Fase 1.5: Despertar temprano de nodos dormidos en la ráfaga
        todos_actualizados = []
        nodos_despertados = False
        for r in todos:
            rowid, concepto, contenido, peso, estado, asoc, *bm25_rest = r
            if estado == 'dormido':
                nuevo_peso = min(1.0, peso + 0.3)
                self.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                    (nuevo_peso, time.time(), concepto)
                )
                nodos_despertados = True
                todos_actualizados.append((rowid, concepto, contenido, nuevo_peso, 'activo', asoc) + tuple(bm25_rest))
            else:
                todos_actualizados.append(r)
        
        if nodos_despertados:
            self.conn.commit()
        todos = todos_actualizados

        total = len(todos)

        # Normalizar BM25 con fórmula estable para pool pequeño (ráfaga típicamente 1-5 candidatos)
        # abs(raw) / (abs(raw) + 3.0) es sigmoid-like: más negativo (mejor match) → mayor score en [0,1]
        # No usa min-max porque con pocos candidatos la normalización de rango es inestable.
        bm25_norm_map = {}
        for r in todos:
            _, concepto, _, _, _, _, *bm25_rest = r
            raw = bm25_rest[0] if bm25_rest else 0.0
            bm25_norm_map[concepto] = abs(raw) / (abs(raw) + 3.0)

        scored = []
        for r in todos:
            rowid, concepto, contenido, peso, estado, asoc, *bm25_rest = r
            texto_nodo = f"{concepto} {contenido or ''}".lower()
            texto_norm = texto_nodo.replace('_', ' ').replace('-', ' ')
            matches = sum(
                1 for pv in palabras_validas
                if re.search(r'\b' + re.escape(pv.lower()) + r'\b', texto_norm)
            )
            densidad = matches / len(palabras_validas) if palabras_validas else 0.0
            num_asoc = len([v for v in (asoc or "").split(",") if v.strip()]) if asoc else 0
            dim_score = dim_scores_map.get(concepto, 0.0)

            match_exacto = False
            from core.fallback_simbolico import _tokenizar_normalizado
            for pv in palabras_validas:
                _c_norm = (concepto or "").lower().replace(" ", "_").replace("-", "_")
                _pv_norm = pv.lower().replace(" ", "_").replace("-", "_")
                if _pv_norm == _c_norm:
                    match_exacto = True
                    break
                tokens_pv = _tokenizar_normalizado(pv)
                if tokens_pv and tokens_pv == _tokenizar_normalizado(concepto):
                    match_exacto = True
                    break

            score_hibrido = self._calcular_score_hibrido(
                bm25_norm=bm25_norm_map.get(concepto, 0.0),
                dim_score=dim_score,
                peso_sinaptico=peso,
                concepto_ratio=0.0,
                sinonimos_ratio=0.0,
                score_latente=densidad,
                score_cadena=0.0,
                asoc_count=num_asoc,
                match_exacto=match_exacto
            )

            scored.append((concepto, contenido, peso, estado, score_hibrido, asoc or ""))
        
        scored.sort(key=lambda r: r[4], reverse=True)
        
        # Fase 3: Auto-sinapsis y despertar TODOS los nodos dormidos encontrados
        sinapsis_creadas = []
        query_tokens = set(re.findall(r'\w{4,}', query.lower()))
        
        # Primero: despertar TODOS los nodos dormidos (ya realizado en Fase 1.5, bucle omitido)
        
        # Segundo: crear sinapsis solo para los top resultados con score válido
        UMBRAL_SCORE_RAFAGA = 0.5
        for concepto, contenido, peso, estado, score, asoc in scored[:limite]:
            
            # No crear sinapsis si el score es muy bajo (match por trigram parcial)
            if score < UMBRAL_SCORE_RAFAGA:
                continue
            
            # Verificar que al menos una palabra de la ráfaga aparece como palabra completa
            texto_nodo = f"{concepto} {contenido or ''}".lower()
            texto_nodo_norm = texto_nodo.replace('_', ' ').replace('-', ' ')
            alguna_palabra_completa = False
            for pv in palabras_validas:
                if re.search(r'\b' + re.escape(pv.lower()) + r'\b', texto_nodo_norm):
                    alguna_palabra_completa = True
                    break
            if not alguna_palabra_completa:
                continue
            
            # Crear sinapsis entre query y nodo encontrado
            # CRÍTICO: solo crear sinapsis si el token del query aparece como
            # palabra completa en el nodo. Evita sinapsis basura cuando el query
            # es una palabra inventada (ej: "xylqvembra") que no existe en ningún nodo.
            if palabra_ganadora and query_tokens:
                for qt in query_tokens:
                    if qt != concepto and len(qt) >= 4:
                        # Verificar que el token del query existe como palabra completa en el nodo
                        if not re.search(r'\b' + re.escape(qt) + r'\b', texto_nodo_norm):
                            continue
                        # ponytail: solo crear sinapsis si el token existe como concepto en largo_plazo
                        self.cursor.execute(
                            "SELECT 1 FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
                            (qt,)
                        )
                        if not self.cursor.fetchone():
                            continue
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
        
        inicio = (pagina - 1) * limite
        return scored[inicio:inicio + limite], len(scored), sinapsis_creadas

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
