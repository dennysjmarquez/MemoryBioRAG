# Tareas — Spec 008

## T1: Política de runtime y WAL seguro
- **RF cubiertos**: RF-1, RF-2, RF-3, RF-5 (base)
- **Descripción**: Implementar clasificación version-aware del WAL-reset bug y una apertura común de conexiones escritoras. Conectar el almacén y los escritores de BioRAG identificados; ningún error de transición de journal se descarta. El cambio de journal de una base existente requiere opt-in explícito.
- **Hecho cuando**: matriz de versiones, transición WAL→DELETE autorizada con lock disponible, rechazo sin mutación por defecto y fallo cerrado si otra conexión impide la transición pasan en tests temporales; no se abre ni altera ninguna DB real.
  - [x] Tests cubren runtimes vulnerables/fixed/backport, `:memory:`, preservación de filas, opt-in y modo ocupado.
  - [x] Tests de integración cubren el almacén principal, DMN y el inventario de escritores directos.
  - [x] Runbook documenta actualización de runtime o transición `WAL→DELETE` explícita sobre copia primero; no instala runtime ni ejecuta migración real. La CLI de operador sigue pendiente.
- [x] **Estado**: completada (17 tests de esta tarea pasan).

---

## T2: Aislamiento de operaciones del singleton
- **RF cubiertos**: RF-5
- **Descripción**: Eliminar el uso cruzado de conexión/cursor entre hilos en DB persistente; mantener la semántica de `:memory:`; aislar metadatos `last_*` por request y coordinar el cierre/reset con operaciones activas. La contención entre conexiones sigue delegada a SQLite con espera acotada.
- **Hecho cuando**: stress concurrente de operaciones simuladas sobre fixtures temporales no mezcla cursores, conserva todas las escrituras y el test de latencia registra medida antes/después.
  - [x] Tests multi-hilo reproducen y dejan de reproducir la pérdida de resultados/error de cursor; se verifican todas las filas e `integrity_check`.
  - [x] Tests de cierre y `reset_cerebro()` esperan a una operación en vuelo antes de cerrar.
  - [x] Prueba sintética pareada: 10.000 `SELECT 1` con acceso repetido a `cursor`; baseline con cursor en atributo plano 7,15 ms (mediana de cinco), final con cursor por hilo 9,23 ms (mediana de cinco). Delta 2,08 ms por 10.000 iteraciones (~0,21 μs por iteración) en este sandbox; no es una proyección de rendimiento de producción.
- [x] **Estado**: completada; suite completa **780 passed in 203.18s**.

---

