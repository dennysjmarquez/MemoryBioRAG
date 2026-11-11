# Spec 008 — Acceso SQLite seguro y consistente para BioRAG

## Contexto y objetivo

BioRAG comparte una base SQLite entre MCP, CLI, dashboard y procesos de mantenimiento, pero hoy varios consumidores abren conexiones por separado y la fachada principal reutiliza una conexión y un cursor entre hilos. Esta funcionalidad define un contrato uniforme para preservar los datos confirmados, hacer visibles los errores y evitar que los procesos continúen operando sobre una generación/ruta distinta de la que abrieron. No intenta reparar bases de datos ni atribuye una causa histórica de corrupción sin una reproducción verificable.

## Usuarios / actores

- El usuario local que ejecuta BioRAG desde varias ventanas, agentes o interfaces.
- El servidor MCP, CLI, dashboard y daemons de BioRAG que leen o escriben el mismo archivo.
- Operadores que configuran la ruta de datos y actualizan/detienen procesos.

## Historias de usuario

- H1: Como usuario de BioRAG, quiero que sus interfaces coordinen el acceso a la misma base para que los cambios confirmados estén disponibles sin que una conexión o cursor compartido mezcle operaciones concurrentes.
- H2: Como operador, quiero que cada proceso detecte el runtime SQLite efectivo y rechace un modo inseguro en vez de ocultar el error o continuar escribiendo.
- H3: Como usuario, quiero ver un error accionable ante bloqueo, sustitución de archivo o integridad dudosa, y que BioRAG no descarte ni repare automáticamente mis datos.
- H4: Como responsable de seguridad, quiero que el acceso a la base respete el menor privilegio y que los errores/logs no filtren el contenido de recuerdos.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-1: CUANDO un consumidor de BioRAG abre una conexión de escritura, EL SISTEMA identificará y registrará el runtime SQLite efectivo de ese proceso.
- RF-2: SI el runtime es vulnerable al WAL-reset bug y la base está en WAL, ENTONCES EL SISTEMA rechazará escrituras por defecto sin cambiar la base existente; solo permitirá una transición no-WAL tras opt-in explícito del operador y confirmación de exclusividad SQLite, y si no puede adquirirla devolverá un error visible y accionable.
- RF-3: EL SISTEMA no eliminará, recreará, restaurará ni reparará automáticamente la base, el journal ni los sidecars ante un error de apertura, bloqueo o integridad.
- RF-4: CUANDO un proceso de BioRAG detecte que la ruta o generación del archivo cambió mientras conserva una conexión, EL SISTEMA impedirá que ese proceso siga escribiendo con la conexión antigua y notificará el motivo.
- RF-5: MIENTRAS múltiples consumidores compatibles lean o escriban la misma base local, EL SISTEMA preservará todas las transacciones confirmadas y resolverá la contención con espera acotada; agotada la espera, devolverá un error explícito sin reintentos infinitos.
- RF-6: SI SQLite informa un error de formato/integridad (incluidos `SQLITE_CORRUPT` y `SQLITE_NOTADB`), ENTONCES EL SISTEMA detendrá nuevas escrituras en esa conexión y propagará el error sin clasificarlo como contención transitoria.
- RF-7: EL SISTEMA usará parámetros para valores SQL; cualquier identificador dinámico se validará con una allowlist, y los mensajes/logs de error no incluirán contenido de recuerdos ni secretos.
- RF-8: CUANDO MCP, CLI, dashboard o daemons de BioRAG accedan a datos, EL SISTEMA resolverá la ruta desde una fuente canónica y expondrá el runtime, ruta efectiva (redactada cuando corresponda), journal mode y tiempos de espera en diagnóstico operativo.

## Requisitos no funcionales

