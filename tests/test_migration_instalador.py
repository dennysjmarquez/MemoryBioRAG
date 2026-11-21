"""
Pruebas de migración de base de datos viva e instalador multiplataforma.
Verifica:
  1. Resolución canónica de rutas en core/paths.py.
  2. Detección y migración de base de datos legacy a ~/.biorag/.
  3. Soporte e inserción limpia de configuración para Hermes AI Agent en YAML.
  4. Preservación de comentarios y opciones en configuraciones.
"""

import os
import sqlite3
import tempfile
from pathlib import Path
import pytest

from core import paths
import install


def test_resolve_db_path_explicit():
    assert paths.resolve_db_path("/custom/path/memory.db") == "/custom/path/memory.db"


def test_resolve_db_path_env(monkeypatch):
    monkeypatch.setenv("BIORAG_PATH", "/env/biorag.db")
    assert paths.resolve_db_path() == "/env/biorag.db"


def test_resolve_db_path_fallback_order(monkeypatch, tmp_path):
    monkeypatch.delenv("BIORAG_PATH", raising=False)
    
    user_db = tmp_path / ".biorag" / "memory_biorag.db"
    legacy_db = tmp_path / "repo" / "MemoryBioRAG_Data" / "memory_biorag.db"
    
    monkeypatch.setattr(paths, "_USER_HOME_DB", str(user_db))
    monkeypatch.setattr(paths, "_LEGACY_DB", str(legacy_db))
    monkeypatch.setattr(paths, "DEFAULT_DB", str(user_db))
    
    # Caso 1: Ninguna existe -> DEFAULT_DB
    assert paths.resolve_db_path() == str(user_db)
    
    # Caso 2: Solo legacy existe -> legacy_db
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    legacy_db.write_text("legacy data")
    assert paths.resolve_db_path() == str(legacy_db)
    
    # Caso 3: Ambas existen o user_db existe -> user_db tiene prioridad
    user_db.parent.mkdir(parents=True, exist_ok=True)
    user_db.write_text("user data")
    assert paths.resolve_db_path() == str(user_db)


