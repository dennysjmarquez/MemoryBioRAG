# Plan técnico — Spec 008

## Estado del diseño

La ruta preferida es conservar SQLite y no imponer un servidor externo. El trabajo se separa en cambios pequeños y reversibles; cada tarea usa únicamente bases temporales. La evidencia previa reporta un runtime 3.45.1 para dos ejecutables de la máquina del usuario, pero cada proceso debe medirse por separado. El sandbox actual usa SQLite 3.40.1, que tampoco debe extrapolarse al equipo local.

## Etapas

1. **Runtime y política de journal**
   - Crear un módulo central que consulte `sqlite3.sqlite_version_info` del proceso que abre la conexión.
   - Aplicar la política oficial del WAL-reset bug: runtime vulnerable no continúa escribiendo en WAL. Una base existente nunca cambia de journal automáticamente; solo un opt-in explícito puede intentar cambiar a rollback journal y SQLite debe confirmar exclusividad. Ante `BUSY`/`LOCKED`, fallar cerrado con diagnóstico y sin borrar/recrear sidecars.
   - Abrir conexiones escritoras con un `busy_timeout` acotado y sin atrapar silenciosamente errores de PRAGMA.
   - No cambiar el journal de una DB existente durante el arranque. En runtime vulnerable + DB WAL, rechazar escritura sin mutación; una transición explícita se permite solo con opt-in y lock exclusivo SQLite. En runtime corregido, una DB existente conserva su journal; WAL se elige al crear una DB nueva.
   - Conectar el almacén central, DMN, dashboard y otros escritores directos identificados a esta política. Lectores read-only no intentan cambiar el journal.

2. **Coordinación dentro del proceso**
   - Para DB persistente, cada hilo de `SQLiteMemoryBioRAG` obtiene conexión y cursor propios; `:memory:` conserva una conexión compartida y serializa las operaciones del motor para no cambiar su semántica.
   - El cierre/reset espera a que terminen las operaciones públicas activas. El estado de respuesta `last_*` es por hilo/request para evitar que búsquedas simultáneas mezclen metadatos.
   - La coordinación de archivos persistentes no mantiene un lock de instancia durante cómputo: SQLite arbitra las escrituras entre conexiones con el `busy_timeout` configurado. Las conexiones auxiliares limitan su cache_size a 8 MiB y mmap_size a 32 MiB; el hilo que crea el motor conserva 64 MiB y 256 MiB.
   - Medir latencia antes/después en fixtures. La medición T2 pareada fue 10.000 `SELECT 1` con acceso repetido a `cursor`: baseline con cursor en atributo plano 7,15 ms (mediana de cinco), final con cursor por hilo 9,23 ms (mediana de cinco), delta ~0,21 μs/iteración en este sandbox; cifra micro-sintética, no benchmark de producción.
   - Los commits/rollback existentes permanecen en los caminos actuales y operan sobre la conexión del hilo. Unificar transacciones multi-paso y clasificar retries por código SQLite siguen pendientes de auditoría en T4/T5; no se mantiene una transacción abierta durante embeddings/ranking por este cambio.

