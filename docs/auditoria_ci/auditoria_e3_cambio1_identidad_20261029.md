# Auditoría: E3 Cambio 1 (identidad Unicode), propuesta `3f71f74`

**Veredicto: APROBADO CON CAMBIOS** (2 cambios antes del OK de Dennys). Nada aplicado al motor.

**Verificado por el auditor:**
- Huellas publicadas: diff `98254a86…`, informe `3ee4d90c…` (coinciden).
- El diff aplica limpio sobre `3f71f74` (= `b4fef27` + documentos). Tras aplicarlo en copia: `core/identidad_unicode.py` `09423e0c…`, `core/memory/search.py` `7193ee7f…` (coinciden con el informe).
- Pruebas en copia: **746 passed** (Python 3.11.2 / SQLite 3.40.1).
- La función `normalizar_identidad` es correcta y acotada: NFC + plegado `<wide>/<narrow>` del bloque U+FF00–FFEF + U+3000 → espacio. `ｶﾞﾗｽ` → `ガラス`; `カ`+U+3099 → `ガ`.

**Cambio pedido 1: contenido y sinónimos nuevos, plegar solo letras y números.** Comprobado: `normalizar_identidad("你好，世界！（测试）：ＡＢＣ１２３")` = `"你好,世界!(测试):ABC123"`. La puntuación china/japonesa estándar (，！（）：？) está en ese bloque y se convertiría en ASCII en el texto que guarda el usuario. La búsqueda tokeniza con `\w` (solo letras y números), así que plegar la puntuación del contenido no aporta nada a la búsqueda y sí altera el texto. Propuesta: en contenido y sinónimos, plegar solo caracteres de categoría Unicode L*/N* del bloque (y no tocar U+3000). En consulta, sustantivos, puentes y nombres, la función completa está bien.

**Cambio pedido 2: no bloquear la actualización de recuerdos antiguos.** Comprobado en copia: con un recuerdo antiguo `ｇｏ_ｔｏ`, `aprender(c, "ｇｏ_ｔｏ", "actualizado")` lanza `ValueError` (`_comprobar_clave_legacy`). Así un recuerdo antiguo con nombre de ancho completo ya no se puede actualizar. Propuesta: si la clave original existe, escribir sobre esa clave original (actualizar el recuerdo existente), sin error y sin crear un duplicado con la clave plegada.

**Sobre la base mixta (orden 1↔2):** no es una regresión, es la identidad funcionando: con la propuesta, `ｚｑｘｈｎ` y `zqxhn` devuelven exactamente la misma lista. Ambos recuerdos contienen el mismo marcador y no hay gold. Debe documentarse así.

**Después del diff v2 y del OK de Dennys:** las 4 QA oficiales + multilingüe + MCP, como siempre.

## Auditoría de la aplicación: commit `c695310` — **APROBADO** (2026-10-29)

- **Motor = diff v2 autorizado**: los 12 archivos de motor/docs son byte a byte iguales a `0b1bd52` + diff `68439804…`; la única diferencia es la línea del test MCP pedida por el auditor (`sustantivos_clave="ejemplo"`).
- **CI de la PR**: Python 3.11 y 3.12 en verde. Suite completa reportada: 753 passed (el auditor obtuvo 752 + 1 fallo del test, que es exactamente la línea corregida).
- **4 QA oficiales = B3/B4a** en global y por categoría, FP 0/40 (informe `4261f71`). **Guardados MCP 69/80**, igual que B3 (zh 18, ja 15, ko 16, ru 20). Multilingüe directa y MCP sin cambios; los 2 FP ingleses siguen (B4b).
- El JSON agregado no contiene consultas, títulos ni contenidos de la viva (comprobado).

**Límites, dichos con honestidad:**
1. Las 4 QA oficiales prueban que **no hay daño** (piso), pero **no ejercitan el cambio**: el auditor comprobó que **0 de 921** consultas cambian con `normalizar_identidad` (con o sin `zzqx`). La mejora la demuestran las pruebas unitarias y las sondas sintéticas.
2. La herramienta MCP `actualizar` no pliega ancho: pendiente pequeño y aislado.
3. La QA oficial guarda agregados y fallos, no todos los rangos individuales. Guardar el rango por caso será útil también para el examen de v37 (cambio separado, más adelante).
