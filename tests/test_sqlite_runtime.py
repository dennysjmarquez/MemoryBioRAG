"""Política de journal/runtime aislada en fixtures temporales."""

import ast
import sqlite3
from pathlib import Path

import pytest

from core import sqlite_runtime


ROOT = Path(__file__).resolve().parents[1]


def _calls(source: str, function: str):
    tree = ast.parse(source)
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name) and node.func.id == function
            or isinstance(node.func, ast.Attribute) and node.func.attr == function
        )
    ]


def test_consumidores_de_produccion_usan_aperturas_clasificadas():
    modules = {
        "core/memory_store.py": (1, 0),
        "core/dmn_engine.py": (1, 0),
        "dashboard-neuro-visor/backend/server.py": (3, 0),
        "core/feedback_implicito.py": (1, 1),
        "core/adn_conceptual.py": (1, 2),
        "core/ppmi_hybrid_search.py": (0, 1),
        "core/neocortex_teleologico.py": (0, 2),
    }
    for relative, (minimum_writers, readonly_opens) in modules.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert len(_calls(source, "open_writer")) >= minimum_writers, relative
        assert len(_calls(source, "open_reader")) == readonly_opens, relative
        assert not _calls(source, "connect"), f"{relative} conserva sqlite3.connect directo"


def test_open_reader_es_readonly_y_emite_diagnostico_sin_ruta_cruda(tmp_path, caplog):
    # '#' verifies URI escaping; '?' is not a legal Windows filename character.
    path = tmp_path / "diagnostico # sensible.db"
    seed = sqlite3.connect(path)
    seed.execute("CREATE TABLE probe (value TEXT)")
    seed.execute("INSERT INTO probe VALUES ('safe')")
    seed.commit()
    seed.close()

    caplog.set_level("DEBUG", logger="BioRAG.SQLiteRuntime")
    conn = sqlite_runtime.open_reader(path, consumer="test_reader", timeout=1.25)
    try:
        assert conn.execute("SELECT value FROM probe").fetchone() == ("safe",)
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO probe VALUES ('blocked')")
    finally:
        conn.close()

    diagnostic = " ".join(record.getMessage() for record in caplog.records)
    assert "consumer=test_reader" in diagnostic
    assert "role=read-only" in diagnostic
    assert "runtime=" in diagnostic and "source_id=" in diagnostic
    assert "journal=" in diagnostic and "busy_timeout_ms=1250" in diagnostic
    assert "route_id=" in diagnostic
    assert str(path) not in diagnostic


def test_open_writer_registra_commit_cooperativo_por_ruta(tmp_path):
    path = tmp_path / "commit_epoch.db"
    before = sqlite_runtime.database_commit_epoch(path)
    conn = sqlite_runtime.open_writer(path, consumer="commit_epoch_test")
    try:
        conn.execute("CREATE TABLE commit_probe (value INTEGER)")
        conn.execute("INSERT INTO commit_probe VALUES (1)")
        conn.commit()
    finally:
        conn.close()
    assert sqlite_runtime.database_commit_epoch(path) > before


def test_open_writer_registra_consumidor_runtime_y_timeout(tmp_path, caplog):
    path = tmp_path / "writer.db"
    caplog.set_level("DEBUG", logger="BioRAG.SQLiteRuntime")
    conn = sqlite_runtime.open_writer(
        path, consumer="test_writer", busy_timeout_ms=789
    )
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 789
    finally:
        conn.close()

    diagnostic = " ".join(record.getMessage() for record in caplog.records)
    assert "consumer=test_writer" in diagnostic
    assert "role=writer" in diagnostic
    assert "runtime=" in diagnostic and "source_id=" in diagnostic
    assert "journal=" in diagnostic and "busy_timeout_ms=789" in diagnostic
    assert "route_id=" in diagnostic
    assert str(path) not in diagnostic


@pytest.mark.parametrize(
    ("version", "vulnerable"),
    [
        ((3, 40, 1), True),
        ((3, 44, 5), True),
        ((3, 44, 6), False),
        ((3, 45, 1), True),
        ((3, 50, 6), True),
        ((3, 50, 7), False),
        ((3, 51, 2), True),
        ((3, 51, 3), False),
        ((3, 7, 0), True),
        ((3, 6, 23), False),
    ],
)
def test_clasifica_runtime_afectado_por_wal_reset(version, vulnerable):
    assert sqlite_runtime.is_wal_reset_vulnerable(version) is vulnerable


def _usar_runtime(monkeypatch, version):
    monkeypatch.setattr(sqlite_runtime, "_effective_sqlite_version", lambda: version)


