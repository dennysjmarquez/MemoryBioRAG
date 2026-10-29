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
