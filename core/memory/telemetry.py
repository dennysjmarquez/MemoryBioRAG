"""Telemetría, benchmark y registro de historial forense de MemoryBioRAG.

Módulo extraído de core/memory_store.py bajo el patrón A1.
Funciones con `self` como primer parámetro.
"""

import os
import time
import sqlite3


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

    # Tabla de eventos de refuerzo dopaminérgico en tiempo real.
    # POR QUÉ una tabla aparte: metricas_cognitivas_nodos tiene grano de "ciclo de
    # sueño" (metrica_id NOT NULL con FK). El feedback ocurre entre ciclos, así que
    # no tiene un ciclo padre al que apuntar. Meterlo ahí obliga a inventar un
    # metrica_id o a relajar la FK; ambas cosas corrompen el historial forense.
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos_refuerzo (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto      TEXT    NOT NULL,
            exito         INTEGER NOT NULL CHECK(exito IN (0,1)),
            peso_anterior REAL    NOT NULL,
            peso_nuevo    REAL    NOT NULL,
            delta         REAL    NOT NULL,
            exitos_previos INTEGER NOT NULL,
            motivo        TEXT,
            created_at    REAL    NOT NULL
        )
    """)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS ix_evref_concepto ON eventos_refuerzo(concepto)")
    self.cursor.execute("CREATE INDEX IF NOT EXISTS ix_evref_fecha    ON eventos_refuerzo(created_at)")

    # Asegurar tablas referenciadas por triggers de DELETE en largo_plazo
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodos_sdm (
            concepto TEXT PRIMARY KEY,
            vector BLOB NOT NULL,
            actualizado_en REAL NOT NULL
        )
    """)
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


def _ultimo_benchmark(self):
    """Retorna la ultima latencia registrada o None si no hay metricas."""
    self.cursor.execute(
        "SELECT latencia_busqueda_ms FROM metricas_rendimiento ORDER BY id DESC LIMIT 1"
    )
    fila = self.cursor.fetchone()
    return fila[0] if fila else None


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


def obtener_provenance_ultimo_resultado(self) -> dict:
    """
    Retorna telemetría estructurada y atribución causal de la última búsqueda.
    Permite a la suite de tests, evaluadores y benchmarks verificar con precisión
    qué subsistema (FTS5, Concept Hub, Grafo Hebbiano, Sustantivos Clave, SDM)
    generó cada candidato y cuál definió su posición en el ranking final.
    """
    origenes = getattr(self, "last_origen_scores", {}) or {}
    hub_exp = getattr(self, "last_hub_expansion", None)
    candidatos_prov = []
    for r in getattr(self, "last_pagina_resultados", []) or []:
        if isinstance(r, (tuple, list)) and len(r) >= 5:
            conc = r[0]
            sc = r[4]
            orig, conf_orig = origenes.get(conc, ("literal", 0.0))
            candidatos_prov.append({
                "concepto": conc,
                "score_final": sc,
                "origen_candidato": orig,
                "confianza_origen": conf_orig,
                "es_canonico_hub": bool(hub_exp and conc in hub_exp.get("canonical_nodes", []))
            })
    return {
        "query": getattr(self, "last_query", ""),
        "hub_activado": bool(hub_exp is not None),
        "hub_id": hub_exp.get("hub_id") if hub_exp else None,
        "hub_confidence": hub_exp.get("hub_confidence", 0.0) if hub_exp else 0.0,
        "candidatos": candidatos_prov
    }