def test_runtime_vulnerable_usa_delete_en_base_nueva(tmp_path, monkeypatch):
    _usar_runtime(monkeypatch, (3, 45, 1))
    path = tmp_path / "nueva.db"

    conn = sqlite_runtime.open_writer(path)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.execute("CREATE TABLE t (valor TEXT)")
        conn.execute("INSERT INTO t VALUES (?)", ("conservado",))
        conn.commit()
    finally:
        conn.close()

    assert mode.lower() == "delete"
    verify = sqlite3.connect(path)
    try:
        assert verify.execute("SELECT valor FROM t").fetchone() == ("conservado",)
    finally:
        verify.close()


def test_runtime_vulnerable_transicion_wal_a_delete_conserva_filas(tmp_path, monkeypatch):
    path = tmp_path / "wal.db"
    seed = sqlite3.connect(path)
    assert seed.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    seed.execute("CREATE TABLE t (valor TEXT)")
    seed.execute("INSERT INTO t VALUES (?)", ("antes",))
    seed.commit()
    seed.close()

    _usar_runtime(monkeypatch, (3, 45, 1))
    conn = sqlite_runtime.open_writer(path, allow_existing_journal_transition=True)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        assert conn.execute("SELECT valor FROM t").fetchone() == ("antes",)
        conn.execute("INSERT INTO t VALUES (?)", ("despues",))
        conn.commit()
    finally:
        conn.close()

    verify = sqlite3.connect(path)
    try:
        assert verify.execute("SELECT valor FROM t ORDER BY rowid").fetchall() == [
            ("antes",),
            ("despues",),
        ]
    finally:
        verify.close()


def test_runtime_vulnerable_no_degrada_wal_si_otra_conexion_sigue_abierta(
    tmp_path, monkeypatch
):
    path = tmp_path / "ocupada.db"
    owner = sqlite3.connect(path, timeout=0)
    assert owner.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    owner.execute("CREATE TABLE t (valor TEXT)")
    owner.execute("INSERT INTO t VALUES ('intacto')")
    owner.commit()

    _usar_runtime(monkeypatch, (3, 45, 1))
    try:
        with pytest.raises(sqlite_runtime.UnsafeSQLiteJournalModeError):
            sqlite_runtime.open_writer(path)
        with pytest.raises(sqlite_runtime.UnsafeSQLiteJournalModeError):
            sqlite_runtime.open_writer(path, allow_existing_journal_transition=True)

        assert owner.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert owner.execute("SELECT valor FROM t").fetchone() == ("intacto",)
    finally:
        owner.close()

    # Solo el opt-in explícito permite intentar la transición tras cerrar handles.
    conn = sqlite_runtime.open_writer(path, allow_existing_journal_transition=True)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
    finally:
        conn.close()


def test_base_wal_existente_no_se_cambia_sin_opt_in(tmp_path, monkeypatch):
    path = tmp_path / "sin_opt_in.db"
    seed = sqlite3.connect(path)
    assert seed.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    seed.execute("CREATE TABLE t (valor TEXT)")
    seed.execute("INSERT INTO t VALUES ('sin_cambios')")
    seed.commit()
    seed.close()

    _usar_runtime(monkeypatch, (3, 45, 1))
    with pytest.raises(sqlite_runtime.UnsafeSQLiteJournalModeError):
        sqlite_runtime.open_writer(path)

    verify = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        assert verify.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert verify.execute("SELECT valor FROM t").fetchone() == ("sin_cambios",)
    finally:
        verify.close()


def test_almacen_principal_y_dmn_aplican_la_misma_politica(tmp_path, monkeypatch):
    _usar_runtime(monkeypatch, (3, 45, 1))
    from core.memory_store import SQLiteMemoryBioRAG
    from core.dmn_engine import DMNEngine

    primary_path = tmp_path / "principal.db"
    store = SQLiteMemoryBioRAG(str(primary_path))
    try:
        assert store.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
    finally:
        store.cerrar_sistema()

    dmn = object.__new__(DMNEngine)
    dmn.db_path = str(tmp_path / "dmn.db")
    conn = dmn._crear_conexion_hilo()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_runtime_corregido_conserva_wal_y_memoria_no_se_fuerza_a_wal(
    tmp_path, monkeypatch
):
    _usar_runtime(monkeypatch, (3, 51, 3))
    disk = sqlite_runtime.open_writer(tmp_path / "fixed.db")
    try:
        assert disk.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        disk.close()

    existing_delete = tmp_path / "existing_delete.db"
    seed = sqlite3.connect(existing_delete)
    seed.execute("CREATE TABLE t (x INTEGER)")
    seed.close()
    disk = sqlite_runtime.open_writer(existing_delete)
    try:
        assert disk.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
    finally:
        disk.close()

    _usar_runtime(monkeypatch, (3, 45, 1))
    memory = sqlite_runtime.open_writer(":memory:")
    try:
        assert memory.execute("PRAGMA journal_mode").fetchone()[0].lower() == "memory"
        memory.execute("CREATE TABLE t (x INTEGER)")
    finally:
        memory.close()
