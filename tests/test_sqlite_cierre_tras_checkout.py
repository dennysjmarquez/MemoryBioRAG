"""Regresión pendiente al cerrar un motor tras sustituir la base mediante Git.

Solo usa un repositorio y bases temporales. No es un procedimiento para una
base real ni prueba una solución para checkout o recuperación.
"""

import hashlib
from pathlib import Path
import sqlite3
import subprocess

import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.sqlite import constants


def leer_copia(db_path, principal, wal=None):
    """Abre exclusivamente copias aisladas de la fixture, nunca el par activo."""
    db_path.write_bytes(principal)
    if wal is not None:
        Path(str(db_path) + "-wal").write_bytes(wal)
    conn = sqlite3.connect(db_path)
    try:
        filas = conn.execute("SELECT texto FROM recuerdos ORDER BY texto").fetchall()
        integridad = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return filas, integridad
    finally:
        conn.close()


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
        # No hay otro escritor en esta fixture: fotografiamos ambos archivos
        # antes del checkout. Estas copias sirven solo de control del test; no
        # cuentan como artefacto de recuperación producido por BioRAG.
        principal_a = db.read_bytes()
        contenido = wal.read_bytes()
        assert contenido
        filas_par, integridad = leer_copia(tmp_path / "control-par.db", principal_a, contenido)
        filas_principal, integridad_sola = leer_copia(tmp_path / "control-principal.db", principal_a)
        assert ("confirmado en A",) in filas_par and integridad == "ok"
        assert ("confirmado en A",) not in filas_principal and integridad_sola == "ok"
        git("checkout", "-q", "-f", "rama-b")
        # Aislar el efecto de checkout del que pueda tener el cierre posterior.
        assert wal.exists() and wal.read_bytes() == contenido
        principal_b = db.read_bytes()
        filas_b, integridad_b = leer_copia(tmp_path / "control-b.db", principal_b)
        assert filas_b == [("rama A",), ("rama B",)] and integridad_b == "ok"
        yield motor, db, wal, principal_a, contenido, hashlib.sha256(principal_b).digest(), tmp_path
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
    motor, db, wal, principal_a, contenido, hash_b, tmp_path = motor_tras_checkout_forzado
    motor.cerrar_sistema()
    # B se examina como copia independiente, nunca junto al WAL de A.
    principal_b_despues = db.read_bytes()
    assert hashlib.sha256(principal_b_despues).digest() == hash_b
    filas_b, integridad_b = leer_copia(tmp_path / "b-tras-cierre.db", principal_b_despues)
    assert filas_b == [("rama A",), ("rama B",)] and integridad_b == "ok"

    # Por ahora el único artefacto de producción propuesto es el WAL original.
    # Al diseñar otra recuperación, comprobar aquí el artefacto que produzca
    # BioRAG, no la copia de control que la propia prueba tomó antes.
    if not wal.exists() or wal.stat().st_size == 0:
        raise WalNoPreservado("el WAL necesario para recuperar A desapareció o quedó vacío")
    wal_tras_cierre = wal.read_bytes()
    filas_a, integridad_a = leer_copia(tmp_path / "a-recuperada.db", principal_a, wal_tras_cierre)
    if ("confirmado en A",) not in filas_a or integridad_a != "ok":
        raise WalNoPreservado("no se recuperó el recuerdo confirmado con el principal de A")
    # Control forense de la política actual; no es el único contrato posible.
    assert wal_tras_cierre == contenido


def test_cierre_sin_checkpoint_explicito_preserva_wal(motor_tras_checkout_forzado, monkeypatch):
    """Ensaya close real, anulando solo el checkpoint explícito de BioRAG."""
    motor, db, wal, principal_a, contenido, hash_b, tmp_path = motor_tras_checkout_forzado
    monkeypatch.setattr(motor, "_consolidar_antes_de_cerrar", lambda connections: None)
    motor.cerrar_sistema()
    assert hashlib.sha256(db.read_bytes()).digest() == hash_b
    if not wal.exists() or wal.stat().st_size == 0:
        raise WalNoPreservado("close sin PRAGMA explícito eliminó o vació el WAL")
    filas, integridad = leer_copia(tmp_path / "a-tras-close.db", principal_a, wal.read_bytes())
    if ("confirmado en A",) not in filas or integridad != "ok":
        raise WalNoPreservado("close sin PRAGMA explícito impidió recuperar A")


def test_ultimo_close_sqlite_puede_consolidar_sin_checkpoint_explicito(tmp_path):
    """Control SQLite: autocheckpoint desactivado no impide limpiar al cerrar."""
    db = tmp_path / "dos-conexiones.db"
    primera = sqlite3.connect(db)
    segunda = None
    try:
        assert primera.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        primera.execute("PRAGMA wal_autocheckpoint=0")
        primera.execute("CREATE TABLE recuerdos (texto TEXT NOT NULL)")
        primera.commit()
        segunda = sqlite3.connect(db)
        segunda.execute("PRAGMA wal_autocheckpoint=0")
        assert segunda.execute("SELECT COUNT(*) FROM recuerdos").fetchone()[0] == 0
        primera.execute("INSERT INTO recuerdos VALUES ('confirmado')")
        primera.commit()
        wal = Path(str(db) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0
        primera.close()
        primera = None
        assert wal.exists() and wal.stat().st_size > 0
        segunda.close()
        segunda = None
        assert not wal.exists() or wal.stat().st_size == 0
        filas, integridad = leer_copia(tmp_path / "principal-consolidado.db", db.read_bytes())
        assert filas == [("confirmado",)] and integridad == "ok"
    finally:
        if primera is not None:
            primera.close()
        if segunda is not None:
            segunda.close()
