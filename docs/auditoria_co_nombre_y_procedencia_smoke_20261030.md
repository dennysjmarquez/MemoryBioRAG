# Auditoría de `co_nombre`, `vincular` y procedencia del smoke

**Fecha:** 2026-10-30

**Tipo:** inspección estática de código y metadatos; sin llamadas MCP, mediciones, acceso a bases de datos ni ejecución de QA.

**Rama actual:** `arena/9a54babb-memorybiorag`.

## 1. Cómo nace `co_nombre`

`aprender` llama a `auto_vincular(cerebro, clave, contenido)` durante la escritura (`core/mcp_server/write.py:314-317`). También se llama durante la ingestión y, para cada recuerdo consolidado, durante `consolidar` (`core/memory/consolidation.py:374-377`). Por eso las aristas pueden aparecer antes o durante la consolidación, según qué nodos ya estén en largo plazo.

Dentro de `auto_vincular` hay una pasada explícita por nombre (`core/sinapsis.py:190-244`):

1. Se tokeniza el nombre del concepto después de cambiar `_` y `-` por espacios. Solo se consideran palabras alfabéticas de **4 o más letras**, menos las stopwords; la pasada requiere al menos dos.
2. Se buscan conceptos activos cuyo nombre contenga alguna de esas palabras. El filtro Python cuenta cuántas palabras del nombre nuevo aparecen en el candidato y acepta un solapamiento de **30 % o más** (`nombre_overlap >= 0.3`), con tope de 30 enlaces por nodo.
3. La fila se inserta dirigida desde el concepto nuevo hacia el candidato, con tipo `co_nombre`; el peso combina solapamiento y peso previo del candidato.
4. En esta pasada no se aplica el guard de cierre triádico que sí aparece en la pasada anterior de similitud de contenido (`core/sinapsis.py:154-166`).

No es la única fuente automática posible. La consolidación también vuelve a ejecutar `auto_vincular` y genera `co_ocurrencia` para pares de recuerdos de la misma sesión que comparten al menos dos tokens de contenido (`core/memory/consolidation.py:48-112, 374-384`). Por tanto, el grafo completo observado en el smoke no permite atribuir sus aristas exclusivamente a `co_nombre`.

## 2. Qué hace `vincular` si ya hay una conexión automática

La tool MCP `vincular` delega en `establecer_asociacion` y devuelve `status=ok` sin informar si creó una arista, encontró una existente o cambió su tipo (`core/mcp_server/synapses.py:42-70`).

`establecer_asociacion` comprueba por separado las dos orientaciones (`core/memory/synapses.py:139-161`):

- Si ya existe una fila para una orientación, no la actualiza ni la convierte a `manual`.
- Si falta una orientación, inserta esa fila faltante con tipo `manual` y peso `0.5`.
- Sincroniza el campo heredado `asociaciones` de ambos nodos y hace commit.

Así, una conexión automática que ya tiene ambas filas permanece automática pese a la respuesta exitosa de `vincular`. Si solo existía la fila automática original, `vincular` puede dejar una fila `co_nombre` (u otro tipo automático) en un sentido y añadir una fila `manual` en el inverso. El texto de éxito, por sí solo, no distingue esos casos.

## 3. Prefijos comunes y efecto en la fixture

Sí: los nombres pueden influir directamente. En el smoke, nombres como `smoke_mcp_reintento_objetivo` y `smoke_mcp_color_favorito` comparten `smoke`; el token `mcp` no alcanza el mínimo de cuatro letras, pero `smoke` sí. Si el nombre nuevo tiene tres tokens válidos, compartir solo `smoke` ya representa `1/3` y supera el umbral de 30 %. Entre los nombres de reintento se comparte además `reintento`.

**Corrección aprobada por Dennys:** la respuesta MCP cruda de `recordar_final`, conservada en el JSON, sí etiqueta la asociación enriquecida con `smoke_mcp_color_favorito` como `tipo_sinapsis: co_nombre` (por ejemplo, junto al resultado `smoke_mcp_reintento_objetivo`: `fuerza_arista=0.53`, `peso_vecino=0.98`; también aparece junto a `smoke_mcp_reintento_idempotencia`). Esto confirma el tipo reportado por la respuesta final; corrige la lectura previa que decía que el resultado no mostraba tipos. **No establece cuándo ni por qué nació la arista:** no hubo snapshots entre llamadas ni captura del tipo de cada fila en los snapshots de grafo, y la consolidación contiene otras rutas de enlace. No atribuyo su creación a `aprender`, `consolidar`, `vincular` ni a una causa única.

Para la fixture de la QA:

- No añadir un prefijo léxico común como `qa_smoke_<dominio>_` a todos los nombres de recuerdos. Mantener el identificador de corrida en el nombre de la DB/ruta temporal, no en los conceptos.
- Conservar nombres semánticos fieles y sustantivos propios de cada recuerdo; no fusionar sustantivos entre notas ni deformar nombres para forzar resultados.
- Tratar los términos compartidos que sí sean semánticamente reales como parte del diseño de la fixture: documentar de antemano las asociaciones automáticas plausibles, y no etiquetar como ruido sin valor algo que la propia denominación conecta.
- En una futura medición, guardar el tipo de cada fila y separar explícitamente `co_nombre`, `co_ocurrencia` y `manual`; no inferir tipo a partir de que una pareja aparezca en la respuesta.

## 4. Procedencia del código del smoke

El campo `commit_codigo` del JSON registra correctamente lo que ejecutó su expresión `git rev-parse HEAD`: `41e1793abb9e346f01e619c17611dc158ff27f4a`. Sin embargo, **no identifica por sí solo todo el código ejecutado**:

- Ese commit no contiene `scripts/evaluar_qa_intuicion_asociaciones_e1.py` ni `scripts/qa_stdio_server_intuicion.py` en su árbol de Git.
- Al ejecutarse el smoke, esos archivos existían en el working tree y fueron cargados desde la ruta local por el runner/servidor; estaban sin seguimiento en ese checkout. Por eso, el valor de `commit_codigo` era el HEAD base y no una huella del arnés local.
- Al reconciliar el checkout con la rama del operador se comprobó que ambos archivos locales eran byte-por-byte idénticos a los del commit `ce62e8d1dcd1775b39331bc06406d3e7a27cbf8a` (`docs: proponer smoke test MCP temporal`). Sus SHA-256 son:
  - `scripts/evaluar_qa_intuicion_asociaciones_e1.py`: `1f25c0772ae163e15c4359cf173837d0f27c954fa2849f9741db25fd0163371a`
  - `scripts/qa_stdio_server_intuicion.py`: `e8c4587d72fffcb73a75d06d22c6112eb39070f3684e9f14b4b61d578cebafe9`

**Corrección de procedencia para auditores:** conservar sin reescribir el JSON original (`commit_codigo=41e1793...`) como registro literal; interpretar ese campo como el HEAD observado del checkout, no como versión completa del código. La evidencia de identidad del arnés/launcher es la pareja de SHA-256 y su coincidencia con `ce62e8d`. El smoke usó el working tree, no un checkout limpio de `41e1793`.

## 5. Observación propuesta para una futura prueba temporal (no ejecutada)

La especificación concreta, con secuencia por llamada, formato de filas y reglas de clasificación de diffs, se publica en `docs/propuesta_snapshot_aristas_mcp_temporal_20261030.md`. El resumen siguiente no la ejecuta:

1. Usar una DB temporal nueva y aislada. Antes y después de cada llamada MCP, tomar un snapshot **de solo lectura de esa DB** con las filas `(origen, destino, tipo, peso, creado_en, ultimo_uso)` de `sinapsis`. Guardar junto al snapshot el número de secuencia, nombre/argumentos de la tool, respuesta MCP cruda, respuesta parseada y error.
2. Diferenciar filas nuevas de filas existentes cuyo peso/tipo solo cambió. Comparar pares no dirigidos para el inventario de conexiones, pero conservar las dos orientaciones y su tipo para detectar el caso mixto `co_nombre`/`manual`.
3. Tomar snapshots entre `aprender`, `consolidar`, cada `vincular` y `recordar`. Si `consolidar` añade filas, atribuirlas solo al intervalo de esa llamada: el tool agrupa varias operaciones internas y un snapshot de borde no prueba qué subpaso concreto las insertó.
4. Para caracterizar prefijos, usar dos DB temporales independientes con los mismos recuerdos sintéticos, pero nombres de nodos diferentes solo en la presencia/ausencia del prefijo genérico. Mantener separados textos, sustantivos, dimensiones, bridges y secuencia; comparar qué tipos de arista aparecen. Esto sería una prueba diagnóstica futura, sujeta a autorización, no una medición realizada ahora.
5. Para observar específicamente la interacción de `vincular` con una arista automática, capturar filas antes y después de llamar MCP `vincular` sobre esa pareja. El diff mostrará si no hubo cambios o si se añadió solo la orientación inversa `manual`; la respuesta `status=ok` no basta.

No se ejecutó ninguno de estos pasos. No se tocó motor, ranking, DB original ni snapshot; no se ejecutó la QA completa y los umbrales siguen pendientes.
