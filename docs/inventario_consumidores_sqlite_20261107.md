# Inventario inicial de consumidores SQLite — 2026-11-07

## Alcance y cautelas

Este inventario es una lectura estática del checkout `arena/a6f83961-memorybiorag`, más pruebas sobre archivos temporales. **No se abrió, validó, reparó, copió ni cambió el journal de ninguna base de datos de producción; tampoco se inspeccionaron procesos/PID del equipo del usuario.** Los resultados de informes forenses de otras sesiones se mantienen como evidencia reportada, no como observación actual.

Una `SQLiteConnection` o un singleton no equivale a un broker global: la instancia de `memory_service` es local a cada proceso Python. MCP, dashboard, CLI, daemons y herramientas de lectura pueden ser procesos distintos, cada uno con su runtime SQLite efectivo.

## Resolución de la ruta

| Consumidor | Fuente de ruta observada | Observación |
|---|---|---|
| `core.paths.resolve_db_path()` | argumento explícito → `BIORAG_PATH` → `<raíz>/MemoryBioRAG_Data/memory_biorag.db` | Desde T3a canonicaliza archivos (`expanduser`, ruta absoluta desde cwd, `realpath`, `normcase`) sin crear archivos/directorios; conserva `:memory:` y file-URI. Usada por MCP/servicio/dashboard y ahora también por el constructor principal. |
| `biorag.py` (CLI) | `BIORAG_PATH` → `_DEFAULT_DB` en `MemoryBioRAG_Data/memory_biorag.db` | Define su propia constante; una ruta relativa se interpreta respecto al cwd al pasar por el constructor del motor, que la canonicaliza. Crea `SQLiteMemoryBioRAG` y llama `cerrar_sistema()` en ramas de salida. |
| MCP | `core/mcp_server/_shared.py::_get_cerebro()` pasa `BIORAG_PATH` al singleton; fallback a `resolve_db_path()` | `core/memory_service.py` conserva una instancia por proceso y cadena de ruta. El lock protege creación/selección/reset; T2 añade leases a métodos públicos del motor y el reset espera a que terminen.
| Dashboard | `dashboard-neuro-visor/backend/server.py`: `DB_PATH = resolve_db_path()` | Conserva esa ruta al iniciar el proceso; algunos endpoints usan el singleton y muchos abren conexión SQL independiente por solicitud. |
| Daemon de mantenimiento | `graph_maintenance_daemon.py::_get_db_path()`: `BIORAG_PATH` canónica o el default común | Proceso detachado; PID/run-lock/spawn-lock/estado se derivan de la ruta DB (default conserva artifacts legacy; otras rutas usan hash). Fija la ruta al iniciar y el run-lock, no el PID, prueba vida. |
| DMN | `DMNEngine.db_path`, recibido al construir el motor | Hilo dedicado; conexión SQLite separada del singleton principal. |
| Reflexión por CLI | argumento `--db` o default; luego `os.path.abspath()` | `core/dmn_reflexion.py` construye `SQLiteMemoryBioRAG` y cierra al acabar el flujo CLI. |

El inventario de nombres de archivo del checkout incluye artefactos SQLite de código, snapshots y temporales. La mera existencia/tamaño/extensión no demuestra cuál usa el proceso local ni si un `.db` es base activa. La ruta activa debe registrarse desde el proceso consumidor, sin leer datos de producción para inferirla.

## Consumidores, modo y ciclo de vida

