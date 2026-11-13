# Encargo de auditoría: guardián autónomo y usabilidad de BioRAG

**Destinatario:** auditora independiente de la reparación WAL del PR #13.  
**Propósito:** transmitir los requisitos de Dennys y pedir una revisión del diagnóstico y del diseño **antes de implementar** el siguiente cambio.  
**Estado:** documento de trabajo, no dictamen de seguridad ni aprobación para tocar datos de producción.

## 1. La petición del usuario

Dennys quiere que BioRAG sea instalable y utilizable por personas que no administran bases de datos. Su objetivo es un sistema robusto para uso personal y empresarial, con seguridad activada por defecto y mantenimiento automático por detrás:

1. El instalador debe proporcionar automáticamente un runtime SQLite corregido y verificar que BioRAG realmente lo utiliza. No trasladar al usuario la tarea de instalar o configurar SQLite.
2. El guardián debe **prevenir, coordinar, recuperar y reanudar**, no limitarse a bloquear la herramienta y mostrar una excepción técnica en el chat. Las esperas y reparaciones recuperables deben manejarse por detrás.
3. MCP, Hormiguita y demás consumidores de BioRAG deben coordinarse. Hormiguita podría eliminarse en el futuro; la seguridad de la base no debe depender de ella.
4. Deben poder coexistir múltiples terminales y clientes (OpenCode y otros), con pruebas reales a 20, 50 y 100 clientes; considerar también cargas mayores. El número de clientes no equivale al número de escritores simultáneos: medir ambos.
5. En su caso particular, Dennys versiona la base en Git. Su flujo: guardar, consolidar recuerdos, cerrar procesos, cambiar de rama y seguir usando BioRAG. Quiere que el sistema gestione ese flujo automáticamente. Otros usuarios normalmente tendrán sus propias bases locales; no debemos imponerles una arquitectura solo por el caso de Git.
6. Preservar información y no bajar recall ni otras métricas. No presentar una operación como exitosa si no fue confirmada. No modificar su base real ni borrar sus archivos para experimentar.
7. Protección por defecto, diseño multiplataforma, poca carga operativa, logs auditables y pruebas repetibles. El usuario no quiere errores técnicos rutinarios en el chat; ante una situación sin recuperación segura, la información se preserva y el fallo no se disfraza como éxito.

**Aspiración:** experiencia transparente y seguridad empresarial. No se presenta como garantía absoluta ya alcanzada. Pérdida de la única copia de información, hardware averiado, falta de espacio, intervención de programas externos y cortes son casos para los cuales hay que definir prevención, límites y respuesta explícita.

## 2. Distinciones que no debemos confundir

- `biorag.consolidar` ejecuta el ciclo de sueño: gestiona recuerdos de corto y largo plazo. No equivale por definición a un checkpoint de SQLite.
- Un commit en WAL puede estar confirmado en el WAL y aún no estar reflejado en el archivo `.db`. Checkpoint es la operación SQLite que transfiere páginas del WAL al principal; para declarar listo un cambio de rama hay que comprobar el resultado, no solo ejecutar el PRAGMA.
- Un `.db` que pasa `integrity_check` sin un WAL no demuestra que el WAL sea descartable, que no contenga commits pendientes, ni que sus datos puedan aplicarse a esa base. La integridad estructural no verifica pertenencia ni completitud semántica.
- Un WAL es un diario de páginas, no una lista de recuerdos que pueda mezclarse a ciegas con otra versión de la base. Para recuperar su contenido puede ser necesaria su base original; una eventual unión de recuerdos exigiría reglas semánticas de conflictos, actualizaciones y borrados. No diseñar esa unión suponiendo que siempre es posible.
- SQLite WAL permite lectores concurrentes con escritura, pero solo un escritor a la vez. Un `busy_timeout` no demuestra que una carga concreta sea aceptable. WAL ordinario necesita procesos en el mismo host; compartir directamente el archivo en red entre máquinas no es la arquitectura propuesta.
- Una anotación forense `*.biorag-pair-state.conflicto.json` registra un conflicto; no asumir que borrarla repara el par. La sal del WAL se compara con el estado registrado, no con una sal independiente del `.db`. Sal coincidente no basta: un WAL copiado puede conservarla.

