# E3 Cambio 2 — guardar sustantivos exactos, comparar también sin marcas

**Estado: PROPUESTA NO APLICAR.** El archivo `docs/e3_cambio2_propuesta_no_aplicar_20261029.patch` es un diff v2 válido contra `cf799c7`, pero no se aplicó al motor ni a ninguna base. La publicación contiene solo documentos. Cualquier aplicación requiere OK explícito de Dennys.

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
- **Actualización MCP:** el primer diff v1 no sincronizaba `sustantivos_clave_exactos` en `biorag_actualizar`. La auditoría `6acfef3` lo detectó; el diff v2 ahora escribe plegada y exacta juntas cuando recibe `sustantivos_clave`, con test MCP dedicado. No amplía el alcance al plegado de ancho ni cambia el resto del recorrido de `actualizar`.

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

## 3. Cambios exigidos por auditoría: diff v2

La auditoría del diff v1, `docs/auditoria_ci/auditoria_e3_cambio2_diff_20261029.md` en la rama auditora, commit `6acfef36ceb9c5cc1880d8b7546f795e86df62ba`, dio **APROBADO CON CAMBIOS — NO aplicar aún**. La versión v2 resuelve los tres hallazgos sin tocar la búsqueda ni FTS:

1. **Regla plegada/exacta única (ingestión y consolidación):** si la nueva `sustantivos_clave` plegada no está vacía, se reemplaza la plegada y la exacta nueva; si exacta no viene o no es coherente, se guarda `NULL`. Si la plegada nueva está vacía, se conservan ambas columnas actuales. Las consultas internas dejan de usar `COALESCE(sustantivos_clave_exactos, '')`, para no confundir `NULL` con una actualización explícita vacía.
2. **`actualizar` MCP:** cuando recibe `sustantivos_clave`, calcula y escribe también `normalizar_sustantivos_clave_exacto(...)` en `sustantivos_clave_exactos`, sincronizada con el valor plegado. Sin expansión del plegado de ancho.
3. **Guardián de consistencia:** `normalizar_sustantivos_clave_exactos_coherentes` solo conserva exactos no vacíos si `fold(exacta) == sustantivos_clave`; de lo contrario retorna `NULL`. Así las rutas de ingreso, consolidación y actualización mantienen el invariante «exacta es NULL o pliega al valor almacenado». Una ausencia de exactos se representa con `NULL`, nunca `''`.
4. **Tests añadidos:** (a) `percibir_corto_plazo(..., sustantivos_clave="")` conserva plegada y exacta y consolidación las transfiere; (b) `actualizar` MCP sincroniza ambas columnas; (c) exactos ausentes quedan `NULL`. Además se prueba que el guardián descarte exactos incoherentes.

La auditoría verificó `fold(exacto(x)) == fold(x)` en 200 000 entradas sin discrepancias. El diseño sigue usando dos columnas aditivas y las filas anteriores quedan `NULL`, sin backfill. La exacta se preserva en NFC; `actualizar` queda incluido solo para mantener la coherencia de las dos columnas, sin cambio de alcance a otras semánticas.

## 4. Sonda mixta sintética previa: baseline vs. diff v1

La sonda mixta reportada en la versión v1 comparó `cf799c7` con una candidata aislada, usando históricas con exactos `NULL`. Resultados medidos (rangos y scores sin redondear); la auditoría confirmó que el ranking no cambia. **No se repitió la sonda después de los cambios v2**, que se limitan a persistencia/coherencia y no alteran FTS ni búsqueda.

| Consulta | Rangos antes / v1 | Scores antes / v1 (rango 1 / rango 2) |
|---|---|---|
| `ガラス` | `jp_ave_a` 1, `jp_vidrio_b` 2 | 0.021999999999999999 / 0.021499999999999998 |
| `カラス` | `jp_ave_a` 1, `jp_vidrio_b` 2 | 0.0207 / 0.020299999999999999 |
| `cafe` | `coffee_old_a` 1, `coffee_new_b` 2 (empate) | 0.019599999999999999 / 0.019599999999999999 |
| `café` | `coffee_old_a` 1, `coffee_new_b` 2 (empate) | 0.0189 / 0.0189 |

Estos scores son del ejercicio previo v1; no se presentan como una medición nueva de v2 ni sustituyen QA oficial.

## 5. Suite completa v2 en copia

El diff v2 se probó en `/home/user/.cache/cambio2-v2/candidate`, copia aislada de `cf799c7`; no se usó base viva. Python 3.11.2, dependencias exactas de `requirements.txt` y WordNet local. Comando exacto, **sin `-k` ni filtros**:

```bash
NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. /home/user/.cache/cambio2-v2/venv/bin/python -m pytest -q tests/
```

Resultado final: **757 passed en 137.20 s**, código de salida 0. Log completo local (no publicado): `/home/user/.cache/cambio2-v2/suite-v2.log`. Sus últimas 12 líneas (el log solo tiene 12 líneas; se incluye todo el tail disponible):

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
.....................................                                    [100%]
757 passed in 137.20s (0:02:17)
```

Los dos módulos con regresiones v2 se ejecutaron primero de forma focalizada: `30 passed in 4.81s`. La conclusión de suite completa corresponde a la ejecución final, sin filtros.

## 6. Base, alcance del diff v2 y límites

El diff v2 aplica limpiamente sobre **`cf799c7fcd4acdbe6e46db0e36732513baabc1dd`**, verificado mediante `git apply --check` en una extracción de ese commit. Toca exactamente estos nueve archivos:

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

Confirmación explícita: **NO cambia triggers FTS, `MATCH`/BM25 ni los filtros de `core/memory/search.py` en las líneas 1537, 2095 y 2202**. Ese archivo no forma parte del diff; las líneas mantienen el SQL base. En `core/memory/schema.py` se añaden las columnas con `ALTER TABLE`, sin alterar triggers, definición de FTS ni su rebuild. `core/mcp_server/search.py` solo valida la forma exacta en entrada y mantiene la forma plegada para las rutas existentes.

SHA-256 del diff v2: `82fa44297624cc65b5d46f7c461340a49eabe40adb345f9ddc3d5246150e0bb9`.

**Estado: documentos y diff v2 publicados; propuesta NO APLICAR.** Ningún cambio de motor ni migración se ha aplicado. Se requiere OK explícito de Dennys antes de aplicar; la QA oficial de cuatro casos queda para después de esa autorización.
