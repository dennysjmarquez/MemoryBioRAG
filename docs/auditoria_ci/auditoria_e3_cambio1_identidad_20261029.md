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
