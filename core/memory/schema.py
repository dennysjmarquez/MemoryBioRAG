"""core/memory/schema.py - Módulo de esquema DDL, migraciones y tablas FTS.

Este módulo concentra las rutinas de inicialización de tablas SQLite,
migraciones de esquema, catálogo dimensional y configuración de FTS5.
La función `_crear_estructura_cerebral` se mantiene monolítica intacta (513 líneas)
por deuda técnica documentada en Spec 003 / RNF-1.3.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro.
- Cuerpos intactos con imports internos preservados.
"""

import logging
import sqlite3
import time

logger = logging.getLogger("BioRAG.MemoryStore")


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
            categoria INTEGER DEFAULT 1,
            sustantivos_clave TEXT DEFAULT ''
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
                categoria INTEGER DEFAULT 1,
                sustantivos_clave TEXT DEFAULT ''
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
            sustantivos_clave TEXT DEFAULT '',
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

    # 3b/3d. Catálogo de tipos de dimensión + dimensiones semánticas (15 ejes)
    self._asegurar_catalogo_dimensiones()

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

    # 3i. Tablas de ADN Conceptual y Neocórtex de Sangre (v26.1)
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS adn_firmas (
            concepto TEXT PRIMARY KEY,
            firma_json TEXT NOT NULL,
            actualizado_en REAL,
            FOREIGN KEY (concepto) REFERENCES largo_plazo(concepto) ON DELETE CASCADE
        )
    """)
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS hipotesis_teleologicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposicion TEXT NOT NULL,
            afinidad REAL,
            puente_genetico TEXT,
            sujetos_json TEXT,
            estado TEXT DEFAULT 'por_validar',
            creado_en REAL
        )
    """)

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
    # v25: sustantivos_clave (T2 spec 001) — solo si falta; sin backfill (RF-15). ALTER condicional
    # porque las recreaciones de largo_plazo (needs_recreate) pueden haberla descartado.
    if 'sustantivos_clave' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN sustantivos_clave TEXT DEFAULT ''")

    self.cursor.execute("PRAGMA table_info(corto_plazo)")
    cp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
    if 'valencia_somatica' not in cp_cols_v20:
        self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")
    # v25: sustantivos_clave (T2 spec 001) — solo si falta; sin backfill (RF-15).
    if 'sustantivos_clave' not in cp_cols_v20:
        self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN sustantivos_clave TEXT DEFAULT ''")

    # --- Migración v24.2 (Cuarentena y Prioridad para arquitectura de memoria agente) ---
    self.cursor.execute("PRAGMA table_info(largo_plazo)")
    lp_cols_v24 = [row[1] for row in self.cursor.fetchall()]
    if 'fecha_expiracion' not in lp_cols_v24:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN fecha_expiracion REAL DEFAULT NULL")
    if 'prioridad' not in lp_cols_v24:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN prioridad INTEGER DEFAULT 3")

    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_valencia ON largo_plazo (valencia_somatica)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_fecha_expiracion ON largo_plazo (fecha_expiracion)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_prioridad ON largo_plazo (prioridad)")

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
    # 8. Tabla de cuarentena de sinapsis (soft-delete reversible de la Hormiguita)
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sinapsis_cuarentena (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            tipo TEXT,
            tabla_origen TEXT NOT NULL DEFAULT 'sinapsis',
            peso REAL,
            datos_extra TEXT,
            motivo TEXT DEFAULT '',
            confianza REAL DEFAULT 0.0,
            restaurado INTEGER DEFAULT 0,
            eliminado_en REAL NOT NULL,
            origen_llamada TEXT DEFAULT 'ciclo_daemon'
        )
    """)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_cuarentena_eliminado ON sinapsis_cuarentena(eliminado_en)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_cuarentena_origen ON sinapsis_cuarentena(origen)")
    # 9. Tabla de log de búsquedas (Phase 2D Telemetría)
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_busquedas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            resultados_count INTEGER NOT NULL,
            top_score REAL,
            creado_en REAL NOT NULL,
            util INTEGER DEFAULT NULL,
            params_json TEXT,
            conceptos_top TEXT
        )
    """)
    # 10. Tabla de historial de accesos de nodos (ACT-R Power Law of Practice)
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodo_accesos_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL,
            acceso_timestamp REAL NOT NULL
        )
    """)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodo_accesos_conc_ts ON nodo_accesos_historial(concepto, acceso_timestamp)")
    self._crear_tabla_data()
    self.conn.commit()


def _crear_tabla_data(self):
    """Tabla clave → valor con estado dinámico del motor vectorial.

    Se crea siempre en la inicialización del sistema (DB nueva y existente),
    nunca desde el deploy ni desde el motor. Las constantes estáticas del motor
    viven en core/ppmi_vectorizer.py, no aquí.

    Robusta ante esquemas heredados: si la tabla `data` ya existe sin la
    columna `descripcion` (instalaciones previas), se agrega con ALTER en
    lugar de asumir que el CREATE TABLE IF NOT EXISTS la añade (no lo hace).
    """
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS data (
            clave TEXT PRIMARY KEY,
            valor TEXT,
            descripcion TEXT
        )
    """)
    cols = {row[1] for row in self.cursor.execute("PRAGMA table_info(data)")}
    if 'descripcion' not in cols:
        self.cursor.execute("ALTER TABLE data ADD COLUMN descripcion TEXT")
    claves_iniciales = [
        (
            'ppmi_ultima_reindexacion',
            str(time.time()),
            'Timestamp Unix de la última reindexación completa del motor PPMI+SVD',
        ),
        (
            'ppmi_nodos_acumulados',
            '0',
            'Nodos nuevos acumulados desde la última reindexación completa del motor PPMI+SVD',
        ),
    ]
    for clave, valor, descripcion in claves_iniciales:
        self.cursor.execute("SELECT 1 FROM data WHERE clave = ?", (clave,))
        if not self.cursor.fetchone():
            self.cursor.execute(
                "INSERT OR IGNORE INTO data (clave, valor, descripcion) VALUES (?, ?, ?)",
                (clave, valor, descripcion),
            )