## 3. Qué pasó y estado reportado

### Incidencia A: WAL no atribuible

Tras un cambio de rama, el usuario vio `SQLiteSidecarConflictError`: el guardián no pudo atribuir con certeza el WAL al principal y rechazó abrirlo. El mensaje indicaba que no movió ni borró los archivos y dejó una constancia forense. Según el usuario, había ordenado cerrar MCP y Hormiguita, y después borró los WAL manualmente. **No tenemos evidencia suficiente para afirmar por qué quedó el WAL ni reconstruir exactamente el orden y resultado de todos los cierres.** Reproducirlo antes de atribuir causa.

### Incidencia B: runtime vulnerable

Después apareció `UnsafeSQLiteJournalModeError`: runtime reportado por el usuario `3.45.1`, base existente en modo WAL. El guardián rechazó la escritura y pidió migración explícita o un runtime corregido. Son dos problemas distintos; instalar una biblioteca corregida no demuestra que se haya resuelto un conflicto de pertenencia del par.

SQLite documenta el fallo WAL-reset bajo condiciones de carrera concretas; lo corrige desde 3.51.3 y tiene backports identificados 3.50.7 y 3.44.6. No afirmar que cada escritura concurrente produce corrupción. Referencia: https://www.sqlite.org/wal.html#the_wal_reset_bug

### Trabajo previo y advertencias de procedencia

- PR #13 se reporta mergeado; correcciones del guardián y revisión previa están documentadas en `docs/auditoria_pr13_d5c3834.md`.
- Hay un preflight en `core/sqlite/preflight.py` y conexión en `core/mcp_server/server.py`: avisa en stderr al arrancar, pero no instala un runtime corregido ni realiza reparación autónoma. Es un paso intermedio, **no cumple el objetivo de producto completo**. Verificar en el árbol disponible y no duplicarlo sin motivo.
- La nota de continuidad reportaba commit `c9934ef` ya enviado. En la inspección actual, `git log -1` muestra `e11d0dc` y esos cambios de preflight aparecen sin commit en el árbol. **No hacer reset, checkout, stash ni sobrescribir cambios para reconciliarlo sin respaldo y verificación.** No asumir que el commit está presente localmente.
- La sesión anterior reportó 87 pruebas SQLite/arquitectura aprobadas y suite general con 859 aprobadas y 3 fallos. Son reportes previos, no una ejecución de este documento; consultar nombres y reproducir antes de usarlos como baseline.
- Otro agente reportó ensayo de WAL→DELETE en copia real: 54 tablas, 364.289 filas, `integrity_check=ok`, 300 escrituras conservadas y 0,33 s de transición; benchmark con 3 lectores/1 escritor en `/tmp`. No revisamos sus scripts ni artefactos; tomarlos como **datos reportados, pendientes de reproducción**, no como validación universal, ni extrapolar a 100 clientes o al disco de producción.
- Se reportó `pysqlite3-binary` con SQLite 3.51.1 en una prueba previa; no fijar el diseño a ese resultado sin verificar el artefacto y versión actuales. Una librería privada y `LD_LIBRARY_PATH` son una posibilidad Linux, **no una solución multiplataforma demostrada**. Runtime estático, búsqueda de librerías y otros consumidores deben verificarse.

## 4. Mapa inicial del código (revisar, no asumir exhaustivo)

