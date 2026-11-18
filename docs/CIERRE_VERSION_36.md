# Cierre técnico de BioRAG v36.0 — resumen de sesión

**Fecha del registro:** 2026-10-21 (UTC)
**Estado:** v36.0 se considera cerrada técnicamente por decisión de Dennys; la rama está disponible en `origin`, pero no se ha integrado en `master` ni etiquetado. La auditoría del plan sigue incompleta: E3 continúa abierta y E4/modularización fase 2 no están verificadas. El usuario hará el match y gestionará la etiqueta B36; este documento no afirma que esos pendientes se hayan cerrado.
**Propósito:** conservar el contexto de la revisión y distinguir el cierre técnico declarado de la auditoría pendiente del alcance y del trabajo futuro.

> Esta nota no prueba merge, publicación, etiqueta ni aprobación final de la integración. En esta revisión se repitieron la QA oficial y el smoke focal de Concept Hub en copias temporales; el resultado de pytest 852/18 corresponde a una corrida aislada registrada previamente. El reloj del runner estampó la QA con `2026-11-18T01:49:37`, aunque la fecha de sesión de referencia es `2026-10-21`; esa marca se conserva como salida del runner, no como fecha fiable de la sesión.

## 1. Decisión de versiones

La numeración vigente acordada es:

| Versión | Alcance | Estado |
|---|---|---|
| **v36.0** | Motor de búsqueda y Concept Hubs con correcciones acotadas de escala, evaluación y base operativa descritos aquí y en el README. | Cierre técnico declarado; E3 sigue abierta y E4/modularización fase 2 no están verificadas. La rama queda disponible para el match y tag que realizará el usuario; no se hicieron aquí. |
| **v37** | Plan de **Memoria Episódica + Recuperación por Intención**, antes rotulado v36. | Trabajo futuro y propuesta; no se implementó como parte de v36. |
| **v38** | Etapa de trabajo neuronal que antes se rotulaba v37. | Etapa posterior; no se presenta como implementada en v36. |

El rótulo de una versión no equivale a publicación. v36.0 es la última base antes de las etapas v37 y v38. La rama ya está subida a `origin`; no se hizo merge a `master` ni se creó una etiqueta, y este informe no resuelve por sí solo los pendientes del plan.

## 2. Qué se hizo en esta sesión

### 2.1 Revisión del plan de memoria episódica

Se evaluó la propuesta de crear episodios persistentes con orden de eventos y después usar tipos epistemológicos para consultas como «el último error», «un ejemplo» o «la decisión». La conclusión fue que puede cubrir una brecha real —reconstruir eventos relacionados y su secuencia—, pero no es la primera capacidad temporal del motor y el plan aún no demuestra que mejore el ranking general.

Capacidades ya observadas en el código:

- `core/memory/episodes.py` contiene `_ts_nodo` (usa `creado_en` o, en su defecto, `ultimo_acceso`), `_expandir_episodio_temporal` (expande a nodos cercanos en el tiempo y compatibles en categorías/dimensiones) y `_afinidad_temporal_pool` (señal por agrupación temporal). Son heurísticas; no son episodios persistentes explícitos vinculados a sesiones.
- `core/memory/search.py` incluye afinidad temporal y expansión temporal opcional.
- `core/mcp_server/search.py` permite ordenar por recencia/antigüedad y filtrar con `dias`, `desde` y `hasta`.
- `core/mcp_server/session.py` y `core/mcp_server/_shared.py` mantienen `_sesiones_activas` en memoria: `contexto_inicio` guarda un timestamp y `contexto_fin` elimina la sesión y puede consolidar un resumen.
- `core/mcp_server/prompt.py` ya distingue dimensiones `intencion` y `epistemia`; no son equivalentes a la propuesta `rol_epistemico`.
- En los módulos inspeccionados no se encontraron tablas `episodios` o `episodio_nodos` ni el campo `rol_epistemico`.

