# Neurona de puentes: cotejo de rutas e integración sintética — 2026-11-01

## Corrección importante de alcance

La prueba anterior (`auditoria_neurona_puentes_compuerta_sintetica_20261101.md`) llamó directamente la función del hub de **cobertura IDF**. Al seguir el punto de entrada real se confirma que esa ruta se selecciona con `BIORAG_HUB_MOTOR=idf`; sin esa variable, el selector usa `escala`. Con `BIORAG_HUB_ESCALA` por defecto, se usa la implementación a escala. La neurona de puentes aparece en la ruta IDF, no en el cuerpo de la ruta a escala o legacy, según las referencias inspeccionadas en `core/`.

Por tanto, **el hallazgo anterior no demuestra una pérdida en el motor de fábrica ni que esta neurona actúe en la configuración de Dennys**. No se consultó el entorno de su instalación ni sus pesos. Se mantiene como riesgo reproducido de la ruta IDF con un estado fabricado, no como resultado de la base viva.

## Qué se comprobó ahora

Se construyó una fixture de cinco puentes y un nodo sintéticos en SQLite **en memoria**, mediante las funciones de creación y validación del Concept Hub. La prueba usa el punto de entrada `expandir_query_con_hub`, la tokenización y el índice reales. Solo la lectura del estado neuronal se sustituye en la comparación activa/apagada por parámetros fabricados; no se entrenaron ni se guardaron parámetros. La búsqueda usa la misma consulta, fixture y umbral por defecto de cada ruta. `conn.total_changes` no aumentó durante las búsquedas; no se verifica por eso toda clase de cambio en memoria o en otros procesos.

| Condición | Observación en esta fixture |
|---|---|
| IDF, neurona apagada | Devuelve el hub. |
| IDF, estado ausente cargado por la función real | Devuelve el mismo resultado que apagada. |
| IDF, estado no neutro fabricado y activo | La función no devuelve el hub después de la atenuación. |
| Escala explícita, interruptor neuronal apagado/encendido y estado fabricado | Ambos resultados son iguales y no se llama a la carga del estado neuronal. |
| Selector de fábrica sin `BIORAG_HUB_MOTOR` | Mismo resultado que escala explícita, para esta fixture; no se llama a la carga neuronal. |

Salida literal del script:

```text
idf=hub_off_y_neutro, sin_hub_on_simulado; escala=sin_cambio_y_sin_cargar_neurona
fixture=5_puentes_sinteticos; escrituras_durante_busqueda=0
```

Archivo: `scripts/auditar_rutas_neurona_puentes_sintetica.py`, SHA-256 `34befc76f4a11b60d1b1c4f5688f13bc024247fe4abf27fcaf9895c089ddaa93`; código auditado en `b7a82ff`. Comando: `PYTHONPATH=. python scripts/auditar_rutas_neurona_puentes_sintetica.py`. En el entorno temporal de prueba, Python 3.11 con NumPy 2.4.6, el script terminó código 0. Además `pytest tests/test_neurona_puentes.py -k 'not aprende and not entrenar' -q`: **13 passed, 3 deselected**; las tres excluidas ejercitan entrenamiento.

## Qué significa para el plan

La neurona existente no debe describirse como activa universalmente: depende de la ruta y de un estado no neutro. Tampoco basta garantizar que el primer filtro no cambie para asegurar que una pista atraviese toda la cadena. Estas pruebas usan un único escenario sintético con estado inventado; **no miden recall, ni prueban que el nodo desaparezca del conjunto final de una búsqueda**. Otras rutas podrían recuperarlo. El interruptor controla el uso de esa neurona, no modifica la configuración general del producto en esta auditoría.

Para avanzar hacia v36/v37 conviene inventariar qué ruta real se usa, cómo se combinan sus resultados con otros canales y cuáles son los guardianes efectivos; después comparar con consultas y copias apropiadas antes de proponer una mejora. No cambiar una puerta ni apagar o entrenar una neurona como reacción automática. Preservar asociaciones y pistas; si una prueba muestra pérdida, informar también si la pérdida afecta la expansión, el pool o solo el orden.

No se ejecutó E1 ni MCP; no se consultaron DB reales, no se entrenaron neuronas, no se cambió el motor ni se modificó el gold. El análisis anterior queda corregido explícitamente, sin borrar la evidencia original.