| Consumidor/componente | Lectura/escritura | Conexión y vida útil | Estado actual (T1–T3) |
|---|---|---|---|
| `core/memory_store.py::SQLiteMemoryBioRAG` | Lectura y escritura principal, esquema, índices y FTS | DB persistente: conexión/cursor por hilo; `:memory:` conserva una conexión compartida con serialización de operaciones del motor. La fachada entrega proxies DB-API que validan conexiones/cursors retenidos. | Todas las conexiones escritoras pasan por `open_writer`; `cerrar_sistema()` espera a métodos públicos activos. Compara `(st_dev, st_ino)`; en WAL fija `-wal`/`-shm` al observarlos. T3g añade firma/header SQLite y `PRAGMA data_version`; pruebas in-place conservan inode y prueban handles retenidos. Cambios SQLite corroborados se admiten; una sustitución de esquema no corroborada falla cerrado. No se afirma detección de sobrescrituras que preserven todas las señales observadas, mutación durante transacción abierta, handles raw creados fuera de la fachada ni sidecars antes de observarlos. Cache auxiliar: 8 MiB; mmap: 32 MiB. |
| `core/memory_service.py` → MCP/servicio | Operaciones del motor | Singleton por proceso/ruta; no comparte conexión entre procesos. | El reset/cambio de ruta espera a operaciones activas del motor antes de soltar el singleton; no coordina procesos distintos. |
| `core/mcp_server/*` | Consume motor central; algunas herramientas hacen `cerrar_sistema()` en `finally` | En singleton persistente, `cerrar_sistema()` es no-op. | No abre SQLite directamente salvo vía motor/servicio. El estado `last_*` del motor es local al hilo/request; el servidor inicia comprobación/spawn del daemon en hilo background. |
| `dashboard-neuro-visor/backend/server.py` | Lecturas; actualizaciones directas (`DELETE` de TTL, cuarentena y operaciones de endpoints) además del servicio | `get_db()` abre conexiones por request; hay un thread de limpieza horaria y limpiezas al startup. | Las tres aperturas directas del dashboard pasan por `open_writer`. Los endpoints no fueron convertidos a una sesión/transaction manager común. |
| `graph_maintenance_daemon.py` | Escrituras del ciclo de mantenimiento | Proceso detached; crea `SQLiteMemoryBioRAG` por ciclo y lo cierra en `finally`. Sobrevive al MCP padre. | Hereda `BIORAG_PATH`, por tanto puede coexistir con MCP/CLI/dashboard como escritor separado. |
| `core/dmn_engine.py::DMNEngine` | Escrituras de sinapsis/insights | Conexión propia del hilo; se cierra al salir del loop y en caminos de ciclo. | Usa `open_writer`; comparte archivo con el motor principal sin broker. |
| `core/adn_conceptual.py` | Lecturas read-only; reconstrucción nocturna escribe varias tablas | Conexiones independientes para consulta; writer por operación de reindexación. | `open_reader` fija `mode=ro` + `query_only`; writer usa `open_writer`; tags `adn_*` en diagnóstico. La reindexación sigue requiriendo revisar límites transaccionales. |
| `core/feedback_implicito.py` | Inferencia read-only; aplicación de feedback escribe `log_busquedas` | Herramienta ejecutable aparte; las conexiones se cierran al terminar cada fase. | `open_reader`/`open_writer`, tags separados `feedback_inference`/`feedback_apply`. |
| `core/ppmi_hybrid_search.py`, `core/neocortex_teleologico.py` | Lecturas de índices/vectores | Conexiones autónomas cuando reciben ruta; se cierran al terminar/cargar datos. | `open_reader` aplica `mode=ro` + `query_only`; tags por consumidor. |
| Scripts de benchmark/diagnóstico y archivos en `scratch/` | Algunos abren SQLite directamente y algunos usan constantes/env que pueden apuntar a la DB activa | Ejecución manual; no hay lifecycle central probado. | Fuera del writer factory. No correrlos contra datos reales hasta clasificarlos y hacerlos exigir fixture/copia explícita. |

### Daemon de mantenimiento: hallazgo de lifecycle

T3c deriva artifacts del daemon de la ruta canónica: el DB default conserva `.hormiguita.pid`, `.hormiguita.lock` y `estado_hormiga.json`; otras DB usan un prefijo hash distinto. El supervisor comprueba el run-lock retenido además del layout route-specific, de modo que un PID reutilizado sin lock no prueba vida. Spawn-lock y run-lock son distintos. Si un daemon legacy ambiguo mantiene el lock global, otra ruta falla cerrado y requiere revisión/cierre ordenado del operador; no se mata ningún proceso ni se borran lock files.

## Escritores unificados en T1

- `core/memory_store.py` (motor principal)
- `core/dmn_engine.py` (DMN)
- `dashboard-neuro-visor/backend/server.py` (limpiezas y conexiones por endpoint)
- `core/adn_conceptual.py` (reindexación)
- `core/feedback_implicito.py` (aplicación de feedback)

