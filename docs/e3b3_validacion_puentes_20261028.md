# E3B3 — validación de puentes Unicode

**Resultado final: las cuatro QA originales coinciden con B2 por categoría, R@1 y FP 0/40.** También coinciden R@5, MRR y censo. En los 80 guardados no se perdió ninguno de B2. Dennys autorizó publicar bajo esas condiciones; el auditor revisará antes del siguiente paso.

## Cambio autorizado

Solo se modifica `validar_bridges`: NFC; tramos Unicode de letras, marcas y números; cada tramo no ancho de más de dos caracteres aporta una unidad si no figura en `STOPWORDS_ES`; cada tramo enteramente ancho W/F aporta `len // 2`. Se exigen al menos dos unidades. El texto guardado no se normaliza aquí.

No se editan las condiciones antidestinatario, de texto duplicado ni de ángulos. Reciben los nuevos tokens, por lo que no debe suponerse que todas sus decisiones posibles son idénticas. El conteo es de puntos de código, no de grafemas ni de significado: `１２３４` y `哈哈哈哈` pasan, como se autorizó. No se incorpora una lista inglesa. [Diff exacto de motor y prueba](e3b3_diff_candidato_20261028.patch).

## Sondas, negativos y snapshot

Se usa una clave neutral y los mismos cuatro puentes acompañantes. B2 se carga desde el commit `88f71bbbee9e340511d777b1b56d5d7ee8139802`, con huella verificada.

| Puente | B2 | B3 |
|---|---|---|
| `바다 등대` | rechaza | acepta |
| `우산 가게` | rechaza | acepta |
| `海岸的灯塔` | rechaza | acepta |
| `灯塔` | rechaza | rechaza |
| `海辺の灯台` | rechaza | acepta |
| `que con` | rechaza | rechaza |
| `go to` | rechaza | rechaza |
| `??? @@@` | acepta | rechaza |
| `once lunas` | acepta | acepta |

Los 14 negativos seleccionados ES/EN se rechazan en ambos brazos. Los cinco puentes reales del hub asociado al caso oficial `0593` se aceptan en ambos, y ninguno de los 30 puentes de los seis hubs del snapshot cambia su decisión. Se leyó el snapshot con `mode=ro&immutable=1`; su SHA-256 es `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`, antes y después.

Las sondas comparadas **antes de aplicar** están en [JSON](e3b3_sondas_20261028.json). Después se reprodujeron con B2 extraído de Git y el B3 aplicado: [salida](e3b3_comparacion_puentes_20261028.log), [datos](e3b3_comparacion_puentes_20261028.json) y [script](../scripts/comparar_validacion_bridges_b3.py).

## 80 intentos de guardado nativo

Se usa FastMCP en proceso, sin transporte ni agente real; las 80 entradas, sus sustantivos y los cinco puentes sintéticos son los mismos de B2. Cada intento tiene una búsqueda previa real. Las plantillas no están revisadas por hablantes. Cada guardado se confirma en la respuesta MCP y en SQLite, con sus cinco puentes y consolidación.

| Idioma | Guardados B2 → B3 | Perdidos | Primer rechazo B3 |
|---|---:|---:|---|
| zh | 0 → 18/20 | 0 | 2 sustantivos de un carácter |
| ja | 0 → 15/20 | 0 | 5 sustantivos de un carácter |
| ko | 16 → 16/20 | 0 | 4 sustantivos de un carácter |
| ru | 20 → 20/20 | 0 | ninguno |

**B3 cumplido en coreano; pendiente hueco 1.** Los guardados siguen en 16→16: los puentes de `ko-05`, `ko-07` y `ko-20` ahora pasan, pero después los frenan los sustantivos de un carácter `연`, `빵` y `북`, respectivamente. `ko-12` sigue frenado por `물`. Dennys confirmó que esto no es un fallo de B3; la decisión sobre sustantivos de un carácter corresponde al hueco 1. No se cambia esa regla anterior.

### Primer rechazo de cada guardado pendiente

En los 11 casos siguientes, el primer rechazo B3 es `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`: el término indicado tiene **un carácter tras NFC**. Los siete casos chinos y japoneses, y los tres coreanos señalados, antes se detenían en `BRIDGES_INVALIDOS`; `ko-12` ya se detenía por el sustantivo en B2. Ninguno de estos intentos guardó el nodo ni creó puentes.

