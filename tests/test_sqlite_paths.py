"""Resolución canónica de rutas sobre paths temporales; no abre DBs externas."""

import os

import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.paths import resolve_db_path


def test_ruta_relativa_se_resuelve_desde_cwd_sin_crear_archivos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BIORAG_PATH", "data/memoria.db")

    resolved = resolve_db_path()

    assert resolved == os.path.realpath(tmp_path / "data" / "memoria.db")
    assert not (tmp_path / "data").exists()


def test_alias_symlink_y_ruta_real_convergen(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    alias_dir = tmp_path / "alias"
    try:
        alias_dir.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink no disponible en este entorno: {exc}")

    via_alias = resolve_db_path(alias_dir / "bio.db")
    direct = resolve_db_path(real_dir / "bio.db")

    assert via_alias == direct
    assert not (real_dir / "bio.db").exists()


def test_argumento_explicito_gana_y_se_canoniza(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_PATH", str(tmp_path / "desde-env.db"))
    explicit = tmp_path / "subdir" / ".." / "explicit.db"

    resolved = resolve_db_path(explicit)

    assert resolved == os.path.realpath(explicit)
    assert "desde-env.db" not in resolved
    assert not (tmp_path / "explicit.db").exists()


def test_motor_abre_y_expone_ruta_canonica_para_path_relativo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cerebro = SQLiteMemoryBioRAG("data/../memoria.db")
    try:
        assert cerebro.db_path == os.path.realpath(tmp_path / "memoria.db")
        assert (tmp_path / "memoria.db").is_file()
    finally:
        cerebro.cerrar_sistema()


def test_memory_uri_y_sqlite_uri_se_preservan(monkeypatch):
    monkeypatch.setenv("BIORAG_PATH", "ignored.db")

    assert resolve_db_path(":memory:") == ":memory:"
    assert resolve_db_path("file:shared?mode=memory&cache=shared") == (
        "file:shared?mode=memory&cache=shared"
    )
