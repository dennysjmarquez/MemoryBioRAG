# Auditoría de rutas MCP y pistas históricas — `caf2dfd`

## Veredicto

Reproducidos los **ocho brazos sintéticos** y sus resultados principales. La evidencia apoya continuar investigando las etiquetas, **no elegir una política** ni aplicar cambios de motor. Hay una precisión importante: las dos asociaciones manuales se conservaron, pero la red no quedó idéntica en las copias; al abrirlas apareció una fila sináptica adicional de tipo `dmn_synthesized`.

## Procedimiento y observaciones

El commit `caf2dfd5897b063ba28ebc67080076b074a48b41` es la cabeza remota cotejada; frente a `e9e2a89` solo modifica el inventario y añade un runner. El motor y rutas `core`, `middleware`, `config` y `biorag.py` coinciden con nuestra referencia `78cf81e`. SHA-256 del runner `ac22345b2e33118425cc216d55b5ca1ba2fdbd8ead83125be8385ba03e987f9c`; `core/memory/search.py` mantiene `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`.

Se ejecutó el runner exacto desde un árbol temporal, con dependencias y HOME aislados, `PYTHONHASHSEED=0` y neurona apagada. Crea bases sintéticas, copia una por brazo y aplica acumulación solo mediante SQL en la copia. Salida 0. No se usaron bases del usuario, no se cambiaron motor ni datos reales y no se fusionaron recuerdos. El test invoca directamente las funciones MCP registradas mediante un capturador; **no usa transporte MCP stdio ni un agente autónomo**.

En las dos rutas de escritura se reprodujo: historia útil, la pista antigua no figura en el FTS de etiquetas y el objetivo no aparece en reemplazo, mientras que con acumulación figura y se recupera en rango 1; historia contradicha, la pista no figura en etiquetas con reemplazo pero el objetivo sí aparece en rango 1. Las pistas nuevas y estables recuperaron el objetivo en rango 1; cuando se recuperó, aparecieron ambos vecinos en asociaciones y contexto. La respuesta de `sustantivos` coincidió con la columna almacenada en **8/8** brazos en un control adicional propio.

El contenido del caso contradicho incluye expresamente el término antiguo, lo que es compatible con una ruta textual alternativa. El ensayo no aísla ese término o el generador de candidatos, por lo que no prueba causalidad exclusiva. Asimismo, el caso útil tiene una fixture diseñada donde la pista antigua no está en contenido; sus resultados no cuantifican pérdidas en otros recuerdos o consultas. Tres búsquedas suceden en secuencia en la misma copia de cada brazo: no hay aquí un control de orden ni de copia nueva por consulta.

## Control adicional de aristas: resultado no previsto

El runner cuenta las dos asociaciones iniciales y observa vecinos, pero no coteja todas las filas antes y después. Añadimos una verificación independiente, sin imprimir aristas ni valores:

- En las ocho copias, las **cuatro filas iniciales** que representan las asociaciones se conservaron; el resultado de `sustantivos` se verificó contra la fila objetivo.
- En las ocho, la copia pasó de cuatro a **cinco** filas tras la primera apertura. Un control separado que solo abrió y cerró la copia, sin operación MCP de escritura, reprodujo la fila adicional; era de tipo `dmn_synthesized`. El control confirma el momento observado, no demuestra una causalidad de ranking o de las asociaciones mostradas.
- Al preabrir la copia en un control adicional y comparar inmediatamente antes y después de la escritura, no hubo diferencias en filas sinápticas durante las dos rutas, en **8/8** brazos. La apertura previa altera la secuencia de prueba, por lo que se reporta como control separado, no como reproducción idéntica del runner.

Por tanto, «las aristas manuales iniciales se conservaron» está respaldado en esta fixture; **«no se alteraron los vínculos» como igualdad completa del grafo es demasiado amplio**. No se propone eliminar la arista automática ni desactivar componentes del motor.

## Continuación

Pedir que el inventario matice esa observación y la causalidad de los casos, e incluya el control de apertura y el orden de las consultas en mediciones posteriores. Para exploración real cumplir el protocolo MCP stdio, siempre sobre copias; este test directo no mide agente+cerebro. Preservar pistas anteriores, no asumir vigencia ni obsolescencia, no aplicar parches ni avanzar a E4 sin revisión y autorización.

El inventario también mantiene la expresión categórica «causas distintas» para los FP ingleses; ver `docs/auditoria_fp_ingles_etiquetas_e4ce0b3_20261102.md`: son mecanismos compatibles con la evidencia, sin demostración de causa exclusiva.

Evidencia privada `auditoria_e3_mcp_caf2dfd.tar.gz`, SHA-256 `5b37e0799e67483b0765a6758c8a895b9667e00df9834064bb4d767ff56c6d35`, Drive `1t5clId2ag2wmEFaK31UYk5w77vtjQYGu`. Incluye la reproducción y los controles, sin SQLite ni datos vivos; se conservan también los intentos preliminares de comparación, cuya comprobación inicial suponía incorrectamente dos filas en lugar de cuatro.
