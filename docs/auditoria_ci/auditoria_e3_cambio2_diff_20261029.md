# Auditoría — E3 Cambio 2, diff de dos columnas (`19e2f94`) — 2026-10-29

**Veredicto: APROBADO CON CAMBIOS. Todavía no se aplica.** El diseño es correcto y el ranking es seguro, pero hay dos rutas que dejan la columna exacta mal.

## Comprobado
- `19e2f94` (padre `cf799c7`) solo añade documentos. Los SHA-256 coinciden: informe `95fe5d53…`, diff `1e6e6666…`.
- El diff se aplica limpio sobre `cf799c7` y toca 9 archivos. **No toca** los triggers FTS, `MATCH`/BM25 ni `core/memory/search.py`.
- **La suite completa en mi copia da 754 passed** (160 s, sin filtros).
- **La columna plegada queda idéntica a la de hoy:** en 200 000 entradas aleatorias (latín con marcas, ñ, kana con dakuten, devanagari con nukta, NFD, ancho completo), `normalizar_sustantivos_clave(normalizar_sustantivos_clave_exacto(x)) == normalizar_sustantivos_clave(x)` da **0 discrepancias**. Lo que lee el ranking no cambia.
- `ガラス,カラス` se guarda como `('カラス', 'ガラス,カラス')` en corto y en largo plazo.

## Defectos (sonda en la copia, base sintética)
1. **Una actualización sin sustantivos borra los exactos.** Después de `percibir_corto_plazo(..., sustantivos_clave="")` y consolidar, la fila queda `('カラス', '')`: la plegada se conserva, pero la exacta se pierde. Causa: `COALESCE(sustantivos_clave_exactos, '')` entrega `''`, y `'' is not None` sobrescribe el valor. Es justo la pérdida de información que el Cambio 2 debe evitar.
2. **`actualizar` MCP deja la columna exacta desfasada:** después de cambiar los sustantivos a `perro,gato`, la fila queda `('perro,gato', 'ガラス,カラス')`. Ahora existen dos columnas, así que esta ruta ya no puede quedar "aparte": basta con escribir también la exacta.
3. (Menor) Las filas sin exactos deben quedar en `NULL`, no en `''`.

## Cambios requeridos
- **Regla única** (consolidación e ingest): la columna exacta **sigue a la plegada**. Si la nueva plegada no está vacía, se toma la exacta nueva (o `NULL` si no viene). Si viene vacía, se conservan las dos actuales. No usar `COALESCE(..., '')` para la exacta.
- **`actualizar`:** si recibe `sustantivos_clave`, escribe también `normalizar_sustantivos_clave_exacto(...)`. El plegado de ancho sigue fuera de alcance.
- **Guardián + tests:** en cualquier ruta, o la exacta es `NULL` o `fold(exacta) == plegada`. Añadir los 3 casos de esta sonda como tests.
- Después: suite completa sin filtros, diff v2 publicado con hash, y solo entonces el OK de Dennys para aplicar y medir las 4 QA (deben dar resultados idénticos).

## Diff v2 (`47f7f60`, SHA-256 `82fa4429…`) — **APROBADO** para aplicar y medir, con el OK de Dennys

- Se aplica limpio sobre `cf799c7` y toca los mismos 9 archivos. `core/memory/search.py` no cambia, ni los FTS/triggers.
- **Suite completa en mi copia: 757 passed** (168 s, sin filtros).
- **Las 3 sondas de la auditoría anterior quedan corregidas:**
  1. Una actualización sin sustantivos ahora conserva las dos columnas: `('カラス', 'ガラス,カラス')`.
  2. `actualizar` sincroniza las dos columnas: `('perro,gato', 'perro,gato')`.
  3. La ausencia de exactos queda en `NULL`, y el guardián `normalizar_sustantivos_clave_exactos_coherentes` descarta las exactas incoherentes.

**Un cambio de comportamiento que debe quedar a la vista** (sale de mi propia instrucción, "regla única en consolidación **e ingest**"): en **corto plazo**, una segunda percepción **sin** sustantivos antes **borraba** la columna plegada; ahora la **conserva**. Sonda sobre una base limpia: antes, corto `('',)` → largo `('',)`; con v2, `('vidrio,ventana',)` → `('vidrio,ventana',)`.
- Lo considero una corrección: una entrada sin datos no debería borrar datos, y así queda igual que la regla RF-15 del largo plazo.
- **No afecta la búsqueda ni la QA**, que no escribe. Las únicas rutas que llaman sin sustantivos son `auto_guardado` (con sus propias claves `sesion_…`), `memory_service` e `interceptor`.
- **Al aplicar:** actualizar el docstring de `ingest.percibir_corto_plazo` ("Sobrescribe el valor previo") para la entrada vacía, y declararlo en los resultados.

**Medición esperada después de aplicar:** las 4 QA oficiales iguales a B3; FP 0/40; multilingüe directa y MCP con 132 casos sin cambios; guardados MCP 69/80.

## Decisión de Dennys (2026-10-29)
- **Opción A aceptada:** una nota sin palabras clave ya no borra las que la memoria tenía en corto plazo.
- **Idea para DESPUÉS** (no entra en el Cambio 2): Dennys plantea que las palabras clave deberían **fusionarse** cuando una memoria recibe varias notas antes de consolidar. Hoy el contenido y los sinónimos se fusionan, pero las palabras clave se **reemplazan** por las más nuevas (Decisión 2 del plan 001, "si el tema cambió"). Lo mismo hace `agregar_sustantivos`, que funciona en corto y largo plazo; `actualizar` solo funciona en largo plazo. Se tratará como cambio propio: diff, OK de Dennys y medición.
