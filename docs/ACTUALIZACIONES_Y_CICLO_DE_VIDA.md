# Actualizaciones y contrato de preparación del sistema

## Estado: implementación local candidata, no certificación empresarial

Se añade un actualizador para checkouts Git y un núcleo compartido post-install /
post-update. No se ejecutó sobre el repo de trabajo ni sobre DB viva. No se ha
publicado release ni se declara completada la compatibilidad con cualquier gestor.

## Para agentes que agregan módulos

Seguir el checklist obligatorio en `AGENTS.md` y la
[guía de extensión lifecycle](GUIA_EXTENSION_LIFECYCLE.md). Allí se explica cómo
registrar callbacks, preservar recursos no SQLite, cubrir ejecución independiente
y probar fallos sin atribuir al actualizador garantías que no tiene.

## Ayuda del updater

`biorag update --help` usa el parser real del updater y no ejecuta un plan. El
entry point `biorag update` y `python biorag.py update` despachan antes de abrir
la memoria; el plan sí consulta la DB elegida en modo de solo lectura.

## Experiencia de usuario

Dentro del checkout instalado, usando el Python de su entorno:

```sh
python3 biorag.py update                 # aplica update DEV desde su upstream
python3 biorag.py update --dry-run       # vista previa, sin cambios
python3 biorag.py update --channel stable
```

El entry point instalado `biorag` despacha mediante `core.cli`; `update` y
`recovery` se procesan antes de importar `biorag` o inicializar memoria.
Alternativa mínima: `python -m core.updater`.
No sustituir el Python del entorno por otro intérprete: pip instala en el mismo
Python que invocó el actualizador. Si pip no está disponible o el entorno está
gestionado externamente, se detiene; no usa sudo ni --break-system-packages.

DEV significa upstream de la rama actual, sin publicar nada, sin cambiar de rama
ni adivinar master/main. STABLE valida política y tag mediante el comprobador
existente, obtiene el tag de la fuente oficial y solo admite avance fast-forward
sobre la rama actual. Un destino anterior o divergente se rechaza: no hay reset,
checkout a otro canal, degradación ni merge automático de historias divergentes.
El canal dev confía en el upstream configurado; stable confía en la política y
repositorio oficial de GitHub, no incorpora verificación criptográfica de firmas.

`--dry-run` planifica sin cambiar código, dependencias ni DB. La planificación
puede consultar la red y abre la DB elegida en modo SQLite de solo lectura. Al
aplicar, BioRAG detiene solo el daemon cuyo PID registró su propio gestor y cuya
identidad se verifica; no inspecciona ni detiene otros procesos. El OS lease
compartido/exclusivo (POSIX `flock`, Windows `LockFileEx`) coordina las conexiones
administradas. Programas externos que abren SQLite directamente no respetan ese
lease; nunca se termina un proceso desconocido. El host MCP externo debe reconectar
tras una actualización para cargar el código nuevo.

Antes de actualizar se crea y prueba un backup de la DB. Al terminar se verifican
el esquema, integridad SQLite e ID aplicado; solo entonces se elimina el backup.
Si falla cualquier fase, el actualizador intenta volver al commit anterior,
reinstalar sus dependencias y restaurar la DB. La reversión compara el inventario de nombres/versiones de paquetes Python con
el estado previo; no es una copia byte a byte del entorno. Si puede verificar las
comprobaciones disponibles, conserva el backup y registra `rolled_back`; si no,
mantiene la barrera y backup, registra `recovery_required` y pide no reiniciar
BioRAG hasta recibir soporte. No se promete que todo quede exactamente “como si
nada hubiera pasado”.

## Identidad aplicada y chequeo read-only

