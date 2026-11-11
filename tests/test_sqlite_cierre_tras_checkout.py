"""Regresión pendiente al cerrar un motor tras sustituir la base mediante Git.

Solo usa un repositorio y bases temporales. No es un procedimiento para una
base real ni prueba una solución para checkout o recuperación.
"""

from pathlib import Path
import sqlite3
import subprocess

import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.sqlite import constants


@pytest.fixture
def motor_tras_checkout_forzado(tmp_path, monkeypatch):
    """Construye dos ramas y confirma una fila en WAL antes del checkout."""
    monkeypatch.setenv("BIORAG_SQLITE_GUARD", "1")
    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "0")
    # Aísla el comportamiento de guardia; no valida la biblioteca SQLite real.
    monkeypatch.setattr(constants, "_effective_sqlite_version", lambda: (3, 51, 3))
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.name", "Prueba")
    git("config", "user.email", "prueba@example.test")
    (repo / ".gitignore").write_text("*.db-wal\n*.db-shm\n*.biorag-*\n")
    db = repo / "memoria.db"
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        conn.execute("CREATE TABLE recuerdos (texto TEXT NOT NULL)")
        conn.execute("INSERT INTO recuerdos VALUES ('rama A')")
        conn.commit()
    finally:
        conn.close()
    git("checkout", "-q", "-b", "rama-a")
    git("add", ".gitignore", "memoria.db")
    git("commit", "-qm", "A")
    git("checkout", "-q", "-b", "rama-b")
    conn = sqlite3.connect(db)
    try:
        conn.execute("INSERT INTO recuerdos VALUES ('rama B')")
        conn.commit()
    finally:
        conn.close()
    git("add", "memoria.db")
    git("commit", "-qm", "B")
    git("checkout", "-q", "rama-a")

    motor = SQLiteMemoryBioRAG(str(db))
    try:
        motor.conn.execute("PRAGMA wal_autocheckpoint=0")
        assert motor.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        motor.conn.execute("INSERT INTO recuerdos VALUES ('confirmado en A')")
        motor.conn.commit()
        wal = Path(str(db) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0
        assert motor.conn.execute("SELECT texto FROM recuerdos WHERE texto='confirmado en A'").fetchone() == ("confirmado en A",)
        git("checkout", "-q", "-f", "rama-b")
        contenido = wal.read_bytes()
        assert contenido
        yield motor, wal, contenido
    finally:
        motor.cerrar_sistema()


class WalNoPreservado(AssertionError):
    """Fallo específico de la propiedad de preservación bajo prueba."""


@pytest.mark.xfail(
    strict=True,
    raises=WalNoPreservado,
    reason="Pendiente: preservar WAL confirmado al cerrar tras cambiar la generación",
)
def test_cierre_tras_checkout_preserva_wal_confirmado(motor_tras_checkout_forzado):
    """No se puede descartar el WAL de la generación anterior al cerrar."""
    motor, wal, contenido = motor_tras_checkout_forzado
    motor.cerrar_sistema()
    if not wal.exists() or wal.read_bytes() != contenido:
        raise WalNoPreservado("el cierre alteró o eliminó el WAL con un recuerdo confirmado")
