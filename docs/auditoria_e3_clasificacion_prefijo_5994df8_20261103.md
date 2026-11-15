# Auditoría E3: clasificación de consultas de prefijo `5994df8`

Se inspeccionó `5994df8a161ad86f54a38ef22f8ed36c7e8e51c0`, hijo de `29a429b`: cambia dos scripts de QA y un informe, sin editar `core/`. `git diff --check` del commit y `py_compile` de los dos scripts modificados y del runner de etapas anterior pasaron. Se reprodujo con `PYTHONHASHSEED=0` en dos checkouts y fixtures sintéticos aislados, usando el mismo arnés del operador y el entorno de auditoría anterior.

## Matriz de prefijos

El runner actualizado de prefijos terminó con exit 0: nueve comprobaciones verdaderas, siete casos, 28 llamadas MCP incluyendo aperturas, cero flags MCP en búsquedas y aperturas. Los JSON parseados completos baseline/instrumentado fueron iguales en 7/7 casos; no hubo cambios en los snapshots observados al abrir y buscar, de alcance limitado. Los controles de paráfrasis y de protección mantuvieron los resultados descritos. En el caso multitémino con paráfrasis, se registró una sentencia `content_match_scoring` y ningún SQL del guardia final con el objetivo como entrada; el predicado de ese guardia exige un solo token extraído. Clasificar por forma SQL permite distinguir mejor los casos inspeccionados, pero no garantiza clasificación de cualquier SQL futuro.

## Regresión en el runner de etapas existente

El runner anterior `scripts/diagnosticar_traza_interna_parafrasis_e3.py`, publicado por el operador en `6369951` y reutilizado como arnés, se ejecutó desde el mismo commit `5994df8` en copia sintética: **exit 1**, `AssertionError: La ruta sintética de exclusión del candidato no quedó confirmada`. `py_compile` no detecta esta incompatibilidad runtime.

Causa identificada en código y comprobada con una ejecución adicional de `execute()`: el launcher ahora etiqueta la consulta del guardia con `filter_kind="final_single_word_prefix_guard"`, mientras el resumen del runner anterior aún compara el valor exacto `"single_word_prefix_guard"`. En la réplica, la consulta nueva sí registró el objetivo como entrada, cero filas válidas, eliminación del candidato en `resultados_con_hibrido`, conteo cero y respuesta de contingencia, pero el booleano `target_excluded_by_single_word_prefix_guard` quedó `false`; por eso la aserción final falla. Es una regresión en la instrumentación/QA, **no un fallo demostrado del motor ni invalidación de la evidencia anterior**. Corregir coherentemente la interfaz de etiquetas entre launcher y consumidores; ejecutar ambos runners con resultados completos y equivalencia baseline/instrumentado antes de cerrar el diagnóstico. No cambiar el motor.

## Evidencia y límites

La salida íntegra propia de la matriz tiene SHA-256 `7467ec548cd41c36b5bcc043ac97f68557de64f3eb4bd48b79ab94053c0b3f55`, diferente del hash de `run08` publicado por el operador. No se accedió a la evidencia privada original y no se determina la causa de esa diferencia. El runner anterior falló antes de escribir su archivo final; se preservaron el traceback y el resultado completo de la ejecución adicional de `execute()`.

Artefacto privado `auditoria_e3_5994df8_20261103.tar.gz`, Drive ID `13PpNJFGtDGmxO1KXOiGkexpHjqxlxxvE`, SHA-256 `c5dca5717144b70f7ad6b7ee452a2e2c62bee62a6effe3b87dd86df7b890430b`. No se ejecutó la suite completa ni se utilizaron bases originales. E3 sigue abierto; no se inició E4.
