# Plan Maestro de Hardening: `biorag update` y Concurrencia Robusta

**Fecha de creación:** 2026-11-23  
**Rama:** `arena/6459e2d0-memorybiorag`  
**Objetivo:** `biorag update` debe ser amigable, determinista y NO frágil. Ningún usuario técnico o no técnico debe quedar con una instalación rota o bloqueada por archivos de lock huérfanos, procesos ociosos o concurrencia no coordinada. Funciona de manera idéntica en Linux, macOS y Windows.

---

## 1. Reglas e Invariantes del Proceso

1. **Un cambio por commit:** Cada fase o refactorización crítica se aísla en su propio commit con pruebas antes y después.
2. **Línea base y regresión cero:** La suite completa debe mantenerse verde en cada paso.
3. **Todo dato debe ser medido y comprobado:** Lo no verificado se etiqueta explícitamente como `[NO VERIFICADO]`.
4. **Respaldo atómico:** Jamás tocar código, dependencias o esquema sin respaldo SQLite verificado por suma criptográfica SHA-256 y ensayo de restauración en temporal.
5. **Cero limpieza manual de locks:** No depender de archivos huérfanos creados con `O_EXCL`. La exclusión y vivacidad se delega a locks del sistema operativo (`fcntl.flock` en POSIX, `LockFileEx` en Windows).
6. **No matar procesos indiscriminadamente:** Priorizar desalojo ordenado y liberación de leases en procesos ociosos.
7. **Documentación viva:** Este archivo es la única fuente de verdad técnica y se actualiza al cierre de cada fase.

---

## 2. Línea Base de Pruebas (Medición Empírica)

- **Comando:** `pytest tests/ -q`
- **Fecha:** 2026-11-23 23:30 UTC
- **Resultado:** **1070 passed, 84 subtests passed in 972.77s (0:16:12)**
- **Estado de salida:** `0` (verde absoluto).

---

## 3. Mediciones Empíricas Previas (Hardware: ASUS ROG Strix G731GT / Linux 6.8 / SSD NVMe)

| Medición | Comando / Método | Resultado | Fecha |
|---|---|---|---|
| Latencia lectura directa tabla `data` | `SELECT valor FROM data WHERE clave = 'biorag_applied_update_id'` | **1.11 ms** | 2026-11-23 |
| Latencia `connect` + `close` SQLite crudo | `sqlite3.connect('/home/dennys/.biorag/memory_biorag.db')` | **0.131 ms** | 2026-11-23 |
| Latencia lectura `PRAGMA user_version` | `c.execute('PRAGMA user_version;').fetchone()[0]` | **0.324 ms** | 2026-11-23 |
| Reconstrucción completa `SQLiteMemoryBioRAG` | Instanciación fría sobre DB de 135 MB (`memory_biorag.db`) | **11,649.57 ms (~11.6 s)** | 2026-11-23 |
| Import puro `SQLiteMemoryBioRAG` (Claude env) | `import SQLiteMemoryBioRAG` en entorno de testing externo | **14.29 s** | 2026-11-23 |

### Puntos no verificados hasta el momento:
- `[NO VERIFICADO]` Duración total de `create_backup` con escritor concurrente activo en la BD de 135 MB.
- `[NO VERIFICADO]` Tiempo exacto de recarga en background del servidor FastMCP ante cambio de `user_version`.
- `[NO VERIFICADO EN WINDOWS NATIVO]` La suite de pruebas de Windows (`test_database_access_windows.py`) corre bajo simulación/mocking de Win32 API (`ctypes.WinDLL` y `msvcrt`); requiere verificación en runner Windows real.

> **Nota sobre latencia de `PRAGMA user_version` (0.324 ms):** Medido el 2026-11-23 en la ASUS ROG Strix G731GT con Python 3.12 sobre la base de datos real de 135 MB (`/home/dennys/.biorag/memory_biorag.db`) mediante `sqlite3.connect` + `c.execute('PRAGMA user_version;').fetchone()[0]` + `c.close()`. En conexiones ya abiertas y bases de datos pequeñas en memoria, la latencia es típicamente de ~0.002 a 0.02 ms. Ambas magnitudes confirman que la comprobación es prácticamente despreciable en costo.

---

## 3.1. Estado de Módulos Preexistentes y Dependencias (`core/process_inspection.py`)

1. **Dependencia declarada `psutil` (v7.2.2):**
   - La restricción informal de "evitar dependencias externas como psutil" queda corregida: `psutil==7.2.2` **ya es una dependencia formal declarada** en `pyproject.toml` y requerida por el core.
2. **Qué hace hoy `core/process_inspection.py`:**
   - Realiza un inventario ordenado y seguro de procesos que tienen abierta la BD SQLite o sus archivos asociados (`-wal`, `-shm`, `.maintenance.lock`).
   - Clasifica procesos por entry point exacto (`daemon`, `worker`, `cli`, `mcp`).
   - Política `fail-closed`: ante holders desconocidos o procesos sin acceso (`AccessDenied`), rechaza (`UNKNOWN_DATABASE_CONSUMER` / `PROCESS_SCAN_INCOMPLETE`).
   - `stop_managed_daemon(root)`: detiene de forma ordenada únicamente el daemon registrado en el PID file (`graph_maintenance_daemon.py`).
   - `stop_known_database_processes(database)`: función capaz de detener procesos MCP/worker verificados, pero **actualmente NO se llama automáticamente sin autorización** en el flujo normal de `exclusive_update`.