| Caso | Concepto | Primer término rechazado, NFC | Estado |
|---|---|---|---|
| zh-11 | `蜂蜜茶` | `茶` | pendiente hueco 1 |
| zh-17 | `密码箱` | `箱` | pendiente hueco 1 |
| ja-05 | `青い凧` | `凧` | pendiente hueco 1 |
| ja-06 | `古い橋の写真` | `橋` | pendiente hueco 1 |
| ja-08 | `旅の手帳` | `旅` | pendiente hueco 1 |
| ja-18 | `黄色い傘` | `傘` | pendiente hueco 1 |
| ja-20 | `カラス` | `羽` | pendiente hueco 1 |
| ko-05 | `노란 연` | `연` | pendiente hueco 1 |
| ko-07 | `호밀 빵` | `빵` | pendiente hueco 1 |
| ko-12 | `물 저장통` | `물` | pendiente hueco 1 |
| ko-20 | `작은 북` | `북` | pendiente hueco 1 |

Esta tabla corresponde a **guardados**; los 14 pendientes de la QA MCP de recordar son otra medición. La etiqueta no convierte ningún rechazo en búsqueda ni en abstención.

Las 80 búsquedas previas se ejecutaron y confirmaron. No hubo excepciones ni discrepancias MCP/SQLite. Los detalles y respuestas están en [guardados B3](e3b3_guardado_nativo_20261028.json), [comparación B2/B3](e3b3_comparacion_multilingue_20261028.json) y [salida del comparador](e3b3_comparacion_multilingue_20261028.log). La salida histórica del comparador es **1** porque exigía aumento de guardados coreanos; no se reescribió ese resultado. Después, Dennys aceptó explícitamente 16→16 porque los tres puentes ya pasan y el bloqueo restante es el hueco 1. No se detectó regresión en estas mediciones.

## Búsquedas MCP después de guardar

Se consultaron por separado el nombre, el primer puente completo y un fragmento sin nombre. Los resultados con hub ON y OFF usan **copias byte a byte de la misma base**, con un estado auxiliar por llamada. Cada brazo se ejecutó con el módulo real B2 y B3, verificado por huella: **216 llamadas por versión sobre la semilla B2 y 414 por versión sobre la semilla B3**, 1.260 llamadas en total. Las respuestas y trazas son idénticas entre versiones sobre cada misma semilla. En los 36 casos guardados por ambas versiones tampoco hubo pérdidas R@5/R@1 al comparar las bases de distinto tamaño; esa segunda comparación no aísla el cambio de código.

| Idioma | Guardados buscados | Nombre R@5 ON/OFF | Puente completo R@5 ON/OFF | Fragmento sin nombre R@5 ON/OFF |
|---|---:|---:|---:|---:|
| zh | 18 | 18/18 | 0/0 | 0/0 |
| ja | 15 | 15/15 | 0/0 | 0/0 |
| ko | 16 | 16/16 | 16/16 | 0/0 |
| ru | 20 | 20/20 | 20/20 | 0/0 |

El puente completo **contiene el nombre**, por lo que un acierto no demuestra recuperación independiente por puente. Los fragmentos sin nombre son genéricos e idénticos para muchos nodos de un idioma: no identifican un recuerdo y no constituyen una prueba semántica concluyente. El fragmento chino que no activa el hub es línea base del límite de palabra, no un fallo que se atribuya a B3.

En los 33 puentes completos chinos y japoneses el hub detectó el nodo correcto y registró origen `concept_hub`, pero MCP devolvió cero resultados. Sobre la misma semilla B2 hace exactamente lo mismo. En los 33, la consulta forma un solo token y no aparece como prefijo en los cuatro campos comprobados. El punto exacto de descarte se rastreó en **tres casos**, descritos abajo; no se supone que esa traza de tres sea una instrumentación de los 33. Este hallazgo es distinto de la ausencia de activación del fragmento sin nombre.

### Tres trazas: dónde se pierde el nodo

Cada consulta se ejecutó por FastMCP con un observador de solo lectura y, por separado, sin él, sobre copias idénticas. La respuesta completa con traza coincidió con la respuesta sin traza **y** con la registrada previamente; el observador no cambió el resultado. Datos: [tres trazas completas](e3b3_trazas_prefijo_20261028.json), [salida](e3b3_trazas_prefijo_20261028.log) y [observador reproducible](e3b3_traza_prefijo_20261028.py).