Antes de una implementación v37 habría que definir cómo los episodios generan candidatos antes del reranking; distinguir intención de consulta y tipo de recuerdo; separar tiempo del evento, tiempo de guardado y tiempo de actualización; y medir consultas con/sin intención temporal sin degradar las demás. Un reranking no rescata recuerdos que nunca entraron al pool. “No devolver una lista vacía” tampoco demuestra que no haya regresiones en Top-1/Top-5 ni falsos positivos.

Otros puntos abiertos de la propuesta:

- La PK sugerida `(episodio_id, concepto)` en `episodio_nodos` no permitiría guardar varias apariciones del mismo concepto como eventos distintos.
- Las regex de términos como «último» o «error» no son por sí solas un selector independiente del idioma.
- El plan menciona `core/memory_store.py → _migrations`, pero en la inspección no se encontró ese registro; las migraciones observadas están en `core/memory/schema.py`.
- Probar tablas nuevas en la DB viva contradice el aislamiento acordado. La idempotencia, reapertura, rollback, sesiones interrumpidas y varios agentes deben probarse en SQLite en memoria o copias temporales.
- El plazo de 5–7 semanas y la afirmación general de que los RAG convencionales no hacen esto no se verificaron.

**Decisión:** no iniciar T1 ni alterar el schema con el plan tal como estaba. La medición de esta propuesta debe hacerse en bases sintéticas o copias temporales, nunca sobre la DB viva ni el snapshot original.

### 2.2 Documentación de v36

- `README.md` identifica v36.0 como cierre técnico de esta rama, deja el match y el tag bajo control del usuario, y resume la numeración v37/v38.
- La sección v36 del README reúne las correcciones de escala de búsqueda y Concept Hubs, el BM25 de referencia, los diagnósticos, la QA clásica/honesta, el destino canónico de datos, instalación MCP, control del daemon y compatibilidad Python. Incluye las métricas de benchmarks separados con sus límites.
- `CHANGELOG.md` agrupa bajo una sola entrada v36.0 las correcciones aceptadas de escala, la instrumentación de QA y las capacidades operativas. No crea releases v35.1, v35.2 ni v35.3; esas etiquetas de trabajo no se presentan como versiones publicadas.
- `VERSION` contiene `v36.0` y `pyproject.toml` declara `36.0.0`; ambos valores coinciden.
- La edición de esta revisión es documental/evidencial: no se modificaron motor, schema, tests, DB ni configuración de rutas.

El README resume la trayectoria y contiene explicaciones históricas extensas de v34 y v35. No pretende sustituir cada informe experimental o cada diff, que siguen en `docs/` y `scripts/experimentos/`.

## 3. Alcance de v36 documentado

La sección v36 del README consolida en una sola versión los cambios aceptados y verificados; no crea releases intermedias v35.1, v35.2 o v35.3. Describe, con límites explícitos:

- **Recuperación a escala:** cuatro ajustes acotados en el buscador: rescate guiado por palabras poco conocidas, ventanas de candidatos ordenadas por parecido trigram, límite al escape QCR de dimensiones inferidas y protección de palabras reales frente al matching difuso. `BIORAG_ESCALA=1` es el valor por defecto; `BIORAG_ESCALA=0` apaga estas ayudas, no todo el ranking.
- **BM25:** cuando las tablas FTS de referencia están disponibles, la expresión BM25 permanece utilizable aunque `BIORAG_ESCALA=0`.
- **Concept Hubs:** motor `escala` e índice invertido por defecto, pesos según frecuencia de palabras, competencia entre recuerdos, tope de ln(2) (un bit) para palabras de función sin que estas abran candidaturas por sí solas y ángulo `ingenuo` neutral (`×1.0`). `BIORAG_HUB_ESCALA=0` es una ablación del cálculo nuevo.
- **Diagnósticos:** `scripts/diagnostico_fallos.py` y `scripts/diagnostico_hub.py` copian la base de entrada a una carpeta temporal y analizan esa copia; no escriben en la DB fuente. Pueden guardar informes JSON, por lo que sus rutas de salida deben elegirse explícitamente.
- **QA:** la QA clásica conserva el gate; E1 agrega métricas suplementarias para etiquetas obsoletas/ambiguas. Las mediciones con ruido son una línea separada. E2c y E2e se rechazaron y revirtieron; no se anuncian como funciones activas.
- **Ruta de datos:** destino canónico `~/.biorag/memory_biorag.db`; siguen aplicando argumentos explícitos, `BIORAG_PATH` y fallback legacy.
- **Migración legacy:** checkpoint best-effort; si ya existe destino, se respaldan las dos bases antes de resolver el conflicto por tamaño. No se fusionan contenidos ni se compara su semántica; mover `.db`, `-wal` y `-shm` no es una transacción atómica de conjunto.
- **Instalador MCP:** `install.py` automatiza detección y escritura de configuración para clientes reconocidos. Escribir una configuración no prueba que el cliente conecte correctamente. Los transportes generados usan `stdio`; la verificación final depende del cliente y el entorno.
- **Daemon:** `BIORAG_DAEMON_ENABLED=0` por defecto; `--stop` solicita `SIGTERM`, espera hasta 30 segundos y puede recurrir a `SIGKILL`. Esto controla el proceso de mantenimiento; no implica borrar asociaciones, desactivar SDM ni cambiar su fallback predeterminado. No garantiza cierre limpio en todos los casos.
- **QA de ranking:** `--con-neurona` permite comparar fórmula y neurona sobre una copia; pregunta antes de entrenar en modo interactivo y ofrece `--si` para confirmación explícita no interactiva. No debe entrenarse la DB original por esta herramienta.
- **Python:** mínimo `>=3.11`; CI declara Python 3.11 y 3.12.

### Benchmarks controlados de escala (separados de la QA actual de v36)

Todos los resultados de estos experimentos son de copias; no se midió la DB viva ni se atribuyen a la comparación con `master`. **Buscador:** QA de 921 casos, `BIORAG_NEURONA=0`, `PYTHONHASHSEED=1`. Los valores son posteriores a las cuatro correcciones y ninguna categoría bajó frente a su propia copia de control sin arreglos.

| Copia | Recuerdos | R@1 | R@5 | MRR | FP |
|---|---:|---:|---:|---:|---:|
| S0 | 866 | 92.57% | 100.00% | 0.954 | 0/40 |
| A640 | 1506 | 93.03% | 99.77% | 0.956 | 0/40 |
| T1000r | 1866 | 92.80% | 99.89% | 0.955 | 0/40 |
| T3000r | ~3866 | 92.57% | 99.54% | 0.953 | 0/40 |

No es una garantía de invariancia universal: permanecen empates en consultas de una palabra y dos casos de T3000r donde repetir una palabra desplaza al recuerdo que cubre toda la pregunta. Detalle reproducible: `scripts/experimentos/escala_recall_20261025/README.md` y `tabla_final.txt`.

**Concept Hubs:** QA de 921 casos en copias con puentes generados heurísticamente desde el contenido; los hubs no fueron redactados por un agente. Valores finales tras fijar `ingenuo` en `×1.0`:

| Copia | Hubs | R@1 | R@5 | MRR | Fallos | FP |
|---|---:|---:|---:|---:|---:|---:|
| S0 | 6 | 93.14% | 100.00% | 0.9573 | 0 | 0/40 |
| H-mitad | 436 | 93.03% | 100.00% | 0.9569 | 0 | 0/40 |
| H-todos | 866 | 93.83% | 100.00% | 0.9619 | 0 | 0/40 |

El diagnóstico de hub solo redujo los errores con confianza ≥0.8 de 255 a 3 en H-todos y de 216 a 11 en H-mitad; el tiempo observado pasó de ~593 a ~8 ms y de ~284 a ~4 ms. En H-todos, `sinonimo` R@1 bajó de 65.45% a 58.18% aunque R@5 subió de 98.18% a 100%; el informe conserva esa debilidad. Ver `scripts/experimentos/hub_escala_20261025/README.md` y `tabla_final.txt`. Estos resultados no son una medición de rendimiento general ni del tráfico de producción.