3. **Decisión de Reutilización Arquitectónica:**
   - **No duplicar:** La Fase de Diagnóstico no reinventará listados de procesos con comandos `lsof` o `netstat`. Reutilizará directamente `inspect_database_processes(database)` de `core/process_inspection.py` para reportar con precisión humana los PIDs que retienen la base de datos si el lock exclusivo expira por timeout.
   - **Cero matanza indiscriminada:** Se mantiene la política fundamental: `biorag update` **no mata procesos MCP por defecto**. En su lugar, la Fase F2 (Idle Lease Release) permitirá que los procesos MCP suelten la conexión SQLite tras unos segundos de inactividad de forma cooperativa. La detención forzada sólo se utilizaría si existe una orden/flag explícito del usuario.

---

## 4. Fases de Ejecución

### Fase F0: Sustitución de Lock Frágil en `core/updater.py` [COMPLETADO - AUDITADO Y CORREGIDO]
- **Problema actual:** `update_lock()` en `core/updater.py` usaba `os.open(..., os.O_CREAT | os.O_EXCL | os.O_RDWR)`. Si el updater moría con `SIGKILL`, el archivo quedaba en disco y bloqueaba cualquier actualización posterior hasta que un humano lo borrara a mano.
- **Solución técnica implementada:**
  - Migrado `update_lock()` para utilizar el backend de lock de SO probado en `core/database_access.py` (`fcntl.flock` con `LOCK_EX | LOCK_NB` en POSIX, `_windows_lock(..., exclusive=True)` en Windows).
  - Al caer el proceso por cualquier motivo (incluyendo `kill -9`), el kernel libera el descriptor y el lock automáticamente.
  - **Corrección de auditoría (Invariante de inodo):** Se eliminó `path.unlink()` del bloque `finally`. El archivo permanece en `.git/` para preservar el inodo y garantizar la exclusión mutua estricta. Si un proceso B es rechazado, jamás borra el inodo que mantiene el proceso A.
  - Implementado test de simulación de tres procesos (`test_lock_mutual_exclusion_three_processes`): A mantiene lock; B intenta y es rechazado; se verifica que el archivo no fue borrado; C intenta y es rechazado; A es terminado con `SIGKILL`; el siguiente proceso adquiere el lock inmediatamente sin intervención manual.
  - Implementado test de contienda simultánea (`test_simultaneous_attempts_exactly_one_wins`): dos procesos lanzados en paralelo; exactamente uno obtiene el lock y el otro es rechazado.
  - Implementado test de contención Windows (`test_updater_lock_windows_flow`) verificando que el camino de rechazo cierra el descriptor sin borrar el archivo.
- **Resultado empírico:**
  - `pytest tests/test_updater_lifecycle.py tests/test_database_access_windows.py`: **37 passed, 4 subtests passed in 14.70s**.
- **Criterio de aceptación:**
  - Exclusión mutua garantizada (tres procesos).
  - No queda lock huérfano tras `kill -9`.
  - Inodo preservado: el lock no se borra en rechazo ni en éxito.
  - Pruebas existentes y nuevas pasan al 100%.

---

### Fase F1: Versión de Esquema, Reconciliación de Señales y Respaldo Verificado [EN PROGRESO]

#### 1. Reconciliación de las Tres Señales de Estado de BD:
1. **`core/schema_status.py` (Estructural):** Inspección de solo lectura (`missing_objects`, `missing_columns`, `integrity_check`, `foreign_key_check`) derivada dinámicamente de `expected_core_schema()` en memoria (sin inventarios manuales duplicados). Detecta `schema_drift` y objetos faltantes.
2. **`biorag_applied_update_id` (Git Commit ID):** Marcador puntual en la tabla `data` que registra el hash exacto del commit que completó y verificó el ciclo de vida (`lifecycle`). Identifica sincronización entre código instalado y la BD.
3. **`PRAGMA user_version` (Entero Monotónico de Esquema):**
   - **Semántica de `user_version = 0`:** Representa una base de datos preexistente o "legada sin sello". Sigue funcionando con total normalidad; solo se sella al completar una migración verificada.
   - **Detección de BD más nueva que el código:** Comprobación estricta en el camino común de apertura (`SQLiteMemoryBioRAG` y `core/migrate.py`): si `user_version > CURRENT_SCHEMA_VERSION`, se aborta con error claro e informativo (`SCHEMA_NEWER_THAN_CODE: database requires a newer BioRAG release`). Esto protege a las versiones nuevas contra escrituras incompatibles.
   - **Detección O(1) de recarga en reposo para MCP (Fase F2):** Consulta ultrarrápida para verificar si el esquema cambió durante la inactividad.