| Caso | Puente completo | ¿En el pool antes del hub? | Antes del filtro: puntuación y origen | Tras el filtro |
|---|---|---|---|---|
| zh-01 | `海岸灯塔是什么意思？` | Sí | 0,3347; `concept_hub` | no está |
| zh-19 | `竹笛是什么意思？` | No; el hub lo recupera de SQLite | 0,9500; `concept_hub` | no está |
| ja-01 | `海辺の灯台とは何ですか。` | Sí | 0,3344; `concept_hub` | no está |

1. El hub identifica el canónico con confianza 1,0 (`core/memory/search.py:212-218`). En `zh-01` y `ja-01` el nodo ya está en el pool que se puntúa (`:1686-1690`); en `zh-19` no está y el hub lo trae de SQLite con puntuación 0,95 (`:2000-2015`). Por tanto, **ninguno de los tres se queda sin puntuación**.
2. En los tres, el filtro trata el origen `concept_hub` como literal: ese origen no figura en `_ORIGENES_NO_LITERALES` (`core/memory/search.py:28-31, 2073-2081`). La consulta es un único token; la comprobación `PALABRA_PREFIJO` no encuentra ese token en los cuatro campos y devuelve un conjunto vacío (`:2084-2091`; predicado en `core/memory_store.py:113-120`). La asignación de `:2092` elimina el nodo del pool. La página ya está vacía en `:2161-2163`.
3. MCP recibe la lista vacía (`core/mcp_server/search.py:480-495`); el umbral de `:593-596` **no se invoca** porque no quedan resultados. En estos tres casos la pérdida observada ocurre antes, en el filtro de prefijo.

**Observación adicional, no reparación:** en `zh-01` y `ja-01` el nodo ya estaba primero; aunque se calculó una promoción de 0,95, el código solo modifica su puntuación si cambia de posición (`core/memory/search.py:2027-2037`), por eso permanece en 0,3347 o 0,3344. No se probó si ese score afectaría la respuesta después de un cambio futuro del filtro; no se propone ni se aplica ningún cambio ahora.

El primer intento del observador se descartó porque apuntaba a una línea sin evento ejecutable, no por un cambio de resultado; se conservó su [salida](e3b3_trazas_prefijo_primer_intento_descartado_20261028.log), se corrigió solo el observador y se repitió sobre copias nuevas. El buscador no se modificó. Esta evidencia queda para el paso **«límite de palabra según la escritura»**.

Las consultas usan `profundidad=activos`, límite público 5, pool MCP interno 15, peso sináptico predeterminado, `asociados=False` y neurona apagada. MCP no expone `ignore_peso_sinaptico=True`: estas búsquedas **no son emparejables** con una QA directa que sí lo usa. [Tabla](e3b3_busquedas_tabla_20261028.md), [comparador](e3b3_comparacion_busquedas_20261028.json), [diagnóstico de prefijo](e3b3_diagnostico_prefijo_20261028.json) y respuestas completas en los cuatro archivos `e3b3_busquedas_hub_*`.

## QA multilingüe previa y pruebas

Los **132 casos** de la QA directa y los **132 casos** del brazo MCP sobre la base directa reproducen B2 sin diferencias, también al invertir el orden. Siguen visibles los mismos **14** rechazos «pendiente hueco 1»; no se cuentan como búsquedas ni abstenciones. La directa usa `ignore_peso_sinaptico=True`; MCP utiliza los parámetros indicados arriba.

- [Pruebas focalizadas del hub](e3b3_pruebas_focalizadas_20261028.log): **62 aprobadas**.
- [Primera suite completa](e3b3_pytest_20261028.log): **673 aprobadas**; se ejecutó sin exportar `BIORAG_NEURONA=0`.
- [Pruebas de arneses y comparadores](e3b3_pruebas_comparadores_20261028.log): **11 aprobadas**.
- [Suite completa final](e3b3_pytest_final_20261028.log): **684 aprobadas** en 334,27 s; incluye esas pruebas adicionales y se ejecutó sin exportar `BIORAG_NEURONA=0`. Después se reforzó el comparador sin cambiar el motor: se ejecutaron [11 pruebas](e3b3_pruebas_comparadores_final_20261028.log) y, tras corregir la comparación de rutas explicada abajo, [16 pruebas](e3b3_pruebas_comparador_rutas_20261028.log), todas aprobadas.