La tabla existente `data` recibe una sola clave reemplazable:
`biorag_applied_update_id`. Su valor es el SHA completo (40/64 hex) del commit
objetivo; no `VERSION`, no una secuencia creciente de filas y no un historial de
migraciones. Su descripción indica que el lifecycle de DB para ese commit pasó
verificación. Solo `core.lifecycle` la escribe después de migrar y verificar el
esquema; una falla de paso o de verificación deja el ID previo intacto. El plan
compara esa clave con el SHA local instalado y revisa los objetos del esquema base
que realmente genera `SQLiteMemoryBioRAG` en una conexión `:memory:`. La conexión
a la DB del usuario es read-only. Así un marcador coincidente no oculta una tabla
o columna base borrada. Tablas opcionales creadas fuera del inicializador común
requieren que su componente registre su propio verificador en `STEPS`.

El anuncio MCP de Stable sigue independiente: compara `VERSION` local con el tag
estable recomendado/aprobado por la política pública y comprueba que ese tag exista.
No lee `data` y no certifica el esquema de una DB. Para DEV, el updater compara
commits Git. La semver sirve para comunicar releases; el SHA identifica qué build
completó el lifecycle de esta instalación.

## Secuencia de aplicación

1. Verifica checkout exacto, rama, limpieza de archivos tracked/untracked,
   operaciones Git pendientes y ausencia de submódulos no soportados.
2. Adquiere lock exclusivo de actualización en el gitdir. Un lock huérfano requiere
   inspección manual; no se roba por una conjetura sobre su antigüedad.
3. Resuelve destino y verifica avance y presencia del contrato de lifecycle.
4. Rechaza DB dentro del checkout. Usa memoria externa configurada; no elimina ni
   mueve datos legacy por sorpresa. Esas instalaciones deben migrar primero.
5. Respalda con SQLite backup, incluyendo WAL confirmado, antes del avance Git.
6. Revalida limpieza/HEAD y hace merge --ff-only al commit planificado, sin push.
7. Instala el producto y dependencias con `python -m pip install .` en ese entorno.
8. Ejecuta **un Python nuevo**: `python -m core.lifecycle --db ... --update-id <target-sha>`.
   Así se cargan callbacks del código nuevo, no módulos importados en el viejo; el
   ID se guarda en `data` únicamente después de completar los pasos y verificaciones.
9. Guarda recibo externo y anuncia éxito solo después del lifecycle satisfactorio.
   Si el daemon BioRAG estaba activo, se reinicia después de verificar; el host MCP
   externo debe reconectar para cargar el código nuevo.

El recibo conserva commits, canal, fase, respaldo y estado. Si falla una fase, el
updater intenta volver al commit, reinstalar dependencias, restaurar atómicamente
el snapshot DB y verificarlo. El inventario de paquetes compara nombres/versiones,
no bytes completos del entorno: no se promete que todo quede exactamente como si
nada hubiera pasado. Si una comprobación falla, conserva el backup, mantiene la
barrera, registra `recovery_required` y pide no reiniciar BioRAG hasta soporte.

El backup se centraliza en `core/database_backup.py`. El updater pasa su respaldo
pendiente al proceso lifecycle mediante un handoff validado (DB, ubicación,
propósito e integridad). La migración no crea una segunda copia ni finaliza/pruna
el respaldo que pertenece a la operación completa. Una migración independiente
sí administra su propio backup. Se retienen por DB las dos copias más recientes
de operaciones exitosas y se podan éxitos anteriores al finalizar con verificación.
Fallidos/pendientes, copias legacy o metadata desconocida jamás se podan por esta
política; pueden ocupar espacio hasta su revisión operativa. No hay límite total
de bytes ni limpieza automática de recibos. Timeouts de
subprocesos no garantizan cancelación de todos sus descendientes: revisar una
instalación fallida antes de reintentar. No se promete tolerancia a disco lleno,
corte de energía, permisos arbitrarios ni procesos externos que editen el repo.

## Instalación, actualización y arranque

`install.py` ahora llama el mismo lifecycle después del checkpoint de paquetes.
En la ruta donde descarga cambios Git, exige limpieza y fast-forward y no
continúa como si hubiera actualizado si falla. Ejecutar install.py dentro de un
checkout sigue preparando ese código local, no implica hacer pull: usar update
para solicitar explícitamente descargar avances del upstream.