| Pieza | Dónde mirar | Qué importa |
|---|---|---|
| Consolidación de recuerdos | `core/mcp_server/consolidation.py`, `core/memory_service.py`, `core/memory/` | Ciclo de sueño y su resultado lógico, separado del checkpoint SQLite. |
| Cierre del motor | `core/memory_store.py`, `_consolidar_antes_de_cerrar`, `cerrar_sistema` | Espera operaciones de la instancia y llama `PRAGMA wal_checkpoint(TRUNCATE)` como best-effort. Recoge filas pero no comprueba el resultado; error SQLite se registra a nivel debug y cierre continúa. No es una barrera verificada entre todos los procesos. |
| Inicio MCP | `core/mcp_server/server.py` | Canal stdio, preflight y lanzamiento asíncrono de Hormiguita mediante `ensure_daemon_alive`. No contaminar stdout del protocolo. |
| Procesos de mantenimiento | `core/daemon_lifecycle.py`, `graph_maintenance_daemon.py`, `core/mcp_server/daemon.py` | Ciclo de vida, arranque concurrente, apagado y escrituras reales; separar responsabilidad de Hormiguita. |
| Apertura y protección | `core/sqlite/opening.py`, `pair_guard.py`, `journal.py`, `tracking.py`, `epoch.py`, fachada `core/sqlite_runtime.py` | Identidad del par, snapshots antes/después, política de runtime, anotación de estado y época entre procesos. Auditar cobertura real de todos los consumidores. |
| Instalación | `install.py`, `requirements.txt`, `pyproject.toml` | Python efectivo, plataforma y despliegue. Inspeccionar `_backup_database`: se reporta copia del `.db` solo; revisar sus llamadas y condiciones antes de cambiarla. Copiar solo el principal activo en WAL no garantiza copia completa. |
| Rutas y consumidores | `core/paths.py`, `core/memory_store.py`, dashboard, scripts y herramientas | Inventariar `sqlite3.connect`, conexiones indirectas y dependencias externas; no afirmar cobertura universal por la fachada sin verificar. |
| Pruebas | `tests/test_sqlite_generation.py`, `test_sqlite_runtime.py`, `test_sqlite_preflight.py`, `test_sqlite_paquete.py`, `test_arquitectura.py` | Preservar los tres escenarios de auditoría y las pruebas de carreras existentes; añadir regresiones antes de cada cambio. |

Guías: `AGENTS.md`, `CONSTITUTION.md`, `docs/SEGURIDAD_OWASP.md`, `docs/sqlite_par_no_verificado.md` y `docs/sqlite_journal_migration_runbook.md`. No integrar `prototypes/sqlite_coordination/`; no hacer refactor masivo de archivos no relacionados.

## 5. Diseño propuesto para debatir, no aprobado

### A. Runtime seguro y entrega

Investigar un runtime empaquetado o biblioteca corregida con FTS5 y demás capacidades requeridas por BioRAG. Evaluar instalación y actualización en Linux, Windows y plataformas soportadas: distribución reproducible, integridad y procedencia de artefactos, arquitectura, licencias, modo offline y compatibilidad. Preferir una vía que no exija sudo ni configuración manual para el caso normal.

Verificar **en cada entrypoint y proceso real** `sqlite_version`, fuente/capacidades y lectura/escritura con el mismo runtime. Probar intérprete estático o dinámico y el comportamiento del cargador de cada plataforma. Un cambio de entorno no actualiza procesos ya vivos: diseñar coordinación y transición de versiones, sin dejar escritores vulnerables trabajando sobre WAL. Clientes externos quedan fuera del control de locks voluntarios; identificar cómo se limita o comunica ese alcance. No modificar bibliotecas globales del sistema como solución por defecto.

### B. Coordinación y disponibilidad

Inventariar primero locks y lifecycle existentes. Comparar mejoras incrementales con un servicio de almacenamiento local único: los MCP y Hormiguita serían clientes; el servicio podría centralizar apertura, colas y mantenimiento. **No asumir que un daemon nuevo es necesario ni que SQLite desaparece de los demás procesos.** Evaluar coste, consumo, arranque simultáneo, singleton, autenticación local, compatibilidad, caída y reinicio.

