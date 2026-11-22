# Auditoría — E3 Cambio 2, investigación (`cf799c7`) — 2026-10-29

**Veredicto: APROBADO CON CAMBIOS.** El diagnóstico está aprobado. El diseño de la propuesta cambia antes de escribir el diff real.

## Comprobado
- `cf799c7` (padre `4261f71`) solo añade 2 documentos; no toca el motor.
- SHA-256 iguales a los publicados: informe `45abe3a3…`, propuesta `38bf7a89…`.
- El diagnóstico es correcto: `constants.py:286-311` quita las marcas (`_quitar_acentos`) **antes** de deduplicar, y `ガラス,カラス` queda como un solo `カラス`.
- La condición de peso igual en el ranking quedó escrita de forma explícita, y la sonda está marcada como predicción, no como medición.

## Problema del diseño propuesto (proyección dentro del FTS)
Lo comprobé en el código de `c695310`:
1. **El FTS lo llenan triggers SQL** (`schema.py`, `largo_plazo_ai`/`_au`) con la columna tal cual. Para "proyectar", el trigger necesitaría una función Python registrada (UDF). Cualquier conexión que no la registre (otra herramienta, restaurar un dump, el CLI de sqlite) **fallaría al escribir**: "no such function".
2. **Hay filtros que leen la columna cruda**, no el FTS: `search.py:1537`, `:2095` (`PALABRA_INICIO_ANCHO`) y `:2202`. Si la columna guarda `ガラス` y la consulta llega plegada a `カラス`, esos filtros pueden **perder candidatos**. Hay que tocarlos todos.
3. Habría que **reconstruir el índice FTS** en las bases existentes.

Son demasiadas piezas para un cambio cuyo requisito es "el ranking no cambia".

## Diseño requerido: dos columnas (aditivo)
- `sustantivos_clave` **sigue exactamente como hoy** (plegada, y deduplicada por la forma plegada). FTS, triggers, BM25 4.0, QCR y prefijos quedan **sin tocar**, así que el ranking es idéntico por construcción.
- **Columna nueva** `sustantivos_clave_exactos TEXT` (NFC, con marcas), en `largo_plazo` y `corto_plazo`, con `ALTER TABLE ADD COLUMN`: el patrón ya existe 35 veces en `schema.py`. Las filas antiguas quedan en NULL; no se migra ni se reescribe nada.
- El **conteo, la deduplicación y la validación** usan la forma exacta: `ガラス,カラス` cuenta 2. La consolidación copia la columna nueva.
- `actualizar` MCP queda como pendiente separado, como se acordó.

**Prueba de éxito:** las 4 QA oficiales deben dar resultados idénticos; el informe debe mostrar `MATCH`/FTS y los filtros de prefijo sin cambios en el diff; la sonda mixta debe registrar scores sin redondear iguales; y la suite completa debe pasar, sin filtros.

**Beneficio honesto:** hoy solo **preserva información** que antes se destruía. La ganancia medible llegará cuando alguien la use, por ejemplo la neurona de razonamiento para desempatar, con su propia medición.
