# Auditoría de cimientos: hub y filtro de una palabra — 2026-11-01

## Alcance y por qué importa

Al seguir cómo el Concept Hub alimenta `buscar_por_frase`, se observó una posible pérdida de una pista **después** de que el hub haya encontrado un nodo. Este caso es distinto de la atenuación neuronal IDF descrita en `auditoria_neurona_puentes_rutas_20261101.md`: aquí también interviene la ruta a escala, que es la seleccionada por defecto en el código cuando no se cambia la configuración. La configuración concreta de la instalación de Dennys no se comprobó.

La evidencia siguiente es **una prueba local sintética**, no una exploración MCP, una medición E1 ni un cálculo de recall sobre datos reales. No demuestra que suceda en una base concreta, no prueba que la pista no sea recuperable mediante otra consulta y no atribuye al cerebro completo el resultado de una búsqueda aislada.

## Seguimiento del código

1. `core/memory/search.py` consulta `expandir_query_con_hub` y puede usar el resultado para expandir términos, sumar señal de hub, dar bypass QCR y traer el primer canónico activo desde largo plazo. La expansión de términos depende del probe FTS; la promoción posterior tiene sus propias condiciones.
2. La promoción puede registrar el origen `concept_hub`. Después, el filtro de una sola palabra trata como literales los orígenes que **no** están en `_ORIGENES_NO_LITERALES` y exige que la palabra aparezca como prefijo en campos del recuerdo. `concept_hub` no figura en ese conjunto en el código auditado. Esto puede afectar un canónico encontrado precisamente por un puente con vocabulario distinto.
3. `total` se calcula antes de esos filtros a partir de `todos`. Su significado no es necesariamente el número final de filas de la página; una discrepancia por sí sola no demuestra corrupción.

## Prueba reproducible

`scripts/auditar_filtro_hub_sintetico.py`, SHA-256 `564c8581e47287e928da8357584fcebe289887a1adda4bfdc50feb7c591b2b93`, código base `6271a7b`. Se ejecutó con Python 3.11 y NumPy 2.4.6:

```text
casos=6; escala_e_idf_una_palabra=hub_presente_canonico_ausente
parche_diagnostico=canonico_presente; idf_dos_palabras=canonico_solo_sin_neurona_simulada
dbs=temporales_sinteticas; entrenamiento=ninguno; prueba=no_mcp_no_e1
```

Cada caso usa una DB temporal nueva y la misma fixture de un recuerdo activo y cinco puentes fabricados, con búsqueda local real. La neurona de ranking está apagada y WordNet, PPMI y síntesis DMN están desactivados en la prueba; por tanto no representa todas las configuraciones. No se accede a bases privadas, no se ejecuta MCP ni se entrena. La comparación IDF activa usa parámetros neuronales **inventados** solo en RAM; no fueron leídos de ningún usuario.

| Ruta / consulta | Condición | Hub devuelto | Canónico en página | Filas / total reportado |
|---|---|---:|---:|---:|
| Escala / una palabra | Código actual, neurona de puentes apagada | Sí | No | 0 / 1 |
| Escala / una palabra | Parche diagnóstico temporal en RAM | Sí | Sí | 1 / 1 |
| IDF / una palabra | Código actual, neurona de puentes apagada | Sí | No | 0 / 1 |
| IDF / una palabra | Parche diagnóstico temporal en RAM | Sí | Sí | 1 / 1 |
| IDF / dos palabras | Neurona de puentes apagada | Sí | Sí | 1 / 1 |
| IDF / dos palabras | Neurona activa con estado inventado | No | No | 0 / 0 |

El parche diagnóstico solo añade `concept_hub` al conjunto de orígenes tratados como no literales durante esa prueba en RAM. El cambio en los dos casos de una palabra respalda que **ese filtro interviene en esta fixture**. No demuestra que sea la única causa posible en otras consultas ni que aplicar esa modificación al producto sea seguro. Los casos son caracterizaciones del estado actual: no se consideran pruebas de aceptación de pérdida, y deberán revisarse si se aprueba una corrección.

## Próximo paso de ingeniería

Antes de proponer un diff de motor, medir de forma aislada los efectos sobre canónicos, pistas, otros orígenes, controles negativos, puntuación y paginación, y comprobar el comportamiento de agente + BioRAG vía MCP en copias apropiadas bajo los permisos vigentes. Una mejora no debe sustituir un tipo de pérdida por otra ni descartar relaciones indirectas; no asumir que cambiar un conjunto sea suficiente para todos los casos. Preparar baseline y diff exacto, sin aplicarlo hasta contar con autorización.

No se modificó motor, base original o gold; no se ejecutó E1 ni se entrenó una neurona. La evidencia muestra un cuello de botella de cimientos que puede afectar la ruta por defecto en esta fixture, no una medición del sistema completo.