Precisar un protocolo de estados (operativo, pausando, drenando, checkpoint, cerrado, reabriendo, recuperación) con dueños y transiciones. Operaciones aceptadas deben tener semántica definida ante timeout, crash, retry y duplicación: confirmación solo tras commit; cola persistente si se promete sobrevivir a caída; idempotencia/deduplicación si se reintenta. No prometer que una cola RAM conserva datos tras caer. Esperas acotadas, backpressure y señales de salud, sin colgar solicitudes indefinidamente.

### C. Preparación para cambios de rama

Un mecanismo coordinado puede drenar operaciones propias, impedir nuevas, cerrar transacciones y ejecutar checkpoint, verificando el resultado SQLite y el estado final, antes de confirmar que está listo. Examinar lectores activos, busy, procesos que no cooperan, transacciones largas y procesos que reabren durante la ventana. Comprobar también que la instantánea versionada refleja lo esperado; un commit Git no ejecuta checkpoint por sí solo.

Un `git checkout` externo no necesariamente avisa a BioRAG y un lock advisory no controla procesos externos. Para cambios inesperados: detectar sustitución y evitar abrir/aplicar un par no demostrado; conservar artefactos y recuperar solo con evidencia suficiente. Vigilar archivos por sí solo no cierra carreras; revisar identidad, sincronización y ventanas TOCTOU. Si las acciones ocurren después de una sustitución destructiva, no se puede asegurar reconstrucción sin copia previa. Definir integración Git opcional, no imponerla a todos los usuarios.

### D. Recuperación y backups

Diseñar backups consistentes mediante API apropiada, nunca asumir que copiar tres archivos por separado con escritores activos constituye una foto atómica. Antes de abrir una base con WAL dudoso, el procedimiento de backup debe respetar la protección del par y evitar que SQLite aplique un diario no verificado. Trabajar en copias aisladas, mantener originales y verificar restauración, permisos, capacidad, retención y confidencialidad. No restaurar automáticamente sobre archivos activos ni descartar información en conflicto. Evaluar `integrity_check`, `foreign_key_check`, FTS y verificaciones semánticas; ninguna sustituye la atribución del par o prueba que no falten recuerdos.

Proponer una política explícita para WAL propio comprobado, sin WAL, WAL dudoso, WAL ajeno con base original disponible, WAL perdido, DB truncada, LFS pointer, falta de espacio y permiso. Un WAL ajeno no se aplica ni elimina automáticamente por sal e integridad del principal. Para reconciliación semántica, documentar si hay evidencia, historial y decisiones suficientes; no inventar borrados ni orden de cambios.

### E. Observabilidad y seguridad

Operaciones normales recuperables silenciosas para el usuario, con logs acotados y auditables que no expongan recuerdos ni rutas sensibles innecesariamente. Fallos irrecuperables no deben fingir éxito: diseñar mensaje humano y diagnóstico accesible cuando la reparación segura no sea posible. Para nuevos procesos, IPC, descargas, archivos y permisos aplicar OWASP Top 10 **antes de implementar**, incluyendo autenticación/autorización local, validación de rutas, symlinks, TOCTOU, privacidad, actualizaciones verificadas y mínimo privilegio.

## 6. Plan de trabajo y revisión

