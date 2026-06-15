#!/usr/bin/env python3
"""BioRAG Installer — Cross-platform MCP setup.

Usage:
  curl -fsSL https://raw.githubusercontent.com/dennysjmarquez/MemoryBioRAG/main/install.py | python3
  python3 install.py                        # interactive (local)
  python3 install.py --uninstall            # remove BioRAG from configs
  python3 install.py --help

Installs BioRAG, connects it to your MCP-compatible agents (OpenCode,
Claude, Antigravity, VS Code, Cursor, Cline), and verifies everything works.

Design principles:
  - Zero external dependencies (stdlib only + pip for mcp)
  - sys.executable everywhere to guarantee same Python
  - pathlib for all paths (cross-platform)
  - Automatic backups before every write (JSON + database)
  - Git clone with ZIP fallback (for systems without git)
  - 4 incremental checkpoints to catch failures early
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
import zipfile
from pathlib import Path


# ── Metadata ────────────────────────────────────────────────────────────────

REPO_OWNER = "dennysjmarquez"
REPO_NAME = "MemoryBioRAG"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"
ZIP_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/main.zip"
INSTALL_DIR = Path.home() / "biorag"
BACKUPS_DIR = Path.home() / ".biorag" / "backups"
SSE_PORT = 8080


# ── Terminal helpers ────────────────────────────────────────────────────────

def _green(m: str) -> str:
    return f"\033[92m{m}\033[0m" if sys.stderr.isatty() else m

def _yellow(m: str) -> str:
    return f"\033[93m{m}\033[0m" if sys.stderr.isatty() else m

def _red(m: str) -> str:
    return f"\033[91m{m}\033[0m" if sys.stderr.isatty() else m

def _dim(m: str) -> str:
    return f"\033[90m{m}\033[0m" if sys.stderr.isatty() else m

def _bold(m: str) -> str:
    return f"\033[1m{m}\033[0m" if sys.stderr.isatty() else m

def _step(msg: str) -> None:
    print(f"\n  {_bold('→')} {msg}")

def _ok(msg: str) -> None:
    print(f"    {_green('✓')} {msg}")

def _warn(msg: str) -> None:
    print(f"    {_yellow('⚠')} {msg}")

def _fail(msg: str) -> None:
    print(f"    {_red('✗')} {msg}")

def _info(msg: str) -> None:
    print(f"    {_dim('•')} {msg}")


def _interactive() -> bool:
    """True if we can prompt the user (stdin is a terminal)."""
    return sys.stdin.isatty()


def _confirm(prompt: str, default: bool = True) -> bool:
    """Ask yes/no. In pipe mode, return default."""
    if not _interactive():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        reply = input(f"    {prompt}{suffix}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default
    if not reply:
        return default
    return reply.startswith("y")


# ── Path resolvers ──────────────────────────────────────────────────────────

def _platform_configs() -> dict[str, dict]:
    """Define all supported platforms with their config paths and formats."""
    is_mac = sys.platform == "darwin"
    is_win = sys.platform == "win32"

    def appdata(*parts: str) -> Path | None:
        if is_win:
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base.joinpath(*parts)
        return None

    return {
        "opencode": {
            "label": "OpenCode",
            "path": Path.home() / ".config" / "opencode" / "opencode.json",
            "key_path": ["mcp", "biorag"],
            "format": "stdio",
        },
        "claude_code": {
            "label": "Claude Code",
            "path": Path.home() / ".claude.json",
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "claude_desktop": {
            "label": "Claude Desktop",
            "path": (
                Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
                if is_mac
                else appdata("Claude", "claude_desktop_config.json")
                or Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
            ),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "antigravity": {
            "label": "Antigravity (Gemini)",
            "path": Path.home() / ".gemini" / "config" / "mcp_config.json",
            "key_path": ["mcpServers", "biorag"],
            "format": "sse",
        },
        "vscode": {
            "label": "VS Code",
            "path": Path.home() / ".vscode" / "mcp.json",
            "key_path": ["servers", "biorag"],
            "format": "stdio",
        },
        "cursor": {
            "label": "Cursor",
            "path": Path.home() / ".cursor" / "mcp.json",
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "cline": {
            "label": "Cline",
            "path": Path.home() / ".config" / "cline" / "cline_mcp_settings.json",
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
    }


def _detect_installed(configs: dict[str, dict]) -> dict[str, dict]:
    """Return only platforms whose config file exists on disk."""
    return {k: v for k, v in configs.items() if v["path"].exists()}


def _python() -> str:
    """The Python executable to use for everything."""
    return sys.executable


def _script_path() -> Path:
    """Absolute path to the MCP server script."""
    return INSTALL_DIR / "mcp_server.py"


def _biorag_cli() -> Path:
    """Absolute path to the biorag CLI."""
    return INSTALL_DIR / "biorag.py"


def _db_path() -> Path:
    """Path to the SQLite database."""
    return INSTALL_DIR / "MemoryBioRAG_Data" / "memory_biorag.db"


# ── JSON helpers ────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict:
    """Read JSON file, return empty dict if missing or corrupt."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        _warn(f"Error leyendo {path}: {exc}. Se empezará de cero.")
        return {}


