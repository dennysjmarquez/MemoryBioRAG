#!/usr/bin/env python3
"""
BioRAG Graph Maintenance Daemon — La Hormiguita como servicio
=============================================================
Demonio que ejecuta ciclos de mantenimiento del grafo de forma periódica.
Usa la hormiguita (dmn_reflexion.py) para evaluar y podar sinapsis
espurias, manteniendo la salud del grafo sin intervención manual.

Características:
- Lock file para evitar duplicación
- Intervalo configurable (default 6 horas)
- Resume automático (usa estado_hormiga.json)
- Quota awareness (respeta límites de API)
- Logging a archivo y consola
- Modo --once para ejecución single-shot

Uso:
    python3 graph_maintenance_daemon.py              # Daemon continuo
    python3 graph_maintenance_daemon.py --once       # Un solo ciclo
    python3 graph_maintenance_daemon.py --status     # Ver estado actual
    python3 graph_maintenance_daemon.py --reset      # Resetear estado

Variables de entorno:
    BIORAG_DAEMON_INTERVALO_HORAS  — Intervalo entre ciclos (default: 6)
    BIORAG_DAEMON_MAX_NODOS        — Nodos por ciclo (default: 10)
    BIORAG_DAEMON_LOCK_PATH        — Ruta del lock file (default: .hormiguita.lock)
    BIORAG_DAEMON_LOG_PATH         — Ruta del log (default: logs/hormiguita.log)
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import fcntl
from datetime import datetime

# Asegurar que el path incluya el directorio actual
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from core.dmn_reflexion import ejecutar_ciclo_reflexivo, _cargar_estado, _guardar_estado

# --- Configuración -----------------------------------------------------------

INTERVALO_HORAS = float(os.environ.get("BIORAG_DAEMON_INTERVALO_HORAS", "1"))
MAX_NODOS_POR_CICLO = int(os.environ.get("BIORAG_DAEMON_MAX_NODOS", "10"))
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOCK_DEFAULT = os.path.join(_PROJECT_ROOT, ".hormiguita.lock")
_PID_DEFAULT = os.path.join(_PROJECT_ROOT, ".hormiguita.pid")
_LOG_DEFAULT = os.path.join(_PROJECT_ROOT, "logs")
LOCK_PATH = os.environ.get("BIORAG_DAEMON_LOCK_PATH", _LOCK_DEFAULT)
PID_PATH = os.environ.get("BIORAG_DAEMON_PID_PATH", _PID_DEFAULT)
LOG_DIR = os.environ.get("BIORAG_DAEMON_LOG_PATH", _LOG_DEFAULT)

# --- Logging -----------------------------------------------------------------

def configurar_logging(log_dir):
    """Configura logging a archivo y consola."""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"hormiguita_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("Hormiguita.Daemon")


# --- Lock file ---------------------------------------------------------------

class DaemonLock:
    """Lock file para evitar que el daemon se ejecute múltiples veces."""
    
    def __init__(self, lock_path):
        self.lock_path = lock_path
        self.lock_file = None
    
    def adquirir(self):
        """Adquiere el lock. Retorna True si éxito, False si ya está tomado."""
        try:
            self.lock_file = open(self.lock_path, "w")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            return True
        except (IOError, OSError):
            return False
    
    def liberar(self):
        """Libera el lock."""
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()
                os.remove(self.lock_path)
            except (IOError, OSError):
                pass


# --- PID file ----------------------------------------------------------------

def _escribir_pid():
    """Escribe el PID actual al archivo PID."""
    try:
        with open(PID_PATH, "w") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        logging.getLogger("Hormiguita.Daemon").warning(
            "No se pudo escribir PID file: %s", e
        )


def _borrar_pid():
    """Borra el archivo PID al salir."""
    try:
        os.remove(PID_PATH)
    except FileNotFoundError:
        pass


# --- Daemon ------------------------------------------------------------------

class GraphMaintenanceDaemon:
    """Daemon principal de mantenimiento del grafo."""
    
    def __init__(self, logger, max_nodos=MAX_NODOS_POR_CICLO, 
                 intervalo_horas=INTERVALO_HORAS):
        self.logger = logger
        self.max_nodos = max_nodos
        self.intervalo_horas = intervalo_horas
        self.running = True
        self._db_path = None
        
        # Configurar signal handlers para graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Maneja señales de shutdown."""
        self.logger.info(f"[Daemon] Señal {signum} recibida, shutting down gracefully...")
        self.running = False
        _borrar_pid()
    
    def _get_db_path(self):
        """Obtiene la ruta de la base de datos."""
        if self._db_path:
            return self._db_path
        default = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "MemoryBioRAG_Data", "memory_biorag.db"
        )
        self._db_path = os.environ.get("BIORAG_PATH") or default
        return self._db_path
    
    def ejecutar_ciclo(self):
        """Ejecuta un ciclo de mantenimiento del grafo."""
        db_path = self._get_db_path()
        
        if not os.path.exists(db_path):
            self.logger.error(f"[Daemon] Base de datos no encontrada: {db_path}")
            return {"resultado": "error", "motivo": "db_no_encontrada"}
        
        cerebro = SQLiteMemoryBioRAG(db_path=db_path)
        
        try:
            self.logger.info("=" * 60)
            self.logger.info("[Daemon] Iniciando ciclo de mantenimiento del grafo")
            self.logger.info("=" * 60)
            
            # Verificar estado previo
            estado = _cargar_estado()
            visitados = len(estado.get("visitados_total", []))
            frontier = len(estado.get("frontier", []))
            ciclos = estado.get("ciclos_completados", 0)
            
            self.logger.info(
                f"[Daemon] Estado previo: {visitados} visitados, "
                f"{frontier} en frontier, {ciclos} ciclos completados"
            )
            
            # Ejecutar ciclo
            resultado = ejecutar_ciclo_reflexivo(cerebro, max_nodos=self.max_nodos)
            
            # Log resultado
            if resultado.get("resultado") == "quota_agotada":
                retry_s = resultado.get("retry_after_seconds", 0)
                retry_h = retry_s / 3600 if retry_s > 0 else self.intervalo_horas
                self.logger.warning(
                    f"[Daemon] Quota agotada: {resultado.get('motivo', 'unknown')}. "
                    f"Próximo intento en {retry_h:.1f}h ({retry_s}s)."
                )
            else:
                self.logger.info(
                    f"[Daemon] Ciclo completado: "
                    f"{resultado.get('nodos_procesados', 0)} nodos procesados, "
                    f"{resultado.get('eliminados_total', 0)} eliminados, "
                    f"{resultado.get('prefiltrados', 0)} pre-filtrados, "
                    f"frontier: {resultado.get('frontier_restante', 0)}"
                )
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"[Daemon] Error en ciclo: {e}", exc_info=True)
            return {"resultado": "error", "motivo": str(e)}
        finally:
            cerebro.cerrar_sistema()
    
    def ejecutar_once(self):
        """Ejecuta un solo ciclo y retorna."""
        self.logger.info("[Daemon] Modo --once: ejecutando un solo ciclo")
        resultado = self.ejecutar_ciclo()
        self.logger.info(f"[Daemon] Resultado: {json.dumps(resultado, indent=2, default=str)}")
        return resultado
    
    def ver_estado(self):
        """Muestra el estado actual de la hormiguita."""
        estado = _cargar_estado()
        
        print("=" * 60)
        print("🦟 ESTADO DE LA HORMIGUITA")
        print("=" * 60)
        print(f"Ciclos completados: {estado.get('ciclos_completados', 0)}")
        print(f"Nodo actual: {estado.get('nodo_actual', 'Ninguno')}")
        print(f"Fase actual: {estado.get('fase_actual', 'N/A')}")
        print(f"Visitados hoy: {len(estado.get('visitados_hoy', []))}")
        print(f"Visitados total: {len(estado.get('visitados_total', []))}")
        print(f"Frontier pendiente: {len(estado.get('frontier', []))}")
        print(f"Tokens gastados hoy: {estado.get('tokens_gastados_hoy', 0)}")
        
        if estado.get("frontier"):
            print(f"\nFrontier (primeros 10):")
            for i, nodo in enumerate(estado["frontier"][:10]):
                print(f"  {i+1}. {nodo}")
        
        if estado.get("historial"):
            print(f"\nÚltimos 5 ciclos:")
            for registro in estado["historial"][-5:]:
                ts = datetime.fromtimestamp(registro.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
                resultado = registro.get("resultado", "N/A")
                print(f"  [{ts}] {resultado}")
        
        print("=" * 60)
    
    def reset_estado(self):
        """Resetea el estado de la hormiguita."""
        estado = {
            "frontier": [],
            "visitados_hoy": [],
            "visitados_total": [],
            "fase_actual": "urgente",
            "ciclos_completados": 0,
            "historial": [],
            "tokens_gastados_hoy": 0,
            "nodo_actual": None,
        }
        _guardar_estado(estado)
        self.logger.info("[Daemon] Estado reseteado")
        print("Estado reseteado correctamente.")
    
    def ejecutar_daemon(self):
        """Ejecuta el daemon en modo continuo."""
        import atexit
        
        # Escribir PID file al arrancar el loop
        _escribir_pid()
        atexit.register(_borrar_pid)
        
        self.logger.info(
            f"[Daemon] Iniciando daemon (PID: {os.getpid()}, "
            f"intervalo: {self.intervalo_horas}h, "
            f"max_nodos: {self.max_nodos})"
        )
        
        while self.running:
            # Ejecutar ciclo
            resultado = self.ejecutar_ciclo()
            
            if not self.running:
                break
            
            # Modo "hasta morir" (intervalo=0): sin sleep entre ciclos,
            # retry cuando quota se agota, esperar 2 días cuando grafo completo
            if self.intervalo_horas == 0:
                if resultado.get("resultado") == "quota_agotada":
                    retry_seconds = resultado.get("retry_after_seconds", 0)
                    if retry_seconds > 0:
                        espera_segundos = retry_seconds
                        horas = retry_seconds / 3600
                        self.logger.info(
                            f"[Daemon] Quota agotada. Reintentando en {horas:.1f}h "
                            f"({retry_seconds}s) — cuando renueve la primera key."
                        )
                    else:
                        retry_min = int(os.environ.get("BIORAG_DAEMON_QUOTA_RETRY_MINUTES", "30"))
                        espera_segundos = retry_min * 60
                        self.logger.info(
                            f"[Daemon] Quota agotada. Reintentando en {retry_min} min..."
                        )
                elif resultado.get("nodos_procesados", 0) == 0 and resultado.get("frontier_restante", 0) == 0:
                    # Grafo completo: todos los nodos visitados, frontier vacía
                    dias_espera = int(os.environ.get("BIORAG_DAEMON_GRAFO_COMPLETO_ESPERA_DIAS", "2"))
                    espera_segundos = dias_espera * 86400
                    self.logger.info(
                        f"[Daemon] Grafo completo (0 nodos, 0 frontier). "
                        f"Esperando {dias_espera} días antes de reintentar..."
                    )
                else:
                    # Ciclo OK con trabajo → continuar inmediatamente sin esperar
                    continue
            else:
                # Modo normal: esperar intervalo entre ciclos
                if resultado.get("resultado") == "quota_agotada":
                    espera_segundos = min(3600, self.intervalo_horas * 3600)
                    self.logger.info(
                        f"[Daemon] Esperando {espera_segundos/3600:.1f}h (quota agotada)"
                    )
                else:
                    espera_segundos = self.intervalo_horas * 3600
                    self.logger.info(
                        f"[Daemon] Esperando {self.intervalo_horas}h para próximo ciclo"
                    )
            
            # Espera interruptible
            inicio_espera = time.time()
            while self.running and (time.time() - inicio_espera) < espera_segundos:
                time.sleep(1)  # Check cada segundo para graceful shutdown
        
        self.logger.info("[Daemon] Daemon detenido")


# --- CLI ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="BioRAG Graph Maintenance Daemon — La Hormiguita como servicio"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Ejecutar un solo ciclo y salir"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Ver estado actual de la hormiguita"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Resetear estado de la hormiguita"
    )
    parser.add_argument(
        "--max-nodos", type=int, default=MAX_NODOS_POR_CICLO,
        help=f"Máximo de nodos por ciclo (default: {MAX_NODOS_POR_CICLO})"
    )
    parser.add_argument(
        "--intervalo", type=float, default=INTERVALO_HORAS,
        help=f"Intervalo entre ciclos en horas (default: {INTERVALO_HORAS})"
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    logger = configurar_logging(LOG_DIR)
    
    # Crear daemon
    daemon = GraphMaintenanceDaemon(
        logger=logger,
        max_nodos=args.max_nodos,
        intervalo_horas=args.intervalo,
    )
    
    # Modo status
    if args.status:
        daemon.ver_estado()
        return
    
    # Modo reset
    if args.reset:
        daemon.reset_estado()
        return
    
    # Adquirir lock
    lock = DaemonLock(LOCK_PATH)
    if not lock.adquirir():
        logger.error("[Daemon] Ya hay una instancia corriendo (lock file presente)")
        print("ERROR: Ya hay una instancia del daemon corriendo.")
        print(f"Si estás seguro de que no, elimina: {LOCK_PATH}")
        sys.exit(1)
    
    try:
        if args.once:
            daemon.ejecutar_once()
        else:
            daemon.ejecutar_daemon()
    finally:
        lock.liberar()
        _borrar_pid()


if __name__ == "__main__":
    main()