## Cuatro QA oficiales — comparación con B2

Las cuatro corridas se iniciaron aisladas con los mismos parámetros y bases de B2, neurona apagada y archivos de estado separados. La base viva es una copia de 1.357 nodos con SHA-256 `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a`; el snapshot tiene 866 nodos. [Parámetros y huellas de inicio](e3b3_inicio_qa_oficial_20261028.txt).

| Condición | Snapshot: R@5 / R@1 / FP B2 → B3 | Viva: R@5 / R@1 / FP B2 → B3 |
|---|---|---|
| Normal | 100,00 → 100,00 % / 95,31 → 95,31 % / 0/40 → 0/40 | 99,88 → 99,88 % / 93,53 → 93,53 % / 0/40 → 0/40 |
| Ruido `zzqx` | 97,34 → 97,34 % / 88,63 → 88,63 % / 0/40 → 0/40 | 96,63 → 96,63 % / 88,12 → 88,12 % / 0/40 → 0/40 |

Snapshot y viva sin ruido coinciden con B2: [igualdad parcial](e3b3_igualdad_parcial_20261028.log). El primer comparador señaló «origen distinto» por escribir la ruta del mismo snapshot como absoluta en B2 y relativa en B3; ambos logs registran la misma huella `104dd2902aaf`. Se guardó la [salida inicial](e3b3_comparacion_parcial_rutas_literal_20261028.log) y se corrigió solo el comparador para resolver rutas antes de compararlas, manteniendo la verificación independiente de SHA. Se añadió una [comprobación de igualdad](../scripts/comprobar_igualdad_qa_b3.py), más exigente que solo «no bajar»: sus [17 pruebas](e3b3_pruebas_igualdad_20261028.log) pasaron. Su primera ejecución por línea de comandos se descartó por un error de importación; se corrigió el arnés y se conservó la [salida](e3b3_igualdad_primer_intento_descartado_20261028.log). No se repitió ninguna QA.

Las cuatro corridas originales terminaron sin reiniciarse. El supervisor verificó huellas, bases, categorías, R@5, R@1, MRR, FP, censo y fallos; una segunda comprobación confirmó **igualdad**, no solo ausencia de bajadas. Las corridas con ruido pueden devolver 1 por el gate histórico; se contrastaron con B2, sin desactivar el gate. [Comparación oficial](e3b3_comparacion_oficial_20261028.json) · [igualdad estricta](e3b3_igualdad_oficial_20261028.json) · [categorías lado a lado](e3b3_categorias_oficial_20261028.md) · [estado de supervisión](e3b3_estado_supervision_20261028.json). No se toca `VERSION`, `README` ni `CHANGELOG`, y no se hace merge de la PR.

## Reproducción resumida

```bash
PYTHONHASHSEED=0 python scripts/comparar_validacion_bridges_b3.py --salida /tmp/puentes.json
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_guardado_nativo_b2.py \
  --sha-write b188d7430e8e37dcbcde1dcb949cc5255c7d205c1b7c1cc9de3ef726e4545218 \
  --salida /tmp/guardados_b3.json
python scripts/comparar_qa_multilingue_b3.py --salida /tmp/comparacion_multilingue.json
python scripts/comparar_qa_busquedas_b3.py --salida /tmp/comparacion_busquedas.json
```

El arnés de búsquedas [`evaluar_qa_guardado_y_busqueda_b3.py`](../scripts/evaluar_qa_guardado_y_busqueda_b3.py) permite recrear ambas semillas y los cruces con el módulo B2 exportado con `git show`; cada semilla se compara con una corrida previa de los 80 guardados y se comprueba por SHA antes de cada consulta. Los [cuatro comandos de reproducción](e3b3_reproduccion_busquedas_20261028.txt) no sobrescriben los resultados registrados. Las semillas sintéticas son temporales y no se incluyen en el repositorio.

## Pendientes fuera de esta entrega

- Sustituir el filtro de conectores por detección estadística: «pendiente hueco 1».
- Identidad `ガラス`/`カラス` en dos entregas; después, límite de palabra según escritura.
- `agregar_sustantivos` reemplaza el campo en vez de añadir: seguimiento fuera de E3.
- Dimensiones no latinas y regex ASCII en `neurona_examen.py`: etapas posteriores.