1. **Inventario y baseline:** trazar `aprender`, `recordar`, consolidación lógica, commits, checkpoint, cierre, instalador, MCP, daemon, dashboard y scripts; diferenciar procesos propios y externos. Reproducir escenarios sobre copias, sin DB de producción. Registrar entorno, versiones, carga y fallos conocidos.
2. **Contrato de seguridad y usabilidad:** estados, garantías concretas, límites y alternativas; OWASP previo. Preguntar a la auditora por carreras, fallos de recuperación y pruebas faltantes antes de implementar.
3. **Cambios pequeños:** test que reproduzca un fallo; un solo cambio; repetir prueba y suite relevante; revisar con auditora. Mantener protección por defecto y las pruebas del PR #13.
4. **Instalador/runtime:** validar artefacto, versión y capacidades en procesos reales, transición de instalaciones existentes y reversión. Matriz real por plataformas, sin dar por probado Windows si no se ejecutó allí.
5. **Coordinación y recuperación:** validar políticas de identidad, exclusión, checkpoint, reanudación, cierre y recuperación sobre copias. No garantizar exclusividad sobre programas externos mediante advisory lock.
6. **Carga y regresión:** 20/50/100 clientes reales; número y frecuencia de lectores/escritores especificados, latencias p50/p95/p99, errores/busy, throughput, memoria, tiempos de arranque/recuperación, tamaño del WAL; comparar antes/después en almacenamiento representativo. Probar recuperación de registros confirmados y ausencia de duplicados. Suite de recall y métricas tanto snapshot como copia consistente de base real cuando esté disponible.
7. **PR y auditoría final:** documentación y pruebas reproducibles, pendientes y limitaciones explícitos. No mergear sin autorización expresa del usuario. Nada de usar datos reales ni borrar archivos sin consentimiento específico.

### Matriz mínima de fallos a preparar

- Arranques simultáneos, caída del coordinador y del cliente en cada etapa de escritura, retry y reinicio.
- Lectores y escritores concurrentes, checkpoint incompleto/busy, transacción larga, backpressure y límite de espera.
- Cierre ordenado, terminación brusca, cambio de rama con procesos cerrados y con procesos abiertos, cambios externos durante validación/apertura.
- WAL propio con commits pendientes, WAL ajeno, WAL copiado conservando sal, WAL truncado, sin WAL y aparición de WAL durante apertura; ausencia de metadatos del par; preservación y recuperación tras cada caso.
- Eliminación accidental de WAL tanto con todas las conexiones cerradas como activas: validar lo que puede recuperarse, no fingir datos perdidos. DB y sidecars no tocados fuera de copias.
- Runtime vulnerable y corregido; mezcla de procesos viejos/nuevos; fallo o corrupción de descarga; librería incompatible; rollback seguro de instalación.
- Permisos, disco lleno, reinicio, backup interrumpido, restauración comprobada, LFS pointer y nombres/rutas en Windows/Linux. Añadir otras plataformas según soporte real.
- Base local y servicio remoto compartido como arquitecturas distintas; no tratar WAL sobre sistema de archivos de red como solución universal.

## 7. Preguntas concretas para la auditora

1. ¿Qué garantías actuales de `pair_guard`, snapshots y época son suficientes o insuficientes para el flujo real de cambios de rama? ¿Qué carreras quedan abiertas?
2. ¿Cómo verificar el resultado del checkpoint y asegurar que no se reabran escritores durante la preparación? ¿Cuáles procesos o conexiones quedan fuera?
3. ¿Qué protocolo de recuperación conserva los originales sin aplicar WAL dudoso y cuáles casos pueden ser automáticos sin riesgo de pérdida?
4. ¿Conviene extender el daemon/lifecycle existente o un coordinador de almacenamiento separado? ¿Cómo evitar singletons duplicados, bloqueos y split brain en cada plataforma?
5. ¿Qué estrategia de distribución permite runtime corregido para todos los procesos propios, con FTS5, sin sudo y con actualización y reversión verificables? ¿Cómo detectar procesos antiguos y escritores externos?
6. ¿Cómo demostrar no pérdida de operaciones confirmadas, ausencia de duplicados por retry y reanudación segura después de crash?
7. ¿Qué auditoría OWASP y pruebas de carga, recuperación, integridad, recall y rendimiento faltan antes de presentar esto como listo para empresas?
8. ¿Qué cambios deben entregarse primero para desbloquear al usuario sin abrir una ventana de corrupción ni fingir que el proyecto completo está resuelto?

**Solicitud de dictamen:** separar bloqueantes, riesgos y sugerencias; aportar reproducción/prueba por hallazgo. Revisar diseño antes de implementación y cada parche posterior. Si una premisa de este documento es falsa, corregirla con evidencia; el objetivo es avanzar con seguridad, no acumular hallazgos.
