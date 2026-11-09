# Auditoría PR #13: secuencia de commits WAL `9b39f4b`

## Dictamen

No recomiendo fusionar todavía. A pesar de CI verde, una prueba sintética muestra que una escritura SQLite sin protocolo puede quedar aceptada por la comprobación de lectura cuando va precedida de un commit coordinado en WAL. No se demostró corrupción, ni acceso de una persona maliciosa, ni que los datos reales tengan el problema; la brecha contradice la protección que se busca para clientes antiguos/raw y merece resolver o decidir expresamente tras evaluar límites.

## Alcance y CI

PR #13, head `9b39f4b47759957f5f0c7b983a521d97c0663b56`, `master` como base. GitHub informa `CLEAN`, `MERGEABLE` y 10 checks exitosos en los dos runs reportados para Python 3.11/3.12 y matriz Ubuntu/macOS/Windows. Son éxitos de los pasos ejecutados; no prueban casos omitidos por plataforma. `git diff --check 664292e 9b39f4b` pasó. En Linux, copia aislada del commit: 54 pruebas focalizadas de SQLite, daemon, rutas, singleton y conexiones por hilo pasaron. La suite completa no se repitió localmente en este commit. Ninguna DB original se abrió.

## Experimento pareado, WAL sintético

Cada brazo usó una DB nueva distinta, `SQLiteMemoryBioRAG` abierto, una tabla de prueba y un cursor retenido; se observó una lectura inicial de cero filas. Después:

1. **Control:** un cliente `sqlite3.connect` sin protocolo insertó y confirmó una fila. La siguiente lectura protegida lanzó `SQLiteDatabaseIdentityChangedError`.
2. **Contraste:** un escritor `open_writer` insertó y confirmó una fila; luego, antes de que el lector volviera a validar, un cliente raw insertó y confirmó otra. La siguiente lectura protegida **no lanzó error y devolvió ambas filas**.

El contraste tuvo lugar tras la publicación del commit coordinado, no necesariamente dentro de su ventana. La firma atestiguada cubre el archivo principal y excluye WAL/SHM; en esta secuencia las escrituras WAL dejaron la firma principal igual, mientras la época coordinada había avanzado. La condición de aceptación permite que esa atestación coincida con el archivo principal aunque el WAL haya recibido otro commit: explicación compatible con el código y las observaciones. Se requiere instrumentación adicional para cualquier conclusión causal más fina. La prueba no establece que estos contenidos sean inválidos en términos semánticos: muestra una escritura **no coordinada aceptada sin la alerta que sí apareció en el control**.

Se reprodujo el mismo resultado dos veces: con `sqlite3` estándar SQLite 3.40.1 sobre Linux, forzando únicamente el clasificador de versión a 3.51.3 para permitir WAL en la fixture; y con SQLite 3.53.4 de `pysqlite3==0.6.1` inyectado temporalmente como `sqlite3` antes de importar el candidato. El segundo caso usa una biblioteca distinta de la ruta estándar del candidato: confirma el fenómeno en ese entorno experimental, no prueba identidad API ni compatibilidad de producción. Ambos son DB temporales, no pruebas de la DB real. El código no intercepta escritores que omiten el protocolo; el usuario ya conoce esa limitación, pero esta sonda muestra que además puede **no detectar** un commit raw después de uno coordinado y antes de la siguiente observación.

Antes de merge: reproducir y decidir contractualmente el tratamiento de escrituras raw/antiguas, probar el caso en WAL con runtimes soportados y escenarios de checkpoint/caída/concurrencia, sin deteriorar la disponibilidad de commits autorizados. Evitar afirmar que un advisory lock impide clientes externos. La propuesta y el diff requieren revisión; no cambiar ni migrar bases reales. El SQLite corregido de cada proceso y la ruta de actualización local siguen pendientes.

Evidencia privada sintética: Drive ID `1-OFlF4cRpwxv3lymtGeoqFxje5rYTpC9`, `auditoria_pr13_9b39f4b.tar.gz`, SHA-256 `52c60f2d3e2fbe913b930ce2e9a5fd75c12aa5189accf6935509d916186bcf84`, con sondas y logs. No se ejecutó merge ni se modificó `master`.