3. **Mapa de ruta, lifecycle y generaciones de archivo**
   - T3a implementa en `core.paths.resolve_db_path()` canonicalización de rutas de archivo (ruta relativa desde cwd, `expanduser`, `realpath`, `normcase`) sin crear archivos/directorios; el motor usa el mismo resolver. El resolver preserva `:memory:` y file-URI sin afirmar que el motor admita URI SQLite.
   - T3b captura `(st_dev, st_ino)` de la DB del motor tras abrirla y vuelve a comprobarlo en el primer acceso SQLite de cada operación pública y antes/después de abrir conexiones auxiliares. Si la identidad cambia o desaparece, falla con error explícito y no intenta limpiar ni reparar archivos. No detecta reemplazos in-place con el mismo inode; un cursor/conexión DB-API retenido y usado directamente fuera de la fachada tampoco queda completamente cercado.
   - T3d, solo en WAL, sigue `(st_dev, st_ino)` de `-wal` y `-shm` desde que son observados; una sustitución/desaparición posterior falla cerrado, sin borrar ni reparar. El primer sidecar puede crearse de forma normal durante el uso, y el rollback journal es transitorio: no se afirma detectar su sustitución. La prueba fuerza el clasificador de runtime corregido en un fixture para cubrir WAL, sin cambiar el SQLite real del sandbox.
   - Medición sintética de una llamada de motor con un `SELECT 1`: 10.000 llamadas, mediana 76,94 ms con verificación frente a 51,07 ms con el verificador sustituido por no-op (~2,59 μs por operación de una sola consulta). Una operación real consulta identidad una vez, no por sentencia; no es benchmark de producción.
   - T3c deriva PID, run-lock, spawn-lock y estado del daemon de la ruta canónica (hash de 24 hex para DB no-default; el default conserva artifacts legacy). El run-lock retenido es la prueba de vida y evita confundir un PID reciclado. Spawn-lock y run-lock son archivos distintos; para un daemon legacy con ruta ambigua se falla cerrado y no se termina el proceso.
   - GraphMaintenanceDaemon usa un lock portable de archivos, fija DB/artifacts al iniciar y recibe del supervisor ruta y estado canónicos. Los tests usan fixtures, lock temporal en un proceso hijo y `Popen` simulado; no requieren lanzar MCP/daemon real.
   - T3e añade `open_reader` para los consumidores read-only identificados (URI de filesystem codificada, `mode=ro`, `query_only`) y tags por consumidor en aperturas read/write. En DEBUG se registra versión/source ID, journal efectivo, busy timeout, rol y `route_id` SHA-256 truncado de la ruta canónica; no se expone la ruta cruda ni contenido. Scripts manuales/externalizados aún pueden abrir SQLite directamente.
   - Detectar reemplazo de DB/sidecars durante la vida de conexiones y rechazar escrituras de generaciones antiguas. Se cubren cambios de inode observados; el reemplazo in-place con el mismo inode no se puede inferir sin una regla de coordinación/versionado, porque cambios concurrentes legítimos también modifican el archivo. Validación de FileLock en Windows/macOS y límites de filesystem siguen pendientes.
   - Documentar actualización/transición: un modo WAL existente no se degrada mientras haya conexiones activas; el error explica cómo cerrar ordenadamente consumidores antiguos.

4. **Seguridad y auditoría de fallos**
   - Auditar conexiones SQLite directas, modo read-only/write, SQL parametrizado, rutas, permisos de archivo y filtrado de logs.
   - Separar `BUSY`/`LOCKED`, `IOERR`, `CORRUPT` y `NOTADB`; no reintentar/reparar de forma opaca.
   - Documentar límites OWASP relevantes y riesgos web/MCP que quedan fuera de esta capa.

5. **Verificación integrada**
   - Con pruebas temporales, cubrir hilos, procesos, colisiones de ruta, bloqueo, timeout, actualización runtime/journal, reemplazo y errores inyectados.
   - Ejecutar pruebas funcionales del motor y la suite completa; la QA oficial solo se ejecuta con la ruta de snapshot autorizada, nunca contra la DB real.
   - Ejecutar `PRAGMA integrity_check` solo en fixtures temporales del test.

## Política de prueba

- TDD por tarea: agregar primero un test que reproduzca el comportamiento o el caso límite.
- No usar `MemoryBioRAG_Data/memory_biorag.db`, `memory_biorag.db`, WAL/SHM reales ni procesos vivos del usuario.
- No alterar datos reales ni cambiar journal mode por comandos ad hoc.
- Baseline disponible para una muestra temporal: 17 tests aprobados antes del cambio (17 passed, 3.49 s). No constituye baseline de toda la suite ni rendimiento de producción.
- La prueba de stress debe usar procesos nuevos con el mismo ejecutable para observar el runtime real de cada proceso.

## Criterios de decisión

- Mantener stdlib SQLite y downgrade seguro de journal a `DELETE` en runtimes vulnerables como primer paso de compatibilidad; no adoptar `pysqlite3` sin cerrar la auditoría de excepciones, ABI, packaging e integración de todos los consumidores.
- No cambiar journal mode de una base existente al arrancar. La futura herramienta de migración requerirá opt-in explícito y no cambiará el modo si SQLite no concede la transición exclusiva.
- `synchronous=FULL` se mantiene como decisión pendiente hasta medirlo y acordar el equilibrio de durabilidad/rendimiento; no se aumentará silenciosamente el costo de cada escritura.
- No usar un daemon broker o servidor externo salvo que las pruebas demuestren que la coordinación in-process/multi-process local no basta.

## Referencia normativa

- [SQLite WAL-reset bug](https://www.sqlite.org/wal.html#the_wal_reset_bug): versiones corregidas publicadas por SQLite y condiciones de la falla.
