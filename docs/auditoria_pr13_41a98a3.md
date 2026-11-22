# Auditoría PR #13: `41a98a3`

## Resumen

Se confirma la corrección del caso anterior de byte WAL en la secuencia probada, se reproduce la mejora de rendimiento y pasan 816 pruebas. Sin embargo, una intercalación artificial adicional muestra que la sonda de metadata se puede guardar asociada a una firma calculada **antes de un cambio directo del WAL**. A diferencia del escenario anterior, en este caso la siguiente lectura no detecta ese cambio. Es una limitación separada de la ventana de commit-publicación y debe comunicarse antes de aceptar o integrar el PR.

La prueba usa manipulación directa y deliberada de bytes de una DB temporal; no es un commit válido SQLite, no demuestra que la base real esté corrupta ni estima frecuencia o efecto de un fallo real de almacenamiento. No demuestra que un escritor antiguo mediante SQL produzca esta intercalación. Si el alcance acordado excluye cambios directos del WAL, documentarlo expresamente en vez de afirmar cobertura general. La ventana commit-publicación para commits SQLite sin protocolo permanece, como en auditoría `2818e72`.

## Verificación positiva

PR #13 head `41a98a3947b797535c047e2129913d703e6eaeed`: GitHub informa `OPEN`, `CLEAN`, `MERGEABLE` y 10 jobs verdes en dos ejecuciones. `git diff --check 4747ca8 41a98a3` pasa. En árbol limpio aislado Linux ejecutamos **62 pruebas focales** y la **suite completa de 816**, todas pasaron; completa 407,19 s. Repetimos 5 regresiones (WAL byte, in-place principal, checkpoint tamaño constante, WAL reutilizado, commit coordinado seguido de raw) además con SQLite 3.53.4 inyectado desde `pysqlite3==0.6.1`: 5 pasaron. Esta inyección no es la configuración de producción ni demuestra compatibilidad de todas las APIs.

Microprueba aislada SQLite estándar 3.40.1 con clasificador de versión simulado a 3.51.3, WAL 18.589.472 bytes, 30 lecturas protegidas, caché caliente: **0,010 s**. Es un solo escenario, no benchmark general de producción. Se confirma por lo probado que agregar stat de WAL no impidió la mejora de velocidad.

## Intercalación de instantánea

En el método `_remember_connection_snapshot`, la firma completa se captura dentro de `database_read_window`; posteriormente se guarda `_cheap_file_probe()` como parte del snapshot. Una sonda en DB sintética fuerza este orden (hook de prueba temporal, sin modificar código candidato):

1. Se inicializa motor WAL, tabla y lectura protegida. Se inicia un INSERT coordinado y se llama al `commit()` normal del wrapper.
2. El hook deja calcular `_file_change_signature()` y justo después cambia un byte en el WAL vía descriptor de archivo, sin commit SQL. Confirma que el digest WAL cambió. La firma antigua retorna a `_remember_connection_snapshot`, que luego almacena el stat posterior al cambio.
3. La siguiente lectura protegida, con el mismo stat del paso 2 y sin cambio de época/data_version, retorna normalmente `(1,)` en `41a98a3`. Control pareado: alteración directa después de completarse todo el snapshot provoca `SQLiteDatabaseIdentityChangedError`.
4. En `2818e72`, la lectura posterior lanza `SQLiteDatabaseIdentityChangedError` en ambos brazos; no prueba que ese commit sea una solución completa.

Reproducido con SQLite estándar Linux 3.40.1 forzando solo el clasificador de versión a 3.51.3 para permitir WAL sintético, y con SQLite 3.53.4 de pysqlite3 inyectado como `sqlite3`. La secuencia es determinista mediante hook en el mismo proceso; no se midió ocurrencia natural ni múltiples procesos. Un byte directo puede invalidar checksum, y no se comprobó cómo SQLite detectaría/rechazaría la alteración al reabrir. La observación concreta es que **el guard de BioRAG no alertó en esa lectura**.

Explorar una instantánea consistente y verificar antes/después sin asumir que un stat sea prueba de identidad de contenido. Validar carreras, falsos positivos por commits/checkpoints legítimos y el coste antes de recomendar una corrección. Es incorrecto decir que tamaño+mtime+ctime equivalen a verificar contenido en todos los sistemas o bajo toda concurrencia; los comentarios mencionan inode aunque `_cheap_file_probe` solo devuelve tamaño y tiempos.

Evidencia privada sintética `auditoria_pr13_41a98a3.tar.gz`, Drive ID `1G7T7prbC_Q8lK_LiuwMRYIMFN-Pyylkw`, SHA-256 `edb53637edb07334539a7d6086d34567d3c2ca1502d2124c9484a20ca922bdbf`. No se fusionó ni se modificó `master` ni la DB original.
