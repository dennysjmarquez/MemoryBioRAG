# Comparación adicional `run04` y análisis causal de fallos comunes

## Revisión y método

Código de proyecto bajo prueba: **`41e1793abb9e346f01e619c17611dc158ff27f4a`**. Esta medición adicional usa ese commit exacto (no confundirlo con `212ca78c5fbcc4915bd7e2080a4c9eb117b5550d` de la primera comparación pública). Los dos brazos copiaron el mismo conjunto de fuentes rastreadas de esa revisión; no se editó ningún test. Solo se sustituyeron las importaciones `sqlite3` por `pysqlite3` en la copia candidata. Ambas copias recibieron byte por byte la misma base sintética de tres nodos; los archivos SQLite originales se excluyeron.

Se corrigió el runner para que `--python` seleccione también el intérprete del propio proceso de reproducción: se relanza con el Python elegido antes de importar BioRAG y construir la fixture, y conserva la ruta del symlink del venv para que CPython cargue su `pyvenv.cfg`. De este modo, creación de fixture, inspección de versiones y pytest usan Python 3.11.2 del mismo venv; pytest 9.1.1 y las dependencias fijadas por `requirements.txt`. `pysqlite3==0.6.1` se mantuvo en un target aparte, no en las dependencias del proyecto.

Los detalles íntegros se conservan fuera del control de versiones en `.private_evidence/sqlite_pysqlite3_ab_20261103_run04_actual/`, junto a los resultados de una selección dirigida y un probe JSON. El script público acepta `--pytest-target` repetido para ejecutar selecciones puntuales idénticas en ambos brazos.

## Suite sin modificar

| Resultado | SQLite estándar | pysqlite3 0.6.1 |
|---|---:|---:|
| Casos contabilizados | 757 | 757 |
| Pasadas | 728 | 728 |
| Fallidas | 13 | 13 |
| Errores de setup | 7 | 7 |
| Omitidas | 9 | 9 |
| IDs exclusivos por brazo | 0 | 0 |

Esto no reproduce los conteos históricos de la comparación anterior ni es una comparación sobre el mismo commit que `run03`. En el commit actual ensayado, baseline y candidato vuelven a tener los mismos IDs fallidos y de error; no hay señal de regresión exclusiva del driver en esta corrida. Fallos/errores comunes no equivalen a aprobar la calidad del código: requieren la siguiente lectura causal.

## Análisis antes de atribuir

Los fallos comunes no tienen todos la misma causa. La evidencia de salida de tests y sus fixtures permite distinguir:

1. **Siete errores de setup en `test_escala_motor`:** la fixture sintética no incluye `principio_naturaleza_agente` ni sus dimensiones. `memoria_crecida` comprueba explícitamente esas dimensiones y falla antes de entregar la fixture. Es una incompatibilidad de datos de test con la fixture, no evidencia sobre diferencias entre drivers.
2. **Cinco fallos de recuperación de Concept Hub:** los tests exigen conceptos concretos (por ejemplo `leccion_control_flujo_codigo_preexistente`) y retornan listas vacías con tres nodos sintéticos. La base sintética no contiene esos nodos ni bridges asociados; no es un test aislado de DB-API.
3. **Tres fallos de convergencia:** sus tests copian la fixture de snapshot. Dos esperan resultados para contenido `biorag version actual` y el concepto `version_actual_biorag`, ausentes en la fixture. El otro consulta una identidad histórica y espera más de cinco candidatos; ninguno existe en los tres nodos. Las fallas por mapa de bonos vacío/resultado vacío son efecto de no tener esos candidatos, no una diferencia observada entre drivers.
4. **Un fallo de autoexpansión MCP:** los dos brazos obtienen `parafrasis_list=None` donde el test espera expansiones PMI. El test necesita coocurrencias léxicas de la consulta «arquitectura frontend memoria agente»; la fixture de tres textos genéricos no contiene ese corpus ni las parejas PMI necesarias. Es data-dependent.
5. **Tres fallos SDM:** los tests se declaran explícitamente de datos reales y consultan nodos con dimensiones y vectores `nodos_sdm`; la fixture de prueba no contiene esos datos. Los síntomas son cero nodos/vecinos/hits, no excepciones de SQLite.
6. **Un fallo de `test_neurona::test_db_vacia_no_falla`:** no se debe etiquetar simplemente como «falta de datos». La aserción de ese test pasa cuando se ejecuta aisladamente en baseline y candidato. En la suite completa, la preparación de `test_escala_motor` establece `BIORAG_NEURONA=0` y luego falla antes del `yield`; por tanto, su bloque de restauración posterior al `yield` no corre y la variable contamina el test siguiente, que observa fase `apagada`. Una comparación dirigida en ambos drivers, ejecutando primero `tests/test_escala_motor.py` y luego ese nodeid, reprodujo los siete errores de preparación y un fallo de contaminación en ambos brazos; ejecutando solo ese nodeid, pasó en ambos. Esto revela fragilidad de aislamiento/teardown en el test setup ante la fixture reducida, no un cambio del driver.

No se modificó ningún test para obtener esta clasificación. Tampoco se reemplazó la fixture por datos personales o por filas con IDs gold artificiales: eso podría hacer parecer verdes pruebas que en realidad requieren los datos de integración correspondientes. No se concluye que cualquier fallo común sea automáticamente culpa de la fixture; el caso de la neurona demuestra la falla secundaria de aislamiento.

## Probe de excepciones y otros contratos

Reejecuté `sqlite_compat_probe.py` bajo el mismo venv. Las versiones observadas fueron stdlib SQLite **3.40.1** y pysqlite3 **0.6.1 / SQLite 3.53.4**. De 13 casos sintéticos, los diez no relacionados con restricciones fueron exactamente iguales. Para UNIQUE, CHECK y FOREIGN KEY coinciden `IntegrityError`, texto, código primario 19 y estado de transacción; difieren los metadatos de código extendido: 2067/275/787 en stdlib y 19 (`SQLITE_CONSTRAINT`) en pysqlite3. `threadsafety` difiere (3 vs 1), ambos reportan `THREADSAFE=1` y FTS5; la prueba limitada de conexión compartida inserta 1600/1600 filas en ambos. Sigue siendo una prueba acotada, no garantía general de concurrencia.

## Conclusión y límites

La comparación adicional no muestra resultados exclusivos del candidato. Los fallos comunes se explican principalmente por fixtures diseñadas para snapshots reales; adicionalmente, se identificó una contaminación de variable de entorno causada por una fixture que falla antes de su `yield`. Esta comparación no valida regresiones históricas de IDs perdidos ni sustituye una prueba con la fixture de integración que esos tests esperan. No se abrió ni modificó ninguna base original. No se modificaron tests, el instalador ni dependencias del proyecto.