El README separa capacidades implementadas, evidencia medida y propuestas futuras. Las metáforas neurocientíficas describen inspiración de diseño, no una simulación literal del cerebro.

## 4. Evidencia de QA reconciliada

Las corridas se hicieron exclusivamente en copias temporales; no se abrió la DB viva ni se escribió sobre el snapshot original.

- **Pytest (registro previo, copia aislada):** `PYTHONHASHSEED=0 python -m pytest tests/` — 852 passed, 18 skipped (870 recopilados; 240.19 s; Python 3.11.2). No se volvió a ejecutar pytest durante esta revisión.
- **QA oficial (repetida en esta revisión sobre una copia fresca):** `BIORAG_QA_GATE=1 bash scripts/run_qa_suite.sh --qa-only` — `[GATE] OK`; 921 casos, 875 de recuperación, 40 negativos y 6 ambiguos; R@5 100.00% (875/875), R@1 93.03% (814/875), MRR 0.9566, FP 0/40; 719.53 s. `scripts/qa_metrics.json` corresponde a esta corrida y `scripts/casos_fallidos.jsonl` conserva dos filas ambiguas; no son fallos globales de recuperación.
- La copia medida no tenía campeón de la neurona de ranking, por lo que no actuó. La fuente indicada fue `snapshots/qa_escape_qcr_20260811.db`, cuyo SHA-256 actual es `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`; la evaluación se realizó sobre una copia temporal. No se afirma identidad binaria de la copia SQLite.
- **Discrepancia de procedencia sin resolver:** un registro anterior señaló `aa7ac66f9fe7…` como prefijo del origen QA, distinto del SHA-256 actual del snapshot (`104dd2902aaf…`). No se determinó si ese prefijo corresponde a otra copia/origen; no se concluye corrupción ni identidad binaria.
- **Smoke focal de Concept Hub (repetido en copia aislada):** `scripts/test_concept_hub.py` obtuvo 5/5 consultas en TOP-1 con hub y 0/5 sin hub. La copia tenía 851 nodos activos, 6 hubs y 30 puentes. Es una evaluación de cinco paráfrasis fijas; no mide rendimiento general ni prueba por sí sola la escala. `tests/test_hub_escala.py` es evidencia distinta: sus fixtures sintéticas incluyen competencia de hasta 3.000 hubs y la suite completa registrada previamente la aprobó.
- Los reportes conservan la marca generada por el runner (`scripts/qa_metrics.json`: `2026-11-18T01:49:37`; `docs/concept_hub_eval_results.json`: `2026-11-18 01:53`). Ambas contradicen la fecha de sesión de referencia `2026-10-21`; se deja explícita la discrepancia y no se usa esa marca como fecha fiable.
- `git diff --check` pasó para los cambios documentales/evidenciales de esta revisión. El JSON de QA ya no contiene rutas absolutas de la copia temporal.

Estas cifras no garantizan resultados para toda memoria o consulta. No confundir los `852 passed` y `18 skipped` con 870 pruebas aprobadas, ni las métricas históricas de v33/v35 con la QA actual de v36.

## 5. Sincronización de la rama y estado local

Los puntos siguientes conservan la captura histórica de sincronización realizada al iniciar el cierre. Al comienzo de esta edición, `arena/6459e2d0-memorybiorag` y `origin/arena/6459e2d0-memorybiorag` coincidían en `d4c8140`. La documentación y evidencia que se agrega en esta revisión permanece en esa misma rama; no se integra en `master` y el agente no hace el match ni la etiqueta.