def _write_json_with_checkpoint(path: Path, data: dict) -> bool:
    """Write JSON, verify it's parseable. Return True on success."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Checkpoint 3: verify the written file is valid JSON
        with open(tmp, "r", encoding="utf-8") as f:
            json.load(f)
        tmp.replace(path)
        return True
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"Error escribiendo {path}: {exc}")
        if tmp.exists():
            tmp.unlink()
        return False


def _nested_set(root: dict, key_path: list[str], value: dict) -> dict:
    """Navigate a nested dict via key_path and set value at the leaf key.

    Example: _nested_set({}, ["mcp", "biorag"], {...})
    → {"mcp": {"biorag": {...}}}
    """
    if len(key_path) == 1:
        root[key_path[0]] = value
        return root
    first = key_path[0]
    if first not in root or not isinstance(root[first], dict):
        root[first] = {}
    _nested_set(root[first], key_path[1:], value)
    return root


def _nested_delete(root: dict, key_path: list[str]) -> bool:
    """Remove the leaf key from nested dict. Return True if removed."""
    if len(key_path) == 1:
        if key_path[0] in root:
            del root[key_path[0]]
            return True
        return False
    first = key_path[0]
    if first not in root or not isinstance(root[first], dict):
        return False
    return _nested_delete(root[first], key_path[1:])


# ── Backup ──────────────────────────────────────────────────────────────────

def _backup_file(path: Path) -> Path | None:
    """Copy file to backups folder with timestamp. Return backup path or None."""
    if not path.exists():
        return None
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = path.name.replace(".json", "").replace(".", "_")
    dest = BACKUPS_DIR / f"{safe}-{ts}.json"
    shutil.copy2(path, dest)
    return dest


def _backup_database() -> Path | None:
    """Backup the SQLite database before destructive operations."""
    db = _db_path()
    if not db.exists():
        return None
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = BACKUPS_DIR / f"memory_biorag_{ts}.db"
    shutil.copy2(db, dest)
    _ok(f"Base de datos respaldada: {_dim(str(dest))}")
    return dest


# ── Checkpoint 1: --help (handled by argparse) ──────────────────────────────

# ── Checkpoint 2: download + install ────────────────────────────────────────

def _download_repo() -> None:
    """Clone or download BioRAG into INSTALL_DIR."""
    if INSTALL_DIR.exists():
        # Already installed — check for .git to decide update vs error
        git_dir = INSTALL_DIR / ".git"
        if git_dir.exists():
            _step("Actualizando repositorio...")
            _backup_database()
            try:
                subprocess.run(
                    ["git", "-C", str(INSTALL_DIR), "pull"],
                    check=True, capture_output=True, text=True,
                )
                _ok("Repositorio actualizado")
            except subprocess.CalledProcessError as exc:
                _fail(f"Git pull falló: {exc.stderr.strip()}")
                sys.exit(1)
        else:
            _step("Repositorio ya existe (sin git). Verificando integridad...")
            if not _script_path().exists():
                _fail(f"Instalación corrupta: falta {_script_path().name}")
                _info(f"Elimina {INSTALL_DIR} y vuelve a ejecutar el instalador.")
                sys.exit(1)
            _ok("Instalación existente verificada")
        return

    _step("Descargando BioRAG...")

    # Try git clone
    if shutil.which("git"):
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", REPO_URL, str(INSTALL_DIR)],
                check=True, capture_output=True, text=True,
            )
            _ok("Clonado via git")
            return
        except subprocess.CalledProcessError as exc:
            _warn(f"Git falló: {exc.stderr.strip()}")
            _info("Intentando descarga ZIP...")

    # Fallback: download ZIP via urllib (stdlib, no git needed)
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        zip_path = tmp_dir / "repo.zip"
        urllib.request.urlretrieve(ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)
        extracted = tmp_dir / f"{REPO_NAME}-main"
        if extracted.exists():
            if INSTALL_DIR.exists():
                shutil.rmtree(INSTALL_DIR)
            shutil.copytree(extracted, INSTALL_DIR)
            _ok(f"Descargado via ZIP ({REPO_NAME})")
        else:
            _fail(f"Estructura ZIP inesperada: no se encontró {extracted}")
            sys.exit(1)
    except Exception as exc:
        _fail(f"Descarga falló: {exc}")
        sys.exit(1)
    finally:
        if "tmp_dir" in dir():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _install_mcp() -> None:
    """Install the 'mcp' package using the same Python."""
    _step("Instalando dependencia MCP...")
    try:
        subprocess.run(
            [_python(), "-m", "pip", "install", "mcp"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        _fail(f"pip install mcp falló: {exc.stderr.strip()}")
        sys.exit(1)

    # Verify
    result = subprocess.run(
        [_python(), "-m", "pip", "show", "mcp"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _fail("mcp no se instaló correctamente")
        sys.exit(1)
    version_line = result.stdout.strip().splitlines()
    version = version_line[1] if len(version_line) > 1 else "ok"
    _ok(f"mcp instalado ({version})")


def _checkpoint2() -> None:
    """Verify the installation directory is valid after download."""
    script = _script_path()
    if not script.exists():
        _fail(f"Archivo clave faltante: {script}")
        sys.exit(1)
    _ok(f"{_script_path().name} encontrado")

    result = subprocess.run(
        [_python(), "-m", "pip", "show", "mcp"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _fail("mcp package no instalado (debería estar del paso anterior)")
        sys.exit(1)
    _ok("mcp package verificado")


# ── MCP config builders ─────────────────────────────────────────────────────

def _build_stdio_entry() -> dict:
    """Build the MCP entry for stdio transport (OpenCode, Claude, etc.)."""
    return {
        "command": _python(),
        "args": [str(_script_path())],
    }


def _build_opencode_entry() -> dict:
    """OpenCode uses a different format: command is an array, type + enabled."""
    return {
        "type": "local",
        "command": [_python(), str(_script_path())],
        "enabled": True,
    }


def _build_sse_entry(port: int = SSE_PORT) -> dict:
    """Build the MCP entry for SSE transport (Antigravity)."""
    return {
        "serverUrl": f"http://localhost:{port}/sse",
    }


# ── Platform configuration ──────────────────────────────────────────────────

def _configure_platform(name: str, info: dict) -> bool:
    """Add BioRAG MCP entry to one platform's config file.

    Returns True on success, False on skip/error.
    """
    path = info["path"]
    backup = _backup_file(path)
    if backup:
        _info(f"Backup: {_dim(str(backup))}")

    config = _read_json(path)
    key_path = info["key_path"]

    if info["format"] == "sse":
        entry = _build_sse_entry()
    elif name == "opencode":
        entry = _build_opencode_entry()
    else:
        entry = _build_stdio_entry()

    _nested_set(config, key_path, entry)
    ok = _write_json_with_checkpoint(path, config)

    if ok:
        _ok(f"Configurado en {info['label']}")
    else:
        _fail(f"Error escribiendo config de {info['label']}")
        if backup:
            shutil.copy2(backup, path)
            _info("Configuración anterior restaurada desde backup")

    return ok


def _remove_from_platform(name: str, info: dict) -> bool:
    """Remove the BioRAG entry from a platform's config. Return True if changed."""
    path = info["path"]
    if not path.exists():
        return False

    backup = _backup_file(path)
    if backup:
        _info(f"Backup: {_dim(str(backup))}")

    config = _read_json(path)
    removed = _nested_delete(config, info["key_path"])
    if not removed:
        _info(f"No se encontró entrada BioRAG en {info['label']}")
        return False

    ok = _write_json_with_checkpoint(path, config)
    if ok:
        _ok(f"BioRAG eliminado de {info['label']}")
    else:
        _fail(f"Error escribiendo {path}")
        if backup:
            shutil.copy2(backup, path)
    return ok


