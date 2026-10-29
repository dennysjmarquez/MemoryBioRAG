# E3 Cambio 2 — guardar sustantivos exactos, comparar también sin marcas

**Estado: SOLO INVESTIGACIÓN. No se modifica el motor ni se migran datos.** El archivo `docs/e3_cambio2_propuesta_no_aplicar_20261029.patch` es un esquema de diff documental, deliberadamente no ejecutable. Cualquier implementación requiere revisión y OK explícito de Dennys, diff de código definitivo, pruebas y QA.

## 1. Hallazgo principal

El normalizador actual de `sustantivos_clave` hace más que quitar tildes latinas: `core/memory/constants.py:286-311` normaliza identidad, pasa cada término por `_quitar_acentos` y deduplica **después** de plegarlo. `core/stemmer_es.py:43-46` define ese plegado como NFKD seguido de eliminar todos los caracteres con clase combinatoria distinta de cero. Así se pierden distinciones escritas con marcas y pueden colisionar términos antes de almacenarse o contarse.

Ejemplo reproducible con Python `unicodedata`:

| Entrada | Forma guardada hoy por el normalizador | Consecuencia |
|---|---|---|
| `ガラス` (ga-ra-su) | `カラス` | Se pierde dakuten de `ガ` |
| `カラス` (ka-ra-su) | `カラス` | Colisiona con `ガラス` |
| `ガラス,カラス` | `カラス` | Dos claves pasan a ser una antes de contar/deduplicar |
| `café` | `cafe` | Se conserva la equivalencia histórica buscada |
| `क़िला` | `किला` | Se pierde nukta y puede colisionar con la forma sin nukta |

La normalización de identidad aprobada en Cambio 1 hace NFC y plegado acotado de ancho; **no elimina estas marcas**. La pérdida ocurre en el paso posterior de `normalizar_sustantivos_clave`.

## 2. Mapa de dónde se eliminan marcas y quién usa esas formas

### Sustantivos clave — afecta directamente almacenamiento, conteo y búsqueda

- **Almacenamiento/deduplicación:** `core/memory/constants.py:286-311`, expuesto como `normalizar_sustantivos_clave` por `core/memory_store.py`. Tras identidad, lowercase y división por comas, aplica `_quitar_acentos`; protege explícitamente `ñ`, pero no otras marcas. La deduplicación y, luego, las comprobaciones del mínimo/máximo se hacen sobre el resultado plegado.
- **Validación:** `core/mcp_server/_shared.py:93-99` comprueba longitudes/categorías sin plegar por sí misma, pero recibe los términos ya normalizados. Las rutas de MCP `recordar`/`buscar`, `aprender`/`guardar` y `agregar_sustantivos` llaman el normalizador antes de validar/entregar.
- **Persistencia:** `core/mcp_server/write.py` entrega ese resultado a `percibir_corto_plazo`; `core/memory/ingest.py:41-52,82-95` documenta y conserva la premisa de que el valor ya viene normalizado. La consolidación copia/fusiona el campo (`core/memory/consolidation.py:248-290,321-326`). Por eso se deben probar ambos almacenes, corto y largo plazo.
- **Comparación en búsqueda:** `core/memory/search.py:392-401` vuelve a aplicar `_quitar_acentos` a los sustantivos clave de la consulta y genera un `MATCH` sobre la columna FTS dedicada, con peso BM25 de 4.0. `core/mcp_server/search.py:207-253,484-498` normaliza y valida el argumento antes de pasarlo. Cambiar solo la escritura no basta: los recuerdos viejos ya contienen la forma plegada.
- **Indexación/filtros posteriores:** FTS5 trigram indexa el texto guardado de `largo_plazo.sustantivos_clave` (esquema y triggers en `core/memory/schema.py:1000-1059`). La búsqueda también usa ese campo en QCR/prefijo y metadatos (`core/memory/search.py:1526-1542,1919-1929,2073-2097`). Cualquier alias debe integrarse de modo que esos filtros no eliminen candidatos recuperados por la vía aproximada.
- **Otros consumidores:** el autoexamen deriva sustantivos con el normalizador (`core/memory/neurona_examen.py:187-197`); `core/memory/neurona.py:633` los pasa como señal de búsqueda. Deben probarse por compatibilidad, sin ensanchar inadvertidamente el alcance a otras neuronas o dimensiones.
- **Ruta de actualización distinta:** `biorag_actualizar`, `core/mcp_server/write.py:1010-1087`, escribe sustantivos en largo plazo mediante el mismo normalizador, pero no comparte el recorrido de validación completo de `aprender` ni `agregar_sustantivos`. Auditoría de Cambio 1 ya la señaló como pendiente porque tampoco pliega ancho de manera consistente. Mantenerla como tarea separada, con pruebas propias; esta investigación no la corrige.

### Otros usos de quitar marcas — fuera del cambio propuesto

