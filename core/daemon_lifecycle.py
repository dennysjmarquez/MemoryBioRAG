"""
BioRAG Daemon Lifecycle — Gestión cross-platform del daemon de mantenimiento del grafo
======================================================================================

El MCP server usa este módulo para asegurar que el daemon de la hormiguita
esté corriendo como proceso detachado. El daemon sobrevive a la muerte del
MCP server — cuando opencode cierra, el daemon sigue. La próxima vez que
opencode abra, el MCP server checkea si sigue vivo.

Uso en mcp_server.py:
    from core.daemon_lifecycle import ensure_daemon_alive
    ensure_daemon_alive()  # Called once at server startup

Variables de entorno:
    BIORAG_DAEMON_INTERVALO_HORAS  — Intervalo entre ciclos (default: 6)
    BIORAG_DAEMON_MAX_NODOS        — Nodos por ciclo (default: 10)
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# --- Paths -------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PID_PATH = os.path.join(PROJECT_ROOT, ".hormiguita.pid")
DAEMON_SCRIPT = os.path.join(PROJECT_ROOT, "graph_maintenance_daemon.py")


def _leer_pid() -> int | None:
    """Lee el PID del archivo. Retorna None si no existe o es inválido."""
    try:
        with open(PID_PATH, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def _escribir_pid(pid: int) -> None:
    """Escribe el PID al archivo."""
    with open(PID_PATH, "w") as f:
        f.write(str(pid))


def _borrar_pid() -> None:
    """Borra el archivo PID si existe."""
    try:
        os.remove(PID_PATH)
    except FileNotFoundError:
        pass


# --- Health check ------------------------------------------------------------

def is_daemon_alive() -> bool:
    """
    Check cross-platform si el daemon está corriendo.
    
    Usa os.kill(pid, 0) — en Unix es un signal de probe, en Windows
    verifica si el proceso existe. Funciona en Linux, macOS y Windows.
    """
    pid = _leer_pid()
    if pid is None:
        return False
    
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        # Proceso no existe — PID reciclado o daemon muerto
        _borrar_pid()
        return False


# --- Detached spawn -----------------------------------------------------------

def spawn_daemon_detached(
    intervalo_horas: float | None = None,
    max_nodos: int | None = None,
) -> bool:
    """
    Lanza el daemon como proceso detachado que sobrevive al padre.
    
    Retorna True si se spawneó correctamente, False si falló.
    """
    python = sys.executable
    cmd = [python, DAEMON_SCRIPT]
    
    if intervalo_horas is not None:
        cmd.extend(["--intervalo", str(intervalo_horas)])
    if max_nodos is not None:
        cmd.extend(["--max-nodos", str(max_nodos)])
    
    env = os.environ.copy()
    env["BIORAG_DAEMON_SPAWNED_FROM_MCP"] = "1"
    # Forzar el estado canónico: el daemon SIEMPRE escribe en la raíz del proyecto.
    # No debe heredar un BIORAG_DMN_ESTADO_PATH mutado por tools on-demand
    # (mcp_server/server.py lo setean por llamada para procesar_nodo_unico).
    env["BIORAG_DMN_ESTADO_PATH"] = os.path.join(PROJECT_ROOT, "estado_hormiga.json")
    
    try:
        if sys.platform == "win32":
            # Windows: proceso detachado sin ventana
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            proc = subprocess.Popen(
                cmd,
                creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=env,
                cwd=PROJECT_ROOT,
            )
        else:
            # Unix: start_new_session=True → setsid() → sobrevive SIGHUP del padre
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=env,
                cwd=PROJECT_ROOT,
            )
        
        logger.info("Daemon spawned (PID %d)", proc.pid)
        
        # Esperar a que el daemon escriba su propio PID file
        # El daemon escribe .hormiguita.pid al arrancar el loop
        for _ in range(10):
            time.sleep(0.5)
            if is_daemon_alive():
                return True
        
        # El daemon no escribió PID — puede que haya fallado
        logger.warning("Daemon spawned pero PID file no apareció en 5s")
        return False
        
    except Exception as e:
        logger.error("Failed to spawn daemon: %s", e)
        return False


# --- Entry point --------------------------------------------------------------

def ensure_daemon_alive(
    intervalo_horas: float | None = None,
    max_nodos: int | None = None,
) -> bool:
    """
    Check + spawn si necesario. Llamar al arrancar el MCP server.
    
    Retorna True si el daemon está vivo (o se spawneó exitosamente).
    """
    if is_daemon_alive():
        pid = _leer_pid()
        logger.info("Daemon ya vivo (PID %s)", pid)
        return True
    
    logger.info("Daemon muerto o ausente — spawning...")
    return spawn_daemon_detached(
        intervalo_horas=intervalo_horas,
        max_nodos=max_nodos,
    )
