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


def is_daemon_enabled() -> bool:
    """Verifica si el daemon en segundo plano está habilitado vía variable de entorno.

    Por defecto está DESACTIVADO (0). Solo se activa si BIORAG_DAEMON_ENABLED=1/true/on.
    """
    val = os.environ.get("BIORAG_DAEMON_ENABLED", "0").strip().lower()
    return val in ("1", "true", "yes", "on")


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
    Usa un lock no bloqueante para evitar que múltiples instancias MCP concurrentes
    intenten spawnear daemons simultáneamente en arranques simultáneos.

    INVARIANTE: Desactivado por defecto. Solo spawnea si BIORAG_DAEMON_ENABLED=1.
    Retorna True si el daemon está vivo (o se spawneó exitosamente).
    """
    if not is_daemon_enabled():
        logger.debug("Daemon deshabilitado por defecto (BIORAG_DAEMON_ENABLED != 1)")
        return False

    if is_daemon_alive():
        pid = _leer_pid()
        logger.info("Daemon ya vivo (PID %s)", pid)
        return True
    
    lock_file = os.path.join(PROJECT_ROOT, ".hormiguita.lock")
    try:
        if sys.platform != "win32":
            import fcntl
            with open(lock_file, "w") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (BlockingIOError, OSError):
                    # Otra instancia ya está en proceso de spawnear el daemon
                    logger.info("Otra instancia MCP está gestionando el spawn del daemon")
                    time.sleep(1.0)
                    return is_daemon_alive()
                
                # Doble chequeo una vez adquirido el lock
                if is_daemon_alive():
                    return True
                
                logger.info("Daemon muerto o ausente — spawning...")
                return spawn_daemon_detached(
                    intervalo_horas=intervalo_horas,
                    max_nodos=max_nodos,
                )
        else:
            return spawn_daemon_detached(
                intervalo_horas=intervalo_horas,
                max_nodos=max_nodos,
            )
    except Exception as e:
        logger.warning("Error en lock de daemon: %s", e)
        if is_daemon_alive():
            return True
        return spawn_daemon_detached(
            intervalo_horas=intervalo_horas,
            max_nodos=max_nodos,
        )


def stop_daemon(timeout: float = 5.0) -> bool:
    """Detiene cualquier instancia activa del daemon de mantenimiento.

    1. Intenta por PID file con SIGTERM (graceful).
    2. Espera hasta `timeout` segundos.
    3. Si no responde, aplica SIGKILL.
    4. Fallback: busca por nombre de proceso si el PID file no existía.
    """
    pid = _leer_pid()
    detenido = False

    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            inicio = time.time()
            while time.time() - inicio < timeout:
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except (OSError, ProcessLookupError):
                    detenido = True
                    break
            if not detenido:
                try:
                    os.kill(pid, signal.SIGKILL)
                    detenido = True
                except (OSError, ProcessLookupError):
                    detenido = True
        except (OSError, ProcessLookupError):
            detenido = True
        _borrar_pid()

    # Fallback cross-process
    if sys.platform != "win32":
        try:
            res = subprocess.run(
                ["pgrep", "-f", "graph_maintenance_daemon.py"],
                capture_output=True, text=True
            )
            my_pid = os.getpid()
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line and line.isdigit():
                    p = int(line)
                    if p != my_pid:
                        try:
                            os.kill(p, signal.SIGTERM)
                            detenido = True
                        except OSError:
                            pass
        except Exception:
            pass

    return detenido