En el último fetch, `origin/master` estaba en `13a51af1fbb1`. La comparación directa de árboles contra el tip `d4c8140` mostró cinco rutas distintas: `core/memory/search.py`, `docs/concept_hub_eval_results.json`, `docs/plan_publicacion_v36.md`, `scripts/casos_fallidos.jsonl` y `scripts/qa_metrics.json`. El único archivo de código de esa lista es `core/memory/search.py`; no se cambió durante esta revisión. El reporte ya guardado en `origin/master` indica R@5 98.40%, R@1 92.34%, MRR 0.9472 y 14 fallos globales; la nueva QA aislada de esta rama da R@5 100.00%, R@1 93.03%, MRR 0.9566 y cero fallos globales. No se ejecutó QA contra `master` en esta revisión ni se atribuye la diferencia a una causa concreta. La copia Git es superficial y no permitió una comparación de tres puntos con merge-base; tras el match se debe ejecutar el gate sobre el árbol exacto que se pretenda integrar/taguear.

- Repositorio: `dennysjmarquez/MemoryBioRAG`; remoto `origin`: `https://github.com/dennysjmarquez/MemoryBioRAG.git`.
- Rama activa: `arena/6459e2d0-memorybiorag`.
- Al inspeccionar este checkout, `HEAD` era `f8c2b166b6f13cd7bbbdffb13135d3d68354b8e0` y la punta recién obtenida de la rama remota era `64bc50646c47c3214934b33edda3fbe20b18ec78` (`fix(search): repair dimensional fallback when table is purged, restore IDF fallback, and gate BM25 on escala active`). La punta remota descendía de `f8c2b166...` (`0` commits locales-only y `307` remotos-only), por lo que la rama local se adelantó mediante fast-forward.
- La referencia local quedó en esa punta remota y el índice se alineó sin actualizar ni retirar archivos del árbol de trabajo. Se verificaron sin cambios los checksums de `README.md`, `CHANGELOG.md`, `VERSION` y `pyproject.toml` durante la operación.
- Los commits `fb7e049` y `d512c25` mencionados en una nota anterior no estaban disponibles como objetos Git en este checkout. Los cambios documentales seguían presentes en el árbol de trabajo; se conservaron y se reconciliaron con la punta remota, sin descartar el resto de cambios locales.
- En el momento del fast-forward, `README.md` y `CHANGELOG.md` coincidían con la punta remota y contenían el cierre técnico de v36.0 y la numeración v37/v38. En esta revisión ambos se ampliaron para consolidar la evidencia. `VERSION` y `pyproject.toml` ya coincidían con la punta remota (`v36.0` y `36.0.0`), así que no requirieron cambios.
- Antes de alinear el índice había 53 rutas rastreadas modificadas y 654 sin seguimiento. De las 653 rutas sin seguimiento que ya estaban en la punta remota, 652 eran idénticas; `docs/plan_publicacion_v36.md` difería y se preservó como cambio local. `docs/CIERRE_VERSION_36.md` era nuevo. También se constató que 46 de las 53 rutas modificadas coincidían byte por byte con la punta remota.
- En aquella sincronización se conservaron fuera del commit documental `core/memory/search.py`, `docs/concept_hub_eval_results.json`, `docs/plan_publicacion_v36.md`, `scripts/casos_fallidos.jsonl` y `scripts/qa_metrics.json`; no se stageó el árbol completo. En esta revisión se actualizaron README, changelog, cierre y los dos informes JSON. No se modificó `core/memory/search.py`, `docs/plan_publicacion_v36.md` ni `scripts/casos_fallidos.jsonl`; se hará match sobre el árbol exacto que el usuario decida.
- En la inspección anterior de sincronización (antes del fetch de comparación de árboles), `origin/master` apuntaba a `932c365f08003e8a00ba59d5cb6420dbd1d6f60b`; la captura posterior usada arriba lo encontró en `13a51af1fbb1`. Son referencias históricas y no se revalidan con esta edición. No se hizo merge a `master` ni se creó una etiqueta; el remoto puede avanzar independientemente.

## 6. Precauciones vigentes