`core/memory_store.py` y `core/memory/schema.py` mantienen la migración aditiva de
arranque como protección adicional. Cambios de esquema no dependen de flags de
búsqueda. `core.migrate` sigue disponible como preparación específica de DB;
`core.lifecycle` es la entrada estándar para preparar todos los componentes.

## Estándar para nuevos componentes

`core/lifecycle.py` define `PreparationContext`, `Step` y la secuencia explícita
`STEPS`. Actualmente registra database-schema; no se inventaron callbacks de
archivos o demonios que no existen todavía. Para añadir un componente:

1. Implementar su preparación en el módulo propietario del componente.
2. Registrar un Step con nombre único en el orden de dependencias. No buscar e
   importar plugins arbitrarios ni ejecutar cualquier archivo llamado migration.
3. Recibir el contexto con DB y raíz de instalación; respetar configuración.
4. Hacer acciones idempotentes y verificar invariantes antes de retornar status=ok.
5. No sobreescribir configuración del usuario con defaults ni usar memoria como
   instrucciones ejecutables. Respaldo previo de los archivos que vaya a cambiar.
6. Propagar errores: no ocultarlos en un warning y anunciar éxito general.
7. Probar instalación nueva, existente, repetición y fallo parcial/recuperación.
8. Declarar si requiere reinicio. Servicios solo mediante política explícita;
   `allow_service_start` es false y no se debe ignorar. En esta versión no existe
   gestor de servicios ni supervisión multiplataforma automática.

Los pasos son secuenciales: no se ejecuta el siguiente tras fallo del anterior.
No se omiten verificaciones solo porque una marca diga «ya instalado».

## MCP y notificación

`planificar_actualizacion_sistema` comparte `core.updater.plan` con la CLI,
solo por stdio. Devuelve el comando vectorizado y exige autorización explícita y
proceso separado. El CLI revisa procesos que usan la DB y, al aplicar, detiene
solo BioRAG MCP/daemon identificados; bloquea procesos desconocidos o inspección
incompleta. Respalda la DB, actualiza, ejecuta lifecycle y verifica el resultado.
El daemon BioRAG que se detuvo se relanza y comprueba. El MCP stdio pertenece al
host IDE: BioRAG no puede prometer que el host lo reinicie. El agente debe comprobar
reconexión/versión y pedir reabrir la sesión si el host no lo hace. Si la tool se
invoca desde el mismo MCP y este es proceso padre del CLI, la auto-terminación se
omite; el lease bloquea apply hasta que el host cierre ese servidor.

El avisador existente anuncia tags aprobados según política, no cada commit DEV.
El aviso incluye planificación con updater y la distinción de instalaciones.
Sin red, con notificaciones desactivadas o sin tag/política válidos no se promete
aviso. No hay que publicar Stable para poder actualizar un checkout DEV.

## Métodos de instalación aún no automatizados

Wheel sin Git, zip sin Git, Docker, Nix y gestores de sistema NO se convierten a
un checkout ni reciben una orden pip inventada contra un paquete desconocido.
Se rechazan con instrucciones para actualizar con el gestor original y ejecutar
el lifecycle. Falta backend específico y probado para automatizar esos métodos.
El paquete no se descarga desde un índice público por asumir que su nombre exista.

## Investigación y decisiones

Se consultó código abierto vía GitHub API:

- OpenCode, [comando upgrade](https://github.com/anomalyco/opencode/blob/dev/packages/cli/src/commands/handlers/upgrade.ts)
  y [servicio updater](https://github.com/anomalyco/opencode/blob/dev/packages/cli/src/services/updater.ts):
  separa interfaz, detección de método, política/versión y ejecución; rechaza
  métodos no detectados y conserva errores accionables.
- Hermes, [post_update.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/post_update.py)
  y [update_contract.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/update_contract.py):
  mantenimiento posterior compartido, migración/verificación y rechazo con
  instrucciones para instalaciones gestionadas por otro mecanismo.

Son patrones observados, no una copia ni una certificación de nuestras garantías.
Las ramas enlazadas son móviles; no se afirma haber auditado esos proyectos enteros.

## Validación ejecutada y pendiente

Validación más reciente en copias aisladas y entorno temporal con requirements.txt:

- Suite global: **984 passed, 18 skipped, 11 subtests passed**, 323.31 s.
  Se ejecutó con BIORAG_TEMPORAL_PROTOTYPE=0 para compatibilidad de llamadas antiguas;
  NO es certificación de toda la suite con contrato obligatorio habilitado.
- Selección focal con el contrato nuevo por defecto: **105 passed, 9 subtests**.
  Incluye correcciones, seis modos, mantenimiento, recuperación, updater,
  instalación, esquema y política de backups.
- E2E MCP stdio real en DB sintética: registro estructurado con mensaje japonés,
  revisión, confirmación idempotente, rechazo de omisión, abstención sin evidencia
  y seis modos con ambos candidatos conservados. Script reproducible:
  scripts/experimentos/competencia_contextual/e2e_structured_mcp.py (código aislado
  bajo /tmp, corpus local NLTK, Python con dependencias MCP).
- Git real solo en repositorios temporales sin red; pip del update se simula.
  Sí se instalaron requirements.txt en venv temporal para ejecutar las pruebas,
  lo cual NO sustituye un update completo con pip real o un smoke de wheel.
- Fallos probados incluyen backup previo a código, pip/lifecycle, fallo después
  de escritura de datos, preservación de recuerdos posteriores, checksum alterado,
  cliente concurrente y salida forzada del dueño del lock POSIX. Esto no certifica
  todos los escenarios de corte de energía/disco lleno/subprocesos huérfanos.

QA oficial de **921 casos terminada en copia**, exit code 0 y gate OK, sin
relajar casos ni umbrales: Recall@5 100%, Recall@1 93.03%, MRR 0.9566,
0 fallos de recuperación y 0/40 falsos positivos. Evidencia:
`evidencia_qa_lifecycle_921.json`. Se midió la copia anterior a la revisión final
menor; no sustituye la suite final de 984 ni el E2E final del código revisado. Los resultados históricos 921/924 no se
usan como evidencia actual. Quedan pendientes Windows, wheel/update integral real,
distribución Stable cross-history y pruebas de fallos a nivel sistema operativo.
No se actualizó ni activó instalación real, no se publicó ni se tocó DB viva.

## Endurecimiento del contrato de resultado

El updater captura y comprueba el JSON final del proceso lifecycle; exit code 0
sin reporte válido no se considera éxito. El runner de componentes devuelve
failed_step y completed cuando falla uno, y el recibo de update conserva ese
reporte. Pruebas cubren salida vacía, status fallido con exit 0 y preservación
de pasos completados. No se infiere éxito por ausencia de excepciones en el CLI.

La publicación en Stable necesita verificar explícitamente cómo se corresponden
la versión del checkout distribuido, la política pública y el tag de código DEV.
El backend stable actual valida tags del repo DEV y exige ancestro común: no se
afirma que actualizar un checkout del repo MemoryBioRAG-Stable con historia
distinta ya esté automatizado. Si no es fast-forward, debe rechazar, no forzar
un merge/reset entre ambos repositorios. Ese E2E de distribución queda pendiente.

## Integridad y política de backups

Se verifica el backup antes de modificar código, y la DB migrada mediante
`PRAGMA quick_check`, `PRAGMA foreign_key_check` y comprobaciones de esquema del
componente. El updater vuelve a comprobar integridad antes de marcar éxito y
aplicar retención. Estas comprobaciones detectan corrupción/inconsistencia
estructural; NO prueban conservación semántica, calidad del ranking ni ausencia
de bugs de aplicación. Por eso no se elimina inmediatamente el último respaldo.

La limpieza elimina únicamente backups propios identificados por sidecar válido,
DB exacta y estado success. Nunca sigue symlinks para podar ni elimina archivos
ajenos por un glob genérico. Keep mínimo 1; default 2. Errores de borrado se
informan como warnings y no convierten una DB sana en migración fallida. Fallos
o procesos interrumpidos conservan sus copias; la retención no es un sistema de
disaster recovery, cuota de disco ni reemplazo de backups externos. Backups e
integridad cuestan O(tamaño DB); la selección de retención O(B log B) para B
sidecars. No se ejecutan en cada recuperación de recuerdos. Backup SQLite usa
páginas y deadline de 120 s; DBs grandes pueden requerir ajuste y medición antes
de despliegue. No se promete latencia constante ni soportar todo volumen.

### Qué se pudo comprobar de otros proyectos

En Hermes, `post_update.py` elimina backups de configuración **sin cambios** en
una ruta de recuperación; eso no es borrar siempre el backup de la DB al tener
éxito. `hermes_cli/backup.py` poda archivos propios solo tras un archivo completo
y cuando se pide retención keep; un backup incompleto no desplaza al último bueno.
Su guard de state.db comprueba integridad sin repararla automáticamente. Fuentes:
[post_update.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/post_update.py),
[backup.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/backup.py).

Del código público de OpenAI Codex se consultó
[state/src/migrations.rs](https://github.com/openai/codex/blob/main/codex-rs/state/src/migrations.rs):
usa migradores SQLx separados por componente y validación de checksums conocidos.
Esa fuente NO permite afirmar que borre backups de DB después de actualizar, ni
describe la política interna de almacenamiento de ChatGPT/OpenAI. No se atribuyen
a terceros garantías que no se verificaron.

## Cierre de recuperación y lenguaje: revisión posterior

Se ensaya restauración del backup en temporal y se compara huella del dump lógico
del snapshot, además de integridad y SHA256 del archivo. La comparación usa
transacción de lectura. Esto mide restaurabilidad del snapshot en este entorno,
no demuestra semántica de una migración ni compatibilidad con un binario anterior.

El updater registra `rolled_back` cuando las comprobaciones de rollback tienen
éxito y `recovery_required` cuando no puede verificarlas; en el segundo caso conserva
la barrera y el backup. El mantenimiento administra conexiones internas mediante
lease compartido por cliente y exclusivo durante preparación; el hijo autorizado
recibe un token. No se borran archivos de lock para evitar romper exclusión por
cambio de inode.

Un proceso externo que abra SQLite directamente puede ignorar el lease: el updater
no lo inspecciona ni lo detiene y no puede prometer exclusión universal frente a
ese cliente no cooperativo. El host MCP es externo; debe reconectar después del
éxito. Ante rollback no verificado, no reiniciar BioRAG y pedir soporte. La
recuperación asistida siguiente es un mecanismo separado para preservar evidencia,
no sustituye la restauración automática ni certifica un entorno idéntico al previo.

```sh
python biorag.py recovery --receipt /ruta/al/recibo.json
python biorag.py recovery --receipt /ruta/al/recibo.json --stage
```

El segundo comando toma mantenimiento y conserva una copia del estado actual y
una restauración separada del backup. No cambia BIORAG_PATH, Git ni pip. Si hubo
recuerdos posteriores, quedan conservados, no se fusionan ni se descartan. Esto es
recuperación asistida preparada, NO rollback integral automático completado.

En paralelo, el registro MCP de correcciones ahora es estructurado, sin parser
lingüístico en el camino nuevo. Hay E2E stdio real con mensaje japonés y los seis
modos. El adaptador español Python legado no se retira porque tiene consumidores
y propuestas persistidas compatibles. Se migraron scripts E2E activos al contrato
MCP nuevo, sin alterar resultados históricos como si fueran nuevas mediciones.
