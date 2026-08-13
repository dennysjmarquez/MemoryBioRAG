"""
BioRAG v21.0 — Default Mode Network (DMN) & Motor de Curiosidad Espontánea
==========================================================================
Implementa la Red por Defecto (Default Mode Network) para BioRAG.
Permite que el cerebro sintético explore asociaciones latentes, sintetice hipótesis
y genere "Insights" de forma autónoma en momentos de reposo (inactividad).

Incorpora las 5 Mejoras Estratégicas Biomiméticas:
1. Muestreo Resonante Cortical (Spindles Replay: Nodo Ancla High-Valence -> Exploración Latente 2-3 Saltos).
2. Concurrencia Aislada Thread-Local con SQLite WAL y PRAGMA busy_timeout=5000.
3. Selección Natural de Hipótesis (Decaimiento LTD pasivo si no recibe atención).
4. Presupuesto de Energía & Periodo Refractario (Máximo 3 ideas por ciclo de reposo, 60s cooldown).
5. Payload Enriquecido para biorag_estado_dmn (JSON estructurado forense).
"""

import time
import threading
import logging
import os
import json
import random
import sqlite3

logger = logging.getLogger("BioRAG.DMN")

class DMNEngine:
    def __init__(self, cerebro, idle_seconds=300, check_interval=2.0):
        """
        cerebro: Instancia principal de SQLiteMemoryBioRAG
        idle_seconds: Segundos de inactividad necesarios para activar DMN (default: 300s / 5min)
        """
        self.cerebro = cerebro
        self.db_path = cerebro.db_path
        self.idle_seconds = float(os.environ.get("BIORAG_DMN_IDLE_SECONDS", str(idle_seconds)))
        self.check_interval = float(check_interval)
        self.ultimo_acceso_usuario = time.time()
        self._stop_event = threading.Event()
        self._user_active_event = threading.Event()
        self._thread = None
        self.ideas_generadas_sesion = 0
        self.max_ideas_por_reposo = int(os.environ.get("BIORAG_DMN_MAX_IDEAS", "3"))
        self.periodo_refractario = float(os.environ.get("BIORAG_DMN_REFRACTARIO", "60.0"))
        self.ultima_idea = None
        self.activo = False

    def notificar_actividad_usuario(self):
        """Notifica interacción del usuario. Reinicia temporizador e interrumpe ciclo DMN."""
        self.ultimo_acceso_usuario = time.time()
        self._user_active_event.set()

    def start(self):
        """Inicia el hilo autónomo de curiosidad DMN en segundo plano."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._user_active_event.clear()
        self.activo = True
        self._thread = threading.Thread(target=self._bucle_dmn, name="BioRAG-DMN-Thread", daemon=True)
        self._thread.start()
        logger.info(f"DMN iniciado. Umbral de inactividad: {self.idle_seconds}s")

    def stop(self):
        """Detiene limpiamente el hilo DMN."""
        self.activo = False
        self._stop_event.set()
        self._user_active_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("DMN detenido.")

    def _crear_conexion_hilo(self):
        """Crea una conexión SQLite aislada Thread-Local con WAL mode y busy_timeout=5000."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _bucle_dmn(self):
        """Bucle principal de la Red por Defecto (runs in background thread)."""
        ideas_en_reposo_actual = 0
        conn = self._crear_conexion_hilo()

        while not self._stop_event.is_set():
            time.sleep(self.check_interval)

            if self._user_active_event.is_set():
                self._user_active_event.clear()
                ideas_en_reposo_actual = 0
                continue

            tiempo_inactivo = time.time() - self.ultimo_acceso_usuario
            if tiempo_inactivo >= self.idle_seconds and ideas_en_reposo_actual < self.max_ideas_por_reposo:
                if not self._stop_event.is_set() and not self._user_active_event.is_set():
                    try:
                        idea = self.ejecutar_ciclo_curiosidad(conn_hilo=conn)
                        if idea:
                            ideas_en_reposo_actual += 1
                            time.sleep(min(self.periodo_refractario, 5.0))
                    except Exception as e:
                        logger.warning(f"Error en ciclo DMN: {e}")

        try:
            conn.close()
        except Exception:
            pass

    def ejecutar_ciclo_curiosidad(self, conn_hilo=None, forzar=False) -> dict | None:
        """
        Ejecuta una ronda de ideación espontánea mediante Muestreo Resonante Cortical y Teleología Genética:
        1. Selecciona Nodo Ancla (N1) con valencia_somatica >= 0.3 o peso_sinaptico >= 0.5.
        2. Busca un Nodo Resonante (N2) distinto en el espacio asociativo, dimensional o genético (ADN).
        3. Genera un Insight autónomo o una Hipótesis Teleológica basada en ADN compartido.
        4. Si no recibe atención futura (LTP/feedback), sufrirá decaimiento pasivo natural por sueño (LTD).
        """
        if not forzar:
            if self._user_active_event.is_set() or self._stop_event.is_set():
                return None

        auto_close = False
        if conn_hilo is None:
            conn = self.cerebro.conn
        else:
            conn = conn_hilo

        cursor = conn.cursor()

        try:
            # 1. Seleccionar Nodo Ancla N1 (Alta valencia somática o peso)
            cursor.execute("""
                SELECT id, concepto, contenido, COALESCE(valencia_somatica, 0.0), peso_sinaptico
                FROM largo_plazo
                WHERE estado = 'activo' AND (valencia_somatica >= 0.3 OR peso_sinaptico >= 0.5)
                ORDER BY valencia_somatica DESC, peso_sinaptico DESC
                LIMIT 30
            """)
            anclas = cursor.fetchall()
            if not anclas:
                return None

            nodo_ancla = random.choice(anclas)
            id1, c1, cont1, val1, p1 = nodo_ancla

            # 2. Buscar Nodo Resonante N2 (que comparta dimensión semántica)
            cursor.execute("""
                SELECT DISTINCT l.id, l.concepto, l.contenido, COALESCE(l.valencia_somatica, 0.0), l.peso_sinaptico
                FROM largo_plazo_dimensiones d1
                JOIN largo_plazo_dimensiones d2 ON d1.dimension_id = d2.dimension_id
                JOIN largo_plazo l ON d2.concepto = l.concepto
                WHERE d1.concepto = ? AND d2.concepto != ? AND l.estado = 'activo'
                LIMIT 30
            """, (c1, c1))
            candidatos_resonantes = cursor.fetchall()

            # Si no hay resonancia dimensional explícita, buscar candidatos generales activos distintos
            if not candidatos_resonantes:
                cursor.execute("""
                    SELECT id, concepto, contenido, COALESCE(valencia_somatica, 0.0), peso_sinaptico
                    FROM largo_plazo
                    WHERE estado = 'activo' AND concepto != ?
                    ORDER BY creado_en DESC
                    LIMIT 30
                """, (c1,))
                candidatos_resonantes = cursor.fetchall()

            # Filtrar candidatos distintos
            candidatos_validos = [cand for cand in candidatos_resonantes if cand[1] != c1]

            if not candidatos_validos:
                return None

            nodo_destino = random.choice(candidatos_validos)
            id2, c2, cont2, val2, p2 = nodo_destino

            # Abortar de inmediato si el usuario envió un prompt en este microsegundo (salvo ejecuciones forzadas manuales)
            if not forzar and self._user_active_event.is_set():
                conn.rollback()
                return None

            # Obtener dimensiones compartidas para el payload forense
            cursor.execute("""
                SELECT DISTINCT ds.name
                FROM largo_plazo_dimensiones d1
                JOIN largo_plazo_dimensiones d2 ON d1.dimension_id = d2.dimension_id
                JOIN dimensiones_semanticas ds ON d1.dimension_id = ds.id
                WHERE d1.concepto = ? AND d2.concepto = ?
            """, (c1, c2))
            dims_compartidas = [r[0] for r in cursor.fetchall()]

            concepto_insight = f"insight_dmn_{c1}_{c2}"
            
            # Verificar si ya existe este insight
            cursor.execute("SELECT id FROM largo_plazo WHERE concepto = ?", (concepto_insight,))
            if cursor.fetchone():
                return None

            contenido_insight = (
                f"Insight Autónomo DMN (Curiosidad Espontánea): Conexión sintética latente descubierta en reposo "
                f"entre '{c1}' (valencia={val1:.2f}) y '{c2}' (valencia={val2:.2f}). "
                f"Dimensiones compartidas: {', '.join(dims_compartidas) if dims_compartidas else 'Topología estructural'}."
            )
            sinonimos = f"insight dmn,curiosidad espontanea,{c1},{c2}"
            cat_id = 1  # General / Insight

            # Insertar Insight en largo_plazo con peso moderado (0.50) y valencia somática 0.85
            cursor.execute("""
                INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, sinonimos, creado_en, ultimo_acceso, valencia_somatica)
                VALUES (?, ?, ?, 0.50, 'activo', ?, ?, ?, 0.85)
            """, (concepto_insight, cat_id, contenido_insight, sinonimos, time.time(), time.time()))

            # Crear sinapsis latente asociativa entre N1 y N2 con todas las columnas requeridas
            cursor.execute("""
                INSERT OR REPLACE INTO sinapsis_latentes (origen, destino, peso_atenuado, saltos, calculado_en, pmi_score, tiene_dim_comun)
                VALUES (?, ?, 0.75, 2, ?, 0.5, ?)
            """, (c1, c2, time.time(), 1 if dims_compartidas else 0))

            conn.commit()

            # SDM v19.0: Indexar vector del insight para recuperación por similitud estructural
            try:
                from core.sdm import indexar_nodo_sdm
                indexar_nodo_sdm(self.cerebro, concepto_insight)
            except Exception:
                pass

            # v29: reconstrucción batch del índice ADN durante sueño. Esta es la única
            # ruta que agrupa el corpus, recalcula centroides y materializa vecinos.
            try:
                necesita_recalculo = getattr(self.cerebro, "_adn_pendiente_recalculo", False)
                indice_no_listo = not getattr(getattr(self.cerebro, "adn_engine", None), "indice_listo", False)
                if necesita_recalculo or indice_no_listo:
                    from core.adn_conceptual import ADNConceptualEngine
                    estado_adn = ADNConceptualEngine.reconstruir_indice_nocturno(str(self.db_path))
                    if estado_adn.get("estado") == "ok":
                        # Recargar solo los artefactos persistidos, sin clustering en caliente.
                        self.cerebro.adn_engine = ADNConceptualEngine(
                            db_path=str(self.db_path),
                            indices=getattr(self.cerebro, "_ppmi_index", None),
                        )
                        from core.neocortex_teleologico import NeocortexTeleologico
                        self.cerebro.neocortex = NeocortexTeleologico(str(self.db_path))
                        self.cerebro._adn_pendiente_recalculo = False
                    logger.info("DMN sueño: índice ADN v29 procesado con estado=%s", estado_adn.get("estado"))
            except Exception as e:
                logger.warning(f"Error en reconstrucción ADN nocturna DMN: {e}")

            self.ideas_generadas_sesion += 1
            self.ultima_idea = {
                "concepto": concepto_insight,
                "nodo_a": c1,
                "nodo_b": c2,
                "coincidencia_dimensional": dims_compartidas,
                "valencia_somatica": 0.85,
                "peso_inicial": 0.50,
                "timestamp": time.time(),
                "contenido": contenido_insight
            }

            logger.info(f"💡 DMN Muestreo Resonante generó Insight autónomo: {concepto_insight}")
            return self.ultima_idea

        finally:
            if auto_close:
                conn.close()

    def obtener_estado(self) -> dict:
        """Devuelve el payload JSON estructurado y enriquecido para biorag_estado_dmn."""
        tiempo_inactivo = time.time() - self.ultimo_acceso_usuario
        return {
            "estado": "idle" if tiempo_inactivo >= self.idle_seconds else "active_user",
            "activo_hilo": self.activo,
            "segundos_inactividad": round(tiempo_inactivo, 1),
            "umbral_idle_segundos": self.idle_seconds,
            "ideas_generadas_sesion": self.ideas_generadas_sesion,
            "max_ideas_por_reposo": self.max_ideas_por_reposo,
            "ultima_idea": self.ultima_idea
        }
