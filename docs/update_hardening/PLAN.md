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

---

## 4. Fases de Ejecución

### Fase F0: Sustitución de Lock Frágil en `core/updater.py` [COMPLETADO]
- **Problema actual:** `update_lock()` en `core/updater.py` usaba `os.open(..., os.O_CREAT | os.O_EXCL | os.O_RDWR)`. Si el updater moría con `SIGKILL`, el archivo quedaba en disco y bloqueaba cualquier actualización posterior hasta que un humano lo borrara a mano.
- **Solución técnica implementada:**
  - Migrado `update_lock()` para utilizar el backend de lock de SO probado en `core/database_access.py` (`fcntl.flock` con `LOCK_EX | LOCK_NB` en POSIX, `_windows_lock(..., exclusive=True)` en Windows).
  - Al caer el proceso por cualquier motivo (incluyendo `kill -9`), el kernel libera el descriptor y el lock automáticamente.
  - Implementado test de simulación de caída forzada (`test_lock_released_on_process_crash`): un subproceso adquiere el lock, se verifica contención concurrente (`UPDATE_LOCKED`), se mata el proceso abruptamente con `proc.kill()` y se verifica que el siguiente `update_lock` lo adquiere sin intervención manual.
  - Implementado test de contención Windows (`test_updater_lock_windows_flow`) verificando compatibilidad multiplataforma.
- **Resultado empírico:**
  - `pytest tests/test_updater_lifecycle.py tests/test_database_access_windows.py`: **35 passed in 7.91s**.
- **Criterio de aceptación:**
  - No queda lock huérfano tras `kill -9`.
  - Pruebas existentes y nuevas pasan.
  - Listo para commit exclusivo.

---

### Fase F1: Versión de Esquema Independiente y Migración Atómica
- **Problema actual:** La versión del esquema está acoplada a la versión de lanzamiento de BioRAG o dispersa en marcadores de texto. Si falla una migración a mitad de camino, la base de datos puede quedar en estado inconsistente.
- **Solución técnica:**
  - Implementar un entero monotónico independiente mediante `PRAGMA user_version`.
  - Proteger toda migración con `BEGIN IMMEDIATE` + `busy_timeout` para evitar colisiones con lectores y escritores concurrentes.
  - Si un proceso externo (ej. CLI `sqlite3`) retiene un lock exclusivo, la migración falla limpiamente sin corromper datos y emite diagnóstico claro.
- **Criterio de aceptación:**
  - `user_version` se incrementa únicamente si la transacción de migración completa con éxito.
  - Rollback garantizado si se simula error a mitad de migración.

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
