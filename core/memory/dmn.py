"""core/memory/dmn.py - Módulo de Default Mode Network (DMN), contexto y métricas.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro.
- Cuerpos intactos con imports internos preservados.
"""

import time


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
