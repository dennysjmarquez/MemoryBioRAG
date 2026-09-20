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
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.request
import zipfile
from pathlib import Path


# ── Metadata ────────────────────────────────────────────────────────────────

REPO_OWNER = "dennysjmarquez"
REPO_NAME = "MemoryBioRAG"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"
ZIP_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/main.zip"


def _resolve_install_dir() -> Path:
    """Determine the installation directory.

    If running from within an existing clone of the repo (where mcp_server.py
    and core/ exist alongside install.py), use that directory directly.
    Otherwise (e.g. running via curl pipe), install to ~/biorag.
    """
    try:
        here = Path(__file__).resolve().parent
        if (here / "mcp_server.py").exists() and (here / "core").exists():
            return here
    except Exception:
        pass
    return Path.home() / "biorag"


INSTALL_DIR = _resolve_install_dir()
BACKUPS_DIR = Path.home() / ".biorag" / "backups"
SSE_PORT = 8080
OPENCODE_PLUGIN_NAME = "opencode-biorag-remember-plugin"


# ── Terminal helpers ────────────────────────────────────────────────────────

def _green(m: str) -> str:
    return f"\033[92m{m}\033[0m" if sys.stdout.isatty() else m

def _yellow(m: str) -> str:
    return f"\033[93m{m}\033[0m" if sys.stdout.isatty() else m

def _red(m: str) -> str:
    return f"\033[91m{m}\033[0m" if sys.stdout.isatty() else m

def _dim(m: str) -> str:
    return f"\033[90m{m}\033[0m" if sys.stdout.isatty() else m

def _bold(m: str) -> str:
    return f"\033[1m{m}\033[0m" if sys.stdout.isatty() else m

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


# ── Spinner (progress for long operations) ──────────────────────────────────