| Ubicación | Uso visible | Tratamiento propuesto |
|---|---|---|
| `core/stemmer_es.py:43-46,166-185,250-286` | Stemming ES/EN y puente entre formas (`stem`, fallback). | No tocar: es normalización interna del stemmer, no persistencia de SK. Probar no regresión. |
| `core/memory/search.py:150-161` | Comparación de stopwords en la consulta. | No tocar en esta propuesta. |
| `core/memory/scoring.py:412-422` | Tokens sin marcas para Jaccard de reordenamiento. | No tocar; no usar esta salida para persistir ni contar SK. |
| `core/fallback_simbolico.py:25-46` y consumidores | Coincidencia simbólica, stopwords y traducción/lemmas. | No tocar; es una capa aproximada separada y puede introducir sus propias colisiones. |
| `core/neurona_asociativa.py:95-96`, `core/memory/escala.py:45-46` | Normalización de rasgos/texto para funciones neuronales o de escala. | No tocar en Cambio 2. |
| `core/srl_extractor.py:32-34` | Forma normalizada de palabras para extraer roles. | No tocar en Cambio 2. |
| `core/lexical_learning.py:36-50` | Índice de episodios léxicos mediante expresión normalizada. | No tocar ni migrar; evaluar por separado si el alcance futuro lo requiere. |

**Distinción importante:** estos consumidores hacen equivalencia aproximada local para sus fines; no demuestran que sea seguro destruir la identidad original de una etiqueta. Cambio 2 se limita a la representación/consulta de `sustantivos_clave` y no cambia el texto del recuerdo, sus sinónimos, nombre, stemming, SRL, aprendizaje léxico ni neuronas.

## 3. Rediseño aprobado por el auditor: dos columnas aditivas

La auditoría `docs/auditoria_ci/auditoria_e3_cambio2_investigacion_20261029.md` (rama auditora, `43b11fd`) aprobó el diagnóstico y rechazó la proyección dentro de FTS. Este documento sustituye explícitamente aquel diseño anterior. Se adopta el esquema requerido de **dos columnas**:

1. **`sustantivos_clave` no cambia:** conserva exactamente la normalización plegada actual, incluso para nuevas escrituras. Continúa siendo la única columna de sustantivos usada por FTS y búsqueda. El SQL FTS, sus triggers, BM25 4.0, QCR, filtros de prefijo, candidatos y fórmula de ranking quedan fuera del diff.
2. **Nueva `sustantivos_clave_exactos TEXT`:** añadir en `corto_plazo` y `largo_plazo` mediante `ALTER TABLE ... ADD COLUMN`. Sin `DEFAULT` que rellene filas: en una base existente las filas antiguas quedan `NULL`; no se intenta reconstruir la información perdida, no se hace backfill, no se actualiza `sustantivos_clave` y no se reconstruye FTS.
3. **Entrada, recuento y validación:** una función nueva normaliza la forma exacta en NFC, conserva marcas, deduplica solo duplicados exactos y hace que el límite/cantidad y formato se evalúen sobre esos términos. Así `ガラス,カラス` cuenta dos. En paralelo se ejecuta el normalizador histórico sin cambios para producir el valor de `sustantivos_clave`, que se pasa a las rutas existentes de búsqueda e indexación.
4. **Escritura y consolidación:** `aprender`/`guardar` persisten ambos campos en corto plazo; `agregar_sustantivos` actualiza ambos en el nodo encontrado; la consolidación copia el exacto a largo plazo mientras conserva la regla actual del campo plegado. Lecturas/escrituras directas antiguas que no suministren exacto no inventan valor. La nueva columna es preservación, no una señal de score ni un cambio de recuperación.
5. **`actualizar` MCP:** queda expresamente pendiente y fuera de esta propuesta, como pidió el auditor. No se debe afirmar que el exacto se sincroniza al modificar etiquetas mediante esa ruta hasta que se autorice y pruebe por separado.

El diseño FTS anterior no se conserva: no hay UDF en triggers, no se cambian los filtros que leen la columna cruda, y no se reconstruye ni modifica el índice. El SQL de ranking vigente sigue leyendo solo `sustantivos_clave` plegado. El archivo patch contiene el diff candidato completo, incluidos tests, pero lleva nombre `NO_APLICAR`: **nada se ha aplicado al motor del PR**.

## 4. Sonda mixta sintética: antes vs. candidata

Se comparó el commit base `cf799c7` con una copia aislada de la candidata. Base recién creada y controlada, sin snapshot ni datos vivos. Cuatro filas: etiqueta antigua `カラス` con exacto `NULL`; fila nueva recibida como `ガラス` (en candidata, campo plegado `カラス` y exacto `ガラス`); etiqueta antigua `cafe` con exacto `NULL`; fila nueva recibida como `café` (campo plegado `cafe`, exacto `café`). Contenido, estado y peso quedan controlados. Ambas rutas buscan el texto de consulta y pasan la misma cadena a `sustantivos_clave_boost`; `activos`, límite 10, `ignore_peso_sinaptico=True`, neurona/hub/WordNet apagados. Se registra el score binario (`float.hex`) y decimal con 17 cifras significativas, sin redondear.