def _crear_tablas_nuevas_si_faltan(self):
    """Crea tablas nuevas (Phase 2D) si no existen en esquemas existentes."""
    # --- Tabla de historial de accesos de nodos (ACT-R Power Law of Practice) ---
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodo_accesos_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL,
            acceso_timestamp REAL NOT NULL
        )
    """)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodo_accesos_conc_ts ON nodo_accesos_historial(concepto, acceso_timestamp)")

# --- Migración v28.1 (Calibración persistente — garantía FP dinámica) ---
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS calibracion_estado (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            umbral_conforme REAL NOT NULL,
            alpha REAL NOT NULL,
            n_negativos INT NOT NULL,
            n_positivos INT NOT NULL,
            n_nodos_corpus INT NOT NULL,
            a_platt REAL,
            b_platt REAL,
            metodo TEXT NOT NULL,
            rango_negativos TEXT,
            fecha_calibracion REAL NOT NULL
        )
    """)
# --- Migración v20.0 (Valencia Somática y Dopamina RPE) ---
    self.cursor.execute("PRAGMA table_info(largo_plazo)")
    lp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
    if 'valencia_somatica' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")
    if 'exitos_dopamina' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN exitos_dopamina INTEGER DEFAULT 0")
    if 'fallos_dopamina' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN fallos_dopamina INTEGER DEFAULT 0")
    if 'sustantivos_clave' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN sustantivos_clave TEXT DEFAULT ''")

    self.cursor.execute("PRAGMA table_info(corto_plazo)")
    cp_cols_v20 = [row[1] for row in self.cursor.fetchall()]
    if 'valencia_somatica' not in cp_cols_v20:
        self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN valencia_somatica REAL DEFAULT 0.0")
    if 'sustantivos_clave' not in cp_cols_v20:
        self.cursor.execute("ALTER TABLE corto_plazo ADD COLUMN sustantivos_clave TEXT DEFAULT ''")

    # --- Migración v24.2 (Cuarentena y Prioridad para arquitectura de memoria agente) ---
    if 'fecha_expiracion' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN fecha_expiracion REAL DEFAULT NULL")
    if 'prioridad' not in lp_cols_v20:
        self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN prioridad INTEGER DEFAULT 3")

    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_valencia ON largo_plazo (valencia_somatica)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_fecha_expiracion ON largo_plazo (fecha_expiracion)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_prioridad ON largo_plazo (prioridad)")

    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_busquedas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            resultados_count INTEGER NOT NULL,
            top_score REAL,
            creado_en REAL NOT NULL,
            util INTEGER DEFAULT NULL,
            params_json TEXT,
            conceptos_top TEXT
        )
    """)
    # Migración: agregar params_json si falta
    try:
        self.cursor.execute("ALTER TABLE log_busquedas ADD COLUMN params_json TEXT")
    except:
        pass  # ya existe
    # Migración: agregar conceptos_top si falta
    try:
        self.cursor.execute("ALTER TABLE log_busquedas ADD COLUMN conceptos_top TEXT")
    except:
        pass  # ya existe

    # Índice para purga eficiente de log_busquedas (O(log n) en DELETE del trigger)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lb_creado_en ON log_busquedas(creado_en)")

    # Triggers de purga a nivel DB — la garantía de que las tablas no crecen sin límite.
    # Patrón idempotente (CREATE TRIGGER IF NOT EXISTS), seguro para DB nueva y existente.
    # recursive_triggers=0, DELETE no re-dispara AFTER INSERT → sin loop.
    # Verificado empíricamente en DB en memoria antes de implementar.
    self.cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_purga_cuarentena
        AFTER INSERT ON sinapsis_cuarentena
        BEGIN
            DELETE FROM sinapsis_cuarentena
            WHERE eliminado_en < (CAST(strftime('%s','now') AS REAL) - 30 * 86400);
        END
    """)
    self.cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_purga_log_busquedas
        AFTER INSERT ON log_busquedas
        BEGIN
            DELETE FROM log_busquedas
            WHERE creado_en < (CAST(strftime('%s','now') AS REAL) - 7 * 86400);
        END
    """)

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

    # Migración v25+ para sinapsis_cuarentena (tabla existe pero puede faltar columna)
    try:
        self.cursor.execute("PRAGMA table_info(sinapsis_cuarentena)")
        sc_cols = [row[1] for row in self.cursor.fetchall()]
        if 'origen_llamada' not in sc_cols:
            self.cursor.execute("ALTER TABLE sinapsis_cuarentena ADD COLUMN origen_llamada TEXT DEFAULT 'ciclo_daemon'")
    except:
        pass  # La tabla no existe aún — CREATE TABLE en _crear_estructura_cerebral la creará

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

    # Catálogo de dimensiones: sembrar tipos y valores faltantes en DB existente
    self._asegurar_catalogo_dimensiones()

    # Índices críticos en tabla sinapsis y largo_plazo (F3: aceleración 2x-30x de consultas al grafo)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_destino ON sinapsis(destino)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_sin_origen ON sinapsis(origen)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_estado ON largo_plazo(estado)")

    self._crear_tabla_data()

    # Concept Hub v29.1 (hubs, bridges con 5 ángulos, nodos y domain dict)
    try:
        from core.concept_hub import crear_tablas as _crear_concept_hub_tablas
        _crear_concept_hub_tablas(self.conn)
    except Exception as _e_ch:
        logger.warning(f"No se pudieron inicializar tablas de Concept Hub: {_e_ch}")

    try:
        from core.lexical_learning import inicializar_tablas_lexicas
        inicializar_tablas_lexicas(self)
    except Exception as _e_lex:
        logger.warning(f"No se pudieron inicializar tablas léxicas: {_e_lex}")

    # v25: asegurar FTS con columna sustantivos_clave en DB existentes — idempotente,
    # reconstruye solo si falta la 4ª columna (mismo check que en _crear_estructura_cerebral).
    self._crear_tabla_fts()

    self.conn.commit()


def _asegurar_catalogo_dimensiones(self):
    """Crea las tablas de catálogo de dimensiones y siembra los 13 tipos + 102 valores.

    Idempotente (INSERT OR IGNORE): corre tanto en DB nueva (desde
    _crear_estructura_cerebral) como en DB existente (desde
    _crear_tablas_nuevas_si_faltan). Los tipos 8-13 y sus dimensiones se
    insertan sin id explícito (AUTOINCREMENT) para no colisionar con ids
    residuales de migraciones anteriores.
    """
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

    self.cursor.execute("""
        INSERT OR IGNORE INTO tipos_dimension (nombre, description) VALUES
            ('cualia', '(El "Modo de explicación"): Las 4 causas aristotélicas / qualia de Pustejovsky (Generative Lexicon). Cómo se explica algo: qué es, de qué está hecho, cómo surgió, para qué sirve.'),
            ('epistemia', '(El "Cómo lo sé"): Evidencialidad (Aikhenvald) + certeza. Fuente y grado de verdad del conocimiento: directo, verificado, inferido, reportado, hipótesis, obsoleto.'),
            ('escala_abstraccion', '(El "Nivel de generalidad"): Del caso concreto a la ley universal. Instancia, patrón, principio, ley/modelo, metáfora.'),
            ('centralidad_identitaria', '(El "Cuánto es mío"): Self-reference effect. Grado en que el contenido define o toca la identidad.'),
            ('textura_experiencial', '(El "Cómo se sentía estar ahí"): Cualidad fenoménica del momento vivido (ínsula). Flujo, tensión, desorientación, rutina, presencia plena.'),
            ('modalidad', '(El "Debo/Puedo"): Modalidad deóntica (Palmer). Obligación, prohibición, permiso, capacidad.')
    """)

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
    self.cursor.execute("""
        INSERT OR IGNORE INTO dimensiones_semanticas (name, description, tipo_id) VALUES
            -- CUALIA (4): las 4 causas aristotélicas / qualia de Pustejovsky
            ('formal_categoria', 'Qué ES: su tipo, categoría o clase esencial', (SELECT id FROM tipos_dimension WHERE nombre='cualia')),
            ('constitutiva_composicion', 'De qué está HECHO: partes, componentes, estructura', (SELECT id FROM tipos_dimension WHERE nombre='cualia')),
            ('agentiva_origen', 'CÓMO SURGIÓ: origen, causa, proceso de creación', (SELECT id FROM tipos_dimension WHERE nombre='cualia')),
            ('telica_funcion', 'PARA QUÉ SIRVE: propósito, función, fin', (SELECT id FROM tipos_dimension WHERE nombre='cualia')),
            -- EPISTEMIA (6): evidencialidad + certeza
            ('directa_experiencial', 'Lo vi, lo viví, lo experimenté con mis propios sentidos', (SELECT id FROM tipos_dimension WHERE nombre='epistemia')),
            ('verificada', 'Hecho comprobado o contrastado con evidencia', (SELECT id FROM tipos_dimension WHERE nombre='epistemia')),
            ('inferida', 'Lo deduje por lógica o razonamiento a partir de señales', (SELECT id FROM tipos_dimension WHERE nombre='epistemia')),
            ('reportada_externa', 'Me lo contaron o lo leí: información de segunda mano', (SELECT id FROM tipos_dimension WHERE nombre='epistemia')),
            ('hipotetica', 'Suposición o conjetura no confirmada: "creo que", "podría ser"', (SELECT id FROM tipos_dimension WHERE nombre='epistemia')),
            ('obsoleta', 'Quedó desactualizado o fue refutado por información nueva', (SELECT id FROM tipos_dimension WHERE nombre='epistemia')),
            -- ESCALA_ABSTRACCION (5): del caso concreto a la ley universal
            ('instancia', 'Caso concreto y particular: un evento, un dato, un ejemplo', (SELECT id FROM tipos_dimension WHERE nombre='escala_abstraccion')),
            ('patron', 'Regularidad que se repite en varios casos', (SELECT id FROM tipos_dimension WHERE nombre='escala_abstraccion')),
            ('principio', 'Regla general o guía de acción que se desprende de los casos', (SELECT id FROM tipos_dimension WHERE nombre='escala_abstraccion')),
            ('ley_modelo', 'Ley, teoría o modelo formal que explica cómo funciona algo', (SELECT id FROM tipos_dimension WHERE nombre='escala_abstraccion')),
            ('metafora', 'Representación figurativa: una cosa entendida como otra', (SELECT id FROM tipos_dimension WHERE nombre='escala_abstraccion')),
            -- CENTRALIDAD_IDENTITARIA (5): self-reference effect
            ('nucleo_identitario', 'Define quién soy. Constitutivo de mi identidad y valores', (SELECT id FROM tipos_dimension WHERE nombre='centralidad_identitaria')),
            ('relevante_personal', 'Me toca a mí directamente: mi historia, mi gente, mi camino', (SELECT id FROM tipos_dimension WHERE nombre='centralidad_identitaria')),
            ('relevante_contextual', 'Importante para el contexto o proyecto actual, no para mi ser', (SELECT id FROM tipos_dimension WHERE nombre='centralidad_identitaria')),
            ('informacion_externa', 'Dato del mundo que no me involucra personalmente', (SELECT id FROM tipos_dimension WHERE nombre='centralidad_identitaria')),
            ('impersonal', 'Ajeno a toda identidad: dato neutro, genérico, técnico', (SELECT id FROM tipos_dimension WHERE nombre='centralidad_identitaria')),
            -- TEXTURA_EXPERIENCIAL (5): cualidad fenoménica del momento vivido
            ('flujo', 'Inmersión total: el tiempo se disuelve, hay fluidez', (SELECT id FROM tipos_dimension WHERE nombre='textura_experiencial')),
            ('tension', 'Presión, esfuerzo sostenido, alerta, estrés', (SELECT id FROM tipos_dimension WHERE nombre='textura_experiencial')),
            ('desorientacion', 'No saber qué está pasando ni cómo seguir', (SELECT id FROM tipos_dimension WHERE nombre='textura_experiencial')),
            ('rutina', 'Algo habitual, mecánico, esperado', (SELECT id FROM tipos_dimension WHERE nombre='textura_experiencial')),
            ('presencia_plena', 'Conciencia vivida del momento: aquí y ahora', (SELECT id FROM tipos_dimension WHERE nombre='textura_experiencial')),
            -- MODALIDAD (4): modalidad deóntica
            ('obligacion', 'Debo, tengo que: imposición o deber', (SELECT id FROM tipos_dimension WHERE nombre='modalidad')),
            ('prohibicion', 'No debo, está prohibido: veda explícita', (SELECT id FROM tipos_dimension WHERE nombre='modalidad')),
            ('permiso', 'Puedo, está permitido: luz verde', (SELECT id FROM tipos_dimension WHERE nombre='modalidad')),
            ('capacidad', 'Soy capaz o no soy capaz de hacerlo: poder de hecho', (SELECT id FROM tipos_dimension WHERE nombre='modalidad'))
    """)
    self.conn.commit()


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

    if fts_existe:
        # v25: verificar columna sustantivos_clave (T2) — si falta, rebuild para agregar la 4ª columna
        try:
            self.cursor.execute("SELECT sustantivos_clave FROM largo_plazo_fts LIMIT 0")
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
                sustantivos_clave,
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
            INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos, sustantivos_clave)
            VALUES (new.rowid, new.concepto, new.contenido, new.sinonimos, COALESCE(new.sustantivos_clave, ''));
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
            INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos, sustantivos_clave)
            VALUES (new.rowid, new.concepto, new.contenido, new.sinonimos, COALESCE(new.sustantivos_clave, ''));
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
    """Puebla la FTS desde datos existentes, incluyendo sinonimos y sustantivos_clave."""
    self.cursor.execute("SELECT COUNT(*) FROM largo_plazo_fts")
    if self.cursor.fetchone()[0] > 0:
        return
    try:
        self.cursor.execute("SELECT rowid, concepto, contenido, sinonimos, COALESCE(sustantivos_clave, '') FROM largo_plazo")
    except sqlite3.OperationalError:
        self.cursor.execute("SELECT rowid, concepto, contenido, '' as sinonimos, '' as sustantivos_clave FROM largo_plazo")
    for row in self.cursor.fetchall():
        rowid, concepto, contenido = row[0], row[1], row[2]
        sinonimos = row[3] if len(row) > 3 else ""
        sust_sk = row[4] if len(row) > 4 else ""
        self.cursor.execute(
            "INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos, sustantivos_clave) VALUES (?, ?, ?, ?, ?)",
            (rowid, concepto or "", contenido or "", sinonimos or "", sust_sk or "")
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
