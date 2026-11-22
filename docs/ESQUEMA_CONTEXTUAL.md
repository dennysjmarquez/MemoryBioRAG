# Ciclo de vida de las tablas contextuales

La estructura y la activación de una función son cosas distintas. Las cinco tablas
`ctx_claims`, `ctx_revisions`, `ctx_proposals`, `ctx_approvals` y `ctx_synapses`, más
el índice de contexto, forman parte del esquema instalado. Se aseguran tanto en
`_crear_estructura_cerebral` (DB nueva) como en `_crear_tablas_nuevas_si_faltan`
(DB existente), sin depender de flags. La instalación de paquetes por sí sola no
abre una DB: la inicialización del core prepara el archivo elegido.

`BIORAG_TEMPORAL_PROTOTYPE=0` no borra ni evita crear tablas: desactiva el contrato
nuevo de búsqueda. `BIORAG_CORRECTIONS=0` desactiva el servicio de correcciones,
no la migración del core. Datos aprobados existentes se conservan.

La definición única está en `core/contextual/schema.py`. El servicio de
correcciones usa esa misma definición para soportar conexiones independientes.
No hay dos copias de DDL. Se crean las cinco tablas aunque solo se abra el ledger;
no se insertan propuestas ni afirmaciones automáticamente.

La primera llamada a recordar puede inicializar el core y, por ese motivo,
ejecutar la migración de arranque. No es el selector de búsqueda quien la realiza:
los lectores contextuales siguen sin DDL ni confirmaciones. Una conexión directa
que omita el arranque puede encontrar ausencia de tablas: debe informar falta de
evidencia, no intentar escribir en medio de una lectura.

La migración es aditiva, idempotente y válida con WAL o DELETE, sin cambiar el
journal_mode. Sin transacción previa toma BEGIN IMMEDIATE para serializar
inicializadores. Dentro de una transacción existente usa SAVEPOINT y no confirma
trabajo ajeno. Ante errores se revierte la migración y se propaga el error.

Completa esquemas parciales con columnas compatibles y conserva filas. Una tabla
con columnas incompatibles produce CONTEXTUAL_SCHEMA_INCOMPATIBLE y requiere
backup y migración explícita; no se borra para forzar el arranque. Esto no es un
reparador universal de corrupción ni verifica todos los constraints históricos.
DB de solo lectura, bloqueos persistentes o permisos insuficientes requieren acción
operativa: los errores no se ocultan. No se promete soportar toda alteración manual.

Crear almacenamiento vacío NO proporciona evidencia de vigencia. Es necesario
registrar y aprobar hechos/sustituciones para resolver consultas contextuales.

## Verificación ejecutada

`python -m unittest discover -s tests -p test_contextual_schema_lifecycle.py -v`

10 pruebas aprobadas con DBs sintéticas: creación y reapertura con flags 0,
WAL/DELETE, esquema parcial, preservación de datos y transacción exterior,
rollback por denegación DDL, columnas incompatibles, solo lectura, concurrencia,
servicio compartido y lector sin DDL. La presencia incondicional de los hooks en
ambas rutas core se comprueba por AST; no equivale a ejecutar toda la instalación.
Evidencia posterior: suite global 984 passed/18 skipped (contrato temporal
explícitamente desactivado por compatibilidad), 105 focales con contrato nuevo
y E2E MCP stdio estructurado aprobados. QA 921 en copia se registra aparte;
ver ACTUALIZACIONES_Y_CICLO_DE_VIDA.md para alcance y pendientes.

## Instalación y actualización: flujo de usuario

Ruta real comprobada: `SQLiteMemoryBioRAG.__init__` en
`core/memory_store.py` llama `_crear_estructura_cerebral` si falta `largo_plazo`
y `_crear_tablas_nuevas_si_faltan` también para DBs existentes. Ambas funciones
delegan en `core/memory/schema.py`. No hay que añadir SQL a la fachada.

El instalador `python install.py` instala/actualiza el código y las dependencias,
ejecuta el checkpoint de instalación y después `python -m core.migrate` usando
su mismo Python y directorio de instalación. Si falla la migración/verificación,
el instalador termina con error y NO imprime «Instalación completada».

El comando nuevo también se puede ejecutar explícitamente tras actualizar un
wheel con pip, usando el Python del entorno instalado:

```sh
python -m core.migrate
# DB alternativa explícita, si corresponde a esa instalación:
python -m core.migrate --db /ruta/a/memory_biorag.db
```

Respeta la resolución de rutas del core (`BIORAG_PATH` y fallback del producto).
Para DB existente crea un respaldo SQLite en `backups/` junto al archivo antes
de inicializar el core; el backup incluye cambios WAL confirmados, no es una
copia incompleta del archivo principal. Una DB nueva se inicializa por la misma
ruta del core, sin fabricar una tabla largo_plazo mínima. Verifica después las
columnas de las cinco tablas contextuales. Conserva backups y propaga errores;
no restaura automáticamente sobre la DB ante un fallo.

`pip install --upgrade ...` por sí solo instala código: deliberadamente no usa
hooks de empaquetado para abrir datos del usuario. Ejecutar la migración tras
actualizar prepara y verifica inmediatamente el esquema; el siguiente arranque
del core también tiene la migración idempotente como red de seguridad. Hay que
reiniciar el cliente MCP para que deje de ejecutar el proceso/código anterior.
No copiar una DB de ejemplo encima de la memoria del usuario.

El avisador existente `core/mcp_server/update_checker.py` consulta de forma no
bloqueante una política estable y tags aprobados (intervalo predeterminado 24 h).
Un commit en master no equivale a una actualización anunciable. Sin publicación
válida, sin red o con BIORAG_UPDATE_CHECK=0 no se garantiza aviso. El mensaje ahora
recuerda migrar con el Python de la instalación y reiniciar MCP. No descarga ni
instala cambios sin autorización.

El smoke del wheel `scripts/smoke_instalacion_mcp.py` incorpora comprobación de
las cinco tablas en la DB temporal tras uso/reinicio. Esa ampliación está escrita,
pero no ejecutada en este entorno sin dependencias MCP instaladas.

Pruebas adicionales ejecutadas:
`python -m unittest discover -s tests -p test_install_schema_migration.py -v`
(5 aprobadas). Cubren orquestación, backup WAL, preservación ante fallo y
verificación negativa con inicializador sintético; no son una instalación real
ni sustituyen E2E de wheel. Total de esta revisión: 15 pruebas focalizadas
aprobadas en esa fase, sin tocar DB viva. La validación posterior está resumida
arriba; wheel completo sigue pendiente.