| Consulta | Rangos antes | Scores antes (rango 1 / rango 2) | Rangos candidata | Scores candidata (rango 1 / rango 2) |
|---|---|---|---|---|
| `ガラス` | `jp_ave_a` 1, `jp_vidrio_b` 2 | 0.021999999999999999 / 0.021499999999999998 | `jp_ave_a` 1, `jp_vidrio_b` 2 | 0.021999999999999999 / 0.021499999999999998 |
| `カラス` | `jp_ave_a` 1, `jp_vidrio_b` 2 | 0.0207 / 0.020299999999999999 | `jp_ave_a` 1, `jp_vidrio_b` 2 | 0.0207 / 0.020299999999999999 |
| `cafe` | `coffee_old_a` 1, `coffee_new_b` 2 (empate) | 0.019599999999999999 / 0.019599999999999999 | `coffee_old_a` 1, `coffee_new_b` 2 (empate) | 0.019599999999999999 / 0.019599999999999999 |
| `café` | `coffee_old_a` 1, `coffee_new_b` 2 (empate) | 0.0189 / 0.0189 | `coffee_old_a` 1, `coffee_new_b` 2 (empate) | 0.0189 / 0.0189 |

Los scores también coinciden bit por bit (`float.hex`) entre las dos ejecuciones para cada ID y consulta. La candidata preserva el exacto en otra columna, mientras el campo plegado que consume FTS queda igual al anterior. Los rangos son la salida **medida de esta sonda sintética**, no una afirmación sobre bases reales ni QA oficial.

## 5. Suite completa en copia

Se ejecutó la propuesta únicamente en `/home/user/.cache/e3-cambio2-candidato`, copia aislada de `cf799c7`; no se usó la base viva. Entorno: Python 3.11.2, dependencias de `requirements.txt` y WordNet local. Comando exacto ejecutado, **sin `-k` ni filtros**:

```bash
NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. /home/user/.cache/e3-cambio2-venv/bin/python -m pytest -q tests/
```

Resultado: **754 passed en 177.62 s**, código de salida 0. El log completo está en `.cache` y no se publica. Sus últimas 12 líneas (el log tiene 12 líneas; por tanto se incluye todo el tail disponible, equivalente a las últimas ~20 solicitadas):

```text
........................................................................ [  9%]
........................................................................ [ 19%]
........................................................................ [ 28%]
........................................................................ [ 38%]
........................................................................ [ 47%]
........................................................................ [ 57%]
........................................................................ [ 66%]
........................................................................ [ 76%]
........................................................................ [ 85%]
........................................................................ [ 95%]
..................................                                       [100%]
754 passed in 177.62s (0:02:57)
```

Durante la iteración se corrigió una omisión detectada por tests de migración: el `ALTER TABLE` aditivo debía ejecutarse tanto al crear esquema nuevo como en la ruta de tablas existentes. La suite final completa se volvió a ejecutar después de esa corrección, sin `-k` ni filtros.

## 6. Alcance del patch y límites

El diff candidato toca exactamente estos nueve archivos:

```text
core/mcp_server/search.py
core/mcp_server/write.py
core/memory/consolidation.py
core/memory/constants.py
core/memory/ingest.py
core/memory/schema.py
core/memory_store.py
tests/test_sustantivos_clave_schema.py
tests/test_validacion_unicode_guardado_b2.py
```

La base declarada del diff es el commit completo `cf799c7fcd4acdbe6e46db0e36732513baabc1dd`. Se extrajo ese commit a una copia temporal y allí se comprobó `git apply --check docs/e3_cambio2_propuesta_no_aplicar_20261029.patch` con resultado OK; el patch no se aplicó.

Confirmación explícita del diff: **NO cambia triggers FTS, `MATCH`/BM25 ni los filtros de `core/memory/search.py` en las líneas 1537, 2095 y 2202**. El archivo `core/memory/search.py` no forma parte del diff; esas líneas mantienen exactamente el SQL base. La modificación en `core/mcp_server/search.py` se limita al preprocesamiento de los términos, y no cambia dichos filtros. En `core/memory/schema.py` solo se añaden columnas con `ALTER TABLE`; no se modifica SQL de creación/actualización de FTS ni triggers.

Esta propuesta preserva información para un posible uso futuro; no ofrece una mejora actual de recall o ranking. Las filas antiguas tienen el nuevo campo `NULL`, y no se pueden recuperar marcas que ya se eliminaron. La sonda demuestra igualdad de scores y rangos en un conjunto mínimo, no reemplaza la QA oficial ni una auditoría de la base viva. No se ejecutó censo ni QA oficial para esta candidata.

**Estado: documento y diff NO APLICAR.** A la espera del OK explícito de Dennys antes de aplicar cualquier cambio de motor o ampliar mediciones. La revisión siguiente debe decidir si autoriza QA oficial; si hubiera una discrepancia de FTS/ranking, detener y revisar antes de tocar la rama.