def test_patch_hermes_yaml(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    initial_content = """# Hermes Configuration
file_read_max_chars: 100000

mcp_servers:
  notebooklm:
    command: notebooklm-mcp
    timeout: 300000
"""
    cfg_file.write_text(initial_content, encoding="utf-8")
    
    entry = {
        "command": "/usr/bin/python3",
        "args": ["/path/to/mcp_server.py"],
        "env": {"BIORAG_PATH": "/path/to/.biorag/memory_biorag.db"},
        "tools": {"prompts": False, "resources": False},
    }
    
    ok = install._patch_hermes_yaml(cfg_file, entry)
    assert ok is True
    
    result = cfg_file.read_text(encoding="utf-8")
    assert "# Hermes Configuration" in result
    assert "notebooklm-mcp" in result
    assert "biorag:" in result
    assert "/path/to/.biorag/memory_biorag.db" in result
    assert "/path/to/mcp_server.py" in result


def test_patch_hermes_yaml_update_existing(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    initial_content = """mcp_servers:
  biorag:
    args:
      - /old/path/mcp_server.py
    command: python3
    env:
      BIORAG_PATH: /old/MemoryBioRAG_Data/memory_biorag.db
  other:
    command: other-mcp
"""
    cfg_file.write_text(initial_content, encoding="utf-8")
    
    entry = {
        "command": "/new/python3",
        "args": ["/new/mcp_server.py"],
        "env": {"BIORAG_PATH": "/new/.biorag/memory_biorag.db"},
        "tools": {"prompts": False, "resources": False},
    }
    
    ok = install._patch_hermes_yaml(cfg_file, entry)
    assert ok is True
    
    result = cfg_file.read_text(encoding="utf-8")
    assert "/old/MemoryBioRAG_Data" not in result
    assert "/new/.biorag/memory_biorag.db" in result
    assert "/new/mcp_server.py" in result
    assert "other:" in result
    assert "other-mcp" in result


def test_remove_hermes_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "BACKUPS_DIR", tmp_path / "backups")
    cfg_file = tmp_path / "config.yaml"
    initial_content = """mcp_servers:
  biorag:
    args:
      - /path/to/mcp_server.py
    command: python3
    env:
      BIORAG_PATH: /path/to/.biorag/memory_biorag.db
  other:
    command: other-mcp
"""
    cfg_file.write_text(initial_content, encoding="utf-8")
    
    info = {
        "label": "Hermes AI Agent",
        "path": cfg_file,
        "key_path": ["mcp_servers", "biorag"],
        "format": "hermes_yaml",
    }
    
    changed = install._remove_from_platform("hermes", info)
    assert changed is True
    
    result = cfg_file.read_text(encoding="utf-8")
    assert "biorag" not in result
    assert "other:" in result
    assert "other-mcp" in result


def test_migrate_legacy_database(tmp_path, monkeypatch):
    legacy = tmp_path / "repo" / "MemoryBioRAG_Data" / "memory_biorag.db"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    
    # Crear una base sqlite real en legacy
    conn = sqlite3.connect(str(legacy))
    conn.execute("CREATE TABLE test_table (id INT, val TEXT)")
    conn.execute("INSERT INTO test_table VALUES (1, 'corteza_activa')")
    conn.commit()
    conn.close()
    
    target = tmp_path / "user_home" / ".biorag" / "memory_biorag.db"
    backups = tmp_path / "user_home" / ".biorag" / "backups"
    
    monkeypatch.setattr(install, "_legacy_db_path", lambda: legacy)
    monkeypatch.setattr(install, "_db_path", lambda: target)
    monkeypatch.setattr(install, "BACKUPS_DIR", backups)
    
    migrated = install._migrate_legacy_database()
    assert migrated is True
    assert not legacy.exists()
    assert target.exists()
    
    # Verificar integridad de datos en target
    conn2 = sqlite3.connect(str(target))
    cur = conn2.cursor()
    cur.execute("SELECT val FROM test_table WHERE id = 1")
    row = cur.fetchone()
    conn2.close()
    assert row is not None
    assert row[0] == "corteza_activa"


def test_daemon_enabled_flag(monkeypatch):
    from core.daemon_lifecycle import is_daemon_enabled, ensure_daemon_alive

    # 1. Por defecto (sin env var) -> False
    monkeypatch.delenv("BIORAG_DAEMON_ENABLED", raising=False)
    assert is_daemon_enabled() is False
    assert ensure_daemon_alive() is False

    # 2. Con 0 -> False
    monkeypatch.setenv("BIORAG_DAEMON_ENABLED", "0")
    assert is_daemon_enabled() is False
    assert ensure_daemon_alive() is False

    # 3. Con 1 -> True
    monkeypatch.setenv("BIORAG_DAEMON_ENABLED", "1")
    assert is_daemon_enabled() is True


def test_daemon_stop_command():
    from core.daemon_lifecycle import stop_daemon
    # Detener cuando no hay daemon debe ser seguro y retornar bool
    assert isinstance(stop_daemon(), bool)


def test_resolve_hormiguita_paths_canonical(monkeypatch):
    from core.paths import (
        resolve_estado_hormiga_path,
        resolve_hormiguita_lock_path,
        resolve_hormiguita_pid_path,
        resolve_hormiguita_log_dir,
    )
    monkeypatch.delenv("BIORAG_DMN_ESTADO_PATH", raising=False)
    monkeypatch.delenv("BIORAG_DAEMON_LOCK_PATH", raising=False)
    monkeypatch.delenv("BIORAG_DAEMON_PID_PATH", raising=False)
    monkeypatch.delenv("BIORAG_DAEMON_LOG_PATH", raising=False)

    estado = resolve_estado_hormiga_path()
    assert ".biorag" in estado
    assert estado.endswith("estado_hormiga.json")

    lock = resolve_hormiguita_lock_path()
    assert ".biorag" in lock
    assert lock.endswith(".hormiguita.lock")

    pid = resolve_hormiguita_pid_path()
    assert ".biorag" in pid
    assert pid.endswith(".hormiguita.pid")

    log_dir = resolve_hormiguita_log_dir()
    assert ".biorag" in log_dir
    assert log_dir.endswith("logs")


def test_resolve_estado_hormiga_env_override(monkeypatch, tmp_path):
    from core.paths import resolve_estado_hormiga_path
    custom = str(tmp_path / "custom_hormiga.json")
    monkeypatch.setenv("BIORAG_DMN_ESTADO_PATH", custom)
    assert resolve_estado_hormiga_path() == custom