#### 2. Realidad de la "Migración Atómica" vs Commits Internos:
- **Clarificación de métricas:**
  - **Llamadas a `.commit()` invocadas en código:** 15 en `SQLiteMemoryBioRAG.__init__` + 1 en `ensure_contextual_schema` + 1 en `_initialize` = 17 llamadas.
  - **Sentencias `COMMIT` reales ejecutadas por SQLite (medición independiente):** 6 sentencias reales en BD nueva (las llamadas sin transacción abierta son no-op para el motor).
  - **Conclusión unánime:** En cualquier caso, no cabe una transacción única `BEGIN IMMEDIATE ... COMMIT` envolviendo toda la inicialización sin reescribir el bootstrap.
- **Doble ruta de recuperación ante fallos:**
  - **Ruta A (`biorag update` / `updater.py`):** Ya cuenta con rollback y restauración automática completa (`restore_database_backup`).
  - **Ruta B (`python -m core.migrate` suelto):** Actualmente `finish_backup(success=False)` sólo marca metadatos y no sobreescribe la BD. Se implementa en `core/migrate.py` la opción (a) acordada: si `migrate()` falla y es dueño del respaldo (`owns_backup`), **ejecuta restauración automática del respaldo verificado**, de modo que la BD viva nunca quede rota a mitad de camino, y si la restauración fallara, imprime la ruta del respaldo y el comando de recuperación manual.

- **Contrato de F1:**
  - Definir `CURRENT_SCHEMA_VERSION = 1` en `core/schema_status.py`.
  - En `core/migrate.py` y `SQLiteMemoryBioRAG.__init__`, verificar si `user_version > CURRENT_SCHEMA_VERSION` (rechazar con `SCHEMA_NEWER_THAN_CODE`).
  - Al completar la verificación del esquema en `_migrate()`:
    - Ejecutar con `isolation_level=None` un `BEGIN IMMEDIATE` para actualizar `PRAGMA user_version = CURRENT_SCHEMA_VERSION` y verificar integridad de cierre.
  - Si `_migrate()` falla siendo dueño del backup: restaurar automáticamente desde el backup temporal verificado.
  - Reportar en `inspect_database` el valor de `user_version` y alertar si la BD es más nueva que el código.

- **Criterio de aceptación:**
  - Prueba de BD con `user_version > CURRENT_SCHEMA_VERSION` rechaza con `SCHEMA_NEWER_THAN_CODE` tanto en `migrate` como en apertura normal.
  - Prueba de BD con `user_version = 0` sigue operando normalmente.
  - Prueba de fallo simulado a mitad de `migrate()` restaura automáticamente la BD previa.
  - Prueba de contención externa concurrente.

- **Resultado empírico medido:**
  - `pytest tests/test_schema_version_f1.py tests/test_schema_status.py tests/test_contextual_schema_lifecycle.py tests/test_updater_lifecycle.py -q`: **61 passed, 8 subtests passed in 15.77s**.
  - Estado F1: **COMPLETADO**.

---

### Fase F2: Desalojo y Gestión de Inactividad (F3 en discusión original)
- **Problema actual:** Clientes MCP (como OpenCode, Claude Desktop, Antigravity) mantienen abiertas conexiones persistentes a SQLite con leases compartidos, bloqueando el lock exclusivo que necesita `biorag update`. Reinstanciar la memoria en cada request es inviable (cuesta ~11.6 s).
- **Solución técnica:**
  - El proceso MCP retiene los módulos y objetos cargados en memoria RAM.
  - Se libera la conexión SQLite (`conn.close()`) y el lease compartido tras $N$ segundos de inactividad configurable (idle timeout).
  - **Prioridad del escritor (Anti-inanición):** Marca de "mantenimiento pendiente". Las nuevas solicitudes entrantes esperan brevemente o devuelven aviso estructurado de espera mientras los requests en vuelo drenan.
  - Al reanudar desde reposo: se lee `PRAGMA user_version` (0.32 ms). Si coincide, se reabre la conexión inmediatamente. Si difiere, se recarga en segundo plano y se devuelve `"BioRAG is reloading after update, retry in a few seconds"`.
- **Criterio de aceptación:**
  - `biorag update` puede adquirir lock exclusivo sin matar procesos MCP que estén ociosos.
  - Ningún timeout de cliente MCP provocado por recarga bloqueante síncrona de 12 s.

---

### Fase F3: Registro de Diagnóstico de Leases (F1 en discusión original)
- **Problema actual:** Si `biorag update` agota el tiempo de espera para obtener exclusividad, el usuario no sabe qué proceso exacto está impidiendo la actualización.
- **Solución técnica:**
  - Cada cliente registra un archivo con lock exclusivo del SO en `<db>.leases/<pid>.json` conteniendo metadata de diagnóstico (PID, comando/rol, timestamp).
  - Si un proceso muere, su lock de SO se libera y el updater lo ignora.
  - Si el timeout expira, `biorag update` reporta con precisión humana qué procesos siguen vivos y activos.
- **Criterio de aceptación:**
  - Salida humana clara indicando PID y comando si hay bloqueo activo.
