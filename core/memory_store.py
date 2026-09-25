import os
import sqlite3
import time
import re
import sys
import math
import json
import logging
import numpy as np
from collections import deque

logger = logging.getLogger("BioRAG.MemoryStore")

from core.stemmer_es import _quitar_acentos

# Auto-cargar .env.local al importar (antes de leer cualquier variable de entorno)
from config import _load_env_local

try:
    from core.calibracion import (zscore_por_query, fusion_rrf, FusionLogistica,
                                   CalibradorPlatt, calibracion_isotonica,
                                   UmbralConforme, mmr)
except ImportError:
    zscore_por_query = fusion_rrf = FusionLogistica = CalibradorPlatt = None
    calibracion_isotonica = UmbralConforme = mmr = None
_load_env_local()

# Pre-cargar WordNet al importar para evitar latencia de 3s en primera consulta semántica
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    obtener_lexnames_query("test")  # Trigger NLTK/WordNet lazy load
except Exception:
    pass  # WordNet opcional, ignorar si falla

# =============================================================================
# Constantes, flags de configuración y re-exports hacia core.memory.constants
# =============================================================================

from core.memory import constants
from core.memory.constants import (
    CANDIDATOS_SIMILITUD, MAX_SALTOS_CADENA, LIMITE_DEFAULT, UMBRAL_JACCARD,
    RAFTAGA_ACTIVA, THRESHOLD_RAFTAGA, LIMITE_RAFTAGA, LIMITE_EVOCACION,
    JSD_WEIGHT, JSD_ADAPTATIVO, JSD_ADAPT_BASE, JSD_ADAPT_LARGO, JSD_ADAPT_CORTO, JSD_ADAPT_NT,
    DMN_SINTESIS_ACTIVA, DMN_SINTESIS_MAX, DMN_SINTESIS_PESO,
    EPISODIO_TEMPORAL_PESO, EPISODIO_TEMPORAL_ACTIVO, EPISODIO_VENTANA_HORAS, EPISODIO_LIMITE, EPISODIO_BUCKET_SEG,
    ANALOGIA_PESO, ANALOGIA_DETECTAR,
    CAMPO_POTENCIAL_PESO, CAMPO_SIGMA, CAMPO_K,
    EPISTEMICO_METADATA,
    MULTIHOP_EXPANSION, MULTIHOP_MAX_TOTAL, MULTIHOP_PRIOR,
    BAYESIAN_BM25, BAYESIAN_BM25_ALPHA,
    RERANKING_JACCARD_ACTIVO, RERANKING_JACCARD_ALPHA, RERANKING_JACCARD_GATE, RERANKING_JACCARD_TOPK, RERANKING_JACCARD_WINDOW,
    SDM_FALLBACK_ACTIVO, SDM_FALLBACK_K,
    QCR_IDF_ACTIVO, QCR_IDF_UMBRAL,
    QCR_TYPO_ACTIVA, DIM_RESONANCIA, DIM_RESONANCIA_K, DIM_ESCAPE, DIM_ESCAPE_T, QCR_TYPO_PISO, QCR_TYPO_DIST,
    NCD_PESO, NCD_ZLIB_LEVEL,
    GABA_ACTIVO,
    PPMI_VECTOR_WEIGHT,
    ADN_RANKING_ENABLED, ADN_PESO, ADN_MAX_EXPANSION, ADN_UMBRAL_ASOCIACION,
    _qcr_levenshtein, _qcr_todos_cercanos, normalizar_sustantivos_clave,
)
from core.memory import comms
from core.memory import telemetry
from core.memory import synapses
from core.memory import episodes

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
            from core.paths import resolve_db_path
            self.db_path = resolve_db_path()
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Conectar a SQLite
        # check_same_thread=False: MCP/WAL reutiliza la instancia entre tools.
        self.conn = sqlite3.connect(self.db_path, timeout=60, check_same_thread=False)
        self._persistente = False
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA cache_size=-64000")
            self.conn.execute("PRAGMA mmap_size=268435456")
        except sqlite3.OperationalError:
            pass
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
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='largo_plazo'")
        if not self.cursor.fetchone():
            self._crear_estructura_cerebral()
        self._crear_tablas_nuevas_si_faltan()
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Trazaabilidad: datos de la última búsqueda para mcp_server.py
        self.last_todos = []
        self.last_origen_scores = {}
        # Signal #14 (v29): metadatos del contrato de degradación asociativa.
        # Con flag OFF queda con valores vacíos por defecto; con flag ON, el
        # último enriquecimiento ADN deja aquí su estado epistémico (Política A).
        self.last_estado_epistemico = {
            "estado": "no_evaluado",
            "confianza_epistemica": 0.0,
            "indice_adn_listo": False,
            "tipo_relacion_por_concepto": {},
            "genes_compartidos_por_concepto": {},
            "candidatos_adn_consultados": 0,
        }
        self.last_parent_map = {}  # parent pointers from last spreading activation
        # Buffer circular de memoria de trabajo (v19.0 Context Window)
        self._context_window = deque(maxlen=10)
        self.dmn = None
        self._dmn_sintesis_hecha = False
        if constants.DMN_SINTESIS_ACTIVA:
            try:
                from core.dmn_engine import sintetizar_sinapsis_dmn
                sintetizar_sinapsis_dmn(self, max_n=constants.DMN_SINTESIS_MAX)
                self._dmn_sintesis_hecha = True
            except Exception:
                pass
        # v22.1: Cache for thematic scores (precomputed once)
        self._thematic_scores_cache = None
        self._thematic_profiles_cache = None
        self._thematic_idf_cache = None
        # Signal #13 (v26.0): Índice de vectores PPMI+SVD (lazy-loaded, ~320KB en RAM)
        # Solo se carga si BIORAG_PPMI_WEIGHT > 0 para cero overhead cuando está OFF
        self._ppmi_index = None
        if constants.PPMI_VECTOR_WEIGHT > 0.0:
            try:
                from core.ppmi_hybrid_search import IndicesBioRAG
                self._ppmi_index = IndicesBioRAG(str(self.db_path))
            except Exception:
                pass  # Silencioso: si la tabla no existe aún, se crea en el próximo sueño

        # v26.1: Neocórtex de Sangre y ADN Conceptual (solo si PPMI está activo:
        # el ADN se construye sobre vectores PPMI/SVD, sin ellos no tiene señales)
        self.neocortex = None
        self.adn_engine = None
        if self._ppmi_index is not None:
            try:
                from core.neocortex_teleologico import NeocortexTeleologico
                from core.adn_conceptual import ADNConceptualEngine
                self.neocortex = NeocortexTeleologico(str(self.db_path))
                self.adn_engine = ADNConceptualEngine(db_path=str(self.db_path), indices=self._ppmi_index)
                # El índice ADN v29 se carga desde artefactos persistidos; nunca se recalcula aquí.
                self._adn_pendiente_recalculo = False
            except Exception as e:
                logger.warning(f"No se pudo inicializar el Neocórtex de Sangre: {e}")

        # v28.1: Componentes de calibración y decisión estadística (FP controlado)
        self._platt_calibrador = None
        self._umbral_conforme = None
        self._fusion_logistica = None
        self._calibracion_entrenada = False
        self._calibracion_meta = None

        # v28.1: Cargar calibración persistida si existe (rápida, sin búsquedas).
        # Esto le da al path caliente el umbral/Platt ya calibrados contra el
        # corpus del momento en que se persistieron. Si el corpus creció o se
        # redujo después, `calibrar_y_persistir()` lo detecta por n_nodos y
        # recalcula la garantía.
        try:
            if getattr(self, 'cursor', None) is not None:
                self._cargar_calibracion_persistida()
        except Exception as _e_cal:
            logger.debug(f"Calibración persistida no cargada: {_e_cal}")

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
        if nombre in self._cat_cache:
            return self._cat_cache[nombre]

        # Mapeo insensible a mayúsculas y alias español/inglés
        norm_map = {
            'proyecto': 'Project', 'project': 'Project',
            'leccion': 'Lesson', 'lección': 'Lesson', 'lesson': 'Lesson',
            'sistema': 'System', 'system': 'System',
            'arquitectura': 'Architecture', 'architecture': 'Architecture',
            'perfil': 'Profile', 'profile': 'Profile',
            'personal': 'Personal',
            'principio': 'Principle', 'principle': 'Principle',
            'protocolo': 'Protocol', 'protocol': 'Protocol',
            'cognicion': 'Cognition', 'cognición': 'Cognition', 'cognition': 'Cognition',
            'metacognicion': 'Cognition', 'metacognición': 'Cognition',
            'relacion': 'Relation', 'relación': 'Relation', 'relation': 'Relation',
            'general': 'General', 'solucion': 'Lesson', 'solución': 'Lesson'
        }
        n_clean = str(nombre).strip().lower()
        if n_clean in norm_map and norm_map[n_clean] in self._cat_cache:
            return self._cat_cache[norm_map[n_clean]]

        for k, v in self._cat_cache.items():
            if k.lower() == n_clean:
                return v

        validas = ", ".join(sorted(self._cat_cache.keys()))
        raise ValueError(f"Categoria '{nombre}' no existe. Validas: {validas}")

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

    def _cargar_firmas_adn(self):
        """Carga las firmas de ADN persistidas en la DB al motor en RAM."""
        if not self.adn_engine:
            return
        self.cursor.execute("SELECT concepto, firma_json FROM adn_firmas")
        for concepto, firma_json in self.cursor.fetchall():
            try:
                firma = json.loads(firma_json)
                self.adn_engine.registrar_concepto(concepto, firma)
            except Exception:
                continue

    def _persistir_firma_adn(self, concepto: str, firma: dict):
        """Persiste una firma genética en la base de datos."""
        try:
            firma_json = json.dumps(firma)
            self.cursor.execute("""
                INSERT OR REPLACE INTO adn_firmas (concepto, firma_json, actualizado_en)
                VALUES (?, ?, ?)
            """, (concepto, firma_json, time.time()))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Error al persistir ADN para {concepto}: {e}")

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

    # =========================================================================
    # TECNOLOGÍA COGNITIVA: Ley de Potencia de Práctica de ACT-R (Anderson & Lebiere, 1998)
    # Modelo formal de activación de nivel base (Base-Level Activation) y retención biológica:
    # B_i = ln( \sum_{k=1}^n t_k^{-d} ), con d = 0.5.
    # Modula la tasa de olvido pasivo (LTD) en el ciclo de consolidación de sueño.
    # =========================================================================

    def _registrar_acceso_nodo(self, concepto: str, ts: float = None):
        """Registra un evento de acceso para el cálculo de activación base ACT-R.
        
        Fundamento científico:
            Ley de Potencia de la Práctica (Newell & Rosenbloom, 1981; Anderson & Lebiere, 1998).
            Implementa un búfer circular de tamaño acotado (máximo 10 marcas temporales)
            en la tabla `nodo_accesos_historial` con ordenamiento por recencia y evicción FIFO.
        """
        if not concepto:
            return
        if ts is None:
            ts = time.time()
        try:
            self.cursor.execute(
                "INSERT INTO nodo_accesos_historial (concepto, acceso_timestamp) VALUES (?, ?)",
                (concepto, ts)
            )
            self.cursor.execute("""
                DELETE FROM nodo_accesos_historial
                WHERE concepto = ?
                  AND id NOT IN (
                      SELECT id FROM nodo_accesos_historial
                      WHERE concepto = ?
                      ORDER BY acceso_timestamp DESC
                      LIMIT 10
                  )
            """, (concepto, concepto))
        except Exception:
            pass

    def _calcular_base_level_actr(self, concepto: str, ahora: float = None):
        r"""Calcula la activación de nivel base de la arquitectura cognitiva ACT-R:
        
        Ecuación:
            B_i = ln( \sum_{k=1}^n t_k^{-d} ), con parámetro canónico d = 0.5
            donde t_k es el tiempo transcurrido (en segundos) desde el k-ésimo acceso.
            
        Retorna:
            float con el nivel de activación B_i, o None si el concepto no posee
            registros de acceso previos en el historial.
        """
        if ahora is None:
            ahora = time.time()
        try:
            self.cursor.execute(
                "SELECT acceso_timestamp FROM nodo_accesos_historial WHERE concepto = ? ORDER BY acceso_timestamp DESC LIMIT 10",
                (concepto,)
            )
            rows = self.cursor.fetchall()
            if rows:
                suma_potencias = sum(max(1.0, ahora - r[0]) ** (-0.5) for r in rows)
                return math.log(max(1e-9, suma_potencias))
        except Exception:
            pass
        return None

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

    def _idf_tokens_qcr(self, tokens):
        """IDF de tokens de query para QCR. Cache por instancia. DF vía FTS5 MATCH (índice), no scan del corpus."""
        if not getattr(self, "_qcr_idf_cache", None):
            self._qcr_idf_cache = {}
        if getattr(self, "_qcr_n_docs", None) is None:
            try:
                self._qcr_n_docs = max(
                    1, int(self.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0] or 1)
                )
            except Exception:
                self._qcr_n_docs = 1
        out = {}
        n = self._qcr_n_docs
        for t in tokens:
            if t in self._qcr_idf_cache:
                out[t] = self._qcr_idf_cache[t]
                continue
            df = 0
            try:
                safe = (t or "").replace('"', "")
                if safe:
                    self.cursor.execute(
                        "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
                        (f'"{safe}"',),
                    )
                    df = int(self.cursor.fetchone()[0] or 0)
            except Exception:
                df = 0
            idf = math.log((n + 1) / (df + 1)) + 1.0
            self._qcr_idf_cache[t] = idf
            out[t] = idf
        return out

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

    def _fallback_busqueda_predicados(self, frase, limite=10):
        """
        Fallback Causal SRL v1.0.
        Se ejecuta cuando la búsqueda tradicional por 8 señales arroja 0 candidatos o score < 0.35.
        Extrae o tokeniza la query y busca coincidencias por roles semánticos en la tabla predicados.
        """
        if not frase or len(frase.strip()) < 3:
            return []

        import re
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

    def percibir_corto_plazo(self, concepto, contenido, sinonimos="", categoria="General", dimensiones=None, predicados=None, valencia_somatica=0.0, sustantivos_clave=""):
        """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo).
        Si el concepto ya existe en corto plazo, concatena contenido y mergea sinónimos.
        dimensiones: dict {tipo_nombre: [valores]} para indexación de 5 ejes.
        predicados: list[dict] con {sujeto, accion, objeto, contexto} para SRL v16.0.
        valencia_somatica: float [0.0, 1.0] para marcadores somáticos (v20.0).
        sustantivos_clave: str (v25 spec 001) — centro de gravedad temático, ya normalizado por
        la tool (aprender/guardar). Sobrescribe el valor previo (no merge): si el tema cambió,
        los sustantivos se reemplazan (Decisión 2 del plan 001). Aditivo: default '' = nodos
        legacy sin sustantivos, el comportamiento previo no cambia."""
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
            INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria, valencia_somatica, sustantivos_clave)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (key, contenido_final, time.time(), sinonimos_final, cat_id, float(valencia_somatica or 0.0), sustantivos_clave or ""))

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
        # v29: el recuerdo se marca como cambio estructural. El ADN y los vecinos
        # se reconstruyen de forma batch en el siguiente ciclo de sueño DMN; no hay
        # inferencia vectorial ni recorrido del corpus en el camino de escritura.
        self._adn_pendiente_recalculo = True
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
        
        # Reindex SDM selectivo: extremos de sinapsis NUEVAS creadas aquí
        dirty = set()
        
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
                    # v26.2: Cierre Triádico en co-ocurrencia — exige vecinos/dimensiones comunes o bootstrap (<=5 sinapsis)
                    try:
                        from core.sinapsis import _vecinos_comunes, _dimensiones_comunes, _CIERRE_TRIADICO
                        if _CIERRE_TRIADICO:
                            vec_com = _vecinos_comunes(self.cursor, c1, c2)
                            dim_com = _dimensiones_comunes(self.cursor, c1, c2) if vec_com == 0 else 1
                            self.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?", (c1, c1))
                            sinap_exist = self.cursor.fetchone()[0]
                            if vec_com == 0 and dim_com == 0 and sinap_exist > 5:
                                continue  # Rechazar: coincidencia tokenizada entre dominios aislados
                    except Exception:
                        pass

                    peso = min(0.9, 0.3 + len(shared) * 0.1)
                    self.cursor.execute(
                        "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                        (c1, c2)
                    )
                    es_nueva = self.cursor.fetchone() is None
                    self.cursor.execute(
                        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, ?, 'co_ocurrencia', ?) "
                        "ON CONFLICT(origen, destino) DO UPDATE SET "
                        "peso = MIN(0.9, peso + 0.1), ultimo_uso = ?",
                        (c1, c2, peso, time.time(), time.time())
                    )
                    if es_nueva:
                        dirty.add(c1)
                        dirty.add(c2)
        
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
                        # v26.2: Cierre Triádico en comunicaciones
                        try:
                            from core.sinapsis import _vecinos_comunes, _dimensiones_comunes, _CIERRE_TRIADICO
                            if _CIERRE_TRIADICO:
                                vec_com = _vecinos_comunes(self.cursor, c1, c2)
                                dim_com = _dimensiones_comunes(self.cursor, c1, c2) if vec_com == 0 else 1
                                self.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?", (c1, c1))
                                sinap_exist = self.cursor.fetchone()[0]
                                if vec_com == 0 and dim_com == 0 and sinap_exist > 5:
                                    continue
                        except Exception:
                            pass

                        self.cursor.execute(
                            "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                            (c1, c2)
                        )
                        es_nueva = self.cursor.fetchone() is None
                        self.cursor.execute(
                            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                            "VALUES (?, ?, 0.4, 'co_ocurrencia', ?) "
                            "ON CONFLICT(origen, destino) DO UPDATE SET "
                            "peso = MIN(0.9, peso + 0.05), ultimo_uso = ?",
                            (c1, c2, time.time(), time.time())
                        )
                        if es_nueva:
                            dirty.add(c1)
                            dirty.add(c2)
        except Exception:
            pass  # Tabla comunicaciones puede no tener datos
        
        self.conn.commit()

        if dirty:
            try:
                from core.sdm import marcar_sdm_dirty
                marcar_sdm_dirty(self, dirty)
            except Exception:
                pass

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
        return telemetry._crear_tabla_historial_si_falta(self)

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
        self.cursor.execute("SELECT concepto, contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0), COALESCE(sustantivos_clave, '') FROM corto_plazo")
        recuerdos_sesion = self.cursor.fetchall()
        
        for concepto, contenido, sinonimos, cat_id, val_somatica, sk_corto in recuerdos_sesion:
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
                
                self.cursor.execute("SELECT contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0), COALESCE(sustantivos_clave, '') FROM largo_plazo WHERE concepto = ?", (concepto,))
                datos_actuales = self.cursor.fetchone()
                nuevo_contenido = datos_actuales[0] + f" | Actualización: {contenido}"
                sinonimos_exist = [s.strip() for s in (datos_actuales[1] or "").split(",") if s.strip()]
                sinonimos_nuevos = [s.strip() for s in (sinonimos or "").split(",") if s.strip() and s.strip() not in sinonimos_exist]
                sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
                cat_id = datos_actuales[2] or cat_id
                val_final = max(datos_actuales[3], val_somatica)
                # CL-6 (RF-6): sustantivos_clave del largo se sobrescribe SOLO si corto_plazo trae valor no vacío.
                # Si corto_plazo viene vacío, se preserva el valor ya consolidado en largo_plazo (RF-15).
                sk_final = (sk_corto or "").strip() if (sk_corto or "").strip() else (datos_actuales[4] or "")
                
                self.cursor.execute("""
                    UPDATE largo_plazo 
                    SET contenido = ?, peso_sinaptico = ?, estado = 'activo', ultimo_acceso = ?, sinonimos = ?, categoria = ?, valencia_somatica = ?, sustantivos_clave = ?
                    WHERE concepto = ?
                """, (nuevo_contenido, nuevo_peso, time.time(), sinonimos_final, cat_id, val_final, sk_final, concepto))
                
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
                    INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos, creado_en, valencia_somatica, sustantivos_clave)
                    VALUES (?, ?, ?, 1.0, 'activo', '', ?, ?, ?, ?, ?)
                """, (concepto, cat_id or 1, contenido, ahora, sinonimos or "", ahora, val_somatica, (sk_corto or "").strip()))
                
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
        for concepto, contenido, _, _, _, _ in recuerdos_sesion:
            auto_vincular(self, concepto, contenido)

        # Clasificación simbólica: WordNet lexnames para cada nodo consolidado
        for concepto, contenido, sinonimos, _, _, _ in recuerdos_sesion:
            self._clasificar_nodo_wordnet(concepto, contenido, sinonimos or "")

        # Fase 2: Auto-generar sinapsis por co-ocurrencia
        # Si dos conceptos aparecieron en la misma sesión (corto_plazo), co-ocurren.
        # También analiza comunicaciones para detectar co-ocurrencia en mensajes.
        self._auto_generar_co_ocurrencia(recuerdos_sesion)

        # E10: aristas dmn_synthesized (tope, nodos activos, dim o co-ocurrencia).
        if constants.DMN_SINTESIS_ACTIVA:
            try:
                from core.dmn_engine import sintetizar_sinapsis_dmn
                sintetizar_sinapsis_dmn(self, max_n=constants.DMN_SINTESIS_MAX)
            except Exception:
                pass

        # Inferencia transitiva: recalcular sinapsis latentes (v16.0)
        # max_saltos=2: cubre A→B→C (transitivo de 1 intermediario), cobertura suficiente
        # para laptops. FACTOR_DECAY=0.7 hace que el 3er salto apenas supere el umbral 0.05
        # (0.7³ × 0.5 ≈ 0.17 para aristas fuertes), por lo que los saltos 3 aportan poco valor real.
        try:
            from core.inferencia_transitiva import calcular_sinapsis_latentes
            n_latentes = calcular_sinapsis_latentes(self, max_saltos=2)
            if n_latentes:
                print(f"[Inferencia Transitiva] {n_latentes} sinapsis latentes calculadas.")
        except Exception as e:
            print(f"[Inferencia Transitiva] Fallback silencioso: {e}")

        # 2. Decaimiento Pasivo (LTD): Power Law of Practice (ACT-R Base-Level Activation)
        # B_i = ln(sum_{k=1}^n t_k^{-0.5}) modula la tasa de olvido en vez del -0.05 estático.
        # Nodos protegidos (valencia_somatica >= 0.8 o categoria Principle/Protocol) son inmunes a LTD pasivo.
        # Prioridad P0-P1: inmunes. P2: 50% LTD. P3: normal (1.0). P4: 1.5x. P5: 2.5x.
        # Sin prioridad asignada (NULL): 1.5x (intermedio, no el más volátil).
        self.cursor.execute("""
            SELECT l.concepto, l.peso_sinaptico, COALESCE(c.decay_rate, 1.0),
                   CASE
                       WHEN l.prioridad = 2 THEN 0.5
                       WHEN l.prioridad = 3 THEN 1.0
                       WHEN l.prioridad = 4 THEN 1.5
                       WHEN l.prioridad >= 5 THEN 2.5
                       WHEN l.prioridad IS NULL THEN 1.5
                       ELSE 0
                   END AS mult_prio
            FROM largo_plazo l
            LEFT JOIN categories c ON c.id = l.categoria
            WHERE l.estado = 'activo'
              AND (l.prioridad IS NULL OR l.prioridad NOT IN (0, 1))
              AND l.concepto NOT IN (SELECT concepto FROM corto_plazo)
              AND COALESCE(l.valencia_somatica, 0.0) < 0.80
              AND (l.categoria IS NULL OR l.categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
        """)
        candidatos_ltd = self.cursor.fetchall()
        ahora_sueno = time.time()
        for concepto_ltd, peso_act, dec_cat, mult_prio in candidatos_ltd:
            b_i = self._calcular_base_level_actr(concepto_ltd, ahora=ahora_sueno)
            # Modulación ACT-R (Ley de Potencia de Práctica/Olvido de Anderson & Lebiere):
            # Si hay accesos, B_i modula el decaimiento de forma exponencial inversa:
            # - B_i alto (uso frecuente/reciente): decae menos (protección contra olvido).
            # - B_i bajo (uso lejano): decae más rápido (olvido acelerado).
            # - Sin accesos previos registrados: decae a la tasa estándar 0.05.
            if b_i is not None:
                decay_base = max(0.01, min(0.10, 0.05 * math.exp(-0.5 * b_i)))
            else:
                decay_base = 0.05
            nuevo_peso = round(max(0.0, peso_act - decay_base * dec_cat * mult_prio), 2)
            self.cursor.execute(
                "UPDATE largo_plazo SET peso_sinaptico = ? WHERE concepto = ?",
                (nuevo_peso, concepto_ltd)
            )

        # 2b. Decay Sináptico: reducir peso de conexiones no usadas en 7+ días
        self.cursor.execute("""
            UPDATE sinapsis
            SET peso = ROUND(MAX(0.0, peso * 0.95), 3)
            WHERE ultimo_uso IS NOT NULL
              AND ultimo_uso < strftime('%s', 'now') - 604800
        """)
        # Podar sinapsis muertas (F4: guiado termodinamico si flag ON).
        try:
            from core.dmn_engine import TERMODINAMICA_DMN, podar_ltd_guiado
            _f4_ltd = bool(TERMODINAMICA_DMN)
        except Exception:
            _f4_ltd = False
        if _f4_ltd:
            try:
                podar_ltd_guiado(self)
            except Exception:
                self.cursor.execute("DELETE FROM sinapsis WHERE peso < 0.05")
        else:
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
              AND (prioridad IS NULL OR prioridad NOT IN (0, 1))
              AND COALESCE(valencia_somatica, 0.0) < 0.80
              AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
        """)
        
        # Detectar quiénes se durmieron POR LTD (solo los que estaban activos y ahora son dormidos)
        self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'dormido'")
        dormidos_after_ltd = set(row[0] for row in self.cursor.fetchall())
        nodos_dormidos_ltd = activos_antes_dormir & dormidos_after_ltd  # intersección: estaban activos Y ahora son dormidos

        # 4. Inhibición Lateral Activa (Control de Saturación de Energía)
        # Excluir cuarentena de conteo activo y energía
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
            # Obtener los nodos activos ordenados de menor peso y más antiguos (excluyendo inmunes y cuarentena)
            self.cursor.execute("""
                SELECT concepto, peso_sinaptico FROM largo_plazo 
                WHERE estado = 'activo' 
                  AND (prioridad IS NULL OR prioridad NOT IN (0, 1))
                  AND COALESCE(valencia_somatica, 0.0) < 0.80
                  AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
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
                  AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
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
        # Omitido en cada ciclo: corre búsquedas reales que actualizan ultimo_acceso,
        # generan commits extra (~10 commits × 0.25s) y suman ~5s sin valor operativo.
        # Activar puntualmente con: cerebro._benchmark_rendimiento()
        # self._benchmark_rendimiento()

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

        # SDM v2.0: Reindex selectivo por dirty-set + full reindex periódico (24h)
        # El dirty-set es explícito (marcado en cada sinapsis NUEVA): no se confía
        # en actualizado_en, que miente cuando un vecino nuevo cambia el vector.
        # indexar_todos_sdm se conserva como red de seguridad periódica.
        try:
            from core.sdm import (
                indexar_todos_sdm, reindex_selectivo_sdm, marcar_sdm_dirty,
                limpiar_sdm_dirty, _sdm_full_reindex_due, _registrar_sdm_full_reindex,
            )
            # Los nodos consolidados en este ciclo cambiaron contenido/peso → dirty
            for concepto, *_ in recuerdos_sesion:
                marcar_sdm_dirty(self, (concepto,))
            if _sdm_full_reindex_due(self):
                n_sdm = indexar_todos_sdm(self)
                limpiar_sdm_dirty(self)
                _registrar_sdm_full_reindex(self)
                if n_sdm:
                    print(f"[SDM] {n_sdm} vectores reindexados (full periódico).")
            else:
                n_sdm = reindex_selectivo_sdm(self)
                if n_sdm:
                    print(f"[SDM] {n_sdm} vectores reindexados (selectivo).")
        except Exception:
            pass
        # Signal #13 (v26.0): Reindexar vectores PPMI+SVD de forma incremental (fold-in < 10ms)
        # El re-entrenamiento completo (SVD full) solo se ejecuta periódicamente si han acumulado >=50 nodos y 7 días
        _ppmi_did_full = False
        try:
            from core.ppmi_vectorizer import reindexar_ppmi_svd, fold_in_nodos, _ppmi_full_reindex_due
            conceptos_nuevos = [c for c, *_ in recuerdos_sesion] if recuerdos_sesion else []
            if _ppmi_full_reindex_due(self.conn, delta_nodos_nuevos=len(conceptos_nuevos)):
                n_ppmi = reindexar_ppmi_svd(self.conn)
                _ppmi_did_full = True
                if n_ppmi:
                    print(f"[PPMI] {n_ppmi} nodos reindexados con PPMI+SVD+Retrofitting (full periódico).")
            else:
                n_ppmi = fold_in_nodos(self.conn, conceptos_nuevos)
                if n_ppmi:
                    print(f"[PPMI] {n_ppmi} nodos reindexados con fold-in incremental.")

            # Actualizar el índice en memoria
            if self._ppmi_index is not None:
                if _ppmi_did_full:
                    # Full reindex: recargar todo desde disco
                    from core.ppmi_hybrid_search import IndicesBioRAG
                    self._ppmi_index = IndicesBioRAG(str(self.db_path))
                else:
                    # Fold-in: actualizar solo los nodos nuevos en el dict en memoria (ahorra ~5.9s)
                    import numpy as np
                    for concepto in conceptos_nuevos:
                        row = self.conn.execute(
                            "SELECT vector FROM nodos WHERE concepto = ?", (concepto,)
                        ).fetchone()
                        if row:
                            self._ppmi_index.vecs[concepto] = np.frombuffer(row[0], dtype='float32').astype('float64')
            self.conn.commit()
        except Exception as _ppmi_err:
            pass  # No bloquear el sueño si PPMI falla

        # Invalidar cachés temáticos y de inferencia en RAM para que reconozcan los nuevos nodos
        self._thematic_scores_cache = None
        self._thematic_profiles_cache = None
        self._thematic_idf_cache = None
        # NO se invalida el cache de pares_dim aquí: la dimension data se transfiere
        # de corto→largo ANTES de que calcular_sinapsis_latentes la lea, así que el
        # cache del ciclo actual ya refleja los nuevos nodos. Persistirlo ahorra 2.566s
        # en el siguiente ciclo. Solo se invalida cuando auto_clustering agrega nuevas dims.

        print("[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.")

    def aplicar_refuerzo_dopaminergico(self, concepto: str, exito: bool, motivo: str = None) -> bool:
        return synapses.aplicar_refuerzo_dopaminergico(self, concepto, exito, motivo)

    def _reconstruir_camino(self, destino):
        return synapses._reconstruir_camino(self, destino)

    def establecer_asociacion(self, concepto_a, concepto_b):
        return synapses.establecer_asociacion(self, concepto_a, concepto_b)

    # ─── CANAL DE COMUNICACION INTER-AGENTE ──────────────────────────────

    def _crear_tabla_comunicaciones(self):
        return comms._crear_tabla_comunicaciones(self)

    def enviar_comunicado(self, origen, destino, contenido):
        return comms.enviar_comunicado(self, origen, destino, contenido)

    def leer_comunicados(self, destino=None, solo_no_leidos=False, ultimos=10, agente=None):
        return comms.leer_comunicados(self, destino=destino, solo_no_leidos=solo_no_leidos, ultimos=ultimos, agente=agente)

    def marcar_como_leido(self, ids, agente=None):
        return comms.marcar_como_leido(self, ids, agente=agente)

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
        return synapses._evocacion_por_cadena(self, semillas, max_saltos=max_saltos, limite=limite)

    @staticmethod
    def _ncd_sim(a, b, level=None):
        """Sim_NCD = 1 - NCD(x,y) con zlib. C(s)=len(compress(utf-8))."""
        import zlib
        if level is None:
            level = constants.NCD_ZLIB_LEVEL
        xa = (a or "").encode("utf-8", errors="ignore")
        yb = (b or "").encode("utf-8", errors="ignore")
        if not xa or not yb:
            return 0.0
        def _c(blob):
            return max(1, len(zlib.compress(blob, level)))
        cx, cy = _c(xa), _c(yb)
        cxy = _c(xa + yb)
        ncd = (cxy - min(cx, cy)) / float(max(cx, cy))
        return max(0.0, min(1.0, 1.0 - ncd))

    def _ncd_sims_pool(self, query, filas):
        """NCD query vs concepto+contenido de cada fila del pool. O(k)."""
        if not query or not filas:
            return {}
        q = (query or "").strip()
        out = {}
        for conc, texto in filas:
            if not conc:
                continue
            out[conc] = self._ncd_sim(q, f"{conc} {texto or ''}")
        return out

    @staticmethod
    def _jsd_weight_adaptativo(query, n_tokens=None):
        """E7: constants.JSD_WEIGHT * 2.5 si Nt>=4, *0.5 si Nt<4. OFF: constants.JSD_WEIGHT estatico."""
        if not constants.JSD_ADAPTATIVO:
            return float(constants.JSD_WEIGHT)
        if n_tokens is None:
            n_tokens = len(re.findall(r"\w{3,}", query or ""))
        base = constants.JSD_WEIGHT if constants.JSD_WEIGHT > 0.0 else constants.JSD_ADAPT_BASE
        if n_tokens >= constants.JSD_ADAPT_NT:
            w = base * constants.JSD_ADAPT_LARGO
        else:
            w = base * constants.JSD_ADAPT_CORTO
        return max(0.0, min(0.20, w))

    def _ts_nodo(self, concepto):
        return episodes._ts_nodo(self, concepto)

    def _expandir_episodio_temporal(self, nodo_ancla, ventana_horas=None, limite_episodio=None):
        return episodes._expandir_episodio_temporal(self, nodo_ancla, ventana_horas=ventana_horas, limite_episodio=limite_episodio)

    def _afinidad_temporal_pool(self, conceptos):
        return episodes._afinidad_temporal_pool(self, conceptos)

    def _analogia_scores_pool(self, v_target, pool):
        """F3: coseno de cada candidato vs vector analogia v_target. O(k*d), clamp [0,1]."""
        if constants.ANALOGIA_PESO <= 0 or v_target is None or not pool:
            return {}
        try:
            import numpy as np
            vecs = (self._ppmi_index.vecs or {}) if self._ppmi_index else {}
            vt = np.asarray(v_target, dtype="float64")
            nvt = float(np.linalg.norm(vt))
            if nvt < 1e-10 or not vecs:
                return {}
            out = {}
            for c in pool:
                if not c:
                    continue
                v = vecs.get(c)
                if v is None:
                    out[c] = 0.0
                    continue
                vv = np.asarray(v, dtype="float64")
                nv = float(np.linalg.norm(vv))
                s = float(np.dot(vt, vv) / (nvt * nv)) if nv > 1e-10 else 0.0
                out[c] = min(1.0, max(0.0, s))
            return out
        except Exception:
            return {}

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

    @staticmethod
    def _calcular_jsd(query_text: str, node_text: str) -> float:
        """Jensen-Shannon Divergence como score de similitud [0,1].

        Calcula la divergencia entre las distribuciones de frecuencia de palabras
        del query y del contenido del nodo. A diferencia de BM25 (que mide
        relevancia por IDF), JSD mide solapamiento distribucional - cuanta
        informacion comparten dos textos.

        JSD = 1/2 * KL(P||M) + 1/2 * KL(Q||M)  donde M = 1/2(P+Q)
        Score = 1 - sqrt(JSD)  -> [0,1], mayor = mas similar.
        """
        if not query_text or not node_text:
            return 0.0

        from core.stopwords import STOPWORDS_ES
        from core.fallback_simbolico import _STOPWORDS_NORM

        def _word_freqs(text: str) -> dict[str, float]:
            text_norm = text.lower().replace('_', ' ').replace('-', ' ')
            words = re.findall(r'\w{2,}', text_norm)
            stopwords = STOPWORDS_ES | _STOPWORDS_NORM
            counts: dict[str, int] = {}
            for w in words:
                if w not in stopwords and len(w) >= 2:
                    counts[w] = counts.get(w, 0) + 1
            total = sum(counts.values())
            if total == 0:
                return {}
            return {w: c / total for w, c in counts.items()}

        p_dist = _word_freqs(query_text)
        q_dist = _word_freqs(node_text)

        if not p_dist or not q_dist:
            return 0.0

        vocab = set(p_dist.keys()) | set(q_dist.keys())

        # Laplace smoothing: α=0.01 para evitar log(0)
        alpha = 0.01
        p_vec = [p_dist.get(w, 0.0) + alpha for w in vocab]
        q_vec = [q_dist.get(w, 0.0) + alpha for w in vocab]

        # Normalize to probability distributions
        p_sum = sum(p_vec)
        q_sum = sum(q_vec)
        p_vec = [x / p_sum for x in p_vec]
        q_vec = [x / q_sum for x in q_vec]

        # Mixture distribution M = ½(P+Q)
        m_vec = [(p + q) / 2.0 for p, q in zip(p_vec, q_vec)]

        def _kl(a: list[float], b: list[float]) -> float:
            return sum(x * math.log(x / y) for x, y in zip(a, b) if x > 0 and y > 0)

        jsd_div = 0.5 * _kl(p_vec, m_vec) + 0.5 * _kl(q_vec, m_vec)

        # Score: 1 - sqrt(JSD) → [0, 1], higher = more similar
        return round(1.0 - math.sqrt(min(jsd_div, 1.0)), 4)

    @staticmethod
    def _calcular_bm25_bayesiano(raw_scores: dict, alpha: float = 1.0) -> dict:
        """Calibracion Bayesian BM25: convierte scores crudos FTS5 a probabilidades [0,1].

        Formula: sigmoid(alpha * (score - beta)) donde beta = mediana(scores) * 0.7
        (estimacion sin labels, basada en distribucion del corpus).

        A diferencia de x/(x+3), la sigmoid calibra probabilisticamente:
        - scores altos -> ~1.0 (alta probabilidad de relevancia)
        - scores bajos -> ~0.0 (baja probabilidad)
        - β se adapta a la distribución de scores de cada query

        Args:
            raw_scores: {concepto: raw_bm25_score} - scores crudos de FTS5
            alpha: steepness de la sigmoid (default 1.0)

        Returns:
            {concepto: probability} - probabilidades calibradas en [0, 1]
        """
        if not raw_scores:
            return {}

        scores = list(raw_scores.values())
        # β = mediana × 0.7 — estimación heurística sin labels
        # IMPORTANTE: BM25 de FTS5 es negativo (más negativo = mejor match)
        # La sigmoid se aplica directamente al score crudo (sin abs)
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        median = sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0
        beta = median * 0.7

        result = {}
        for concepto, raw in raw_scores.items():
            # sigmoid(α × (score - β))
            # BM25 scores son negativos: más negativo → más relevante
            # sigmoid(-large) ≈ 0.0 (mejor match), sigmoid(-small) ≈ 1.0 (peor match)
            z = alpha * (raw - beta)
            # Clamp to avoid overflow
            if z > 500:
                prob = 1.0
            elif z < -500:
                prob = 0.0
            else:
                prob = 1.0 / (1.0 + math.exp(-z))
            result[concepto] = round(prob, 4)

        return result

    def _calcular_score_hibrido(self, bm25_norm=0.0, dim_score=0.0,
                                peso_sinaptico=0.0, concepto_ratio=0.0,
                                sinonimos_ratio=0.0, score_latente=0.0,
                                score_cadena=0.0, temporal=0.0,
                                asoc_count=0, match_exacto=False,
                                grupo_score=0.0, tematico_score=0.0,
                                jsd_score: float = 0.0,
                                jsd_weight: float = 0.0,
                                pred_score: float = 0.0,
                                ppmi_score: float = 0.0,
                                hub_match: float = 0.0,
                                ncd_score: float = 0.0,
                                episodio_score: float = 0.0,
                                analogia_score: float = 0.0,
                                campo_score: float = 0.0):
        """Score hibrido: senales + JSD + Predicados + PPMI + Hub.
        grupo_score: similitud por grupo semántico WordNet (coseno binario).
        tematico_score: similitud temática por ausencia/presencia de dimensiones (IDF).
        match_exacto: preserva precisión en búsquedas por nombre exacto (floor 0.5).
        jsd_score: Jensen-Shannon Divergence como similitud [0,1].
        jsd_weight: peso de JSD en la fórmula (0.0 = desactivado, 0.05 = default activo).
        pred_score: matching de query tokens contra predicados SRL [0,1].
        ppmi_score: similitud vectorial PPMI+SVD+Retrofitting normalizada [0,1]. Signal #13 (v26.0)."""
        asoc_norm = min(1.0, asoc_count / 20.0)
        peso_norm = min(1.0, peso_sinaptico)

        # Gate per-candidate: tematico_score solo si hay evidencia léxica real
        # (bm25_norm > 0.001 o concepto_ratio > 0.001). Sin evidencia léxica,
        # tematico_score no debe poder mover el score sola.
        tematico_score_gated = tematico_score if (bm25_norm > 0.001 or concepto_ratio > 0.001) else 0.0

        # Base weights (sum to 1.0 when jsd_weight=0, constants.PPMI_VECTOR_WEIGHT folded in)
        # Weights dict: bm25=0.25, dim=0.14, concepto=0.08, sinonimos=0.08,
        # peso=0.10, jaccard=0.10, grupo=0.10, tematico=0.08,
        # temporal=0.04, asoc=0.02, pred=0.20, hub=0.20 = 1.39
        # constants.PPMI_VECTOR_WEIGHT = 0.15 -> total 1.54
        # Re-normalizamos todos los pesos para que sumen 1.0 - jsd_weight
        # Derivamos la suma base del dict para evitar hardcoding
        _base_weights = {
            "bm25": 0.25, "dim": 0.14, "concepto": 0.08, "sinonimos": 0.08,
            "peso": 0.10, "jaccard": 0.10, "grupo": 0.10, "tematico": 0.08,
            "temporal": 0.04, "asoc": 0.02, "pred": 0.20, "hub": 0.20,
        }
        _base_sum = sum(_base_weights.values())  # 1.39
        # Pesos pool (E6/F2/F3/F5) entran en el denominador para no inflar el total.
        total_base = _base_sum + constants.PPMI_VECTOR_WEIGHT + constants.NCD_PESO + constants.EPISODIO_TEMPORAL_PESO + constants.ANALOGIA_PESO + constants.CAMPO_POTENCIAL_PESO
        base_weight = (1.0 - jsd_weight) / total_base if total_base > 0 else 0.0

        score = (
            base_weight * (
                0.25 * bm25_norm +          # FTS5 BM25
                0.14 * dim_score +           # Dimensiones semánticas
                0.08 * concepto_ratio +      # Match en concepto
                0.08 * sinonimos_ratio +     # Match en sinónimos
                0.10 * peso_norm +           # Peso sináptico
                0.10 * max(score_latente, score_cadena) +  # Jaccard/cadena
                0.10 * grupo_score +         # Grupo semántico WordNet
                0.08 * tematico_score_gated +      # Similitud temática (gate per-candidate)
                0.04 * temporal +            # Recencia
                0.02 * asoc_norm +           # Asociaciones
                0.20 * pred_score +          # Signal #12: Predicados SRL
                constants.PPMI_VECTOR_WEIGHT * ppmi_score +  # Signal #13: PPMI+SVD
                0.20 * hub_match +            # Signal #14: Concept Hub
                constants.NCD_PESO * ncd_score +  # E6: 1-NCD zlib, solo pool
                constants.EPISODIO_TEMPORAL_PESO * episodio_score +  # F2: afinidad temporal pool
                constants.ANALOGIA_PESO * analogia_score +  # F3: analogia relacional PPMI
                constants.CAMPO_POTENCIAL_PESO * campo_score  # F5: campo semantico PPMI
            ) +
            jsd_weight * jsd_score           # Signal #11: JSD distributional overlap
        )

        # Bonos en espacio logit (aditivos en log-odds) para preservar orden interno
        # match_exacto: bono ~logit(0.95) - logit(score_base) ≈ +2.94 log-odds
        # sinonimos_ratio >= 0.95: bono para llegar a ~0.70 + 0.10*ppmi
        if match_exacto:
            # Convertir a log-odds, sumar bono, volver a probabilidad
            p = max(1e-6, min(1-1e-6, score))
            logit = math.log(p / (1.0 - p)) + 2.94  # logit(0.95) ≈ 2.94
            score = 1.0 / (1.0 + math.exp(-logit))
        elif sinonimos_ratio >= 0.95:
            # Bono para alcanzar ~0.70 + 0.10*ppmi: bono aditivo en logit space
            target = 0.70 + 0.10 * ppmi_score
            p = max(1e-6, min(1-1e-6, score))
            logit = math.log(p / (1.0 - p))
            # Bono aditivo en espacio logit: diferencia entre target_logit y 0
            # Equivalente a añadir log(target/(1-target)) al logit
            target_logit = math.log(target / (1.0 - target))
            bonus = target_logit  # bono para llevar score base 0.5 -> target
            score = 1.0 / (1.0 + math.exp(-(logit + bonus)))

        return round(min(1.0, max(0.0, score)), 4)

    # =============================================================================
    # v28.1: Calibración de probabilidad y decisión con garantía (FP controlado)
    # =============================================================================

    def _preparar_datos_calibracion(self, n_calibracion: int = 500) -> tuple:
        """Prepara datos de calibración usando el QA baseline (921 casos).

        Returns:
            (scores, labels)
            scores: scores del top-1 para cada caso (score_hibrido crudo)
            labels: 1 si el top-1 era el esperado, 0 en caso contrario
        """
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        qa_path = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")
        if not os.path.exists(qa_path):
            qa_path = os.path.join(base_dir, "scripts", "casos_qa.jsonl")

        if not os.path.exists(qa_path):
            logger.warning("No se encontró QA baseline para calibración")
            return [], []

        scores = []
        labels = []
        n = 0
        with open(qa_path, 'r', encoding='utf-8') as f:
            for line in f:
                if n >= n_calibracion:
                    break
                try:
                    caso = json.loads(line.strip())
                    query = caso.get('query', '')
                    expected = caso.get('concepto_esperado', '') or caso.get('expected', '')
                    if not query or not expected:
                        continue
                    resultados = self.buscar_por_frase(query, limite=1)
                    if resultados and resultados[0]:
                        score = resultados[0][0][4]  # score_hibrido (first result, first tuple, index 4)
                        label = 1 if resultados[0][0][0] == expected else 0
                        scores.append(score)
                        labels.append(label)
                        n += 1
                except Exception:
                    continue
        return scores, labels

    def entrenar_calibracion(self, n_calibracion: int = 500, metodo: str = "platt") -> bool:
        """Entrena el calibrador de Platt (o isotónico) usando el QA baseline.

        Args:
            n_calibracion: máximo de casos a usar
            metodo: 'platt' o 'isotonica'
        """
        if not CalibradorPlatt or not calibracion_isotonica:
            logger.warning("Módulo calibracion no disponible")
            return False

        scores, labels = self._preparar_datos_calibracion(n_calibracion)
        if not scores:
            logger.warning("No hay datos de calibración")
            return False

        if metodo == "platt" and CalibradorPlatt:
            self._platt_calibrador = CalibradorPlatt().entrenar(scores, labels)
            logger.info(f"Platt calibrado: a={self._platt_calibrador.a:.4f}, b={self._platt_calibrador.b:.4f}")
        elif calibracion_isotonica:
            self._platt_calibrador = calibracion_isotonica(
                [float(s) for s in scores], [int(l) for l in labels]
            )
            logger.info("Calibración isotónica entrenada")
        else:
            logger.warning("Método de calibración no disponible")
            return False

        self._calibracion_entrenada = True
        return True

    def calibrar_umbral_conforme(self, alpha: float = None, n_negativos: int = 100) -> float:
        """Crea el umbral de abstención con garantía FP <= alpha (predicción conforme).

        Usa consultas negativas conocidas (sin respuesta en corpus) para fijar
        el umbral con garantía FP <= alpha (distribution-free).

        alpha: garantía FP objetivo. Si None, se lee de BIORAG_ALPHA_CONFORME
        (default 0.10). GUARDA (DECISION_ALPHA.md): con n negativos el alpha
        mínimo alcanzable es 1/(n+1). Pedir menos no da esa garantía — solo
        coloca el umbral en el máximo de la muestra, que es el estadístico más
        inestable. Se avisa y se usa alpha_min en vez de fingir precisión.

        IMPORTANTE — SELECCIÓN DE NEGATIVOS: se usan EXCLUSIVAMENTE los casos de
        categoría `negativo` del QA baseline. NO se usan "expected no existe en
        largo_plazo" como criterio: eso filtra por nombre exacto y deja colar
        casos literales/naturales que SÍ tienen respuesta en el corpus (matchean
        con score 0.95+, corrompiendo el cuantil y empujando el umbral arriba).

        IMPORTANTE — MISMA ESCALA QUE EN USO: los scores recogidos aquí son
        `score_hibrido` crudo (resultados[0][0][4]). `_debe_responder` debe
        recibir la MISMA escala cruda; no mezclar con probabilidades de Platt.
        """
        if not UmbralConforme:
            logger.warning("UmbralConforme no disponible")
            return 0.0

        # alpha default desde env (DECISION_ALPHA.md, sección 5): ajustable por
        # entorno (QA / producción / agente) sin tocar código.
        if alpha is None:
            alpha = float(os.environ.get('BIORAG_ALPHA_CONFORME', '0.10'))

        # Buscar casos negativos: queries de la categoría `negativo` del QA
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        qa_path = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")
        if not os.path.exists(qa_path):
            qa_path = os.path.join(base_dir, "scripts", "casos_qa.jsonl")

        scores_neg = []
        with open(qa_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    caso = json.loads(line.strip())
                    if caso.get('categoria', '') != 'negativo':
                        continue
                    query = caso.get('query', '')
                    if not query:
                        continue

                    resultados = self.buscar_por_frase(query, limite=1)
                    if resultados and resultados[0]:
                        scores_neg.append(resultados[0][0][4])
                        if len(scores_neg) >= n_negativos:
                            break
                except Exception:
                    continue

        if not scores_neg:
            logger.warning("No se encontraron negativos para calibración conforme")
            return 0.0

        # GUARDA (DECISION_ALPHA.md sección 5): alpha mínimo honesto = 1/(n+1).
        # Con 32 muestras pedir alpha=0.01 no da esa garantía: solo coloca el
        # umbral en el máximo observado (el estadístico más inestable). Avisar
        # en vez de fingir precisión.
        n_reales = min(len(scores_neg), n_negativos)
        alpha_min = 1.0 / (n_reales + 1)
        if alpha < alpha_min:
            logger.warning(
                f"alpha={alpha} pedido, pero con {n_reales} negativos el mínimo "
                f"alcanzable es {alpha_min:.3f}. Se usa {alpha_min:.3f}. "
                f"Para un alpha menor, amplía el corpus de negativos."
            )
            alpha = alpha_min

        # Detección de umbral degenerado: calibrar() solo evalúa la cobertura
        # sobre positivos si se los pasan. Sin esto, una recalibración con
        # negativos contaminados (p.ej. queries de log que luego resultaron ser
        # nodos existentes) fijaría el umbral por encima del máximo positivo y
        # el sistema se abstendría en el 100% de los casos EN SILENCIO.
        # Se pasan solo los positivos del QA (label==1): los negativos del QA
        # puntúan bajo y diluirían el chequeo de frac_pasa.
        try:
            scores_pos_muestra, labels_pos_muestra = self._preparar_datos_calibracion(100)
            scores_positivos = [s for s, l in zip(scores_pos_muestra, labels_pos_muestra) if l == 1] or None
        except Exception:
            scores_positivos = None
        self._umbral_conforme = UmbralConforme(alpha=alpha).calibrar(
            scores_neg[:n_reales], scores_positivos=scores_positivos
        )
        logger.info(f"Umbral conforme (alpha={alpha}): {self._umbral_conforme.umbral:.4f} (n={self._umbral_conforme.n_calibracion})")
        return self._umbral_conforme.umbral

    def _score_con_calibracion(self, score_bruto: float) -> float:
        """Convierte score bruto a probabilidad calibrada (Platt o isotónica)."""
        if self._platt_calibrador:
            if hasattr(self._platt_calibrador, 'probabilidad'):
                return self._platt_calibrador.probabilidad(score_bruto)
            elif callable(self._platt_calibrador):
                return self._platt_calibrador(score_bruto)
        return score_bruto

    # Cold start: umbral conservador para instancias sin calibración.
    # Si alguien instala BioRAG con DB vacía o sin `biorag_calibrar`, este
    # umbral evita devolver ruido. Se reemplaza automáticamente cuando se
    # ejecuta la primera calibración (conforme o manual).
    UMBRAL_COLD_START = 0.65

    def _debe_responder(self, score: float) -> bool:
        """Decide si responder o abstenerse basado en umbral conforme.

        RECIBE LA MISMA ESCALA USADA EN calibrar_umbral_conforme: score_hibrido
        crudo. Si se calibró con crudo, aquí va crudo.

        FLUJO:
          1. Si hay calibración conforme cargada → usa su umbral.
          2. Si NO hay calibración → SIN FILTRO (responder siempre).
             Cold start (0.65) solo se aplica cuando BIORAG_CALIBRACION_ACTIVA
             está explícitamente seteado a 1 (producción MCP).

        POR QUÉ: el umbral filtra por CALIDAD, no por existencia. Sin calibración
        no hay evidencia de qué score separa relevantes de irrelevantes. Forzar
        0.65 destruye R@5 (medido: 96% → 73%) porque muchos nodos válidos
        tienen score < 0.65 por la arquitectura del scoring (FTS5 + sinapsis
        + dimensional = scores planos).
        """
        if self._umbral_conforme:
            return self._umbral_conforme.responder(score)
        # Sin calibración: responder siempre.
        # Calidad sin calibrar = ruido por defecto (aceptable).
        # Calidad con umbral mal calibrado =失掉Recall (inaceptable).
        return True

    def buscar_con_calibracion(self, query: str, limite: int = 10,
                               usar_calibracion: bool = True) -> list:
        """Búsqueda estándar con abstención sobre top-1 del score híbrido crudo.

        Si hay calibración conforme → filtra por top-1 (decisión SI/NO responder).
        Si no hay calibración → devuelve todos los resultados (sin filtro).

        NOTA: buscar_por_frase NO aplica umbral. Este método SÍ porque
        es el punto de decisión "¿respondo al usuario?" (MCP path).

        Args:
            query: consulta
            limite: máximo resultados
            usar_calibracion: aplicar abstención conforme (default True)
        """
        resultados = self.buscar(query, limite=limite)
        if usar_calibracion and resultados:
            # Solo top-1 decide SI responder. El resto se devuelve tal cual.
            if not self._debe_responder(resultados[0][4]):
                return []  # abstención
        return resultados[:limite]

    # =============================================================================
    # v28.1: Calibración dinámica persistente — garantía FP independiente del corpus
    # =============================================================================
    # PRINCIPIO (Dennys, 2026-08-16): el corpus no es estático — crece o decrece.
    # Un umbral calibrado contra N nodos deja de ser válido cuando el corpus cambia
    # de tamaño. Por eso la calibración se PERSISTE (tabla calibracion_estado) junto
    # con el n_nodos_corpus del momento, y se RECALCULA automáticamente cuando el
    # tamaño actual se aleja del calibrado. La garantía FP <= alpha es
    # distribution-free (predicción conforme split, Vovk 2005): no asume la forma
    # de la distribución, solo que la muestra de calibración viene de la misma
    # población que las consultas de producción.
    # =============================================================================

    def _contar_nodos_corpus(self) -> int:
        """Número de nodos activos actuales (para detectar drift de tamaño)."""
        try:
            row = self.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'"
            ).fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def _cargar_calibracion_persistida(self) -> bool:
        """Carga la última calibración persistida. Devuelve True si hay una vigente."""
        try:
            self.cursor.execute("PRAGMA table_info(calibracion_estado)")
            if not self.cursor.fetchall():
                return False

            # BIORAG_CALIBRACION_ACTIVA: gate para activar la abstención por umbral.
            # OFF por defecto hasta tener negativos reales de tipo B para calibrar.
            if os.environ.get("BIORAG_CALIBRACION_ACTIVA", "0") != "1":
                return False

            row = self.cursor.execute(
                "SELECT umbral_conforme, alpha, n_negativos, n_positivos, "
                "n_nodos_corpus, a_platt, b_platt, metodo, rango_negativos, "
                "fecha_calibracion FROM calibracion_estado WHERE id = 1"
            ).fetchone()
            if not row:
                return False
            (umbral, alpha, n_neg, n_pos, n_nodos, a_platt, b_platt,
             metodo, rango, fecha) = row
            if umbral is None or umbral <= 0:
                return False
            self._umbral_conforme = UmbralConforme(alpha=alpha)
            self._umbral_conforme.umbral = float(umbral)
            self._umbral_conforme.n_calibracion = int(n_neg)
            if rango:
                try:
                    r0, r1 = rango.split(",")
                    self._umbral_conforme.rango_negativos = (float(r0), float(r1))
                except Exception:
                    pass
            if a_platt is not None and b_platt is not None and CalibradorPlatt:
                platt = CalibradorPlatt()
                platt.a = float(a_platt)
                platt.b = float(b_platt)
                self._platt_calibrador = platt
            self._calibracion_meta = {
                "alpha": float(alpha),
                "n_negativos": int(n_neg),
                "n_positivos": int(n_pos),
                "n_nodos_corpus": int(n_nodos),
                "metodo": metodo,
                "fecha_calibracion": float(fecha),
            }
            self._calibracion_entrenada = True
            return True
        except Exception as e:
            logger.warning(f"No se pudo cargar calibración persistida: {e}")
            return False

    def _persistir_calibracion(self, n_positivos: int, metodo: str = "conforme") -> None:
        """Persiste el estado de calibración junto al tamaño de corpus del momento."""
        try:
            u = self._umbral_conforme
            a_platt = getattr(getattr(self, "_platt_calibrador", None), "a", None)
            b_platt = getattr(getattr(self, "_platt_calibrador", None), "b", None)
            rango = f"{u.rango_negativos[0]:.4f},{u.rango_negativos[1]:.4f}" \
                if u.rango_negativos else None
            n_nodos = self._contar_nodos_corpus()
            self.cursor.execute("""
                INSERT INTO calibracion_estado
                    (id, umbral_conforme, alpha, n_negativos, n_positivos,
                     n_nodos_corpus, a_platt, b_platt, metodo, rango_negativos,
                     fecha_calibracion)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    umbral_conforme = excluded.umbral_conforme,
                    alpha = excluded.alpha,
                    n_negativos = excluded.n_negativos,
                    n_positivos = excluded.n_positivos,
                    n_nodos_corpus = excluded.n_nodos_corpus,
                    a_platt = excluded.a_platt,
                    b_platt = excluded.b_platt,
                    metodo = excluded.metodo,
                    rango_negativos = excluded.rango_negativos,
                    fecha_calibracion = excluded.fecha_calibracion
            """, (u.umbral, u.alpha, u.n_calibracion, n_positivos, n_nodos,
                  a_platt, b_platt, metodo, rango, time.time()))
            self.conn.commit()
            self._calibracion_meta = {
                "alpha": u.alpha,
                "n_negativos": u.n_calibracion,
                "n_positivos": n_positivos,
                "n_nodos_corpus": n_nodos,
                "metodo": metodo,
                "fecha_calibracion": time.time(),
            }
            logger.info(
                f"Calibración persistida: umbral={u.umbral:.4f} alpha={u.alpha} "
                f"n_nodos={n_nodos}"
            )
        except Exception as e:
            logger.warning(f"No se pudo persistir calibración: {e}")

    def calibrar_y_persistir(self, alpha: float = None, n_negativos: int = 40,
                             n_positivos_max: int = 300,
                             recalcular_si_drift: bool = True,
                             force: bool = False) -> dict:
        """Calibra (o recalibra si el corpus cambió) y persiste la garantía.

        DEVUELVE EL UMBRAL CON GARANTÍA FP <= alpha SOBRE EL CORPUS ACTUAL.
        Si ya hay una calibración persistida y el tamaño del corpus no cambió
        significativamente, reutiliza la vigente (no quema tiempo de búsqueda).

        Umbral por defecto 0.10: con los negativos del QA baseline (40 casos)
        fija el cuantil ceil((n+1)(1-alpha))/n de sus scores crudos.
        BASE HISTÓRICA: pre-v28.1 el sistema usaba cortes fijos
        (BIORAG_FP_THRESHOLD=0.25, BIORAG_QCR_ESCAPE_CAPA_MIN=0.60) que no
        dependían de la distribución real. alpha=0.10 es una PREFERENCIA
        (no una decisión con datos): su justificación requiere medir el ratio
        de consultas con/sin respuesta en log_busquedas (AUDITORÍA v28.1, paso 3).

        Args:
            alpha: garantía FP objetivo (0 < alpha < 1). None = leer env
                BIORAG_ALPHA_CONFORME (default 0.10). Si es menor que
                1/(n_negativos+1), se usa el mínimo alcanzable con la muestra
                (GUARDA DECISION_ALPHA.md sección 5) y se avisa.
            n_negativos: máximo de negativos a usar (los 40 del QA baseline).
            n_positivos_max: máximo de positivos para calibrar Platt (opcional).
            recalcular_si_drift: re-calibrar si n_nodos cambió > tolerancia.
            force: True = recalibrar siempre, ignorando calibración vigente.
        """
        n_nodos_actual = self._contar_nodos_corpus()
        meta = getattr(self, "_calibracion_meta", None)

        # alpha default desde env (DECISION_ALPHA.md sección 5)
        if alpha is None:
            alpha = float(os.environ.get('BIORAG_ALPHA_CONFORME', '0.10'))

        # Reutilizar calibración vigente si el corpus no se movió mucho
        if (not force and recalcular_si_drift and meta and self._umbral_conforme
                and self._umbral_conforme.umbral > 0):
            n_previo = meta.get("n_nodos_corpus", 0)
            drift_rel = abs(n_nodos_actual - n_previo) / max(n_previo, 1)
            # Tolerancia: 20% de cambio relativo (matemática simple, escalable:
            # el cuantil conforme es robusto a perturbaciones pequeñas del corpus).
            # BASE PRE-CALIBRACIÓN: el umbral era un valor FIJO (0.25 FP / 0.60 QCR)
            # que no se recalculaba jamás aunque el corpus triplicara su tamaño.
            # AUDITORÍA v28.1 (P3): faltaría invalidar también ante reindexado PPMI
            # (ppmi_ultima_reindexacion) y cambios de pesos del scoring — el tamaño
            # del corpus no es la única causa de deriva del piso de ruido.
            if drift_rel <= 0.20:
                return {
                    "umbral": self._umbral_conforme.umbral,
                    "alpha": self._umbral_conforme.alpha,
                    "n_negativos": self._umbral_conforme.n_calibracion,
                    "n_nodos_corpus": n_nodos_actual,
                    "recalibrado": False,
                    "motivo": "corpus_sin_drift_significativo",
                    "fecha": meta.get("fecha_calibracion"),
                }
            logger.info(
                f"Corpus cambió {100*drift_rel:.1f}% ({n_previo} -> {n_nodos_actual}); "
                f"recalibrando umbral conforme"
            )

        # Intentar cargar persistida (si no la teníamos en memoria)
        if not force and not meta and self._cargar_calibracion_persistida():
            meta = self._calibracion_meta
            n_previo = meta.get("n_nodos_corpus", 0)
            drift_rel = abs(n_nodos_actual - n_previo) / max(n_previo, 1)
            if drift_rel <= 0.20 and self._umbral_conforme.umbral > 0:
                return {
                    "umbral": self._umbral_conforme.umbral,
                    "alpha": self._umbral_conforme.alpha,
                    "n_negativos": self._umbral_conforme.n_calibracion,
                    "n_nodos_corpus": n_nodos_actual,
                    "recalibrado": False,
                    "motivo": "persistida_sin_drift",
                    "fecha": meta.get("fecha_calibracion"),
                }

        # Calibrar sobre el corpus ACTUAL
        umbral = self.calibrar_umbral_conforme(alpha=alpha, n_negativos=n_negativos)
        if umbral <= 0:
            return {"umbral": 0.0, "error": "calibracion_fallida"}

        n_pos = 0
        if n_positivos_max > 0 and CalibradorPlatt:
            try:
                scores_pos, labels_pos = self._preparar_datos_calibracion(n_positivos_max)
                if len(scores_pos) >= 20:
                    self._platt_calibrador = CalibradorPlatt().entrenar(
                        scores_pos, labels_pos
                    )
                    n_pos = len(scores_pos)
                    logger.info(
                        f"Platt recalibrado: a={self._platt_calibrador.a:.4f}, "
                        f"b={self._platt_calibrador.b:.4f} (n={n_pos})"
                    )
            except Exception as e:
                logger.warning(f"Platt falló en recalibración: {e}")

        self._persistir_calibracion(n_pos, metodo="conforme")
        return {
            "umbral": umbral,
            # alpha EFECTIVO tras la guarda 1/(n+1), no el pedido
            "alpha": self._umbral_conforme.alpha,
            "alpha_pedido": alpha,
            "n_negativos": self._umbral_conforme.n_calibracion,
            "n_nodos_corpus": n_nodos_actual,
            "recalibrado": True,
            "motivo": "calibrado_sobre_corpus_actual",
            "fecha": time.time(),
        }

    def nivel_certeza(self, score: float) -> str:
        """Clasifica un score crudo en los 3 niveles de honestidad epistémica.

        Regla del Neocórtex de Sangre (Dennys, 2026-08-14): nunca silencio vacío.
        Tres niveles:
          - evidencia_directa: score supera el umbral conforme (garantía FP <= alpha)
          - relacionado_confianza_media: por debajo del umbral pero hay señal
          - sin_evidencia_directa: score por debajo del umbral inferior (0.35)

        El umbral inferior 0.35 es el piso de ruido medido en live DB
        (rango de negativos: 0.34-0.61). Si el corpus cambia de tamaño, la
        recalibración ajusta el umbral superior; el piso se re-deriva del
        rango persistido de negativos.

        NOTA DE BASE (Dennys, 2026-08-16): antes de la calibración v28.1 el
        sistema tenía UN SOLO corte fijo, BIORAG_QCR_ESCAPE_CAPA_MIN = 0.60
        (gate QCR) y el umbral de FP BIORAG_FP_THRESHOLD = 0.25. El piso 0.35
        y el corte 0.60 que aparecen en este método son los valores fijos que
        la calibración reemplaza por cuantiles derivados de la distribución
        real de negativos. No reintroducir umbrales absolutos sin evidencia.
        """
        u = self._umbral_conforme
        if u and u.umbral > 0:
            if float(score) > u.umbral:
                return "evidencia_directa"
            piso = (u.rango_negativos[0] or 0.0) if u.rango_negativos else 0.35
            if float(score) >= max(piso, 0.35) - 0.01:
                return "relacionado_confianza_media"
            return "sin_evidencia_directa"
        # Sin calibración: fallback conservador de 3 niveles
        # BASE HISTÓRICA (valores fijos que la calibración v28.1 reemplaza):
        #   0.60 = BIORAG_QCR_ESCAPE_CAPA_MIN, el único corte del gate QCR pre-v28.1
        #   0.35 = piso de ruido medido en live DB (rango negativos 0.34-0.61)
        # Con calibración estos dos números salen de la distribución real;
        # aquí quedan como referencia de la base que se estaba usando.
        if score >= 0.60:
            return "evidencia_directa"
        if score >= 0.35:
            return "relacionado_confianza_media"
        return "sin_evidencia_directa"

    def confianza_calibrada(self, score: float) -> float:
        """Probabilidad calibrada (Platt) o score crudo si no hay calibrador."""
        if self._platt_calibrador:
            try:
                if hasattr(self._platt_calibrador, 'probabilidad'):
                    return float(self._platt_calibrador.probabilidad(score))
                return float(self._platt_calibrador(score))
            except Exception:
                pass
        return float(score)

    def expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        return synapses.expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)

    def _expandir_contexto_bfs(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        return synapses._expandir_contexto_bfs(self, pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)

    def _rerank_jaccard_protect_r0(self, resultados, frase_limpia, preview_chars=1500):
        """Re-ranking jaccard léxico (Fase C) con protección de rank 0.

        Fiel a apply_rerank_protect_r0 de scripts/experimento_faseB_protect_r0.py,
        config ganadora del holdout 2026-08-04: elimina TODAS las regresiones R@1
        (variante, pregunta_natural, sinonimo, typo) manteniendo el +6 R@5 de por_tema.
        Gate por max jaccard del pool[:window]; re-sort del top-k por
        score + alpha*(jaccard/max_j); si el ítem que ocupaba la posición 0
        del pool original fue desplazado, se restaura a la primera posición.

        NOTA DE FIDELIDAD: el experimento calculó jaccard sobre el contenido YA
        truncado a preview_chars (default 1500) que retorna buscar_por_frase.
        Aquí el contenido aún está completo (el truncado ocurre después del
        re-ranking), por eso se trunca a min(preview_chars, 3000) para replicar
        el cálculo validado (71,306 jaccards reproducidos exactos).
        """
        if not resultados or len(resultados) < 2 or not frase_limpia.strip():
            return resultados

        preview_chars = min(int(preview_chars or 1500), 3000)

        import unicodedata
        from core.stopwords import _STOPWORDS_QUERY

        def strip_accents(text):
            return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

        def tokens(text):
            t = re.sub(r'[^\w\s_-]', ' ', text.lower())
            out = []
            for w in t.split():
                wc = strip_accents(w)
                if wc not in _STOPWORDS_QUERY and len(w) >= 2:
                    out.append(wc)
            return set(out)

        def jaccard(a, b):
            if not a or not b:
                return 0.0
            return len(a & b) / len(a | b)

        q_tok = tokens(frase_limpia)
        if not q_tok:
            return resultados

        win = resultados[:constants.RERANKING_JACCARD_WINDOW]
        max_j = max(
            (jaccard(q_tok, tokens((r[1] or "")[:preview_chars])) for r in win),
            default=0.0,
        )
        if max_j < constants.RERANKING_JACCARD_GATE:
            return resultados

        original_r0 = resultados[0]
        head = resultados[:constants.RERANKING_JACCARD_TOPK]
        tail = resultados[constants.RERANKING_JACCARD_TOPK:]
        max_j_norm = max_j or 1e-9
        head = sorted(
            head,
            key=lambda r: r[4] + constants.RERANKING_JACCARD_ALPHA * (jaccard(q_tok, tokens((r[1] or "")[:preview_chars])) / max_j_norm),
            reverse=True,
        )
        if head and head[0] is not original_r0:
            head = [original_r0] + [it for it in head if it is not original_r0]
        return head + tail

    def obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=5, peso_min=0.50):
        return synapses.obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=top_vecinos, peso_min=peso_min)

    # OPT-NUEVA-5: constates de evaluacion epistemica (Ce). Umbrales = HIPOTESIS
    # inicial documentada (sin set calibrado); ranking intacto por construccion.
    EPISTEMICO_TOP_K = 5
    EPISTEMICO_UMBRAL_CONOCIDO = 0.55
    EPISTEMICO_UMBRAL_INCERTIDUMBRE = 0.30
    EPISTEMICO_VACIOS_CAP = 200

    def _epistemico_coherencia_dimensional(self, top_conceptos):
        """Fraccion del top-k (sin top-1) que comparte >=1 dimension con top-1."""
        if not top_conceptos or len(top_conceptos) < 2:
            return 0.0
        try:
            ph = ",".join("?" for _ in top_conceptos)
            dims = {}
            for concepto, dim_id in self.cursor.execute(
                    "SELECT concepto, dimension_id FROM largo_plazo_dimensiones WHERE concepto IN (%s)" % ph,
                    tuple(top_conceptos)):
                dims.setdefault(concepto, set()).add(dim_id)
            base = dims.get(top_conceptos[0]) or set()
            if not base:
                return 0.0
            resto = top_conceptos[1:]
            return sum(1 for c in resto if (dims.get(c) or set()) & base) / len(resto)
        except Exception as e:
            logger.warning("epistemico: coherencia_dimensional fallo, coh=0 (%s: %s)", type(e).__name__, e)
            return 0.0

    def _epistemico_evaluar(self, pagina_resultados):
        """Ce = 0.5*top1 + 0.3*densidad_top5 + 0.2*coherencia_dim. Solo lectura."""
        top = list(pagina_resultados or [])[:self.EPISTEMICO_TOP_K]
        if not top:
            return {"estado_epistemico": "vacio_cognitivo", "Ce": 0.0,
                    "top1_score": 0.0, "densidad_pool": 0.0,
                    "coherencia_dimensional": 0.0}

        def _clip(x):
            try:
                return max(0.0, min(1.0, float(x or 0.0)))
            except Exception as e:
                logger.warning("epistemico: clip score fallo, score=0 (%s: %s)", type(e).__name__, e)
                return 0.0

        scores = [_clip(r[4]) for r in top]
        s1 = scores[0]
        densidad = sum(scores) / len(scores)
        dim_coh = self._epistemico_coherencia_dimensional([r[0] for r in top])
        ce = round(0.5 * s1 + 0.3 * densidad + 0.2 * dim_coh, 4)
        if ce >= self.EPISTEMICO_UMBRAL_CONOCIDO:
            estado = "conocido"
        elif ce >= self.EPISTEMICO_UMBRAL_INCERTIDUMBRE:
            estado = "incertidumbre_parcial"
        else:
            estado = "vacio_cognitivo"
        return {"estado_epistemico": estado, "Ce": ce,
                "top1_score": round(s1, 4), "densidad_pool": round(densidad, 4),
                "coherencia_dimensional": round(dim_coh, 4)}

    def _epistemico_publicar(self, frase, pagina_resultados, total):
        """Hook de cola: merge metadatos en last_estado_epistemico + encola vacios.
        JAMAS muta pagina_resultados. Devuelve None."""
        try:
            info = self._epistemico_evaluar(pagina_resultados)
        except Exception as e:
            logger.warning("epistemico: evaluar fallo, sin metadatos (%s: %s)", type(e).__name__, e)
            return
        try:
            base = getattr(self, "last_estado_epistemico", {}) or {}
            if not isinstance(base, dict):
                base = {}
            merged = dict(base)
            merged.update(info)
            merged["epistemico_n_resultados"] = len(pagina_resultados or [])
            self.last_estado_epistemico = merged
        except Exception as e:
            logger.warning("epistemico: merge metadatos fallo (%s: %s)", type(e).__name__, e)
        if info.get("estado_epistemico") == "vacio_cognitivo":
            self._epistemico_encolar_vacio(frase, info.get("Ce", 0.0))

    def _epistemico_publicar_sin_consulta(self):
        """Early-exit (query vacia/basura): no hubo busqueda, no es vacio."""
        try:
            base = getattr(self, "last_estado_epistemico", {}) or {}
            if not isinstance(base, dict):
                base = {}
            merged = dict(base)
            merged.update({"estado_epistemico": "sin_consulta", "Ce": 0.0,
                           "epistemico_n_resultados": 0})
            self.last_estado_epistemico = merged
        except Exception as e:
            logger.warning("epistemico: sin_consulta fallo (%s: %s)", type(e).__name__, e)

    def _epistemico_encolar_vacio(self, frase, ce):
        """Encola termino no resuelto en estado_hormiga.json (vacios_cognitivos).
        Best-effort con dedup exacto y cap FIFO: jamas rompe la busqueda."""
        try:
            termino = (frase or "").strip()[:200]
            if not termino:
                return
            from core.dmn_reflexion import _cargar_estado, _guardar_estado
            import time as _t
            estado = _cargar_estado()
            cola = estado.get("vacios_cognitivos")
            if not isinstance(cola, list):
                cola = []
            if any(isinstance(e, dict) and e.get("termino") == termino for e in cola):
                return
            cola.append({"termino": termino, "Ce": float(ce or 0.0), "ts": _t.time()})
            estado["vacios_cognitivos"] = cola[-self.EPISTEMICO_VACIOS_CAP:]
            _guardar_estado(estado)
        except Exception as e:
            logger.warning("epistemico: encolar vacio DMN fallo (%s: %s)", type(e).__name__, e)

    def _multihop_vecinos(self, semillas, excluir, limite):
        return synapses._multihop_vecinos(self, semillas, excluir, limite)

    def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=None, categoria=None, preview_chars=1500, historial_fallos=None, context_window=0, dimensiones_dict=None, dimensiones_ids=None, parafrasis_list=None, desde_ts=None, hasta_ts=None, modo_estricto=False, usar_inferencia=True, buscar_por_rol=None, ignore_peso_sinaptico=False, ordenar_por="relevancia", permitir_expansion_empate=False, expandir_episodio=False, analogia=False, sustantivos_clave_boost=None):
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
        ordenar_por: 'relevancia' (default, orden por score híbrido), 'recencia' (creado_en DESC,
                     más recientes primero) o 'antiguedad' (creado_en ASC, más antiguos primero).
                     Post-hoc: reordena el conjunto ya filtrado por relevancia ANTES de paginar.
                     WARNER: solo responde intención temporal, no determina relevancia.
        permitir_expansion_empate: si True, amplía el límite cuando candidatos justo debajo
                     del corte tienen score >= 90% del último incluido (Dynamic Multiplicator).
                     Default False: `limite` es un contrato estricto, el motor nunca devuelve
                     más resultados de los pedidos.
        Retorna (resultados, total) donde resultados es lista de
        (concepto, contenido, peso, estado, score, asociaciones)
        """
        self.notificar_actividad_usuario()
        self.last_parent_map = {}  # Reset parent pointers for this search
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
            limite = constants.LIMITE_DEFAULT
        # Si no hay frase Y no hay dimensiones Y no hay rol, retornar vacío
        # PERO si hay dimensiones o rol (aunque no haya frase), continuar
        if not frase.strip() and not dimensiones_ids and not buscar_por_rol:
            if constants.EPISTEMICO_METADATA:
                self._epistemico_publicar_sin_consulta()
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

        # ── GUARD: solo expandir si la búsqueda normal (sin expandir) no alcanza ──
        # Medido esta sesión: expandir SIEMPRE (Concept Hub + WordNet + Domain Dict)
        # regresionó 'literal' de ~100%→73% y Spreading Activation de 6%→1.4% —
        # el ruido de los términos inyectados competía con queries que ya
        # matcheaban limpio. Probe barato: ¿la query CRUDA ya encuentra >=3 por
        # FTS5 AND? Si sí, no expandir — ya no hace falta y solo mete ruido.
        _necesita_expansion = True
        if frase.strip() and len(frase.split()) >= 1:
            try:
                # Escape simple e independiente — _fts_safe_phrase se define más
                # abajo en esta misma función, no está disponible aquí todavía
                # (bug real detectado: la primera versión de este guard llamaba
                # a _fts_safe_phrase antes de su definición, NameError silencioso
                # por el except Exception, y el guard nunca bloqueaba nada).
                _tokens_probe = [
                    re.sub(r'["\x00]', '', t) for t in frase.split() if t.strip()
                ]
                _tokens_probe = [t for t in _tokens_probe if t]
                if _tokens_probe:
                    _fts_and_probe = " AND ".join(f'"{t}"' for t in _tokens_probe)
                    _cnt_probe = self.cursor.execute(
                        "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
                        (_fts_and_probe,)
                    ).fetchone()[0]
                    _necesita_expansion = _cnt_probe == 0
            except Exception as exc:
                logger.debug(f"[BioRAG.Probe] Excepción en probe FTS5 AND (fallback a expandir=True): {exc}")
                _necesita_expansion = True  # si el probe falla, más seguro expandir

        # ── CONCEPT HUB: Expansión semántica pre-FTS5 (condicional, igual que WordNet y DomainDict)
        # El hub resuelve el "abismo léxico": queries que no tienen ningún overlap léxico con el
        # nodo correcto. Pero si FTS5 ya encontró candidatos (probe AND), inyectar hub_terms
        # contamina el score BM25: los términos expandidos tienen IDF bajo y dilluyen el peso de
        # los tokens originales (vocabulary drift), empujando el nodo correcto fuera del top-5.
        #
        # Guard invariante al tamaño del corpus:
        #   _necesita_expansion = True  si el probe FTS5 AND retorna 0 resultados
        #   _necesita_expansion = False si ya hay al menos 1 hit léxico directo
        # Este check es relativo a la query, no al corpus — no cambia si el corpus crece.
        # Alineado con WordNet (L4260) y DomainDict (L4303) que usan el mismo guard.
        #
        # La promoción del nodo canónico (post-ranking, L5568+) sigue activa siempre,
        # independientemente de este guard — el Hub sigue rescatando abismos léxicos
        # via hub_val en score híbrido y canonical insertion directa desde DB.
        hub_expansion = None
        # BIORAG_HUB_ENABLED (default "1"): apaga TANTO la expansión de términos
        # COMO la promoción del nodo canónico post-ranking, para ablación limpia.
        if os.environ.get("BIORAG_HUB_ENABLED", "1") != "0":
            try:
                from core.concept_hub import expandir_query_con_hub
                hub_expansion = expandir_query_con_hub(frase_limpia, self.conn, threshold=0.40)
                if hub_expansion and hub_expansion.get("expanded_terms") and _necesita_expansion:
                    hub_terms = " ".join(hub_expansion["expanded_terms"])
                    frase = frase + " " + hub_terms
                    # NOTA: NUNCA sobreescribir 'query = frase'.
                    # 'query' debe conservar los términos originales del usuario para
                    # evitar explosión combinatoria O(N*M) en el scoring simbólico (Levenshtein).
            except Exception as exc:
                logger.warning(f"[BioRAG.ConceptHub] Excepción en expandir_query_con_hub: {exc}")
                hub_expansion = None

        # ── WORDNET EXPANDIDO: Expansión automática por sinónimos+hiperonimios ──
        # Solo para palabras genuinamente en inglés (WordNet en inglés).
        # Evitar palabras en español que pasen por ser ASCII puro (sin tildes ni ñ).
        # BIORAG_WORDNET_ENABLED (default "1"): apaga la expansión léxica y la Capa 5 de scoring.
        if _necesita_expansion and os.environ.get("BIORAG_WORDNET_ENABLED", "1") != "0":
          try:
            from core.stopwords import STOPWORDS_ES
            from nltk.corpus import wordnet as _wn
            tokens_frase_orig = [w for w in frase_limpia_filtrada.split() if len(w) >= 3]
            
            wordnet_terms = []
            for token in tokens_frase_orig[:6]:  # máx 6 tokens originales
                token_l = token.lower()
                if token_l in STOPWORDS_ES:
                    continue
                # Si la palabra tiene synsets en español (OMW), es palabra española -> no expandir con inglés
                try:
                    spa_synsets = _wn.synsets(token_l, lang='spa')
                    if spa_synsets:
                        continue
                except Exception:
                    pass
                
                # Solo si es ASCII y parece término técnico en inglés
                import re as _re
                if _re.match(r'^[a-zA-Z]{3,}$', token):
                    try:
                        synsets = _wn.synsets(token)
                        for s in synsets[:2]:
                            for l in s.lemmas():
                                name = l.name().replace('_', ' ')
                                if name.lower() != token.lower() and name not in wordnet_terms:
                                    wordnet_terms.append(name)
                                    if len(wordnet_terms) >= 8:
                                        break
                            if len(wordnet_terms) >= 8:
                                break
                    except Exception:
                        pass
            if wordnet_terms:
                frase = frase + " " + " ".join(wordnet_terms)
          except Exception:
            pass  # WordNet no disponible — fallback silencioso

        # ── DOMAIN DICT: Expansión por diccionario de dominio técnico ──
        # Cache: carga el diccionario una vez por instancia de cerebro.
        # Solo expande sobre los tokens ORIGINALES de la query, no sobre lo ya expandido.
        if _necesita_expansion:
          try:
            if not hasattr(self, '_domain_dict_cache'):
                cursor_dict = self.conn.execute(
                    "SELECT term, synonyms FROM concept_hub_domain_dict"
                )
                self._domain_dict_cache = {row[0]: row[1] for row in cursor_dict.fetchall()}
            tokens_originales = frase_limpia_filtrada.split()
            domain_terms = []
            for token in tokens_originales:
                token_lower = token.lower()
                if token_lower in self._domain_dict_cache and self._domain_dict_cache[token_lower]:
                    synonyms = self._domain_dict_cache[token_lower].split(',')
                    domain_terms.extend(synonyms[:3])  # máx 3 sinónimos por término
            if domain_terms:
                frase = frase + " " + " ".join(domain_terms)
          except Exception:
            pass  # Tabla domain_dict no existe aún — fallback silencioso

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
            if constants.EPISTEMICO_METADATA:
                self._epistemico_publicar_sin_consulta()
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

        def _fts_safe_term(term):
            """Split hyphenated tokens so FTS5 doesn't parse '-' as NOT operator.
            'fin-aprendizaje-creerse' -> 'fin aprendizaje creerse'"""
            import re as _re
            parts = _re.split(r'[-]+', term)
            return " ".join(p for p in parts if p)

        def _fts_safe_phrase(phrase):
            """Apply _fts_safe_term to each whitespace-separated token in a phrase."""
            return " ".join(_fts_safe_term(t) for t in phrase.split())

        # RF-18 (spec 001): simetría de acentos con la columna sustantivos_clave.
        # Evidencia empírica T7 (2026-09-17): FTS5 trigram es accent-SENSITIVE en
        # ambos lados; el contenido/concepto/sinónimos del corpus conserva tildes
        # originales. Normalizar la query general aquí ROMPE el matching contra ese
        # contenido (MATCH 'metodologia' -> 0 hits vs contenido "metodología"), lo que
        # regresionó por_tema en evaluar_qa (89.23% -> 81.54%). La simetría real se
        # resuelve SOLO en el boost de sustantivos_clave (columna que siempre se
        # almacena sin tildes) — ver bloque RF-19 abajo. La query principal se envía
        # tal cual al fts_match.
        frase_fts = frase
        parafrasis_fts = parafrasis_list

        # ponytail: no semantic expansion table — agent passes synonyms as parafrasis_list directly
        if modo_estricto:
            if parafrasis_fts:
                fts_match = " OR ".join(f"({' AND '.join(_fts_safe_phrase(v).split())})" for v in [frase_fts] + parafrasis_fts)
            elif len(frase_fts.split()) > 1:
                fts_match = " AND ".join(_fts_safe_phrase(frase_fts).split())
            else:
                fts_match = _fts_safe_phrase(frase_fts)
        elif parafrasis_fts:
            fts_variantes = [f'"{_fts_safe_phrase(frase_fts)}"'] + [f'"{_fts_safe_phrase(p)}"' for p in parafrasis_fts]
            fts_match = " OR ".join(fts_variantes)
        elif len(frase_fts.split()) > 1:
            fts_match = " OR ".join(_fts_safe_phrase(frase_fts).split())
        else:
            fts_match = _fts_safe_phrase(frase_fts)

        # RF-19 (spec 001): boost por sustantivos_clave — condición MATCH adicional en la
        # columna dedicada (peso BM25 4.0x según RF-5). Solo en modo no estricto (path
        # default): en estricto un OR debilitaría la semántica AND. Solo se construye cuando
        # se provee, porque el FTS de snapshots legacy (3 columnas) no tiene la columna.
        if sustantivos_clave_boost and not modo_estricto:
            sk_tokens = [t for t in _quitar_acentos(str(sustantivos_clave_boost)).split(",") if t]
            if sk_tokens:
                sk_fts = " OR ".join(f'"{_fts_safe_term(t)}"' for t in sk_tokens)
                boost_match = f"sustantivos_clave:({sk_fts})"
                fts_match = f"({fts_match}) OR {boost_match}" if fts_match else boost_match
        sql = """
            SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                   l.estado, l.asociaciones,
                   bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val
            FROM largo_plazo_fts f
            CROSS JOIN largo_plazo l ON l.rowid = f.rowid
            WHERE largo_plazo_fts MATCH ?{filtro}
            ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico)
        """.format(filtro=clause)

        todos = []
        bm25_raw = {}  # concepto -> raw BM25 from FTS5
        # Split hyphenated tokens for FTS5 safety and better matching
        palabras_raw = [w for w in frase.split() if len(w) >= 2]
        palabras = []
        for w in palabras_raw:
            partes = re.split(r'[-]+', w)
            palabras.extend(p for p in partes if p and len(p) >= 2)
        if not palabras:
            palabras = palabras_raw
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
        # Split hyphenated tokens for better substring matching.
        palabras_like = []
        for w in frase.split():
            if len(w) >= 2:
                partes = re.split(r'[-]+', w)
                palabras_like.extend(p for p in partes if p and len(p) >= 2)
        if not palabras_like:
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
        # v30.2: Generación FTS desacoplada (B2) — sql_con_pc = sql (sin pc_clause en NEAR+AND+OR).
        # El filtrado destructivo de FTS se reemplaza por el Quality Gate de Fallback 2.1 (B3).
        sql_con_pc = sql
        pc_params = []

        # Intentar NEAR query primero (palabras cercanas entre sí)
        # Split hyphenated tokens so FTS5 doesn't parse '-' as NOT operator
        palabras_safe = []
        for w in palabras:
            partes = re.split(r'[-]+', w)
            palabras_safe.extend(p for p in partes if p and len(p) >= 2)
        if not solo_protegidos and len(palabras_safe) > 1:
            near_query = f'NEAR({" ".join(palabras_safe)}, 15)'
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

        # NEAR early-exit fix: si NEAR devolvió candidatos pero con pool pequeño (3 <= len(todos) < limite),
        # merge con los mejores candidatos de BM25 OR en vez de bloquear el fallback (caso 0497)
        if not solo_protegidos and 3 <= len(todos) < limite and fts_match:
            try:
                self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))
                _raw = self.cursor.fetchall()
                seen_rowids = {r[0] for r in todos}
                for r in _raw:
                    if r[0] not in seen_rowids:
                        todos.append(r[:6])
                        bm25_raw[r[1]] = r[6]
                        if r[1] not in origen_scores:
                            origen_scores[r[1]] = ("literal", 0.0)
                        seen_rowids.add(r[0])
            except sqlite3.OperationalError:
                pass

        # Store FTS5-only concepts for pseudo-relevance feedback (before content expansion)
        fts5_conceptos = [r[1] for r in todos if r[1]]

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
                    f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb} ORDER BY rowid LIMIT {sql_limit}"
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
                                    (fts_q,) + pc_lat_params + (constants.CANDIDATOS_SIMILITUD,)
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
                                    s = score_similitud_latente(self.cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache, cerebro=self)
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
            sql_snap = sql_con_pc.replace("ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico)",
                                          "AND l.ultimo_acceso > ? ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico) LIMIT 5")
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
                            evocados, parent_map = self._evocacion_por_cadena(semillas)
                            self.last_parent_map = parent_map
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
        # v30.2 (B3): Fallback Quality Gate desacoplado del tamaño de pool.
        # Se activa si len(todos) < 3 O si ningún candidato FTS alcanza max_cov >= 0.60.
        # Usa _tokenizar_normalizado de core.fallback_simbolico (Strict Real: sin subcadenas espurias).
        from core.fallback_simbolico import _tokenizar_normalizado as _fb_tok
        _q_toks_fb = _fb_tok(query)
        def _calc_strict_cov(_r):
            _d_toks = _fb_tok(f"{_r[1]} {_r[2] or ''}")
            return len(_q_toks_fb & _d_toks) / len(_q_toks_fb) if _q_toks_fb else 0.0
        _max_cov_fb = max((_calc_strict_cov(_r) for _r in todos), default=0.0) if _q_toks_fb else 0.0
        _fb_activo = len(todos) < 3 or (len(_q_toks_fb) >= 2 and _max_cov_fb < 0.60)

        if not modo_estricto and _fb_activo and len(query) >= 3:
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
                        # Promover origen_scores a "simbolico" si la puntuación simbólica es superior
                        prev_origen, prev_sc = origen_scores.get(conc, (None, 0.0))
                        if prev_origen != "simbolico" or score_fb > prev_sc:
                            origen_scores[conc] = ("simbolico", score_fb)
            except ImportError:
                pass
            except Exception:
                pass

        # ─── Fallback 2.2: Expansión Sináptica (spreading activation) ───
        # Cuando todas las capas devuelven < 3 resultados, usar el grafo de sinapsis
        # para encontrar nodos conectados a las semillas (nodos que SÍ matchean).
        # Automático — no requiere configuración.
        if not modo_estricto and len(todos) < 3 and len(query) >= 2:
            try:
                from core.similitud_conceptual import buscar_por_similitud_latente
                latente_results = buscar_por_similitud_latente(
                    self.cursor, query, limite=max(limite, 5), umbral=0.3, cerebro=self
                )
                seen_rowids = {r[0] for r in todos}
                for lat_score, row in latente_results:
                    if row[0] not in seen_rowids:
                        todos.append(row[:6])
                        seen_rowids.add(row[0])
                        # Opción B: no usar lat_score para score_latente.
                        # Los nodos latentes ya tienen sus señales (BM25, dims, PPMI)
                        # computadas en el loop principal; _calcular_score_hibrido
                        # calcula score_latente desde sus señales base.
                        if row[1] not in origen_scores:
                            origen_scores[row[1]] = ("latente", 0.0)
            except ImportError:
                pass
            except Exception:
                pass

        # ─── Fallback 2.5 (E1): SDM binario 2048 bits ───
        # POR QUÉ aquí y no en scoring: el gold ausente del pool no se recupera
        # reordenando. Solo se activa si FTS+fallbacks dejaron < 3 candidatos y
        # la consulta tiene ≥ 3 tokens (consultas negativas cortas no disparan).
        # No toca layout SDM. No fusiona nodos. QCR sigue activo (FP).
        if (
            constants.SDM_FALLBACK_ACTIVO
            and not modo_estricto
            and len(todos) < 3
            and len(re.findall(r"\w{2,}", query or "")) >= 3
        ):
            try:
                from core.sdm import rescatar_fallback_sdm
                _sdm_hits = rescatar_fallback_sdm(
                    self, query, limite=max(constants.SDM_FALLBACK_K, limite or 5)
                )
                _seen_sdm = {r[1] for r in todos}
                for hit in _sdm_hits:
                    conc = hit["concepto"]
                    if conc in _seen_sdm:
                        if conc not in origen_scores:
                            origen_scores[conc] = ("sdm", float(hit["similitud"]))
                        continue
                    self.cursor.execute(
                        "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                        "FROM largo_plazo WHERE concepto = ?",
                        (conc,),
                    )
                    row = self.cursor.fetchone()
                    if row and (profundidad == "profundo" or row[4] == "activo"):
                        todos.append(row)
                        _seen_sdm.add(conc)
                        origen_scores[conc] = ("sdm", float(hit["similitud"]))
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
            if len(palabras_sin) <= 3:
                try:
                    from core.fallback_simbolico import expandir_query_wordnet
                    syn_wn = expandir_query_wordnet(set(palabras_sin))
                    palabras_sin.extend([w for w in syn_wn if len(w) >= 3][:5])
                except Exception:
                    pass
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

        # ── Fase C: índice invertido de formas aprendidas (GENERACIÓN, no ranking).
        # POR QUÉ aquí: el gold debe entrar al pool ANTES de _calcular_score_hibrido.
        # No toca FTS ni pesos. Solo inyecta nodos canónicos de episodios explicit/consolidated.
        try:
            from core.lexical_learning import resolver_formas_aprendidas
            _lex_hits = resolver_formas_aprendidas(self, frase_limpia or query or frase)
            if _lex_hits:
                _seen_lex = {r[1] for r in todos}
                for hit in _lex_hits:
                    conc = hit["canonical_concept"]
                    if conc in _seen_lex:
                        origen_scores[conc] = ("lexico_aprendido", hit["confidence"])
                        continue
                    self.cursor.execute(
                        "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                        "FROM largo_plazo WHERE concepto = ?",
                        (conc,),
                    )
                    row = self.cursor.fetchone()
                    if row and (profundidad == "profundo" or row[4] == "activo"):
                        todos.append(row)
                        _seen_lex.add(conc)
                        origen_scores[conc] = ("lexico_aprendido", hit["confidence"])
        except Exception:
            pass

            # v22.1: Content-based expansion for por_tema queries ───
        # Find nodes where query words appear in content, but ONLY when FTS returns
        # few results (indicates the query is thematic, not literal).
        # This ensures thematically relevant nodes are in the candidate pool.
        # Key: requires >= 2 word matches (not just 1) to avoid noise.
        # Results are prepended (not appended) to ensure they appear in top-N for thematic scoring.
        # Also: compute content_match_count for ALL nodes (not just new ones) so
        # FTS-found nodes that also match content get boosted.
        content_match_counts = {}
        if not modo_estricto and len(palabras) >= 2:
            # Compute match count for ALL current candidates
            match_count_clause = " + ".join(
                f"CASE WHEN LOWER(l.contenido) LIKE '%' || ? || '%' THEN 1 ELSE 0 END"
                for _ in palabras
            )
            match_params = [w.lower() for w in palabras]
            all_conceptos = [r[1] for r in todos if r[1]]
            if all_conceptos:
                ph = ",".join(["?" for _ in all_conceptos])
                try:
                    self.cursor.execute(
                        f"SELECT concepto, ({match_count_clause}) AS match_count "
                        f"FROM largo_plazo WHERE concepto IN ({ph})",
                        match_params + all_conceptos
                    )
                    for conc, mc in self.cursor.fetchall():
                        content_match_counts[conc] = mc
                except sqlite3.OperationalError:
                    pass

            # Only expand candidate pool when FTS returned few results
            if len(todos) < 3:
                seen_ids = {r[0] for r in todos}
                seen_conceptos = {r[1] for r in todos}
                min_matches = min(2, len(palabras))
                content_sql = f"""
                    SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                           l.estado, l.asociaciones,
                           ({match_count_clause}) AS match_count
                    FROM largo_plazo l
                    WHERE l.estado = 'activo'
                      AND ({match_count_clause}) >= ?
                    ORDER BY match_count DESC, l.peso_sinaptico DESC
                    LIMIT ?
                """
                try:
                    self.cursor.execute(content_sql, match_params + match_params + [min_matches, max(limite * 3, 20)])
                    content_new = []
                    for row in self.cursor.fetchall():
                        if row[0] not in seen_ids and row[1] not in seen_conceptos:
                            content_new.append(row[:6])
                            seen_ids.add(row[0])
                            seen_conceptos.add(row[1])
                            if row[1] not in origen_scores:
                                origen_scores[row[1]] = ("contenido", min(1.0, row[6] / len(palabras) * 1.5))
                            content_match_counts[row[1]] = row[6]
                    if content_new:
                        todos = content_new + todos
                except sqlite3.OperationalError:
                    pass

        # Multihop v1: expansion 1-salto (flag OFF default; gate decide).
        # Solo activos+activos: jamas inyecta en dormido/profundo/negativo-921.
        if constants.MULTIHOP_EXPANSION and profundidad == "activos" and todos:
            try:
                _mh_nuevos = self._multihop_vecinos(
                    [r[1] for r in todos if r[1]],
                    {r[1] for r in todos if r[1]},
                    constants.MULTIHOP_MAX_TOTAL,
                )
                if _mh_nuevos:
                    _mh_nombres = [c for c, _ in _mh_nuevos]
                    _mh_ph = ",".join("?" * len(_mh_nombres))
                    _mh_rows = {
                        row[1]: row
                        for row in self.cursor.execute(
                            "SELECT rowid, concepto, contenido, peso_sinaptico,"
                            " estado, asociaciones FROM largo_plazo"
                            " WHERE concepto IN (%s) AND estado='activo'" % _mh_ph,
                            tuple(_mh_nombres),
                        )
                    }
                    for _c in _mh_nombres:
                        _row = _mh_rows.get(_c)
                        if _row is None:
                            continue
                        todos.append(_row)
                        if _c not in origen_scores:
                            origen_scores[_c] = ("expansion", constants.MULTIHOP_PRIOR)
            except Exception as e:
                logger.warning("multihop: expansion fallo (%s: %s)", type(e).__name__, e)

        # [AUDIT #15 — PPMI Vector Retrieval: DESCARTADO tras 3 iteraciones]
        # Iteración 1 (pool < 3, antes de SA): mató SA (27→1 queries). Revertido.
        # Iteración 2 (pool < 3, después de SA): neutral, 0 rescates (pool siempre >= 3).
        # Iteración 3 (always-on, cos > 0.55): +6 regresiones por ruido PPMI.
        # Causa raíz: FTS5 OR con trigram infla pool a 200+ nodos → bloquea fallbacks.
        # La solución correcta no es inyectar vía PPMI, es reducir ruido FTS5.

        # ─── Capa 3: Pseudo-relevance feedback for query dimensions ───
        # If no explicit dimensiones_ids but there's a query and FTS5 results,
        # use top-K FTS5 results' dimensions as pseudo-query dimensions.
        # Only trigger if FTS5 returned ≥3 results (semantic query, not noise).
        # This captures domain-specific dims (identidad_artificial, intencion_documentar)
        # that WordNet cannot classify from surface words.
        if not dimensiones_ids and frase.strip() and len(fts5_conceptos) >= 3:
            try:
                top_fts5_conceptos = fts5_conceptos[:5]
                if top_fts5_conceptos:
                    placeholders = ",".join(["?" for _ in top_fts5_conceptos])
                    dim_sql = f"""
                        SELECT DISTINCT dimension_id
                        FROM largo_plazo_dimensiones
                        WHERE concepto IN ({placeholders})
                    """
                    self.cursor.execute(dim_sql, top_fts5_conceptos)
                    pseudo_dims = [row[0] for row in self.cursor.fetchall()]
                    if pseudo_dims:
                        dimensiones_ids = pseudo_dims
            except Exception:
                pass  # Silently skip
        
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
                            w_map[d_id] = float(conf if auto_gen else 1.0)
                    except Exception:
                        pass
                    for d_id in query_dim_set:
                        if d_id not in w_map:
                            w_map[d_id] = float(1.0)
                            
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
            if constants.DIM_RESONANCIA:
                # Fase A (resonancia dimensional): candidatura por merito
                # (shared DESC), sin sesgo rowid del LIMIT-500. EXP-Q: los 3
                # golds pasaban el umbral pero caian fuera de la ventana.
                fallback_sql = f"""
                    SELECT d.concepto, GROUP_CONCAT(d.dimension_id)
                    FROM largo_plazo_dimensiones d
                    JOIN largo_plazo l ON l.concepto = d.concepto
                    WHERE d.dimension_id IN ({dim_ids_str}){fb_where_extra}
                    GROUP BY d.concepto
                    HAVING COUNT(*) >= ?
                    ORDER BY COUNT(*) DESC, l.peso_sinaptico DESC, d.concepto ASC
                    LIMIT ?
                """
            else:
                fallback_sql = f"""
                    SELECT d.concepto, d.dimension_id
                    FROM largo_plazo_dimensiones d
                    JOIN largo_plazo l ON l.concepto = d.concepto
                    WHERE d.dimension_id IN ({dim_ids_str}){fb_where_extra}
                    LIMIT 500
                """
            try:
                if constants.DIM_RESONANCIA:
                    self.cursor.execute(fallback_sql, tuple(fb_filtros_params) + (umbral_efectivo, constants.DIM_RESONANCIA_K))
                    concepto_fb_ids = {}
                    for concepto, dims_csv in self.cursor.fetchall():
                        concepto_fb_ids[concepto] = [int(x) for x in (dims_csv or "").split(",") if x]
                else:
                    self.cursor.execute(fallback_sql, tuple(fb_filtros_params))
                    concepto_fb_ids = {}
                    for concepto, dim_id in self.cursor.fetchall():
                        if concepto not in concepto_fb_ids:
                            concepto_fb_ids[concepto] = []
                        concepto_fb_ids[concepto].append(dim_id)
                if not constants.DIM_RESONANCIA and len(concepto_fb_ids) > 50:
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
                        w_map_fb[d_id] = float(conf if auto_gen else 1.0)
                except Exception:
                    pass
                for d_id in query_dim_set:
                    if d_id not in w_map_fb:
                        w_map_fb[d_id] = float(1.0)
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

        # Normalización BM25 relativa intra-query (invariante a escala del corpus N).
        # Reemplaza la constante fija 3.0 que saturaba y comprimía scores al crecer el corpus.
        # Calcula min/max sobre los candidatos de la query actual para preservar discriminación.
        # Aplica escala = min(1.0, hi) para evitar inflar ruido en queries sin match fuerte (typos).
        # Guarda _last_bm25_bounds para que buscar_por_rafaga comparta la misma escala en biorag_recordar.
        raw_vals = [abs(v) for v in bm25_raw.values()]
        if raw_vals:
            lo, hi = min(raw_vals), max(raw_vals)
            rango = hi - lo if hi > lo else 1.0
            escala = min(1.0, hi) if hi > 0 else 1.0
            if hi > lo:
                bm25_norm_map = {c: ((abs(v) - lo) / rango) * escala for c, v in bm25_raw.items()}
            elif len(bm25_raw) == 1 and hi >= 3.0:
                bm25_norm_map = {c: escala for c, v in bm25_raw.items()}
            else:
                bm25_norm_map = {c: 0.0 for c, v in bm25_raw.items()}
            self._last_bm25_bounds = (lo, hi, escala)
        else:
            bm25_norm_map = {}
            self._last_bm25_bounds = None

        # Asignar BM25 sintético a candidatos de rescate (typo, simbólico, dimensional_fallback, concepto)
        # para que no compitan con bm25=0 frente a matches parciales débiles,
        # preservando la escala intra-query para mantener 0% falsos positivos en ruido.
        escala_activa = self._last_bm25_bounds[2] if (self._last_bm25_bounds and self._last_bm25_bounds[2] > 0.3) else 0.8
        for conc, (origen, sc_capa) in origen_scores.items():
            if conc not in bm25_norm_map and origen in ("typo", "simbolico", "dimensional_fallback", "concepto", "lexico_aprendido"):
                bm25_norm_map[conc] = min(1.0, escala_activa * float(sc_capa or 0.5))

        # ─── Capa 4.5: Precompute predicate data for scoring ───
        # Fetch predicate contexto (keywords) for all candidates
        conceptos_todos = [r[1] for r in todos if r[1]]
        pred_contexto_map = {}  # concepto -> set of predicate tokens
        if conceptos_todos:
            ph_conceptos = ",".join(["?" for _ in conceptos_todos])
            try:
                self.cursor.execute(
                    f"SELECT concepto, COALESCE(contexto, '') FROM predicados WHERE concepto IN ({ph_conceptos})",
                    conceptos_todos
                )
                for conc, ctx in self.cursor.fetchall():
                    if conc not in pred_contexto_map:
                        pred_contexto_map[conc] = set()
                    if ctx:
                        pred_contexto_map[conc].update(
                            t for t in re.findall(r'\w{3,}', ctx.lower()) if len(t) >= 3
                        )
            except Exception:
                pass

        # ─── Capa 5: Score por grupo semántico (WordNet lexnames) ───
        grupo_scores_map = {}
        # Skip WordNet for very short queries (< 3 chars) or very long (> 100 chars, likely garbage/adversarial)
        # NLTK load takes ~3s on first run, and long queries are not legitimate semantic queries
        if 3 <= len(frase) <= 100 and os.environ.get("BIORAG_WORDNET_ENABLED", "1") != "0":
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

        # ── Precompute PPMI Query Vector ONCE before candidate loop ──
        _ppmi_vq = None
        _ppmi_q_set = set(tokens_query) if tokens_query else set()
        _ppmi_es_corta = len(_ppmi_q_set) <= 2
        _ppmi_pool_set = {r[1] for r in todos}
        if constants.PPMI_VECTOR_WEIGHT > 0.0 and self._ppmi_index and tokens_query:
            try:
                _ppmi_vq = self._ppmi_index.vector_query(list(tokens_query))
            except Exception:
                _ppmi_vq = None

        # v22.1: Pre-compute thematic profiles and lazy-cache pairwise scores
        # On-demand calculation per candidate pair (O(K^2) for K=50 top candidates instead of O(N^2) for N=800 all nodes)
        _perfiles_tematicos = {}
        _idf_tematico = {}
        _todas_dims = None
        try:
            from core.tematica import calcular_perfiles_presencia, calcular_idf_dims, similitud_tematica
            if self._thematic_profiles_cache is not None:
                _perfiles_tematicos = self._thematic_profiles_cache
                _idf_tematico = self._thematic_idf_cache
            else:
                _perfiles_tematicos = calcular_perfiles_presencia(self)
                _idf_tematico = calcular_idf_dims(self)
                self._thematic_profiles_cache = _perfiles_tematicos
                self._thematic_idf_cache = _idf_tematico
                self._thematic_scores_cache = {}
            if self._thematic_scores_cache is None:
                self._thematic_scores_cache = {}
            _todas_dims = set(_idf_tematico.keys())
        except Exception:
            pass

        # ─── Precompute Spreading Activation (cadena) scores from top seeds ───
        cadena_scores_map = {}
        if not modo_estricto and todos:
            try:
                semillas_top = [r[1] for r in todos[:5] if r[1]]
                if semillas_top:
                    evocados, _ = self._evocacion_por_cadena(semillas_top)
                    for conc_ev, decay_score, _ in evocados:
                        cadena_scores_map[conc_ev] = max(cadena_scores_map.get(conc_ev, 0.0), decay_score)
            except Exception:
                pass

        # E6: NCD zlib O(k) sobre el pool (query vs concepto+contenido).
        ncd_map = {}
        if constants.NCD_PESO > 0.0 and todos:
            try:
                ncd_map = self._ncd_sims_pool(
                    query,
                    [(r[1], r[2]) for r in todos if r[1]],
                )
            except Exception:
                ncd_map = {}

        # E7: JSD adaptativo una vez por query (Nt tokens >=3).
        _jsd_w_e7 = self._jsd_weight_adaptativo(query)

        episodio_map = {}
        if constants.EPISODIO_TEMPORAL_PESO > 0.0 and todos:
            try:
                episodio_map = self._afinidad_temporal_pool([r[1] for r in todos if r[1]])
            except Exception:
                episodio_map = {}

        # F3: analogia relacional. Con flags 0 ni regex ni coseno (byte-identico).
        analogia_map = {}
        if (analogia or constants.ANALOGIA_DETECTAR) and constants.ANALOGIA_PESO > 0.0 and todos:
            try:
                from core.ppmi_hybrid_search import detectar_analogia, _vec_concepto
                _abc = detectar_analogia(query)
                if _abc and self._ppmi_index is not None:
                    _vecs = self._ppmi_index.vecs or {}
                    _va = _vec_concepto(_vecs, _abc[0])
                    _vb = _vec_concepto(_vecs, _abc[1])
                    _vc = _vec_concepto(_vecs, _abc[2])
                    if _va is not None and _vb is not None and _vc is not None:
                        import numpy as _np
                        _vt = _np.asarray(_vc, dtype="float64") + (
                            _np.asarray(_vb, dtype="float64") - _np.asarray(_va, dtype="float64")
                        )
                        analogia_map = self._analogia_scores_pool(
                            _vt, [r[1] for r in todos if r[1]]
                        )
            except Exception:
                analogia_map = {}

        # F5: campo semantico. Peso 0 -> dict vacio, ni gauss ni matmul.
        campo_map = {}
        if constants.CAMPO_POTENCIAL_PESO > 0.0 and todos and _ppmi_vq is not None:
            try:
                from core.ppmi_hybrid_search import calcular_campo_potencial_ppmi
                _pool_c = [r[1] for r in todos if r[1]][:constants.CAMPO_K if constants.CAMPO_K > 0 else 0]
                if _pool_c:
                    campo_map = calcular_campo_potencial_ppmi(
                        self, _ppmi_vq, _pool_c, sigma=constants.CAMPO_SIGMA
                    )
            except Exception:
                campo_map = {}

        # Calcular score hibrido para cada resultado (fórmula única 9 señales)
        total = len(todos)
        resultados_con_hibrido = []
        for _, (rowid, concepto, contenido, peso, estado, asociaciones) in enumerate(todos):
            origen, score_capa = origen_scores.get(concepto, ("literal", 0.0))
            dim_score = dim_scores_map.get(concepto, 0.0)
            _q_norm = query.lower().replace(" ", "_").replace("-", "_")
            _c_norm = (concepto or "").lower().replace(" ", "_").replace("-", "_")
            match_exacto = (_q_norm == _c_norm) or (bool(tokens_query) and tokens_query == _tokenizar_normalizado(concepto))
            # v22.1: Content-expanded nodes get a boost (they matched on content, not just FTS)
            score_latente = score_capa if origen in ("latente", "expansion", "contenido") else 0.0
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
            score_cadena = max(score_capa if origen == "cadena" else 0.0, cadena_scores_map.get(concepto, 0.0))
            
            # Calculate symbolic similarity for concept name and synonyms, and update ratios
            concepto_s_score = score_simbolico_concepto(tokens_query, concepto)
            concepto_ratio = max(resultados_concepto.get(concepto, 0.0), concepto_s_score)
            
            sinonimos_str = concepto_sinonimos_map.get(concepto, "")
            sinonimos_s_score = score_simbolico_sinonimos(tokens_query, sinonimos_str)
            sinonimos_ratio = max(resultados_semantica.get(concepto, 0.0), sinonimos_s_score)

            # Fix Grupo C v2 (2026-08-13): el piso de sinónimos (memory_store.py:3170,
            # sinonimos_ratio >= 0.95) no disparaba cuando la query es 100% stopword
            # (ej. "buscar") — score_simbolico_sinonimos recibe tokens_query vacío
            # (fallback_simbolico.py:47 elimina stopwords) y devuelve 0.0, y Capa 4
            # (memory_store.py:4066, condición `if conc not in todos`) nunca llena
            # resultados_semantica para nodos que entraron por otra capa (ej. FTS
            # literal). Resultado: sinonimos_ratio = max(0,0) = 0 aunque la palabra SÍ
            # esté en el campo sinonimos del nodo. Fix v2 RESTRICTIVO: el substring
            # solo aplica cuando tokens_query está vacío (query 100% stopword). Fue
            # necesario restringirlo tras medir que la versión amplia (criterio
            # substring para toda query) elevaba nodos ruidosos al piso y regresaba
            # los casos 0532 y 0781 del benchmark. Con esta condición, "boost" y
            # "falso positivo" (con tokens reales) no se ven afectados, y solo se
            # rescata el caso exacto del bug: query sin tokens simbólicos cuyo
            # sinónimo está en el campo sinonimos del nodo, mismo criterio LIKE de
            # Capa 4 (memory_store.py:4067).
            sinonimos_substring = 0.0
            if not tokens_query and sinonimos_str and palabras_like:
                sinonimos_substring = sum(
                    1 for w in palabras_like if w.lower() in sinonimos_str.lower()
                ) / len(palabras_like)
            sinonimos_ratio = max(sinonimos_ratio, sinonimos_substring)

            # v22.1: Compute thematic score (presence + absence of dimensions)
            # On-demand pairwise calculation over top-15 candidates with memoization (O(1) cached)
            # Fix: per-candidate gate — tematico_score solo si hay evidencia léxica real
            # (bm25 > 0.001 o concepto_ratio > 0.001) Y no hay señal fuerte de sinónimo
            tematico_score = 0.0
            bm25_val = bm25_norm_map.get(concepto, 0.0)
            if _perfiles_tematicos and _todas_dims and (bm25_val > 0.001 or concepto_ratio > 0.001) and sinonimos_ratio < 0.5:
                sims = []
                for _, (other_concepto, _, _, _, _, _) in enumerate(todos[:15]):
                    if other_concepto != concepto and concepto and other_concepto:
                        c1, c2 = str(concepto), str(other_concepto)
                        pair_key = (c1, c2) if c1 <= c2 else (c2, c1)
                        if pair_key not in self._thematic_scores_cache:
                            s = similitud_tematica(concepto, other_concepto, self, _perfiles_tematicos, _idf_tematico)
                            self._thematic_scores_cache[pair_key] = s
                        else:
                            s = self._thematic_scores_cache[pair_key]
                        if s > 0.02:  # umbral estable
                            sims.append(s)
                if sims:
                    tematico_score = min(1.0, sum(sims) / len(sims) * 3.0)  # multiplicador óptimo 3.0

            # Signal #11: Jensen-Shannon Divergence (distributional overlap)
            jsd_val = 0.0
            if _jsd_w_e7 > 0.0:
                node_text = f"{concepto} {contenido or ''}"
                jsd_val = self._calcular_jsd(query, node_text)

            # Signal #12: Predicate matching (query tokens vs predicate keywords)
            # ⚠️ CANIBALIZACIÓN DEMOSTRADA 2026-08-04: si se re-corre el backfill de
            # predicados (scripts/backfill_predicados.py), re-verificar contra el
            # re-ranking jaccard (Fase C). El backfill restaura recuperación perdida
            # pero canibaliza la señal #12 con jaccard activo. Capacidad disponible,
            # NO enganchada. Ver nodo biorag: backfill_predicados_restaura_parcial_no_84_62_y_canibaliza_con_jaccard.
            pred_val = 0.0
            pred_tokens = pred_contexto_map.get(concepto, set())
            if pred_tokens and tokens_query:
                matches = sum(1 for t in tokens_query if t in pred_tokens)
                pred_val = min(1.0, matches / max(1, len(tokens_query)))

            # Signal #13: PPMI+SVD vector similarity (v26.0)
            # ON por defecto (constants.PPMI_VECTOR_WEIGHT=0.15). Apagar con: export BIORAG_PPMI_WEIGHT=0.0
            ppmi_val = 0.0
            if _ppmi_vq is not None:
                try:
                    from core.ppmi_hybrid_search import score_candidato
                    q_toks_list = list(tokens_query)
                    q_set = set(q_toks_list)
                    es_corta = len(q_set) <= 2
                    pool_set = {r[1] for r in todos}
                    vq = self._ppmi_index.vector_query(q_toks_list)
                    _raw_ppmi, _ = score_candidato(self._ppmi_index, vq, q_set, es_corta, concepto, pool_set)
                    # Normalizar: el score bruto de score_candidato ronda 0-2 para query corta (dividir por 2.0), 0-1 para larga
                    ppmi_val = min(1.0, max(0.0, _raw_ppmi / (2.0 if es_corta else 1.0)))

                except Exception:
                    ppmi_val = 0.0

            # Signal #14: Concept Hub match
            hub_val = 0.0
            if hub_expansion:
                canonical_nodes = hub_expansion.get("canonical_nodes", [])
                hub_conf = hub_expansion.get("hub_confidence", 0.0)
                if concepto in canonical_nodes:
                    # Nodo canónico: boost fuerte (garantiza aparición en TOP)
                    hub_val = min(1.0, hub_conf * 2.0)
                elif any(concepto in cn for cn in canonical_nodes):
                    # Nodo vinculado al hub: boost medio
                    hub_val = min(0.8, hub_conf * 1.5)
                else:
                    # Nodo no relacionado: sin boost
                    hub_val = 0.0

            score_hibrido = self._calcular_score_hibrido(
                bm25_norm=bm25_norm_map.get(concepto, 0.0),
                dim_score=dim_score,
                peso_sinaptico=0.0 if ignore_peso_sinaptico else peso,
                concepto_ratio=concepto_ratio,
                sinonimos_ratio=sinonimos_ratio,
                score_latente=score_latente,
                score_cadena=score_cadena,
                asoc_count=len([v for v in (asociaciones or "").split(",") if v.strip()]),
                match_exacto=match_exacto,
                grupo_score=grupo_scores_map.get(concepto, 0.0),
                tematico_score=tematico_score,
                jsd_score=jsd_val,
                jsd_weight=_jsd_w_e7,
                pred_score=pred_val,
                ppmi_score=ppmi_val,
                hub_match=hub_val,
                ncd_score=ncd_map.get(concepto, 0.0),
                episodio_score=episodio_map.get(concepto, 0.0),
                analogia_score=analogia_map.get(concepto, 0.0),
                campo_score=campo_map.get(concepto, 0.0),
            )

            resultados_con_hibrido.append(
                (concepto, contenido, peso, estado, score_hibrido, asociaciones or "")
            )

        # Reordenar por score hibrido descendente
        resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

        # Promoción de candidatos generados por episodio léxico explícito.
        # POR QUÉ: el gold entra al pool (generación) pero el ranker híbrido no
        # conoce la enseñanza. No es un ranker genérico (EXP-N9); es el contrato
        # de «A significa B» con evidencia explicit/consolidated.
        if resultados_con_hibrido:
            _prom = []
            for conc, cont, peso, est, sc, asoc in resultados_con_hibrido:
                orig, conf_l = origen_scores.get(conc, ("", 0.0))
                if orig == "lexico_aprendido":
                    sc = max(sc, min(0.99, 0.88 + 0.10 * float(conf_l or 0.0)))
                _prom.append((conc, cont, peso, est, sc, asoc))
            resultados_con_hibrido = _prom
            resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

        # v26.2: Puerta QCR (Query Coverage Ratio) para consultas compuestas (>= 2 palabras)
        # Exige que al menos el 50% de los tokens de la consulta coincidan en el nodo/sinónimos/metadatos
        # para prevenir que 1 sola palabra accidental en textos largos genere Falsos Positivos.
        # Desactivable con export BIORAG_QCR_ACTIVO=0
        QCR_ACTIVO = os.getenv("BIORAG_QCR_ACTIVO", "1") == "1"
        # v26.4: El escape de capa ya no es binario — exige score_capa >= umbral (0.60).
        # Motivo: los orígenes semantica/dimensional_fallback sin piso generaban FPs (ratio bajo,
        # capa 0.25-0.33). Los orígenes simbolico nacen con capa >= 0.60 por construcción (fallback
        # simbolico umbral=0.60), así que este umbral preserva los rescates de typo/variante.
        # Costo residual conocido y documentado: 2 FP (capa 0.667/1.0) aceptados tras análisis
        # 921 casos (2026-08-11) — no existe señal (tokens ni capa) que los separe de los TP.
        QCR_ESCAPE_CAPA_MIN = float(os.getenv("BIORAG_QCR_ESCAPE_CAPA_MIN", "0.60"))
        # Concept Hub: nodos canónicos bypass QCR cuando el hub tiene alta confianza
        hub_canonical_set = set()
        if hub_expansion and hub_expansion.get("hub_confidence", 0) >= 0.4:
            hub_canonical_set = set(hub_expansion.get("canonical_nodes", []))
        q_tokens_qcr = [t.lower() for t in re.findall(r'\w{3,}', query)]
        _qcr_idf_map = {}
        if QCR_ACTIVO and constants.QCR_IDF_ACTIVO and q_tokens_qcr:
            try:
                _qcr_idf_map = self._idf_tokens_qcr(q_tokens_qcr)
            except Exception:
                _qcr_idf_map = {}
        _qcr_umbral = constants.QCR_IDF_UMBRAL if (constants.QCR_IDF_ACTIVO and _qcr_idf_map) else 0.50
        if QCR_ACTIVO and len(q_tokens_qcr) >= 2 and resultados_con_hibrido:
            filtrados_qcr = []
            _idf_den = sum(_qcr_idf_map.get(t, 1.0) for t in q_tokens_qcr) if _qcr_idf_map else float(len(q_tokens_qcr))
            for conc, cont, peso, est, sc, asoc in resultados_con_hibrido:
                # Bypass QCR para nodos canónicos del hub
                if conc in hub_canonical_set:
                    filtrados_qcr.append((conc, cont, peso, est, sc, asoc))
                    continue
                text_target = f"{conc} {cont} {concepto_sinonimos_map.get(conc, '')}".lower()
                if _qcr_idf_map:
                    _num = sum(_qcr_idf_map.get(t, 1.0) for t in q_tokens_qcr if t in text_target)
                    ratio_qcr = (_num / _idf_den) if _idf_den > 0 else 0.0
                else:
                    matches_qcr = sum(1 for t in q_tokens_qcr if t in text_target)
                    ratio_qcr = matches_qcr / len(q_tokens_qcr)
                origen_tipo, score_capa = origen_scores.get(conc, ("literal", 0.0))
                if ratio_qcr >= _qcr_umbral or (
                    origen_tipo in (
                        "semantica", "simbolico", "expansion", "dimensional_fallback",
                        "typo", "concepto", "lexico_aprendido",
                    )
                    and score_capa >= QCR_ESCAPE_CAPA_MIN
                ) or (
                    # Fase B (resonancia dimensional): escape calibrado T=0.45
                    # (40 neg max 0.0; Q-01 0.488). OFF = cortocircuito.
                    constants.DIM_ESCAPE and origen_tipo == "dimensional_fallback"
                    and score_capa >= constants.DIM_ESCAPE_T
                ):
                    filtrados_qcr.append((conc, cont, peso, est, sc, asoc))
                elif (constants.QCR_TYPO_ACTIVA and sc >= constants.QCR_TYPO_PISO
                        and constants._qcr_todos_cercanos(q_tokens_qcr, text_target, constants.QCR_TYPO_DIST)):
                    # F-QCR-D4: segunda oportunidad por typos (ver flags). Flag OFF:
                    # cortocircuito, path byte-identico.
                    filtrados_qcr.append((conc, cont, peso, est, sc, asoc))
            if filtrados_qcr:
                resultados_con_hibrido = filtrados_qcr

        # ── CONCEPT HUB: Post-procesamiento — promoción competitiva del nodo canónico ──
        # El canónico compite contra el mejor candidato léxico en vez de forzarse
        # incondicionalmente a TOP1. Esto evita que un Hub falso positivo (confianza
        # mínima 0.40 → score 0.38) desplace un match léxico perfecto (score 0.80).
        #
        # Regla:
        #   hub_gana = score_forzado >= mejor_score_lexico
        #   → True:  canónico va a TOP1 (semántica supera léxico)
        #   → False: canónico se inserta en su posición natural por score
        #             (presencia garantizada, no TOP1 garantizado)
        #
        # Para matches de alta confianza (1.0 → score 0.95) el hub siempre gana
        # porque el scoring híbrido máximo real es ~0.948 (TEST 3, invariante scoring).
        # Para matches de baja confianza (0.40 → score 0.38) el léxico gana si hay
        # cualquier candidato decente, que es el comportamiento correcto.
        if hub_expansion and hub_expansion.get("hub_confidence", 0) >= 0.4:
            primary_canonical = hub_expansion.get("canonical_nodes", [None])[0]
            if primary_canonical:
                score_forzado = min(0.95, hub_expansion["hub_confidence"] * 0.95)
                mejor_score_lexico = resultados_con_hibrido[0][4] if resultados_con_hibrido else 0.0
                hub_gana = score_forzado >= mejor_score_lexico

                # v30.1 — PISO DE PROMOCIÓN (fix de orden no monotónico).
                # Antes: cuando el hub ganaba se hacía insert(0, ...) con score_forzado,
                # que puede ser MENOR que el mejor score léxico (ej. confianza 0.467 →
                # 0.444 colocado encima de un léxico de 0.513). El resultado devuelto
                # quedaba con scores no ordenados descendente, rompiendo el contrato de
                # buscar_por_frase para todo consumidor que corte por score en vez de por
                # posición (mcp_server.py reordena los pools frase/ráfaga por r[4]).
                # Ahora: la promoción se expresa EN EL SCORE. Si el canónico va a TOP1,
                # su score se eleva al mejor léxico + 1 tick (0.0001, la resolución de
                # round(...,4)), así posición y score dicen lo mismo y el orden sobrevive
                # a cualquier re-sort posterior. La semántica de promoción no cambia: el
                # canónico sigue yendo a TOP1 cuando hub_gana.
                score_promocion = (
                    round(min(1.0, max(score_forzado, mejor_score_lexico + 0.0001)), 4)
                    if hub_gana else score_forzado
                )

                ya_existe = any(r[0] == primary_canonical for r in resultados_con_hibrido)
                if not ya_existe:
                    # Canónico ausente → traer desde DB
                    try:
                        self.cursor.execute(
                            "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones "
                            "FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
                            (primary_canonical,)
                        )
                        row = self.cursor.fetchone()
                        if row:
                            entrada = (row[0], row[1], row[2], row[3], score_promocion, row[4] or "")
                            if hub_gana:
                                # Hub supera al mejor léxico → TOP1
                                resultados_con_hibrido.insert(0, entrada)
                                origen_scores[primary_canonical] = ("concept_hub", hub_expansion["hub_confidence"])
                            else:
                                # Léxico supera al hub → insertar en posición que
                                # preserve orden por score (presencia garantizada)
                                pos = next(
                                    (i for i, r in enumerate(resultados_con_hibrido) if r[4] < score_promocion),
                                    len(resultados_con_hibrido)
                                )
                                resultados_con_hibrido.insert(pos, entrada)
                                origen_scores[primary_canonical] = ("concept_hub", hub_expansion["hub_confidence"])
                    except Exception as exc:
                        logger.warning(f"[BioRAG.ConceptHub] Error recuperando canónico '{primary_canonical}' de DB: {exc}")
                else:
                    # Canónico ya existe en resultados
                    idx = next(i for i, r in enumerate(resultados_con_hibrido) if r[0] == primary_canonical)
                    if hub_gana:
                        if idx > 0:
                            # Hub supera al mejor léxico → mover a TOP1
                            nodo = resultados_con_hibrido.pop(idx)
                            nodo_mod = list(nodo)
                            nodo_mod[4] = score_promocion
                            resultados_con_hibrido.insert(0, tuple(nodo_mod))
                        origen_scores[primary_canonical] = ("concept_hub", hub_expansion["hub_confidence"])
                        # Si no hub_gana: el canónico ya está en su posición natural,
                        # no lo movemos — el léxico merece el TOP1

        # Fase C (v22.2): Re-ranking jaccard léxico condicional.
        # OFF por defecto (BIORAG_RERANKING_JACCARD_ENABLED=0) — activación gradual
        # monitoreada contra el benchmark. Config ganadora del holdout 2026-08-04.
        if constants.RERANKING_JACCARD_ACTIVO:
            resultados_con_hibrido = self._rerank_jaccard_protect_r0(
                resultados_con_hibrido, frase_limpia, preview_chars=preview_chars
            )

        # v20.0 Inhibición Lateral GABA en Tiempo Real (Edelman 1987)
        # Si el candidato Top-1 es un atractor fuerte (score >= 0.80),
        # atenúa activamente a los competidores secundarios del mismo nicho (x0.60)
        # Ablación: export BIORAG_GABA_ACTIVO=0
        if constants.GABA_ACTIVO and resultados_con_hibrido and resultados_con_hibrido[0][4] >= 0.80:
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
        # RF-19 (spec 001): incluye la columna sustantivos_clave — un nodo boosteado por esa
        # columna dedicada (match en FTS con peso BM25 4.0x) no debe ser descartado aquí por no
        # ser prefijo del contenido/concepto/sinónimos.
        _ORIGENES_NO_LITERALES = {"typo", "expansion", "latente", "cadena", "simbolico", "dimensional_fallback", "semantica", "unicode", "lexico_aprendido", "sdm"}
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
                    f"(PALABRA_PREFIJO(?, concepto) = 1 OR PALABRA_PREFIJO(?, contenido) = 1 OR PALABRA_PREFIJO(?, COALESCE(sinonimos, '')) = 1 "
                    f"OR PALABRA_PREFIJO(?, COALESCE(sustantivos_clave, '')) = 1) "
                    f"AND concepto IN ({placeholders})",
                    (token, token, token, token) + tuple(conceptos_literal)
                )
                validos = {row[0] for row in self.cursor.fetchall()}
                resultados_con_hibrido = [r for r in literal_results if r[0] in validos] + non_literal_results

        # ── v30.1: GUARDIA DE ORDEN MONOTÓNICO (antes de paginar) ──────────
        # Los post-procesos (promoción del Concept Hub, filtro PALABRA_PREFIJO de una
        # palabra, re-ranking jaccard) reconstruyen la lista por posición, no por score.
        # El filtro PALABRA_PREFIJO concatenaba `literales_validos + no_literales` sin
        # reordenar, y cada bloque conservaba el orden previo: de ahí salían resultados
        # con scores NO descendentes (9 casos en casos_fallidos.jsonl del 2026-09-02,
        # ej. 'perfil' → [0.7562, 0.6780, 0.7523]).
        #
        # Un ranking que no está ordenado por el score que él mismo reporta rompe a todo
        # consumidor que corte por score en vez de por posición (mcp_server.py combina y
        # reordena los pools de buscar_por_frase y buscar_por_rafaga por r[4], así que
        # frase y ráfaga podían devolver órdenes distintos para la misma consulta).
        #
        # Este re-sort es la última palabra sobre relevancia: solo aplica cuando
        # ordenar_por == "relevancia" (el bloque siguiente de recencia/antiguedad
        # reordena a propósito por fecha y debe respetarse). O(n log n) sobre el pool ya
        # filtrado, sin coste medible. Desactivable: export BIORAG_ORDEN_MONOTONICO=0
        if (
            ordenar_por == "relevancia"
            and resultados_con_hibrido
            and os.getenv("BIORAG_ORDEN_MONOTONICO", "1") == "1"
        ):
            resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

        # ── Ordenamiento post-hoc por fecha (antes de paginar) ──────────
        # Solo responde intención temporal: "qué pasó hace X", "cuál fue lo último".
        # NO reemplaza relevancia — reordena el conjunto ya filtrado por relevancia.
        if ordenar_por in ("recencia", "antiguedad") and resultados_con_hibrido:
            conceptos_todo = [r[0] for r in resultados_con_hibrido]
            ph_todo = ",".join("?" * len(conceptos_todo))
            try:
                self.cursor.execute(
                    f"SELECT concepto, creado_en FROM largo_plazo WHERE concepto IN ({ph_todo})",
                    tuple(conceptos_todo),
                )
                creado_map = {row[0]: row[1] or 0 for row in self.cursor.fetchall()}
            except Exception:
                creado_map = {}
            reverse = (ordenar_por == "recencia")
            resultados_con_hibrido.sort(
                key=lambda r: creado_map.get(r[0], 0),
                reverse=reverse,
            )

        # Dynamic Multiplicator (opt-in): ampliación por empate en el corte,
        # solo para queries cortas (≤2 palabras). Evidencia real (EXPERIMENTS.md,
        # 18-ago-2026): para queries de una palabra, el concepto correcto a veces
        # cae justo debajo de `limite` compitiendo con candidatos igual de plausibles.
        # Solo se activa con permitir_expansion_empate=True — por defecto, limite es
        # un contrato estricto que el motor no rompe.
        if permitir_expansion_empate:
            query_words_ambiguedad = re.findall(r"\w+", frase.lower())
            if (pagina == 1 and limite and len(query_words_ambiguedad) <= 2
                    and len(resultados_con_hibrido) > limite):
                score_corte = resultados_con_hibrido[limite - 1][4]
                tope = min(limite + 10, len(resultados_con_hibrido))
                limite_ampliado = limite
                for idx in range(limite, tope):
                    if resultados_con_hibrido[idx][4] >= score_corte * 0.90:
                        limite_ampliado = idx + 1
                    else:
                        break
                limite = limite_ampliado

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
            if ordenar_por == "relevancia":
                pagina_resultados.sort(key=lambda r: r[4], reverse=True)

        # Context window: expandir cada resultado con vecinos por sinapsis
        if context_window and context_window > 0 and pagina_resultados:
            primarios_ctx, vecinos_ctx = self.expandir_contexto_vecinos(
                pagina_resultados,
                depth=context_window,
                profundidad=profundidad,
                preview_chars=preview_chars
            )
            pagina_resultados = primarios_ctx + vecinos_ctx

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

        # Fallback Causal SRL: únicamente si la búsqueda tradicional por 8 señales devolvió 0 resultados Y no hay filtro estricto de rol
        if not pagina_resultados and not buscar_por_rol:
            res_srl = self._fallback_busqueda_predicados(query, limite=limite)
            if res_srl:
                pagina_resultados = res_srl
                total = len(res_srl)

        # Guardar trazabilidad para mcp_server.py y auditoría causal
        self.last_todos = todos
        self.last_origen_scores = origen_scores
        self.last_query = query
        self.last_hub_expansion = hub_expansion

        _exp_ep = expandir_episodio or constants.EPISODIO_TEMPORAL_ACTIVO
        if _exp_ep and pagina_resultados:
            try:
                _ancla = pagina_resultados[0][0]
                _eps = self._expandir_episodio_temporal(_ancla)
                _seen = {r[0] for r in pagina_resultados}
                for hit in _eps:
                    if hit["concepto"] in _seen:
                        continue
                    sc = min(0.45, float(pagina_resultados[0][4] or 0.0) * 0.85)
                    pagina_resultados.append((
                        hit["concepto"], hit["contenido"], hit["peso"],
                        hit["estado"], sc, hit["asociaciones"],
                    ))
                    _seen.add(hit["concepto"])
                    origen_scores[hit["concepto"]] = ("episodio_temporal", 1.0)
                total = max(total, len(pagina_resultados))
            except Exception:
                pass

        # Signal #14 (v29): Enriquecer candidatos con ADN Conceptual bajo flag.
        # Flag OFF por defecto → esta rama no altera la ruta del baseline.
        # Con flag ON aplica el contrato de degradación asociativa (§3 del plan):
        # nunca silencio vacío, etiqueta directo/asociativo, sin barridos globales.
        if constants.ADN_RANKING_ENABLED and pagina_resultados:
            pagina_resultados, metadatos_epi = self._enriquecer_con_adn(query, pagina_resultados, limite)
            self.last_estado_epistemico = metadatos_epi
            total = len(pagina_resultados)

        # =====================================================================
        # TECNOLOGÍA COGNITIVA: Registro de Acceso ACT-R (Anderson & Lebiere, 1998)
        # Alimenta el cálculo de Base-Level Activation para la Ley de Potencia.
        # Solo opera fuera del entorno de benchmarking o telemetría silenciada.
        # =====================================================================
        if pagina_resultados and os.environ.get("BIORAG_NO_LOG") != "1":
            try:
                ahora_acc = time.time()
                for r in pagina_resultados:
                    if r and r[0]:
                        self._registrar_acceso_nodo(r[0], ahora_acc)
            except Exception:
                pass

        # Phase 2D: Telemetría de búsquedas (non-blocking)
        # Respeta BIORAG_NO_LOG=1 para no contaminar el log con consultas de test/benchmark
        if os.environ.get("BIORAG_NO_LOG") == "1":
            self.last_log_id = None
        else:
            try:
                top_score = pagina_resultados[0][4] if pagina_resultados else None
                # Guardar top-5 conceptos para atribución de feedback (ver
                # docs/FIX_FEEDBACK_NO_ALCANZABLE.md): permite unir feedback por
                # concepto a la búsqueda que lo recuperó, sin depender de estado
                # en memoria (que no sobrevive entre llamadas MCP).
                conceptos_top = None
                if pagina_resultados:
                    top_conceptos = [r[0] for r in pagina_resultados[:5]]
                    conceptos_top = ",".join(top_conceptos)
                self.cursor.execute(
                    "INSERT INTO log_busquedas (query, resultados_count, top_score, creado_en, conceptos_top) VALUES (?, ?, ?, ?, ?)",
                    (query, total, top_score, time.time(), conceptos_top),
                )
                self.last_log_id = self.cursor.lastrowid
                self.conn.commit()
            except Exception:
                self.last_log_id = None
                pass

        # SIN UMBRAL en buscar_por_frase.
        #
        # POR QUÉ: el umbral conforme se calibra sobre scores de consultas
        # negativas y filtra por CALIDAD (¿respondo o abstengo?). Aplicarlo
        # aquí destruye R@5 (medido: 96% → 73%) porque muchos nodos válidos
        # tienen score < umbral por la arquitectura del scoring.
        #
        # DÓNDE SÍ se aplica: MCP path (_recordar_impl en mcp_server.py),
        # que es el punto de decisión "¿respondo al usuario?".
        #
        # buscar_por_frase es motor de búsqueda puro: devuelve todo lo que
        # encuentre, sin filtro de calidad. El consumidor decide.
        # OPT-NUEVA-5: solo publica metadatos (side-channel); ranking intacto.
        if constants.EPISTEMICO_METADATA:
            self._epistemico_publicar(frase, pagina_resultados, total)
        self.last_pagina_resultados = pagina_resultados
        return pagina_resultados, total

    def obtener_provenance_ultimo_resultado(self) -> dict:
        return telemetry.obtener_provenance_ultimo_resultado(self)

    def _enriquecer_con_adn(self, query, resultados_base, limite=None):
        """Signal #14 (v29): fusión ADN Conceptual con los resultados base (Política A).

        Implementa el contrato de degradación asociativa del plan (§3 y §4.2):
        - NUNCA silencio vacío: si no hay base ni señal ADN, devuelve la lista
          interna vacía pero con metadatos explícitos de `sin_evidencia_local`.
        - Escala S_base y S_adn a [0,1] dentro del pool de candidatos antes de
          combinar (§4.1). No suma cosenos crudos.
        - Fusión versionada (§4.2):
            S_final_directo    = 0.85*S_base + 0.15*S_adn
            S_final_asociativo = min(0.49, 0.70*S_base + 0.30*S_adn)
          La cota 0.49 impide que una asociación de baja confianza adelante a
          una coincidencia directa fiable.
        - Expansión ADN SOLO desde anclajes (mejores 2 resultados base), nunca
          un barrido global de `indices.vecs` (§2.3). `buscar_por_esencia` usa
          `adn_vecinos_v29` persistido o el pool de sus 2 cromosomas dominantes.
        - Preserva la estructura de tupla de 6 campos que los consumidores ya
          esperan: (concepto, contenido, peso, estado, score, asociaciones).
          El score final ocupa la posición 4; los metadatos de procedencia se
          devuelven por separado para no romper el contrato público.

        Returns:
            (pagina_resultados, metadatos_epistemicos)
        """
        base = list(resultados_base)
        metadatos = {
            "estado": "sin_evidencia_local",
            "confianza_epistemica": 0.0,
            "indice_adn_listo": bool(self.adn_engine is not None and self.adn_engine.indice_listo),
            "tipo_relacion_por_concepto": {},
            "genes_compartidos_por_concepto": {},
        }

        # Guarda de degradación: sin índice ADN no hay señal complementaria,
        # pero si ya hay base (evidencia directa), NO se etiqueta como sin_evidencia.
        if self.adn_engine is None or not self.adn_engine.indice_listo:
            metadatos["estado"] = "conocido" if base else "sin_evidencia_local"
            return base, metadatos

        # Evaluación epistémica C_e (calibra visibilidad, NUNCA silencia: §4.2)
        ce = 0.0
        if self.neocortex is not None:
            try:
                ce = float(self.neocortex.evaluar_episteme(query).get("confianza_epistemica", 0.0))
            except Exception:
                ce = 0.0
        metadatos["confianza_epistemica"] = ce

        # 1) S_base normalizado en [0,1] dentro del pool (max del pool, no global).
        max_base = max((float(r[4]) for r in base), default=0.0)
        pool = {}  # concepto -> dict con campos base + señal ADN
        for r in base:
            s_base = float(r[4])
            s_base_norm = s_base / max_base if max_base > 0 else 0.0
            pool[r[0]] = {
                "concepto": r[0], "contenido": r[1], "peso": r[2], "estado": r[3],
                "s_base": s_base_norm, "s_adn": 0.0, "asociaciones": r[5],
                "genes": [], "procedencia": "directa",
            }

        # 2) Expansión ADN desde los 2 mejores anclajes de la base (§3.1.2/3).
        anclajes = sorted(base, key=lambda r: float(r[4]), reverse=True)[:2]
        n_adn_consultados = 0
        for ancla in anclajes:
            try:
                vecinos = self.adn_engine.buscar_por_esencia(ancla[0], top_k=constants.ADN_MAX_EXPANSION)
            except Exception:
                vecinos = []
            for v in vecinos:
                n_adn_consultados += 1
                concepto_adn = v.get("concepto")
                if not concepto_adn or concepto_adn in pool:
                    continue
                s_adn = float(v.get("afinidad_genetica", 0.0))
                if s_adn < constants.ADN_UMBRAL_ASOCIACION:
                    continue
                pool[concepto_adn] = {
                    "concepto": concepto_adn, "contenido": "", "peso": 0.0, "estado": "activo",
                    "s_base": 0.0, "s_adn": s_adn, "asociaciones": [],
                    "genes": v.get("genes_compartidos", []), "procedencia": "asociacion",
                }
        metadatos["candidatos_adn_consultados"] = n_adn_consultados

        # 3) S_adn para los candidatos directos: afinidad persistida del nodo
        #    en adn_vecinos_v29 (primer vecino), o firma del concepto en firma ADN.
        for concepto, info in pool.items():
            if info["procedencia"] != "directa":
                continue
            try:
                vecinos_nodo = self.adn_engine.vecinos.get(concepto, [])
                if vecinos_nodo:
                    info["s_adn"] = float(vecinos_nodo[0].get("afinidad_genetica", 0.0))
                    info["genes"] = vecinos_nodo[0].get("genes_compartidos", [])
            except Exception:
                info["s_adn"] = 0.0

        # 4) Fusión versionada (§4.2) + etiquetado de procedencia (§3.1.5).
        resultado = []
        for info in pool.values():
            s_base, s_adn = info["s_base"], info["s_adn"]
            if info["procedencia"] == "directa":
                s_final = 0.85 * s_base + 0.15 * s_adn
                tipo_relacion = "evidencia_directa"
            else:
                s_final = min(0.49, 0.70 * s_base + 0.30 * s_adn)
                tipo_relacion = "asociacion"
            metadatos["tipo_relacion_por_concepto"][info["concepto"]] = tipo_relacion
            metadatos["genes_compartidos_por_concepto"][info["concepto"]] = info["genes"]
            resultado.append((
                info["concepto"], info["contenido"], info["peso"], info["estado"],
                round(min(1.0, max(0.0, s_final)), 4), info["asociaciones"],
            ))

        resultado.sort(key=lambda r: r[4], reverse=True)
        if limite:
            resultado = resultado[:limite]

        # 5) Contrato §3.1.6: sin ancla → lista interna vacía + metadatos explícitos.
        metadatos["estado"] = (
            "conocido" if ce >= 0.60 else
            ("relacionado" if ce >= 0.20 else "asociativo_baja_confianza")
        )
        if not resultado:
            metadatos["estado"] = "sin_evidencia_local"
        return resultado, metadatos

    def actualizar_log_busqueda(self, params_json: str):
        return telemetry.actualizar_log_busqueda(self, params_json)

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
            limite = constants.LIMITE_RAFTAGA
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
                "bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val "
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
                "bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val "
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

        # Normalización BM25 consistente con buscar_por_frase (Opción 1: Reúso y extensión de escala)
        # Para garantizar comparabilidad cuando mcp_server combina resultados de frase + ráfaga
        # y reordena por score (r[4]), ráfaga normaliza contra la misma escala [lo, hi] de frase.
        # Si un candidato de ráfaga excede los límites previos, el rango se extiende sin recortar.
        rafaga_raw_vals = [abs(r[6] if len(r) > 6 else 0.0) for r in todos]
        if rafaga_raw_vals:
            r_lo, r_hi = min(rafaga_raw_vals), max(rafaga_raw_vals)
            if getattr(self, '_last_bm25_bounds', None) is not None:
                base_lo, base_hi, _ = self._last_bm25_bounds
                lo = min(base_lo, r_lo)
                hi = max(base_hi, r_hi)
            else:
                lo, hi = r_lo, r_hi
            rango = hi - lo if hi > lo else 1.0
            escala = min(1.0, hi) if hi > 0 else 1.0
            if hi > lo:
                bm25_norm_map = {
                    r[1]: ((abs(r[6] if len(r) > 6 else 0.0) - lo) / rango) * escala for r in todos
                }
            elif len(todos) == 1 and hi >= 3.0:
                bm25_norm_map = {r[1]: escala for r in todos}
            else:
                bm25_norm_map = {r[1]: 0.0 for r in todos}
        else:
            bm25_norm_map = {}

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

            # Signal #11: JSD (rafaga path)
            jsd_val = 0.0
            if constants.JSD_WEIGHT > 0.0:
                node_text = f"{concepto} {contenido or ''}"
                jsd_val = self._calcular_jsd(query, node_text)

            score_hibrido = self._calcular_score_hibrido(
                bm25_norm=bm25_norm_map.get(concepto, 0.0),
                dim_score=dim_score,
                peso_sinaptico=peso,
                concepto_ratio=0.0,
                sinonimos_ratio=0.0,
                score_latente=densidad,
                score_cadena=0.0,
                asoc_count=num_asoc,
                match_exacto=match_exacto,
                tematico_score=0.0,
                jsd_score=jsd_val,
                jsd_weight=constants.JSD_WEIGHT,
                pred_score=0.0,   # Rafaga path: no predicate data precomputed
                ppmi_score=0.0    # Signal #13: neutral en ráfaga (queries ya son muy específicas)
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

        # Reindex SDM selectivo: marcar dirty las sinapsis rafaga_rememb nuevas
        # (sinapsis_creadas solo acumula inserciones reales, no refuerzos)
        if sinapsis_creadas:
            try:
                from core.sdm import marcar_sdm_dirty
                dirty_rafaga = {e for par in sinapsis_creadas for e in par[:2]}
                marcar_sdm_dirty(self, dirty_rafaga)
            except Exception:
                pass
        
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
        return telemetry._benchmark_rendimiento(self)

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
        return telemetry._ultimo_benchmark(self)

    def purgar_cuarentena_vencida(self) -> int:
        """Elimina definitivamente nodos en cuarentena con fecha_expiracion vencida.
        Corre automáticamente al inicio de cada recordar (path caliente).
        Retorna cantidad de nodos eliminados."""
        ahora = time.time()
        self.cursor.execute(
            "DELETE FROM largo_plazo WHERE estado = 'cuarentena' AND fecha_expiracion IS NOT NULL AND fecha_expiracion < ?",
            (ahora,)
        )
        n = self.cursor.rowcount
        if n > 0:
            self.conn.commit()
        return n

    def mover_a_cuarentena(self, concepto: str, dias_expiracion: int = 30) -> bool:
        """Mueve un nodo a estado 'cuarentena' con fecha de expiración.
        Reversible: si el nodo se referencia antes de expirar, vuelve a activo.
        El purge definitivo corre automáticamente en cada recordar."""
        self.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (concepto,))
        row = self.cursor.fetchone()
        if not row:
            return False
        ahora = time.time()
        expiracion = ahora + (dias_expiracion * 86400)
        self.cursor.execute(
            "UPDATE largo_plazo SET estado = 'cuarentena', fecha_expiracion = ? WHERE concepto = ?",
            (expiracion, concepto)
        )
        self.conn.commit()
        return True

    def rescatar_de_cuarentena(self, concepto: str) -> bool:
        """Rescata un nodo de cuarentena antes de que expire.
        Vuelve a estado activo. Se gatilla automáticamente si el nodo
        aparece en resultados de recordar con score > 0."""
        self.cursor.execute(
            "UPDATE largo_plazo SET estado = 'activo', fecha_expiracion = NULL WHERE concepto = ? AND estado = 'cuarentena'",
            (concepto,)
        )
        n = self.cursor.rowcount
        if n > 0:
            self.conn.commit()
        return n > 0

    def buscar_en_cuarentena(self, frase: str, limite: int = 3):
        """Busca nodos en estado 'cuarentena' que matcheen la frase via FTS.

        Independiente del 'profundidad' de la búsqueda principal: el filtro
        l.estado = 'activo' de buscar_por_frase excluye la cuarentena, así que
        el auto-rescate del camino normal de recordar necesita su propia query.
        Sin esto, un nodo en cuarentena solo podía salir por purge o por
        rescate manual con deep=True (cuarentena de una sola vía en la práctica).

        Retorna lista de (concepto, contenido, peso_sinaptico, bm25)."""
        if not frase or not frase.strip():
            return []
        import re as _re

        def _fts_safe_term(term):
            partes = _re.split(r'[-]+', term)
            return " ".join(p for p in partes if p)

        tokens = [t for t in frase.split() if len(t) >= 2]
        if not tokens:
            return []
        fts_match = " OR ".join(f'"{_fts_safe_term(t)}"' for t in tokens)
        self.cursor.execute(
            """
            SELECT l.concepto, l.contenido, l.peso_sinaptico,
                   bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val
            FROM largo_plazo_fts f
            CROSS JOIN largo_plazo l ON l.rowid = f.rowid
            WHERE largo_plazo_fts MATCH ? AND l.estado = 'cuarentena'
            ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0)
            LIMIT ?
            """,
            (fts_match, limite)
        )
        return self.cursor.fetchall()

    def cerrar_sistema(self):
        """Cierra SQLite. No-op si la instancia es el singleton MCP (_persistente)."""
        if getattr(self, "_persistente", False):
            return
        try:
            self.conn.close()
        except Exception:
            pass
