# Cierre técnico de BioRAG v36.0 — resumen de sesión

**Fecha del registro:** 2026-10-21 (UTC)
**Estado:** v36.0 se considera cerrada técnicamente por decisión de Dennys. La integración en `master` y la etiqueta de publicación siguen pendientes.
**Propósito:** conservar el contexto de la sesión para revisar la rama y decidir la integración sin confundir el cierre de v36 con trabajo futuro ni perder cambios locales.

> Este documento es una nota de continuidad, no una prueba de merge, publicación, tag ni de que todos los archivos locales estén incluidos en commits. Las métricas que cita son ejecuciones registradas previamente; no se repitieron en esta sesión documental.

## 1. Decisión de versiones

La numeración vigente acordada es:

| Versión | Alcance | Estado |
|---|---|---|
| **v36.0** | Base que se cierra ahora; infraestructura operativa y de evaluación descrita en este documento y en el README. | Cierre técnico declarado; falta integración/tag en `master`. |
| **v37** | Plan de **Memoria Episódica + Recuperación por Intención**, antes rotulado v36. | Trabajo futuro y propuesta; no se implementó como parte de v36. |
| **v38** | Etapa de trabajo neuronal que antes se rotulaba v37. | Etapa posterior; no se presenta como implementada en v36. |

El rótulo de una versión no equivale a publicación. v36.0 es la última base antes de las etapas v37 y v38, pero la rama actual aún no se ha empujado ni integrado en `master`.

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

- `README.md` identifica v36.0 como cierre técnico de esta rama, marca que el merge/tag en `master` sigue pendiente y resume la evolución v34→v36 y la numeración v37/v38.
- La sección v36 del README recoge el destino canónico de datos, instalación/configuración MCP, control del daemon, evaluación de la neurona de ranking y compatibilidad Python.
- `CHANGELOG.md` agrupa la instrumentación de QA y las capacidades operativas bajo una sola entrada v36.0, en vez de mantener la QA de neurona como una entrada separada sin versión.
- `VERSION` contiene `v36.0` y `pyproject.toml` declara `36.0.0`; ambos valores coinciden.
- La edición fue documental: no se modificaron motor, schema, tests, DB ni configuración de rutas en esta sesión.

El README resume la trayectoria y contiene explicaciones históricas extensas de v34 y v35. No pretende sustituir cada informe experimental o cada diff, que siguen en `docs/`.

## 3. Alcance de v36 documentado

La sección v36 del README describe, con límites explícitos:

- **Ruta de datos:** destino canónico `~/.biorag/memory_biorag.db`; se mantienen los argumentos explícitos, `BIORAG_PATH` y el fallback legacy.
- **Migración legacy:** checkpoint best-effort; si ya existe destino, se respaldan las dos bases antes de resolver el conflicto por tamaño. No se fusionan contenidos ni se compara su semántica; mover `.db`, `-wal` y `-shm` no es una transacción atómica de conjunto.
- **Instalador MCP:** `install.py` automatiza detección y escritura de configuración para clientes reconocidos. Escribir una configuración no prueba que el cliente conecte correctamente. Los transportes generados usan `stdio`; la verificación final depende del cliente y el entorno.
- **Daemon:** `BIORAG_DAEMON_ENABLED=0` por defecto; `--stop` solicita `SIGTERM`, espera hasta 30 segundos y puede recurrir a `SIGKILL`. No garantiza cierre limpio en todos los casos.
- **QA de ranking:** `--con-neurona` permite comparar fórmula y neurona sobre una copia; pregunta antes de entrenar en modo interactivo y ofrece `--si` para confirmación explícita no interactiva. No debe entrenarse la DB original por esta herramienta.
- **Python:** mínimo `>=3.11`; CI declara Python 3.11 y 3.12.

El README debe mantener separadas las capacidades implementadas, los resultados medidos y las ideas futuras. Las metáforas neurocientíficas describen inspiración de diseño, no una simulación literal del cerebro.

## 4. Evidencia de QA registrada

Resultados previamente registrados para el cierre, ejecutados en copias temporales:

- **Pruebas unitarias:** `PYTHONHASHSEED=0 python -m pytest tests/` — 852 passed, 18 skipped (870 recopilados; 240.19 s; Python 3.11.2).
- **QA oficial:** `bash scripts/run_qa_suite.sh --qa-only`, con `BIORAG_QA_GATE=1` — 921 casos; R@5 100.00% (875/875), R@1 93.03% (814/875), MRR 0.9566, FP 0/40; `[GATE] OK`.
- Los seis casos ambiguos se evaluaron fuera del denominador de recuperación global; dos aparecen en el archivo temporal de fallos.
- La copia medida no tenía campeón de la neurona de ranking, por lo que no actuó en esa corrida.
- El snapshot original conservó el SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796` antes y después; las salidas se aislaron.
- En esta sesión se comprobó `git diff --check -- README.md CHANGELOG.md`; pasó. No se reejecutaron pytest ni QA.

Estas cifras no garantizan resultados para toda memoria o consulta. No confundir los `852 passed` y `18 skipped` con 870 pruebas aprobadas, ni las métricas históricas de v33/v35 con las de la corrida registrada para v36.

## 5. Sincronización de la rama y estado local

Esta sección registra la sincronización efectuada al preparar este cierre documental. Es una captura puntual; no afirma una integración en `master`, una etiqueta ni el estado futuro del remoto.

- Repositorio: `dennysjmarquez/MemoryBioRAG`; remoto `origin`: `https://github.com/dennysjmarquez/MemoryBioRAG.git`.
- Rama activa: `arena/6459e2d0-memorybiorag`.
- Al inspeccionar este checkout, `HEAD` era `f8c2b166b6f13cd7bbbdffb13135d3d68354b8e0` y la punta recién obtenida de la rama remota era `64bc50646c47c3214934b33edda3fbe20b18ec78` (`fix(search): repair dimensional fallback when table is purged, restore IDF fallback, and gate BM25 on escala active`). La punta remota descendía de `f8c2b166...` (`0` commits locales-only y `307` remotos-only), por lo que la rama local se adelantó mediante fast-forward.
- La referencia local quedó en esa punta remota y el índice se alineó sin actualizar ni retirar archivos del árbol de trabajo. Se verificaron sin cambios los checksums de `README.md`, `CHANGELOG.md`, `VERSION` y `pyproject.toml` durante la operación.
- Los commits `fb7e049` y `d512c25` mencionados en una nota anterior no estaban disponibles como objetos Git en este checkout. Los cambios documentales seguían presentes en el árbol de trabajo; se conservaron y se reconciliaron con la punta remota, sin descartar el resto de cambios locales.
- `README.md` y `CHANGELOG.md` conservan el contenido de la punta remota y el cierre técnico de v36.0, incluida la numeración v37/v38. `VERSION` y `pyproject.toml` ya coincidían con la punta remota (`v36.0` y `36.0.0`), así que no requirieron cambios locales adicionales.
- Antes de alinear el índice había 53 rutas rastreadas modificadas y 654 sin seguimiento. De las 653 rutas sin seguimiento que ya estaban en la punta remota, 652 eran idénticas; `docs/plan_publicacion_v36.md` difería y se preservó como cambio local. `docs/CIERRE_VERSION_36.md` era nuevo. También se constató que 46 de las 53 rutas modificadas coincidían byte por byte con la punta remota.
- Tras la sincronización quedaron fuera del alcance documental y se conservaron localmente `core/memory/search.py`, `docs/concept_hub_eval_results.json`, `docs/plan_publicacion_v36.md`, `scripts/casos_fallidos.jsonl` y `scripts/qa_metrics.json`. No se stageó el árbol completo.
- `origin/master` apuntaba a `932c365f08003e8a00ba59d5cb6420dbd1d6f60b` en la inspección. No se hizo merge a `master` ni se creó una etiqueta; el estado de la rama remota puede avanzar independientemente de esta captura.

## 6. Precauciones vigentes

1. No hacer `git add -A`: el árbol contiene código, tests, informes, logs, JSON/JSONL, evidencia de evaluación y datos que requieren selección explícita.
2. Mantener fuera del commit documental los cambios locales ajenos a v36 enumerados arriba. No modificar `tests/conftest.py`, `BIORAG_PATH` ni `scripts/run_qa_suite.sh` sin permiso.
3. No restaurar bases vivas, snapshots originales ni `MemoryBioRAG_Data/memory_biorag.db`. La sincronización no abrió ni modificó bases de datos.
4. No usar `reset`, `checkout` ni cambios de rama para descartar o “limpiar” archivos. No forzar el push ni integrar esta rama en `master` desde este checkout.
5. Los resultados de QA de la sección anterior son registros previos; no se ejecutaron pytest ni QA como parte de este cierre documental.

## 7. Siguiente recorrido

1. La numeración vigente se conserva: **v36.0 (cierre técnico) → v37 (plan episódico/intencional) → v38 (trabajo neuronal posterior)**. El titular de la rama decidirá su integración en `master` y cualquier etiqueta de publicación.
2. Para v37, retomar el diseño episódico/intencional como propuesta: inventario de candidatos, tratamiento de tiempos, benchmark pareado y guardianes de no regresión antes de tocar schema o motor.
3. Dejar v38 como etapa neuronal posterior, separada de v36/v37 y condicionada a propósito, baseline, límites, fallback, pruebas aisladas y autorización correspondiente.

## 8. Referencias principales

- `README.md` — resumen público de versiones, sección v36 y mapa v34→v38.
- `CHANGELOG.md` — entrada v36.0 y evidencia registrada.
- `VERSION` y `pyproject.toml` — metadatos de versión.
- `core/memory/episodes.py`, `core/memory/search.py` — mecanismos temporales existentes.
- `core/mcp_server/search.py`, `core/mcp_server/session.py`, `core/mcp_server/_shared.py`, `core/mcp_server/prompt.py` — filtros/orden temporal, ciclo de sesión y dimensiones.
- `core/memory/schema.py` — creación de schema y migraciones inline.
- `docs/plan_publicacion_v36.md` — leer primero la aclaración de numeración al inicio; el alcance histórico etiquetado v36 se reetiquetó como v37.
- `docs/registro_recuperacion_cambios_para_v36_20261101.md` y `docs/estado_e3_retorno_plan_20261101.md` — inventarios/estados históricos; comprobarlos antes de tratarlos como estado actual.