Los lectores de aplicación identificados usan `open_reader`: URI de ruta construida de forma segura, `mode=ro` y `PRAGMA query_only=ON`. Los scripts manuales y cualquier cliente externo que abra el archivo por fuera de estas interfaces todavía pueden omitir la política.

### Diagnóstico T3e

Cada apertura centralizada writer/reader registra a nivel DEBUG consumidor, rol, versión SQLite enlazada, `sqlite_source_id()`, journal efectivo, busy timeout y `route_id` derivado de la ruta canónica. El log no incluye ruta literal ni contenido de la DB. `route_id` es un SHA-256 truncado para correlación, no se presenta como anonimización criptográfica: quien conoce rutas candidatas puede probarlas. Los consumidores instrumentados son `memory_store`, `dmn_engine`, `dashboard`, `feedback_inference`, `feedback_apply`, `adn_clustering_read`, `adn_index_read`, `adn_reindex`, `ppmi_hybrid_search`, `neocortex_token_index` y `neocortex_results`. Aperturas manuales, scripts y clientes externos no quedan cubiertos.

`core.sqlite_runtime` consulta la versión SQLite enlazada **en el proceso que abre el writer**. Clasifica como vulnerable a WAL-reset las versiones SQLite anteriores a los arreglos publicados (3.51.3, backport 3.50.7, backport 3.44.6). Para una DB nueva, un runtime vulnerable comienza en DELETE y un runtime corregido puede empezar WAL. Una DB existente conserva su journal; vulnerable + WAL rechaza la escritura sin cambiar el archivo por defecto. La transición de una existente solo está disponible con opt-in explícito en la función y lock exclusivo SQLite. `docs/sqlite_journal_migration_runbook.md` explica la vía explícita probada primero en copias: `open_writer(..., allow_existing_journal_transition=True)`, verificación del journal y `integrity_check`, fallo cerrado si no hay exclusividad. Aún no hay CLI de operador; no se migró ninguna DB de usuario.

## Versiones: evidencia por entorno

- Sandbox de esta sesión: Python 3.11.2, SQLite 3.40.1, medido localmente aquí.
- Informes forenses compartidos desde otra rama dicen que dos ejecutables de la máquina del usuario reportaron SQLite 3.45.1/source ID `e876e51a...alt1`; todavía no demuestra qué runtime usó cada daemon/proceso en el incidente.
- No se comprobó ni se pidió abrir la DB activa ni consultar los procesos locales del usuario.

## Hallazgo de seguridad web que requiere revisión separada

La inspección estática de `dashboard-neuro-visor/backend/server.py` muestra `uvicorn.run(..., host="0.0.0.0")`, CORS con `allow_origins=["*"]`, endpoints que leen y escriben la DB directamente, y no se encontró autenticación en ese módulo. CORS wildcard por sí solo no otorga acceso a la DB, pero la combinación de escucha en todas las interfaces y rutas sin auth visible merece una revisión de exposición/red y autenticación antes de despliegue empresarial. No se modificó aquí porque la tarea T1 cubre el writer SQLite; queda como hallazgo OWASP A01/A05 para una tarea autorizada y probada por separado. SQL parametrizado se usa en los endpoints inspeccionados, pero hace falta una auditoría sistemática de SQL dinámico y de límites de entrada.

## Próximos huecos del mapa

1. [x] Añadir instrumentación para los consumidores de aplicación identificados: runtime/source ID, journal, timeout, rol y route_id canónico correlacionable, sin ruta literal ni contenido de recuerdos.
2. Terminar el mapa de transacciones/commit y excepciones para MCP, dashboard, daemon, DMN y reindexación ADN.
3. Auditar límites transaccionales multi-paso y operaciones module-level que no pasan por métodos públicos del motor; T2 cubre conexiones por hilo, metadatos de request y espera de cierre/reset, pero no coordina procesos distintos.
4. Completar T3: ejecutar de nuevo matriz Actions en Windows/macOS y validar sidecar/run-lock por filesystem; el run `42526947166` confirmó `invalid path` por seis filenames con `:` prohibidos en Windows, ya renombrados en la rama. Tests temporales cubren handles retenidos y copia in-place con el mismo inode, con límites de coordinación documentados.
5. Clasificar scripts manuales y evaluar endpoints/dashboard en una revisión de seguridad separada.
