# Auditoría E3: paráfrasis MCP `b9d7962`

## Alcance y dictamen

Se auditó el commit publicado `b9d796266614fc857550c6726f2643b0368e5bd2`, hijo de `035cf7875202ba03fdbbcbf6d9db4df8ea5b85d5`. El objeto `09ff763` no estaba disponible: no se afirma identidad byte a byte entre ambos commits. El diff publicado añade una fe de erratas y modifica un runner sintético; no toca `core/`. `git diff --check` y compilación pasaron.

La reproducción de seis sesiones MCP stdio respalda los agregados observados en este fixture, no una conclusión general sobre paráfrasis. **Pedir al operador una corrección no bloqueante de la tabla:** el informe dice «casos con respuesta de recordar: 3», pero el runner registró respuesta con forma de búsqueda en 6/6; tres casos contienen resultados. Además, llamar «útiles» a esos resultados en la tabla va más allá de lo que adjudica el fixture; «con resultados» es la descripción comprobada. La evidencia no queda invalidada por esa errata.

## Reproducción

Se extrajo el commit en un directorio temporal aislado, con seis copias sintéticas, `PYTHONHASHSEED=0`, `HOME` aislado y FastMCP stdio real. El runner terminó con código 0. En los seis casos, la herramienta de apertura devolvió `status=ok`, la respuesta de `recordar` tuvo forma de búsqueda y no se registraron banderas MCP, excepciones Python escapadas ni errores de snapshot. Las respuestas de búsqueda no incluyeron `status` crudo; eso no es, por sí solo, una señal de error.

- La sonda FTS5 directa encontró el objetivo mediante el término de paráfrasis en los casos normal y estricto; la consulta principal no lo encontró en esa sonda.
- MCP devolvió `total=0` en normal y estricto; el control sin paráfrasis también devolvió `total=0`. No se demuestra que FTS5 y MCP tengan el mismo flujo, ni un resultado por paráfrasis atribuido erróneamente a otra capa. El contraste no permite una conclusión causal general.
- El aviso de brecha apareció en 6/6, incluidas las 3 respuestas con resultados. El fixture no mide utilidad humana. Los tres resultados observados no traían fecha legible.
- El manifiesto sintético reproducido tiene SHA-256 `6a5fb18b0053594b37c478a68231caae318091b18da668339f01cddd484c92e8`, igual al publicado para el manifiesto del operador. Las dos huellas del propio manifiesto de la réplica coinciden con sus archivos. El archivo de resultados de la réplica tiene SHA-256 `579fd9ee31213b983f283901d08dee6168e1e84095e07c2cee1e59996d66fe6c`, distinto del declarado por el operador; su evidencia privada no está disponible para comparar bytes o adjudicar la diferencia. Los agregados reproducidos coinciden en los aspectos enumerados, no se afirma igualdad de artefactos completos.
- La evidencia de esta reproducción se conserva en `google_drive/auditoria_neuronas/auditoria_e3_parafrasis_b9d7962.tar.gz`, SHA-256 `13e6574c0704d503a4c759ae6683ca17422e2936d31086b407b475eee014e5ab`. Contiene exclusivamente fixture y salidas sintéticas; no bases originales.

## Límites

Se ejecutó el runner del operador, no un segundo arnés independiente. La sonda SQL se ejecuta después de la llamada MCP, sobre la copia correspondiente; no demuestra que el motor haya usado ese camino. Los snapshots cubren nueve tablas físicas de grafo y una proyección, no toda SQLite. No se inyectaron errores internos ni se volvió a ejecutar la suite completa de 824 pruebas informada por el operador. Sus artefactos anteriores y la evidencia privada de su corrida no estuvieron disponibles aquí; por eso no se ratifican sus hashes ni su preservación. Esta auditoría no implica que todas las paráfrasis fallen o funcionen en corpus reales.

La corrección es documental: mantener E3 abierto, no modificar el motor ni filtrar asociaciones; no avanzar a E4 hasta la decisión acordada. La investigación de protección SQLite continúa por separado.