## T3: Ruta canónica, procesos y generaciones
- **RF cubiertos**: RF-4, RF-8
- **Descripción**: Completar inventario de conexiones; normalizar ruta; asociar lifecycle del daemon a ruta/identidad del proceso; detectar DB/sidecars sustituidos sin limpiar ni reparar archivos.
- **Hecho cuando**: tests de ruta relativa/symlink, cambio de archivo abierto, daemon/PID reutilizado y dos rutas concurrentes pasan sin tocar procesos ni bases externas.
  - [x] T3a: `resolve_db_path()` y el motor devuelven rutas absolutas/canónicas para archivos; rutas relativas se anclan al cwd del consumidor; el resolver preserva `:memory:`/file-URI sin asumir compatibilidad del motor con URI; no crea archivos/directorios.
  - [x] T3b: el motor captura `(st_dev, st_ino)` al abrir una DB temporal y rechaza el siguiente acceso SQLite si el path identifica otro archivo; test comprueba que no escribe ni en la generación vieja ni en la nueva.
  - [x] Medición sintética T3b: 10.000 llamadas con un solo `SELECT 1`, mediana 76,94 ms con identidad vs. 51,07 ms con el check sustituido por no-op (~2,59 μs por operación DB de una sola consulta; no es benchmark de producción).
  - [x] T3d: en journal WAL se fijan las identidades de `-wal` y `-shm` al observarse y se rechaza su sustitución/desaparición; tests temporales reemplazan ambos sidecars sin reparar el nuevo archivo.
  - [x] T3g: la fachada entrega proxies para conexiones/cursors DB-API retenidos y valida antes de usarlos. Contrasta `(st_dev, st_ino)`, `PRAGMA data_version`, firma/header SQLite y WAL; commits de `open_writer` se correlacionan dentro del proceso. Fixtures reemplazan en-place con inode igual: el caso de esquema distinto falla cerrado y el caso mismo-esquema devuelve la generación nueva o falla, nunca filas stale.
  - [ ] Límites restantes: una escritura byte-a-byte que preserve todos los metadatos/header observados, cambios durante una transacción ya abierta, handles creados fuera de la fachada y sidecars antes de primera observación no son distinguibles de manera absoluta de actividad SQLite válida; rollback journal es transitorio. Validar semántica por filesystem/OS.
  - [x] T3c: PID/lock/estado se derivan de la ruta canónica; el run-lock retenido, no el número PID, es la prueba de vida. Dos rutas obtienen artifacts distintos; un daemon legacy ambiguo bloquea el spawn de otra ruta (fail-closed).
  - [x] Tests cubren PID reutilizado sin lock, lock entre procesos temporales y spawn con `Popen` simulado; no se lanzó un daemon real.
  - [x] T3e: aperturas read-only de ADN, feedback, PPMI y neocórtex pasan por `open_reader` (`mode=ro` + `query_only`); escritores y lectores registrados con consumidor, runtime/source ID, journal, timeout y hash de ruta canónica en logs DEBUG, sin ruta cruda ni contenido de DB.
  - [x] T3f: CI añade matriz enfocada Ubuntu/Windows/macOS para rutas, runtime, generaciones/sidecars y locks multiproceso. El run Actions `42526947166` confirmó el fallo de checkout con `invalid path 'docs/Plan Maestro: ...'`; se renombraron los seis archivos versionados con `:` no permitido en NTFS. Falta verificar el checkout corregido en Actions.
  - [ ] Ejecutar CI multiplataforma; documentar/aceptar límites del reemplazo in-place. Scripts manuales/externalizados todavía pueden evitar las aperturas instrumentadas.
- [ ] **Estado**: en progreso (identidad principal/sidecars, handles DB-API retenidos, diagnóstico por consumidor y lifecycle implementados; continúan límites del modelo de archivo, resultados Windows/macOS pendientes y revisión operativa).
  - Validación integrada actual: suite completa **800 passed in 259.20s** (fixtures temporales; `BIORAG_PATH` unset); 37 pruebas focalizadas de generación/runtime/locks también pasaron. El escaneo del índice no encuentra nombres de archivo con caracteres prohibidos por Windows. Los runners Actions Windows/macOS aún deben ejecutarse.

---

## T4: Política de errores y seguridad de acceso
- **RF cubiertos**: RF-6, RF-7
- **Descripción**: Clasificar errores SQLite extendidos; limitar retry a contención temporal; auditar SQL dinámico, configuración de ruta y filtrado de logs.
- **Hecho cuando**: tests inyectados demuestran `BUSY` acotado, `CORRUPT`/`IOERR` no reintentados, parámetros conservados y mensajes sin contenido de recuerdos.
  - [ ] Matriz de errores y mensajes de usuario documentados.
  - [ ] Hallazgos de alcance OWASP separados de la garantía de SQLite.
- [ ] **Estado**: pendiente

---

## T5: Validación integrada y documentación operativa
- **RF cubiertos**: RF-1 a RF-8
- **Descripción**: Ejecutar suite completa, stress multi-proceso y pruebas de integridad sobre fixtures; actualizar guía del operador con cambios de runtime y cierre seguro.
- **Hecho cuando**: todas las pruebas aplicables pasan, la tabla RF×test está completa y no se usa DB/daemon real durante pruebas.
  - [ ] Tests funcionales focalizados y suite completa con salida registrada.
  - [ ] Guía enumera runtime por consumidor y limitaciones sin prometer protección absoluta.
- [ ] **Estado**: pendiente

## Cobertura de requisitos
| RF | Cubierto por |
|----|-------------|
| RF-1 | T1, T3 |
| RF-2 | T1 |
| RF-3 | T1, T5 |
| RF-4 | T3 |
| RF-5 | T1, T2, T5 |
| RF-6 | T4 |
| RF-7 | T4 |
| RF-8 | T3, T5 |
