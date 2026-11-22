"""Almacén namespaced de revisiones confirmadas en la DB del motor.

La fuente y confirmed son declaraciones del llamador, no verificación automática.
Atributos monovalorados por contexto exacto. Nuevas aristas no borran historia.
"""
from dataclasses import dataclass
import math
import sqlite3


@dataclass(frozen=True)
class Claim:
    id: str
    node: str
    entity: str
    attribute: str
    scope: str
    value: str
    source: str
    valid_from: float
    valid_until: float | None = None
    confirmed: bool = False


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Se requiere texto no vacío')
    return value


def instant(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Se requiere un instante finito explícito')
    return value


class Ledger:
    def __init__(self, connection):
        self.db = connection
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS ctx_claims (
                id TEXT PRIMARY KEY, node TEXT NOT NULL, entity TEXT NOT NULL,
                attribute TEXT NOT NULL, scope TEXT NOT NULL, value TEXT NOT NULL,
                source TEXT NOT NULL, valid_from REAL NOT NULL, valid_until REAL,
                confirmed INTEGER NOT NULL CHECK(confirmed IN (0,1))
            );
            CREATE INDEX IF NOT EXISTS ctx_claims_context
              ON ctx_claims(entity,attribute,scope,valid_from);
            CREATE TABLE IF NOT EXISTS ctx_revisions (
                successor TEXT NOT NULL REFERENCES ctx_claims(id),
                predecessor TEXT NOT NULL REFERENCES ctx_claims(id),
                source TEXT NOT NULL,
                PRIMARY KEY(successor,predecessor),
                CHECK(successor<>predecessor)
            );
        ''')

    def add(self, c):
        for value in (c.id, c.node, c.entity, c.attribute, c.scope, c.value, c.source):
            text(value)
        instant(c.valid_from)
        if c.valid_until is not None:
            instant(c.valid_until)
            if c.valid_until <= c.valid_from:
                raise ValueError('Intervalo vacío o invertido')
        if type(c.confirmed) is not bool:
            raise ValueError('confirmed debe ser booleano')
        with self.db:
            self.db.execute('INSERT INTO ctx_claims VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (c.id, c.node, c.entity, c.attribute, c.scope, c.value,
                             c.source, c.valid_from, c.valid_until, int(c.confirmed)))

    def context(self, entity, attribute, scope, at, limit=4096):
        for v in (entity, attribute, scope):
            text(v)
        instant(at)
        rows = self.db.execute('''SELECT * FROM ctx_claims
            WHERE entity=? AND attribute=? AND scope=? AND valid_from<=?
            ORDER BY id LIMIT ?''', (entity, attribute, scope, at, limit + 1)).fetchall()
        if len(rows) > limit:
            raise ValueError('Contexto excede el presupuesto; decisión bloqueada')
        return {r[0]: Claim(*r[:-1], bool(r[-1])) for r in rows}

    def edges(self, entity, attribute, scope, at):
        return self.db.execute('''SELECT r.successor,r.predecessor,r.source
            FROM ctx_claims c JOIN ctx_revisions r ON r.successor=c.id
            WHERE c.entity=? AND c.attribute=? AND c.scope=? AND c.valid_from<=?
            ORDER BY r.successor,r.predecessor''',
                               (entity, attribute, scope, at)).fetchall()

    def supersede(self, successor, predecessor, source):
        text(source)
        with self.db:
            records = []
            for key in (successor, predecessor):
                row = self.db.execute('SELECT * FROM ctx_claims WHERE id=?', (key,)).fetchone()
                if row is None:
                    raise ValueError('Extremo de sustitución inexistente')
                records.append(Claim(*row[:-1], bool(row[-1])))
            new, old = records
            if (new.entity, new.attribute, new.scope) != (old.entity, old.attribute, old.scope):
                raise ValueError('No sustituir entre alcances/atributos/entidades distintos')
            if not new.confirmed or not old.confirmed:
                raise ValueError('Sustitución requiere extremos confirmados')
            if new.valid_from < old.valid_from:
                raise ValueError('El sucesor no puede empezar antes que su predecesor')
            # Para crear new→old, old no debe alcanzar ya a new.
            cycle = self.db.execute('''WITH RECURSIVE reachable(id) AS (
                SELECT ? UNION
                SELECT r.predecessor FROM ctx_revisions r JOIN reachable v ON r.successor=v.id
            ) SELECT 1 FROM reachable WHERE id=?''', (predecessor, successor)).fetchone()
            if cycle:
                raise ValueError('Sustitución cíclica')
            self.db.execute('INSERT INTO ctx_revisions VALUES (?,?,?)', (successor, predecessor, source))