# ── Checkpoint 4: verification ─────────────────────────────────────────────

def _test_cli() -> bool:
    """Run biorag.py estado and verify it responds."""
    cli = _biorag_cli()
    if not cli.exists():
        _fail(f"CLI no encontrado: {cli}")
        return False

    try:
        result = subprocess.run(
            [_python(), str(cli), "estado"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            _fail(f"biorag.py estado falló (código {result.returncode})")
            _info(result.stderr.strip()[:300])
            return False
        _ok("CLI funcional — biorag.py estado responde")
        return True
    except subprocess.TimeoutExpired:
        _fail("biorag.py estado no respondió en 15 segundos")
        return False
    except Exception as exc:
        _fail(f"Error verificando CLI: {exc}")
        return False


def _test_mcp_server() -> bool:
    """Start MCP server briefly and verify it stays alive after initialize."""
    script = _script_path()
    _info("Iniciando servidor MCP para prueba...")
    try:
        proc = subprocess.Popen(
            [_python(), str(script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            init_msg = json.dumps({
                "jsonrpc": "2.0", "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "biorag-installer", "version": "1.0"},
                },
            })
            stdout_data, stderr_data = proc.communicate(input=init_msg, timeout=8)
        except subprocess.TimeoutExpired:
            # communicate timed out: server is alive waiting for more messages
            proc.kill()
            proc.wait(timeout=3)
            _ok("Servidor MCP inició correctamente")
            return True

        # Process exited before timeout — unexpected for a stdio server
        _fail(f"Servidor MCP terminó inesperadamente (código {proc.returncode})")
        err = stderr_data.strip()[:300] if stderr_data else ""
        if err:
            _info(f"stderr: {err}")
        return False
    except Exception as exc:
        _fail(f"Error probando servidor MCP: {exc}")
        return False


def _verify_final() -> None:
    """Checkpoint 4: full verification."""
    _step("Verificación final (Checkpoint 4)...")
    cli_ok = _test_cli()
    if not cli_ok:
        _warn("CLI no responde — revisa que la base de datos exista")
        _info("Solución: python3 biorag.py crear (si es primera vez)")

    mcp_ok = _test_mcp_server()
    if not mcp_ok and cli_ok:
        _warn("Servidor MCP con problemas — verifica que mcp esté instalado")
        _info("Solución: sys.executable -m pip install mcp")
    elif not mcp_ok:
        _warn("Servidor MCP no probado completamente")

    if cli_ok and mcp_ok:
        print(f"\n  {_green(_bold('✓ Todo funcional'))}")
    elif cli_ok:
        print(f"\n  {_yellow('⚠ CLI funcional, MCP con advertencias')}")


# ── Systemd service (SSE daemon) ───────────────────────────────────────────

def _install_systemd(port: int = SSE_PORT) -> bool:
    """Create a systemd service for the SSE server (Linux only)."""
    if sys.platform != "linux":
        _warn("systemd solo está disponible en Linux")
        return False

    service_name = "biorag-mcp"
    service_path = Path("/etc/systemd/system") / f"{service_name}.service"
    user = os.environ.get("USER", "root")

    unit = textwrap.dedent(f"""\
        [Unit]
        Description=BioRAG MCP Server (SSE mode)
        After=network.target

        [Service]
        Type=simple
        ExecStart={_python()} {_script_path()} --sse --port {port}
        Restart=always
        RestartSec=5
        User={user}

        [Install]
        WantedBy=default.target
    """)

    try:
        # Write via sudo
        tmp = Path(tempfile.mktemp())
        tmp.write_text(unit)
        subprocess.run(
            ["sudo", "cp", str(tmp), str(service_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["sudo", "systemctl", "daemon-reload"],
            check=True, capture_output=True, text=True,
        )
        tmp.unlink()
        _ok(f"Servicio systemd creado: {service_path}")
        _info("Inicia con: sudo systemctl enable --now biorag-mcp")
        _info(f"Servidor SSE en http://localhost:{port}/sse")
        return True
    except subprocess.CalledProcessError as exc:
        _fail(f"Error creando servicio: {exc.stderr.strip()}")
        return False
    except Exception as exc:
        _fail(f"Error: {exc}")
        return False


# ── Help / show-config (copy-paste blocks) ─────────────────────────────────

def _print_config_blocks() -> None:
    """Print JSON blocks for each platform (copy-paste friendly)."""
    script_path = _script_path()
    python_path = _python()

    blocks = {
        "OpenCode": {
            "path": "~/.config/opencode/opencode.json",
            "json": {
                "mcp": {
                    "biorag": {
                        "type": "local",
                        "command": [python_path, str(script_path)],
                        "enabled": True,
                    }
                }
            },
        },
        "Claude Code": {
            "path": "~/.claude.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
        "Claude Desktop": {
            "path": "~/.config/Claude/claude_desktop_config.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
        "Antigravity (Gemini)": {
            "path": "~/.gemini/config/mcp_config.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "serverUrl": f"http://localhost:{SSE_PORT}/sse",
                    }
                }
            },
            "note": "Requiere servidor SSE corriendo (ver --systemd)",
        },
        "VS Code": {
            "path": ".vscode/mcp.json (en la raíz del proyecto)",
            "json": {
                "servers": {
                    "biorag": {
                        "type": "stdio",
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
        "Cursor": {
            "path": "~/.cursor/mcp.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
        "Cline": {
            "path": "~/.config/cline/cline_mcp_settings.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
    }

    for label, info in blocks.items():
        print(f"\n  {_bold(label)}")
        _info(f"Archivo: {info['path']}")
        block = json.dumps(info["json"], indent=2, ensure_ascii=False)
        print(f"\n{block}")
        if "note" in info:
            _warn(info["note"])
        print()


# ── Main flow ───────────────────────────────────────────────────────────────

def install() -> None:
    """Full installation flow."""
    print(f"\n  {_bold('BioRAG Installer')} {_dim('— Memoria compartida para agentes de IA')}")
    print(f"  {_dim('=' * 48)}")

    # 1. Prerequisites
    _step("Verificando requisitos...")
    if sys.version_info < (3, 8):
        _fail("Python 3.8+ requerido")
        _info("Descarga: https://python.org/downloads/")
        sys.exit(1)
    _ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # 2. Download
    _download_repo()

    # 3. Install mcp package
    _install_mcp()

    # Checkpoint 2
    _step("Checkpoint 2 — verificando instalación...")
    _checkpoint2()

    # 4. Detect platforms
    all_platforms = _platform_configs()
    detected = _detect_installed(all_platforms)

    if not detected:
        _step("Configuración MCP")
        _warn("No se detectaron agentes MCP instalados")
        _info("Puedes configurar manualmente con:")
        _print_config_blocks()
    else:
        _step(f"Configurando MCP ({len(detected)} agente(s) detectado(s))...")
        configured = 0
        for name, info in detected.items():
            if _interactive():
                ok = _confirm(f"¿Configurar BioRAG en {info['label']}?", default=True)
                if not ok:
                    _info(f"Saltando {info['label']}")
                    continue
            ok = _configure_platform(name, info)
            if ok:
                configured += 1

        if configured == 0:
            _warn("No se configuró ningún agente")
            _info("Puedes hacerlo manualmente con --show-config")
        else:
            _ok(f"{configured} agente(s) configurado(s)")

        # Offer systemd if Antigravity was configured
        if "antigravity" in detected and _confirm("¿Crear servicio systemd para SSE?", default=False):
            _install_systemd()

    # Checkpoint 4
    _step("Verificación final...")
    _verify_final()

    # Done
    print(f"\n  {_green(_bold('Instalación completada'))}")
    print(f"\n    {_dim('BioRAG en:')}       {INSTALL_DIR}")
    print(f"    {_dim('Base de datos:')}    {_db_path()}")
    configured_names = [info['label'] for info in detected.values()] if detected else []
    print(f"    {_dim('MCP config:')}       {', '.join(configured_names) if configured_names else 'manual'}")
    print(f"\n    {_dim('Próximo paso:')}")
    print(f"    {_dim('Reinicia tu agente y dile:')}")
    prompt_msg = '"recuerda que me gusta el cafe"'
    print(f"    {_bold(prompt_msg)}")
    if detected:
        print(f"\n    {_dim('Si no ves las herramientas MCP, reinicia el agente.')}")
    if "antigravity" in detected and not _interactive():
        print(f"    {_yellow('⚠ Antigravity requiere servidor SSE corriendo.')}")
        print(f"    {_dim('Ejecuta despues: python3 ~/biorag/install.py --systemd')}")
        print(f"    {_dim('O inicia manual: python3 ~/biorag/mcp_server.py --sse --port 8080')}")
    print()


def uninstall() -> None:
    """Remove BioRAG from all platform configs. Optionally delete data."""
    all_platforms = _platform_configs()
    detected = _detect_installed(all_platforms)

    if not detected:
        _warn("No se detectaron configuraciones de BioRAG en ningún agente")
    else:
        _step("Eliminando BioRAG de configuraciones...")
        for name, info in detected.items():
            if _interactive():
                ok = _confirm(f"¿Eliminar BioRAG de {info['label']}?", default=True)
                if not ok:
                    continue
            _remove_from_platform(name, info)

    _step("Datos locales")
    if INSTALL_DIR.exists() and _confirm("¿Eliminar ~/biorag (incluye base de datos)?", default=False):
        _backup_database()
        shutil.rmtree(INSTALL_DIR)
        _ok("~/biorag eliminado")
    else:
        _info("~/biorag conservado")

    if BACKUPS_DIR.exists() and _confirm("¿Eliminar ~/.biorag/backups?", default=False):
        shutil.rmtree(BACKUPS_DIR)
        _ok("Backups eliminados")
    else:
        _info("Backups conservados")

    print(f"\n  {_green(_bold('BioRAG desinstalado'))}\n")


def show_summary() -> None:
    """Show current installation status."""
    print(f"\n  {_bold('BioRAG Status')}\n")

    if INSTALL_DIR.exists():
        _ok(f"Instalado en: {INSTALL_DIR}")
        if _db_path().exists():
            size = _db_path().stat().st_size / 1024
            _ok(f"Base de datos: {size:.0f} KB")
        else:
            _warn("Base de datos no encontrada")
    else:
        _warn(f"No instalado en {INSTALL_DIR}")

    all_p = _platform_configs()
    detected = _detect_installed(all_p)
    if detected:
        _ok(f"Configurado para: {', '.join(d['label'] for d in detected.values())}")
    else:
        _warn("No hay agentes MCP configurados")

    print()


# ── CLI ─────────────────────────────────────────────────────────────────────

def download_if_needed() -> bool:
    """Ensure BioRAG is downloaded (for --show-config, --systemd)."""
    if not _script_path().exists():
        _download_repo()
        _install_mcp()
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BioRAG Installer — Memoria compartida para agentes de IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(f"""\
            Ejemplos:
              curl -fsSL https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/install.py | python3
              python3 install.py
              python3 install.py --uninstall
              python3 install.py --show-config
              python3 install.py --systemd
        """),
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Eliminar BioRAG de configuraciones MCP y datos locales",
    )
    parser.add_argument(
        "--show-config", action="store_true",
        help="Mostrar bloques JSON de configuración para cada plataforma",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Mostrar estado de instalación actual",
    )
    parser.add_argument(
        "--systemd", action="store_true",
        help="Crear servicio systemd para SSE (Linux)",
    )
    parser.add_argument(
        "--port", type=int, default=SSE_PORT,
        help=f"Puerto para modo SSE (default: {SSE_PORT})",
    )

    args = parser.parse_args()

    if args.show_config:
        download_if_needed()
        _print_config_blocks()
        return

    if args.status:
        show_summary()
        return

    if args.uninstall:
        uninstall()
        return

    if args.systemd:
        download_if_needed()
        _install_systemd(args.port)
        return

    # Default: full install
    install()


if __name__ == "__main__":
    main()