1. No hacer `git add -A`: el árbol contiene código, tests, informes, logs, JSON/JSONL, evidencia de evaluación y datos que requieren selección explícita.
2. Stagear solo los archivos de documentación/evidencia v36 seleccionados explícitamente; no hacer `git add -A` ni incorporar código o artefactos sin revisar en el match. No modificar `tests/conftest.py`, cambiar `BIORAG_PATH` ni `scripts/run_qa_suite.sh` sin permiso.
3. No restaurar bases vivas, snapshots originales ni `MemoryBioRAG_Data/memory_biorag.db`. La sincronización no abrió ni modificó bases de datos.
4. No usar `reset`, `checkout` ni cambios de rama para descartar o “limpiar” archivos. No forzar el push ni integrar esta rama en `master` desde este checkout.
5. El resultado de pytest es un registro previo. En esta revisión sí se reejecutaron la QA oficial y el smoke de Concept Hub, ambos únicamente en copias temporales; no se tocaron `tests/conftest.py`, `scripts/run_qa_suite.sh`, la DB viva ni el snapshot original.

## 7. Revisión de requisitos previos a la etiqueta

La auditoría de documentación y del estado actual identifica pendientes que no se deben dar por cerrados solo porque la QA oficial pasa:

- **E3 continúa abierta.** `docs/auditoria_fp_ingles_etiquetas_e4ce0b3_20261102.md` reproduce indicadores acotados, pero declara que no repara los falsos positivos ingleses ni resuelve las etiquetas pendientes. La auditoría no autorizó un parche ni el paso a E4. El cambio 2 de E3 cuenta con una aprobación independiente; eso no cierra E3 completa.
- **E4 no está acreditada como cerrada.** El plan de publicación la define como lograr que el motor no dependa de la base; no se encontró en esta revisión un cierre que demuestre ese criterio. No se infiere que una corrida de QA ordinaria lo cubra.
- **Modularización fase 2 no está implementada/verificada.** El plan exige subpaquetes (`core/lexico/`, `core/memory/busqueda/`, `ranking/`, `neuronas/`, `sueno/`) con puentes de compatibilidad y QA idéntica. Esas rutas no existen en el árbol actual; la fase 1 documental no sustituye la fase 2.
- **E2c y E2e siguen siendo investigaciones rechazadas/revertidas**, no capacidades que se deban anunciar como implementadas en v36.

**Resultado para el cierre:** E3 sigue abierta; E4 y modularización fase 2 no se dan por cerradas ni verificadas. La rama queda disponible para que el usuario ejecute el match y gestione la etiqueta B36 (v36.0) sobre el árbol exacto que decida. La QA documentada aquí no sustituye el gate posterior al match. Este agente no hace el merge final ni crea una etiqueta.

## 8. Siguiente recorrido

1. La numeración vigente se conserva: **v36.0 (cierre técnico) → v37 (plan episódico/intencional) → v38 (trabajo neuronal posterior)**. El usuario hará el match y gestionará la etiqueta B36; el merge final también queda a su cargo. No se crea una etiqueta desde esta rama.
2. Para v37, retomar el diseño episódico/intencional como propuesta: inventario de candidatos, tratamiento de tiempos, benchmark pareado y guardianes de no regresión antes de tocar schema o motor.
3. Dejar v38 como etapa neuronal posterior, separada de v36/v37 y condicionada a propósito, baseline, límites, fallback, pruebas aisladas y autorización correspondiente.

## 9. Referencias principales

- `README.md` — resumen público de versiones, sección v36 y mapa v34→v38.
- `CHANGELOG.md` — entrada v36.0 y evidencia registrada.
- `VERSION` y `pyproject.toml` — metadatos de versión.
- `core/memory/episodes.py`, `core/memory/search.py` — mecanismos temporales existentes.
- `core/mcp_server/search.py`, `core/mcp_server/session.py`, `core/mcp_server/_shared.py`, `core/mcp_server/prompt.py` — filtros/orden temporal, ciclo de sesión y dimensiones.
- `core/memory/schema.py` — creación de schema y migraciones inline.
- `docs/plan_publicacion_v36.md` — leer primero la aclaración de numeración al inicio; el alcance histórico etiquetado v36 se reetiquetó como v37.
- `docs/registro_recuperacion_cambios_para_v36_20261101.md` y `docs/estado_e3_retorno_plan_20261101.md` — inventarios/estados históricos; comprobarlos antes de tratarlos como estado actual.