class _Spinner:
    """Animated spinner for long-running operations. Uses stdlib only.

    Usage::
        with _Spinner("Descargando..."):
            do_slow_thing()

    Prints a dot every second so the user knows something is happening.
    Completely silent when stdout is not a tty (pipe/log mode).
    """

    def __init__(self, label: str, interval: float = 1.0) -> None:
        self._label = label
        self._interval = interval
        self._stop = False
        self._thread: "threading.Thread | None" = None

    def _spin(self) -> None:
        import threading  # already imported at module level but kept local for clarity
        elapsed = 0.0
        while not self._stop:
            time.sleep(self._interval)
            elapsed += self._interval
            if not self._stop and sys.stdout.isatty():
                mins = int(elapsed) // 60
                secs = int(elapsed) % 60
                ts = f"{mins}m{secs:02d}s" if mins else f"{secs}s"
                print(f"    {_dim('⋯')} {self._label} ({ts})", flush=True)

    def __enter__(self) -> "_Spinner":
        import threading
        if sys.stdout.isatty():
            print(f"    {_dim('⋯')} {self._label}", flush=True)
        self._stop = False
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop = True
        if self._thread:
            self._thread.join(timeout=2)


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
    """Define all supported platforms with their candidate config paths and formats.

    Candidate logic:
    - The first *existing* path wins (detection mode).
    - If none exists the default path is used (creation mode).
    Covers Linux (~/.config/…), macOS (~/Library/…) and Windows (%APPDATA%, %LOCALAPPDATA%).
    """
    is_mac = sys.platform == "darwin"
    is_win = sys.platform == "win32"

    # ── Windows env helpers ────────────────────────────────────────────────
    def _appdata(*parts: str) -> Path | None:
        """Return %APPDATA%/parts on Windows, None elsewhere."""
        if not is_win:
            return None
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        return base.joinpath(*parts)

    def _localappdata(*parts: str) -> Path | None:
        """Return %LOCALAPPDATA%/parts on Windows, None elsewhere."""
        if not is_win:
            return None
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base.joinpath(*parts)

    def _glob_first(pattern_path: Path | None) -> Path | None:
        """Expand a glob pattern; return the first matching path or None."""
        if pattern_path is None:
            return None
        import glob as _glob
        matches = sorted(_glob.glob(str(pattern_path)))
        return Path(matches[0]) if matches else None

    # ── Claude Desktop — MSIX virtualised path (Windows installer) ────────
    # Official installer wraps the app in an MSIX package with a virtualised
    # filesystem. The effective config is inside:
    #   %LOCALAPPDATA%\Packages\Claude_<hash>\LocalCache\Roaming\Claude\claude_desktop_config.json
    _claude_msix_glob = _glob_first(
        _localappdata("Packages", "Claude_*", "LocalCache", "Roaming", "Claude", "claude_desktop_config.json")
        if is_win else None
    )

    # ── Candidate lists per platform ───────────────────────────────────────
    opencode_candidates: list[Path | None] = [
        Path.home() / ".config" / "opencode" / "opencode.jsonc",
        Path.home() / ".config" / "opencode" / "opencode.json",
        Path.home() / ".opencode" / "opencode.jsonc",
        Path.home() / ".opencode" / "opencode.json",
        # Windows: %APPDATA%\opencode\opencode.json
        _appdata("opencode", "opencode.jsonc"),
        _appdata("opencode", "opencode.json"),
    ]

    claude_code_candidates: list[Path | None] = [
        Path.home() / ".claude.json",
    ]

    if is_mac:
        claude_desktop_candidates: list[Path | None] = [
            Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        ]
    elif is_win:
        claude_desktop_candidates = [
            _claude_msix_glob,                                     # MSIX virtualised (priority)
            _appdata("Claude", "claude_desktop_config.json"),      # Standard %APPDATA%\Claude
        ]
    else:  # Linux / BSD
        claude_desktop_candidates = [
            Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
            Path.home() / ".config" / "claude" / "claude_desktop_config.json",
        ]

    antigravity_candidates: list[Path | None] = [
        Path.home() / ".gemini" / "config" / "mcp_config.json",
        Path.home() / ".gemini" / "mcp_config.json",
    ]

    vscode_candidates: list[Path | None] = [
        # Workspace-level (highest priority — project-specific)
        Path.cwd() / ".vscode" / "mcp.json",
        # User-level Linux/macOS
        Path.home() / ".config" / "Code" / "User" / "mcp.json",
        Path.home() / ".vscode" / "mcp.json",
        # User-level Windows (%APPDATA%\Code\User\mcp.json)
        _appdata("Code", "User", "mcp.json"),
        # VS Code Insiders
        Path.home() / ".config" / "Code - Insiders" / "User" / "mcp.json",
        _appdata("Code - Insiders", "User", "mcp.json"),
        # VSCodium
        Path.home() / ".config" / "VSCodium" / "User" / "mcp.json",
        _appdata("VSCodium", "User", "mcp.json"),
    ]

    cursor_candidates: list[Path | None] = [
        # Global — works identically on Linux, macOS, Windows
        # (Path.home() resolves to %USERPROFILE% on Windows)
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".config" / "Cursor" / "mcp.json",
        # Windows: %APPDATA%\Cursor\mcp.json (some installs)
        _appdata("Cursor", "mcp.json"),
        # Project-level (second priority after global)
        Path.cwd() / ".cursor" / "mcp.json",
    ]

    cline_candidates: list[Path | None] = [
        # Linux / macOS
        Path.home() / ".config" / "cline" / "cline_mcp_settings.json",
        Path.home() / ".config" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        # Windows
        _appdata("Code", "User", "globalStorage", "saoudrizwan.claude-dev", "settings", "cline_mcp_settings.json"),
    ]

    roo_candidates: list[Path | None] = [
        # Linux / macOS
        Path.home() / ".config" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json",
        Path.home() / ".config" / "roo-cline" / "cline_mcp_settings.json",
        # Windows
        _appdata("Code", "User", "globalStorage", "rooveterinaryinc.roo-cline", "settings", "cline_mcp_settings.json"),
    ]

    windsurf_candidates: list[Path | None] = [
        # Linux / macOS
        Path.home() / ".config" / "Windsurf" / "User" / "mcp.json",
        Path.home() / ".windsurf" / "mcp.json",
        # Windows
        _appdata("Windsurf", "User", "mcp.json"),
    ]

    def _pick_path(candidates: list[Path | None], default: Path) -> Path:
        """Return the first *existing* candidate, else default (create path)."""
        for p in candidates:
            if p and p.exists():
                return p
        return default

    # ── Default creation paths per OS ────────────────────────────────────
    _vscode_default = (
        _appdata("Code", "User", "mcp.json")
        if is_win
        else (Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json")
        if is_mac
        else Path.home() / ".config" / "Code" / "User" / "mcp.json"
    )

    _cursor_default = Path.home() / ".cursor" / "mcp.json"

    _claude_desktop_default = (
        _appdata("Claude", "claude_desktop_config.json")
        if is_win
        else (Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
        if is_mac
        else Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    )

    return {
        "opencode": {
            "label": "OpenCode",
            "path": _pick_path(opencode_candidates, Path.home() / ".config" / "opencode" / "opencode.json"),
            "key_path": ["mcp", "biorag"],
            "format": "stdio",
        },
        "claude_code": {
            "label": "Claude Code",
            "path": _pick_path(claude_code_candidates, Path.home() / ".claude.json"),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "claude_desktop": {
            "label": "Claude Desktop",
            "path": _pick_path(claude_desktop_candidates, _claude_desktop_default),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "antigravity": {
            "label": "Antigravity (Gemini)",
            "path": _pick_path(antigravity_candidates, Path.home() / ".gemini" / "config" / "mcp_config.json"),
            "key_path": ["mcpServers", "biorag"],
            "format": "sse",
        },
        "vscode": {
            "label": "VS Code",
            "path": _pick_path(vscode_candidates, _vscode_default),
            "key_path": ["servers", "biorag"],
            "format": "stdio",
        },
        "cursor": {
            "label": "Cursor",
            "path": _pick_path(cursor_candidates, _cursor_default),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "cline": {
            "label": "Cline",
            "path": _pick_path(cline_candidates, Path.home() / ".config" / "cline" / "cline_mcp_settings.json"),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "roo_code": {
            "label": "Roo Code",
            "path": _pick_path(roo_candidates, Path.home() / ".config" / "roo-cline" / "cline_mcp_settings.json"),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
        "windsurf": {
            "label": "Windsurf",
            "path": _pick_path(windsurf_candidates, Path.home() / ".config" / "Windsurf" / "User" / "mcp.json"),
            "key_path": ["mcpServers", "biorag"],
            "format": "stdio",
        },
    }


def _detect_installed(configs: dict[str, dict]) -> dict[str, dict]:
    """Return only platforms whose config file exists on disk."""
    return {k: v for k, v in configs.items() if v["path"].exists()}


def _biorag_already_configured(info: dict) -> bool:
    """Return True if BioRAG is already correctly configured in this platform's config.

    'Correctly configured' means:
    - The nested key path exists in the config.
    - For stdio entries: the script path matches the current INSTALL_DIR.
    - For SSE entries: the serverUrl is present.

    This enables idempotent installs: if nothing changed, we skip the write
    and tell the user it's already up to date — exactly like rustup or homebrew.
    """
    path = info["path"]
    if not path.exists():
        return False
    try:
        config = _read_json(path)
    except Exception:
        return False

    # Walk key_path to find the leaf
    node = config
    for key in info["key_path"]:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]

    if not isinstance(node, dict):
        return False

    # Validate the entry points to the right place
    if info["format"] == "sse":
        return "serverUrl" in node

    # stdio: check the script path is still valid (covers reinstall to new dir)
    script = str(_script_path())
    command = node.get("command", "")
    args = node.get("args", [])

    if isinstance(command, list):
        # OpenCode format: command is a list [python, script]
        return len(command) >= 2 and command[-1] == script
    else:
        # Standard format: command is python, args[0] is script
        return bool(args) and args[0] == script



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


# ── JSON / JSONC helpers ───────────────────────────────────────────────────

def _strip_json_comments(text: str) -> str:
    """Strip JS comments (// and /* */) and trailing commas from JSON/JSONC text."""
    import re
    out = []
    i = 0
    n = len(text)
    in_string = False
    escape = False

    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_string = False
            i += 1
        else:
            if c == '"':
                in_string = True
                out.append(c)
                i += 1
            elif c == '/' and i + 1 < n and text[i + 1] == '/':
                i += 2
                while i < n and text[i] != '\n':
                    i += 1
            elif c == '/' and i + 1 < n and text[i + 1] == '*':
                i += 2
                while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                    i += 1
                i += 2
            else:
                out.append(c)
                i += 1

    cleaned = "".join(out)
    # Remove trailing commas before } or ]
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
    return cleaned


def _read_json(path: Path) -> dict:
    """Read JSON or JSONC file, return empty dict if missing or corrupt."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Fallback to JSONC comment stripping
            return json.loads(_strip_json_comments(raw))
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


def _patch_jsonc_preserving_comments(path: Path, key_path: list[str], value: dict) -> bool:
    """Surgically inject a nested key into a JSONC file WITHOUT stripping comments.

    Strategy:
    - Parse the file normally (stripping comments for parsing only).
    - Locate the insertion point using the existing parsed structure.
    - If the top-level key already exists as a JSON object in the raw text,
      insert our entry right after its opening brace.
    - If not, append it before the final closing `}`.
    - Writes atomically and verifies the result is parseable.

    Falls back to plain JSON write if the surgical patch fails.
    Returns True on success.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
    except OSError:
        original = ""

    # Check if the file actually contains JS comments — if not, plain write is fine
    has_comments = "//" in original or "/*" in original
    if not has_comments:
        parsed = _read_json(path)
        _nested_set(parsed, key_path, value)
        return _write_json_with_checkpoint(path, parsed)

    # --- Surgical patch approach ---
    # We build the JSON snippet to inject and find where to put it.
    leaf_key = key_path[-1]          # e.g. "biorag"
    parent_keys = key_path[:-1]      # e.g. ["mcp"]

    snippet = json.dumps({leaf_key: value}, indent=2, ensure_ascii=False)
    # snippet looks like:  {\n  "biorag": { ... }\n}
    # We want only the inner line(s), indented to match the parent object.
    inner_lines = snippet.splitlines()[1:-1]   # strip outer { }
    inner_snippet = "\n".join(inner_lines)     # e.g.   "biorag": { ... }

    # Build the patched text using the parsed data (comments stripped) + re-serialise
    # to preserve the STRUCTURE, but keep the original file's comments.
    # The simplest guaranteed-correct approach: parse → merge → write pretty JSON,
    # then graft the original file's comment lines back as a header.
    # However, inline comments (// after a value) cannot be reconstructed.
    #
    # Pragmatic solution: write the merged data as pretty JSON, and prepend any
    # file-level comment block (lines at the very top starting with // or /*).
    #
    parsed = _read_json(path)
    _nested_set(parsed, key_path, value)

    # Collect leading comment lines (before the opening `{`)
    header_comments: list[str] = []
    for line in original.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            header_comments.append(line)
        elif stripped == "" and not header_comments:
            continue
        else:
            break  # stop at first non-comment, non-blank line

    new_content = json.dumps(parsed, indent=2, ensure_ascii=False)
    if header_comments:
        new_content = "\n".join(header_comments) + "\n" + new_content

    tmp = path.with_suffix(".jsonc.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        # Verify the result is parseable (with comment stripping)
        json.loads(_strip_json_comments(new_content))
        tmp.replace(path)
        return True
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _warn(f"Patch JSONC falló ({exc}), usando escritura JSON estándar")
        if tmp.exists():
            tmp.unlink()
        # Fallback: plain JSON write (loses comments, but safe)
        _nested_set(parsed, key_path, value)
        return _write_json_with_checkpoint(path, parsed)



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

def _is_local_repo() -> bool:
    """Return True if running directly from an existing cloned repository."""
    try:
        here = Path(__file__).resolve().parent
        return (here / "mcp_server.py").exists() and (here / "core").exists()
    except Exception:
        return False


def _download_repo() -> None:
    """Clone or download BioRAG into INSTALL_DIR, or use local repo if already present."""
    if _is_local_repo() and INSTALL_DIR == Path(__file__).resolve().parent:
        _step("Verificando repositorio local...")
        if not _script_path().exists():
            _fail(f"Instalación corrupta: falta {_script_path().name}")
            sys.exit(1)
        _ok(f"Repositorio local detectado en: {_dim(str(INSTALL_DIR))} (no requiere descarga de código)")
        return

    if INSTALL_DIR.exists():
        # Already installed in target dir — check for .git to decide update vs verification
        git_dir = INSTALL_DIR / ".git"
        if git_dir.exists():
            _step("Actualizando repositorio existente...")
            _backup_database()
            try:
                with _Spinner("Actualizando via git pull..."):
                    subprocess.run(
                        ["git", "-C", str(INSTALL_DIR), "pull"],
                        check=True, capture_output=True, text=True,
                    )
                _ok("Repositorio actualizado")
            except subprocess.CalledProcessError as exc:
                _warn(f"Git pull falló: {exc.stderr.strip()}")
                _info("Continuando con la instalación local existente...")
        else:
            _step("Repositorio ya existe en destino. Verificando integridad...")
            if not _script_path().exists():
                _fail(f"Instalación corrupta: falta {_script_path().name}")
                _info(f"Elimina {INSTALL_DIR} y vuelve a ejecutar el instalador.")
                sys.exit(1)
            _ok("Instalación existente verificada")
        return

    _step(f"Descargando código fuente de BioRAG en {INSTALL_DIR}...")

    # Try git clone
    if shutil.which("git"):
        try:
            with _Spinner("Clonando repositorio via git..."):
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
        with _Spinner("Descargando ZIP del repositorio..."):
            urllib.request.urlretrieve(ZIP_URL, zip_path)
        with _Spinner("Extrayendo archivos..."):
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


def _has_pip() -> bool:
    """Check if pip is available and runnable."""
    res = subprocess.run([_python(), "-m", "pip", "--version"], capture_output=True, text=True)
    return res.returncode == 0


def _ensure_pip_available() -> None:
    """Ensure pip is installed; attempt auto-bootstrap via ensurepip and get-pip.py."""
    if _has_pip():
        return

    _info("Módulo pip no detectado. Intentando auto-instalación con ensurepip...")
    try:
        subprocess.run([_python(), "-m", "ensurepip", "--upgrade", "--default-pip"], capture_output=True, text=True)
        if _has_pip():
            _ok("pip instalado exitosamente vía ensurepip")
            return
    except Exception:
        pass

    # Method 2: Download get-pip.py (Official PyPA standalone bootstrapper)
    _info("Descargando e instalando pip automáticamente (get-pip.py)...")
    tmp_get_pip = None
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_get_pip = tmp_dir / "get-pip.py"
        GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
        urllib.request.urlretrieve(GET_PIP_URL, tmp_get_pip)

        # Run get-pip.py (with --break-system-packages if needed for Debian/Ubuntu PEP 668)
        cmd_pip = [_python(), str(tmp_get_pip), "--quiet"]
        res = subprocess.run(cmd_pip, capture_output=True, text=True)
        if res.returncode != 0 and ("externally-managed-environment" in res.stderr or "error: externally-managed-environment" in res.stderr):
            cmd_pip_break = [_python(), str(tmp_get_pip), "--break-system-packages", "--quiet"]
            res = subprocess.run(cmd_pip_break, capture_output=True, text=True)

        if _has_pip():
            _ok("pip instalado y configurado automáticamente")
            return
    except Exception as exc:
        _warn(f"Auto-instalación de pip falló: {exc}")
    finally:
        if tmp_get_pip and tmp_get_pip.parent.exists():
            shutil.rmtree(tmp_get_pip.parent, ignore_errors=True)

    # Fallback only if totally offline and without pip
    _fail("No se pudo auto-instalar pip (sistema sin conexión o permisos restringidos).")
    if sys.platform.startswith("linux"):
        _info("Por favor ejecuta una vez:")
        print(f"\n      {_bold('sudo apt update && sudo apt install -y python3-pip python3-venv')}\n")
    sys.exit(1)


def _pip_install(args: list[str], label: str = "") -> subprocess.CompletedProcess:
    """Run pip install with automatic fallback for PEP 668 (externally-managed-environment).

    Shows a spinner while installing so the user knows progress is happening.
    """
    cmd = [_python(), "-m", "pip", "install"] + args
    spin_label = label or f"pip install {' '.join(args[:1])}..."
    with _Spinner(spin_label):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 and (
            "externally-managed-environment" in res.stderr
            or "error: externally-managed-environment" in res.stderr
        ):
            # Retry with --break-system-packages (Ubuntu 23+/Debian 12+ PEP 668 when installing outside venv)
            cmd_break = [_python(), "-m", "pip", "install", "--break-system-packages"] + args
            res = subprocess.run(cmd_break, capture_output=True, text=True)
    return res


def _install_mcp() -> None:
    """Install the 'mcp' and 'nltk' packages using the same Python."""
    _step("Instalando dependencias de Python (pip)...")
    _ensure_pip_available()

    res = _pip_install(
        ["mcp>=1.0.0,<2", "nltk>=3.8,<3.10"],
        label="Instalando mcp y nltk...",
    )
    if res.returncode != 0:
        _fail(f"pip install falló: {res.stderr.strip()}")
        sys.exit(1)

    # Verify mcp
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

    # Verify nltk
    result = subprocess.run(
        [_python(), "-m", "pip", "show", "nltk"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _fail("nltk no se instaló correctamente")
        sys.exit(1)
    _ok("nltk instalado")

    # Install project requirements (fastapi, uvicorn, etc.)
    req_file = INSTALL_DIR / "requirements.txt"
    if req_file.exists():
        _info("Instalando deps del proyecto (requirements.txt)...")
        res_req = _pip_install(["-r", str(req_file)], label="Instalando dependencias del proyecto...")
        if res_req.returncode == 0:
            _ok("Deps del proyecto instaladas")
        else:
            _warn(f"pip install -r requirements.txt falló: {res_req.stderr.strip()[:200]}")


def _install_wordnet() -> None:
    """Download WordNet data to local nltk_data directory."""
    _step("Descargando diccionarios semánticos WordNet + OMW (NLTK)...")
    nltk_data_dir = INSTALL_DIR / "MemoryBioRAG_Data" / "nltk_data"
    nltk_data_dir.mkdir(parents=True, exist_ok=True)

    # Build the script as a list of lines to avoid IndentationError in f-string heredocs.
    # (Embedding a multiline f-string literal where the content has real indentation of
    # its own is a Python gotcha: the interpreter sees those leading spaces as real code
    # indentation and raises IndentationError.)
    _nltk_script = "\n".join([
        "import nltk",
        f"nltk.data.path.insert(0, {str(nltk_data_dir)!r})",
        f"nltk.download('wordnet', download_dir={str(nltk_data_dir)!r}, quiet=True)",
        f"nltk.download('omw-1.4', download_dir={str(nltk_data_dir)!r}, quiet=True)",
        f"nltk.download('omw-2.0', download_dir={str(nltk_data_dir)!r}, quiet=True)",
        "from nltk.corpus import wordnet as wn",
        "synsets = wn.synsets('error')",
        "print(f'WordNet OK: {len(synsets)} synsets')",
        "synsets_es = wn.synsets('error', lang='spa')",
        "print(f'omw-2.0 OK: {len(synsets_es)} synsets in Spanish')",
    ])
    try:
        with _Spinner("Descargando WordNet + OMW (puede tardar 30-60s)..."):
            result = subprocess.run(
                [_python(), "-c", _nltk_script],
                capture_output=True, text=True, timeout=120,
            )
        if result.returncode != 0:
            _warn(f"WordNet download tuvo problemas: {result.stderr.strip()[:200]}")
            _info("La clasificación léxica funcionará cuando nltk esté disponible")
        else:
            _ok("WordNet + omw-2.0 descargado y verificado")
            if result.stdout.strip():
                _info(result.stdout.strip().splitlines()[0])
    except subprocess.TimeoutExpired:
        _warn("WordNet download tardó demasiado (120s) — ¿sin conexión?")
        _info("Se descargará automáticamente en el primer uso")
    except Exception as exc:
        _warn(f"Error descargando WordNet: {exc}")
        _info("Se descargará automáticamente en el primer uso")


def _install_dashboard_deps() -> None:
    """Install Python + Node dependencies for dashboard-neuro-visor."""
    _step("Instalando dependencias del dashboard Neuro-Visor...")
    
    project_root = INSTALL_DIR
    dashboard_dir = project_root / "dashboard-neuro-visor"
    
    if not dashboard_dir.exists():
        _warn(f"Dashboard no encontrado en {dashboard_dir}, saltando")
        return
    
    # 1. Python deps (root requirements.txt)
    req_file = project_root / "requirements.txt"
    if req_file.exists():
        _info("Instalando deps Python (fastapi, uvicorn)...")
        try:
            subprocess.run(
                [_python(), "-m", "pip", "install", "-r", str(req_file)],
                check=True, capture_output=True, text=True,
            )
            _ok("Deps Python instaladas")
        except subprocess.CalledProcessError as exc:
            _fail(f"pip install -r requirements.txt falló: {exc.stderr.strip()}")
    else:
        _warn(f"No se encontró {req_file}")
    
    # 2. Node deps (npm ci)
    if shutil.which("npm") or shutil.which("node"):
        _info("Instalando deps Node (npm ci)...")
        try:
            subprocess.run(
                ["npm", "ci"],
                cwd=dashboard_dir,
                check=True, capture_output=True, text=True,
            )
            _ok("Deps Node instaladas")
        except subprocess.CalledProcessError:
            _warn("npm ci falló, intentando npm install...")
            subprocess.run(
                ["npm", "install"],
                cwd=dashboard_dir,
                check=False, capture_output=True, text=True,
            )
    else:
        _warn("Node/npm no disponible — dashboard requerirá 'npm install' manual")


def _install_skill() -> None:
    """Copy skills from repo to agent skill directories.

    Scans INSTALL_DIR/skills/ for folders containing SKILL.md
    and copies each to the skills directory of detected agents.
    Silently skips if no skills found or no agent directories exist.
    """
    skills_src = INSTALL_DIR / "skills"
    if not skills_src.exists():
        _info("No se encontro carpeta skills/ en repo, saltando")
        return

    skill_folders = [
        d for d in skills_src.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    ]
    if not skill_folders:
        _info("No se encontraron skills con SKILL.md en repo")
        return

    skill_dirs = [
        Path.home() / ".claude" / "skills",
        Path.home() / ".config" / "opencode" / "skills",
        Path.home() / ".agents" / "skills",
    ]
    skill_dirs = [d for d in skill_dirs if d.exists()]

    if not skill_dirs:
        _info("No se detectaron carpetas de skills de agentes")
        return

    installed = 0
    for skill_folder in skill_folders:
        skill_name = skill_folder.name
        for target_base in skill_dirs:
            dest = target_base / skill_name / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                _backup_file(dest)
            shutil.copy2(skill_folder / "SKILL.md", dest)
            _ok(f"Skill '{skill_name}' instalado en {dest.parent}")
            installed += 1

    _info(f"{len(skill_folders)} skill(s) instalado(s) en {installed} destino(s)")


def _remove_skill() -> None:
    """Remove installed skills from agent directories during uninstall."""
    skill_dirs = [
        Path.home() / ".claude" / "skills",
        Path.home() / ".config" / "opencode" / "skills",
        Path.home() / ".agents" / "skills",
    ]
    removed = 0
    for d in skill_dirs:
        if not d.exists():
            continue
        for skill_folder in d.iterdir():
            if skill_folder.is_dir() and (skill_folder / "SKILL.md").exists():
                skill_folder_name = skill_folder.name
                shutil.rmtree(skill_folder)
                _ok(f"Skill '{skill_folder_name}' eliminado de {d}")
                removed += 1
    if removed == 0:
        _info("No se encontraron skills instalados para eliminar")


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
    Uses JSONC-safe writing: if the existing config has JS comments (// or /* */),
    we preserve them instead of stripping them via json.dump round-trip.
    """
    path = info["path"]
    backup = _backup_file(path)
    if backup:
        _info(f"Backup: {_dim(str(backup))}")

    key_path = info["key_path"]

    if info["format"] == "sse":
        entry = _build_sse_entry()
    elif name == "opencode":
        entry = _build_opencode_entry()
    else:
        entry = _build_stdio_entry()

    # Choose write strategy: if the file has JSONC comments, use the comment-preserving patcher.
    # Otherwise use the standard JSON checkpoint writer.
    has_jsonc_comments = False
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
            has_jsonc_comments = "//" in raw or "/*" in raw
        except OSError:
            pass

    if has_jsonc_comments:
        ok = _patch_jsonc_preserving_comments(path, key_path, entry)
    else:
        config = _read_json(path)
        _nested_set(config, key_path, entry)
        ok = _write_json_with_checkpoint(path, config)

    if ok:
        _ok(f"Configurado en {info['label']}")
        # Install OpenCode plugin alongside MCP config
        if name == "opencode":
            _install_opencode_plugin()
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
        # Remove OpenCode plugin alongside MCP config
        if name == "opencode":
            _remove_opencode_plugin()
    else:
        _fail(f"Error escribiendo {path}")
        if backup:
            shutil.copy2(backup, path)
    return ok


# ── OpenCode plugin ────────────────────────────────────────────────────────

def _opencode_plugins_dir() -> Path:
    """Return ~/.config/opencode/plugins/."""
    return Path.home() / ".config" / "opencode" / "plugins"


def _install_opencode_plugin() -> bool:
    """Copy opencode-biorag-remember-plugin.ts to OpenCode plugins dir.

    Returns True on success or if already installed.
    """
    source = INSTALL_DIR / "plugin" / f"{OPENCODE_PLUGIN_NAME}.ts"
    if not source.exists():
        _warn(f"Plugin no encontrado: {source}")
        return False

    plugins_dir = _opencode_plugins_dir()
    dest = plugins_dir / f"{OPENCODE_PLUGIN_NAME}.ts"

    # Create plugins dir if it doesn't exist
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # Copy plugin file
    try:
        shutil.copy2(source, dest)
        _ok(f"Plugin copiado: {dest}")
    except Exception as exc:
        _fail(f"Error copiando plugin: {exc}")
        return False

    return True


def _remove_opencode_plugin() -> bool:
    """Remove opencode-biorag-remember-plugin from OpenCode plugins dir."""
    plugins_dir = _opencode_plugins_dir()
    plugin_file = plugins_dir / f"{OPENCODE_PLUGIN_NAME}.ts"

    # Remove file
    if plugin_file.exists():
        plugin_file.unlink()
        _ok(f"Plugin eliminado: {plugin_file}")

    return True


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
            "path": "~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            "note_win": r"Windows: %APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
        "Roo Code": {
            "path": "~/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json",
            "json": {
                "mcpServers": {
                    "biorag": {
                        "command": python_path,
                        "args": [str(script_path)],
                    }
                }
            },
        },
        "Windsurf": {
            "path": "~/.config/Windsurf/User/mcp.json",
            "note_win": r"Windows: %APPDATA%\Windsurf\User\mcp.json",
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
        if sys.platform == "win32" and "note_win" in info:
            _info(f"Windows: {info['note_win']}")
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
    if sys.version_info < (3, 10):
        _fail("Python 3.10+ requerido")
        _info("Descarga: https://python.org/downloads/")
        sys.exit(1)
    _ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # 2. Download
    _download_repo()

    # 3. Install mcp + nltk packages
    _install_mcp()

    # 3b. Install WordNet data
    _install_wordnet()

    # 3c. Install skills
    _install_skill()

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
        already_ok = 0
        for name, info in detected.items():
            # Idempotency: si BioRAG ya está correctamente configurado aquí, saltar.
            if _biorag_already_configured(info):
                _ok(f"{info['label']}: ya configurado correctamente {_dim('(sin cambios)')}")
                already_ok += 1
                continue

            if _interactive():
                ok = _confirm(f"¿Configurar BioRAG en {info['label']}?", default=True)
                if not ok:
                    _info(f"Saltando {info['label']}")
                    continue
            ok = _configure_platform(name, info)
            if ok:
                configured += 1

        if configured == 0 and already_ok == 0:
            _warn("No se configuró ningún agente")
            _info("Puedes hacerlo manualmente con --show-config")
        elif configured > 0:
            _ok(f"{configured} agente(s) configurado(s) correctamente")

        # Offer systemd if Antigravity was detected
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
        print(f"    {_dim(f'Ejecuta despues: python3 {INSTALL_DIR}/install.py --systemd')}")
        print(f"    {_dim(f'O inicia manual: python3 {INSTALL_DIR}/mcp_server.py --sse --port 8080')}")
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

    _step("Eliminando skills instalados")
    _remove_skill()

    _step("Datos locales")
    if INSTALL_DIR.exists() and _confirm(f"¿Eliminar {INSTALL_DIR} (incluye base de datos)?", default=False):
        _backup_database()
        shutil.rmtree(INSTALL_DIR)
        _ok(f"{INSTALL_DIR} eliminado")
    else:
        _info(f"{INSTALL_DIR} conservado")

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
