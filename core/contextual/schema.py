"""Esquema contextual compartido por inicialización y correcciones.

No depende de flags ni de un idioma. DDL aditiva y atómica, sin executescript
(que podría confirmar una transacción ajena). No se invoca desde lectores.
"""
import sqlite3

DDL = (
    """
    CREATE TABLE IF NOT EXISTS ctx_claims (
        id TEXT PRIMARY KEY, node TEXT NOT NULL, entity TEXT NOT NULL,
        attribute TEXT NOT NULL, scope TEXT NOT NULL, value TEXT NOT NULL,
        source TEXT NOT NULL, valid_from REAL NOT NULL, valid_until REAL,
        confirmed INTEGER NOT NULL CHECK(confirmed IN (0,1))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ctx_claims_context
      ON ctx_claims(entity,attribute,scope,valid_from)
    """,
    """
    CREATE TABLE IF NOT EXISTS ctx_revisions (
        successor TEXT NOT NULL REFERENCES ctx_claims(id),
        predecessor TEXT NOT NULL REFERENCES ctx_claims(id),
        source TEXT NOT NULL,
        PRIMARY KEY(successor,predecessor),
        CHECK(successor<>predecessor)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ctx_proposals (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_by TEXT NOT NULL)
    """,
    """
    CREATE TABLE IF NOT EXISTS ctx_approvals (
        request_id TEXT PRIMARY KEY, proposal_id TEXT UNIQUE NOT NULL REFERENCES ctx_proposals(id),
        request TEXT NOT NULL, receipt TEXT NOT NULL)
    """,
    """
    CREATE TABLE IF NOT EXISTS ctx_synapses (
        successor_claim TEXT PRIMARY KEY REFERENCES ctx_claims(id),
        predecessor_claim TEXT NOT NULL REFERENCES ctx_claims(id),
        origen TEXT NOT NULL, destino TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo='sustituye'), scope TEXT NOT NULL, source TEXT NOT NULL)
    """,
)

COLUMNS = {
    'ctx_claims': ('id','node','entity','attribute','scope','value','source','valid_from','valid_until','confirmed'),
    'ctx_revisions': ('successor','predecessor','source'),
    'ctx_proposals': ('id','payload','created_by'),
    'ctx_approvals': ('request_id','proposal_id','request','receipt'),
    'ctx_synapses': ('successor_claim','predecessor_claim','origen','destino','tipo','scope','source'),
}


def ensure_contextual_schema(connection):
    """Prepara las cinco tablas incluso con funcionalidades desactivadas.

    Completa esquemas parciales válidos. Un esquema de columnas incompatible
    bloquea con error visible y no se borra/reconstruye. SAVEPOINT conserva
    la transacción del llamador; no la confirma. Sin transacción previa,
    usa BEGIN IMMEDIATE y confirma únicamente su propia migración.
    Una conexión de solo lectura no puede ejecutar esta migración.
    """
    own_transaction = not connection.in_transaction
    if own_transaction:
        connection.execute('BEGIN IMMEDIATE')
    connection.execute('SAVEPOINT biorag_contextual_schema')
    savepoint_open = True
    try:
        for table, expected in COLUMNS.items():
            actual = tuple(row[1] for row in connection.execute('PRAGMA table_info('+table+')'))
            if actual and actual != expected:
                raise sqlite3.DatabaseError('CONTEXTUAL_SCHEMA_INCOMPATIBLE: '+table+'; backup y migración explícita requeridos')
        for statement in DDL:
            connection.execute(statement)
        connection.execute('RELEASE SAVEPOINT biorag_contextual_schema')
        savepoint_open = False
        if own_transaction:
            connection.commit()
    except Exception:
        if savepoint_open:
            connection.execute('ROLLBACK TO SAVEPOINT biorag_contextual_schema')
            connection.execute('RELEASE SAVEPOINT biorag_contextual_schema')
        if own_transaction:
            connection.rollback()
        raise