- El funcionamiento normal permanecerá local y no requerirá un servicio externo ni una conexión de red.
- La implementación mantendrá una huella pequeña de CPU y memoria compatible con una computadora de usuario; cualquier caché o buffer tendrá un límite explícito.
- La política será compatible con los sistemas operativos soportados por el repositorio (Linux, macOS y Windows) o declarará de forma explícita una limitación si una defensa depende del sistema operativo.
- Una solución no se considerará validada solo por `integrity_check`: pruebas separadas cubrirán hilos, procesos, bloqueos, transiciones de journal y reemplazo de archivo usando fixtures temporales.
- Los mensajes y documentación dirigidos al usuario estarán en español.

## Casos límite

- Base nueva, `:memory:`, modo WAL preexistente, journal/sidecar presente y más de un proceso conectado.
- Contención transitoria `BUSY`/`LOCKED`, timeout agotado, operación de checkpoint y modos WAL/rollback.
- Archivo de base, WAL o SHM renombrado, borrado o sustituido mientras hay conexiones antiguas abiertas.
- Ruta relativa, symlink, cambio de `BIORAG_PATH` o consumidores lanzados desde directorios distintos.
- Error de permisos, disco lleno, `SQLITE_IOERR`, `SQLITE_CORRUPT` y `SQLITE_NOTADB`; los errores de hardware/filesystem se reportan, no se prometen reparar.
- Runtime SQLite de cada proceso distinto (Python del sistema, `.venv`, daemon detachado o cliente externo).
- Varios daemons o MCP iniciados simultáneamente y PID obsoleto/reutilizado.

## Fuera de alcance

- Recuperación/reparación de bases ya corruptas, recuperación de archivos borrados, backup externo o sincronización remota.
- Protección frente a fallo físico de disco, pérdida eléctrica, defectos del filesystem o uso de SQLite sobre NFS/SMB; esas configuraciones no se declararán seguras sin validación específica.
- Cifrado en reposo: SQLite estándar no lo proporciona; el control de acceso al archivo depende de permisos/ACL del sistema operativo.
- Actualizar o detener automáticamente procesos preexistentes del usuario, eliminar sidecars originales o migrar una base de producción sin autorización.
- Garantizar la seguridad de clientes externos que abran la base saltándose las interfaces de BioRAG.
- Certificar cumplimiento completo de OWASP Top 10. La funcionalidad solo aplicará controles relevantes al acceso SQLite y documentará los riesgos web/operativos observados por separado.

## Criterios de finalización

- Todos los RF tienen pruebas automáticas verdes sobre bases temporales.
- Las pruebas de concurrencia comprueban datos esperados e `integrity_check` después de escrituras concurrentes, sin tocar la base del usuario.
- Cada apertura de escritura dentro del código de producción pasa por la política común o queda documentada como excepción de solo lectura/externa.
- La documentación identifica qué procesos abren cada base, cómo resuelven la ruta y cómo se detienen/cambian de generación.
- La suite completa prescrita por el repositorio pasa; si el entorno no permite ejecutarla, el bloqueo y el subconjunto validado quedan documentados.
- La revisión final distingue hechos observados, hipótesis y límites; no se afirma causalidad histórica ni protección absoluta.

## Seguridad y límites de confianza

- BioRAG tratará `BIORAG_PATH` como configuración confiable del operador, nunca como ruta controlada por una solicitud remota.
- Las interfaces web/MCP no expondrán acceso SQL arbitrario ni permitirán elegir identificadores o rutas sin validación.
- Los mensajes de diagnóstico expondrán tipo/código de error y acción recomendada, no el texto de recuerdos.
- Las consultas SQL con entradas del usuario usarán placeholders; se revisarán por separado los fragmentos de SQL dinámico.
- El acceso al archivo seguirá sujeto a permisos/ACL locales. El modo de apertura no constituye autenticación ni aislamiento multiusuario.
- OWASP A01/A03/A05/A09 se consideran solo en la medida relacionada con autorización/ruta, inyección, configuración segura y logs; el dashboard actual y el transporte MCP requieren una evaluación de seguridad web independiente.

## Dudas abiertas

- Ninguna para el contrato inicial. El runtime local indicado por informes anteriores (SQLite 3.45.1) no se toma como versión de todos los procesos: cada consumidor debe informar su runtime efectivo.
