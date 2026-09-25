"""Canal de comunicación inter-agente de MemoryBioRAG.

Módulo extraído de core/memory_store.py bajo el patrón A1.
Funciones con `self` como primer parámetro.
"""

import os
import time


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
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_leido_ts ON comunicaciones (leido, timestamp DESC)")
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
