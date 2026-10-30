# Revisión de procedencia y recorrido de sinapsis, ráfaga, despertar y asociaciones

**Fecha:** 2026-10-30
**Estado:** investigación estática de documentación y código; sin pruebas, sin mediciones nuevas y sin cambios al motor.
**Rama:** `arena/9a54babb-memorybiorag`
**Propósito:** dejar evidencia inspeccionable para auditoría y separar hechos comprobados en el código de hipótesis o efectos que requieren medición autorizada.

## 1. Alcance y límites

Esta revisión inspeccionó documentación y código fuente del checkout. No abrió, consultó, copió ni modificó una base de datos; no corrió tests, QA, benchmarks ni MCP; no midió cambios de grafo. Las referencias de línea se dan para facilitar la auditoría del estado de código en esta rama.

La existencia de un escritor en código no prueba que se ejecute en cada llamada ni cuánto aporta a la recuperación en una fixture concreta. Tampoco se considera que tipo, peso o presencia de arista equivalgan por sí solos a relevancia semántica. El principio de evaluación continúa siendo: **el ruido útil no se mata**.

## 2. Documentación previa: qué dice y qué no demuestra

- `docs/plan_tejedora_agujeros_estructurales.md` registra que la hipótesis de tejer islas no mejoró R@5 en aquella evaluación (0,000 pp sobre 921 casos) y que el experimento fue cerrado. Es evidencia de ese experimento; no demuestra que las asociaciones no tengan utilidad en otras tareas.
- `docs/fase3_grafo_relacional_auditoria.md` presenta un inventario y conteos para un snapshot histórico. No es una consulta a la DB de esta rama ni un inventario actual. Algunas descripciones de procedencia no coinciden con el escritor que aparece en el código actual (detalles abajo).
- `docs/INFORME_abismo_3e0a318_vs_d42f9c7.md`, §8.4, describe búsqueda profunda y ráfaga como rutas de despertar, y documenta una evaluación concreta sobre copias. Sus resultados no se generalizan sin una medición nueva.
- `docs/Mi neurona en el sistema/GUIA_CREAR_UNA_NEURONA.md` contiene un mapa de los sitios donde nacen sinapsis, incluida la ráfaga.
- `docs/implementacion_qa_intuicion_asociaciones_e1.md` y `docs/qa_intuicion_asociaciones_propuesta_20261030.md` separan resultados principales de asociaciones/contexto, reservan `deep=False` y no fuerzan ráfaga. El diseño exige contabilizar enlaces automáticos y validar el grafo final antes de declarar una ruta gold de dos saltos.
- La comparación aprobada ya documentada en `docs/informe_comparacion_prefijo_aristas_mcp_20261030.md` reportó 9 frente a 12 aristas dirigidas finales y ubicó las escrituras en el intervalo MCP de `consolidar`, no en `vincular`. Esta revisión no repite ni amplía esa medición y no atribuye esos conteos a una subfunción concreta.

No se encontró un informe dedicado que describa el efecto de `rafaga_rememb` sobre el espejo CSV `largo_plazo.asociaciones`; ese recorrido se establece a continuación únicamente a partir del código.

## 3. Recorrido `aprender → consolidar → vincular`

### `aprender`

En `core/mcp_server/write.py:314-353`, el handler guarda primero en corto plazo, llama a `auto_vincular` y, si se proporcionan sinónimos, también a `vincular_por_sinonimos`. Si llega `vincular_con`, llama a `establecer_asociacion` por cada destino. Esto permite creación automática y explícita antes de consolidar.

### `consolidar`

`core/memory/consolidation.py:374-406` transfiere recuerdos a largo plazo y, en este orden, vuelve a ejecutar `auto_vincular`, clasifica nodos, genera coocurrencias, puede llamar a síntesis DMN y recalcula `sinapsis_latentes`. Por tanto, el grafo que observa `vincular` ya puede tener aristas automáticas. La consolidación también incluye posteriores operaciones de mantenimiento/poda (`:450-469`).

### `vincular`

La herramienta MCP `core/mcp_server/synapses.py:42-70` llama a `establecer_asociacion`. En `core/memory/synapses.py:139-161`, esa operación normaliza nombres, comprueba por separado las direcciones A→B y B→A e inserta las ausentes como `manual` con peso 0,5; no sustituye filas que ya existan. Sincroniza los dos espejos y confirma la transacción.

Consecuencias verificables:

- Una arista automática ya presente en ambas direcciones no pasa a ser `manual` por llamar a `vincular`.
- Si solo existía una dirección, la inversa que falte puede quedar como `manual`, mientras la fila original conserva otro tipo.
- El handler devuelve `status: ok` aunque no se haya insertado ninguna fila nueva.
- El texto MCP indica que ambos nodos deben existir, pero el método `establecer_asociacion` no contiene una comprobación explícita contra `largo_plazo`; cualquier restricción adicional dependería del esquema.

## 4. Procedencia de tipos y qué aportan en el flujo

| Tipo | Escritor/ruta localizado en el código | Alcance o dependencia visible en el código |
|---|---|---|
| `co_ocurrencia` | `auto_vincular` compara tokens del nombre+contenido mediante similitud y cierre triádico (`core/sinapsis.py:104-188`). Consolidación tiene otro escritor: pares de recuerdos de la sesión con al menos dos tokens compartidos y pares detectados en mensajes (`core/memory/consolidation.py:48-170`). | Una misma etiqueta agrupa señales distintas. Las aristas participan en el grafo directo; el escritor de coocurrencia de consolidación refuerza peso en conflicto, pero no cambia explícitamente el tipo. |
| `co_nombre` | Segunda pasada de `auto_vincular`: palabras del nombre de al menos cuatro letras y solapamiento mínimo de 30 %, con límite de fan-out (`core/sinapsis.py:190-244`). | Nombres/prefijos solo influyen si sus tokens superan los filtros. No son evidencia suficiente de utilidad semántica. |
| `co_semantica` | Tercera pasada de `auto_vincular`: solapamiento de tokens en los campos `sinonimos` y umbral de solapamiento (`core/sinapsis.py:246-310`). | **Diferencia documental:** el inventario histórico Fase 3 atribuye este tipo a compartir ≥3 dimensiones; el escritor localizado en el código actual compara sinónimos. No se infiere que los conteos históricos describan esta implementación actual. |
| `pmi_hebbiano` | Cuarta pasada de `auto_vincular`, que consulta pares PMI de tokens, busca candidatos en FTS y aplica umbral de peso y límite (`core/sinapsis.py:312-371`). | Es una señal estadística automática. La descripción de Fase 3 como PMI de co-búsquedas no es equivalente al procedimiento de este escritor actual. |
| `sinonimo_explicito` | Sinónimos recibidos en `aprender` y `vincular_por_sinonimos` (`core/mcp_server/write.py:319-322`; `core/sinapsis.py:435-480`); también aprendizaje léxico (`core/lexical_learning.py:274-326`). | En el upsert de estos escritores, el tipo se conserva si la fila previa ya era `manual`, `manual_v7`, `sinonimo_explicito` o `test`. |
| `manual` | `vincular` y `aprender(vincular_con)` (`core/memory/synapses.py:139-161`; `core/mcp_server/write.py:324-353`). | Decisión explícita del agente; no reemplaza la fila previa. `core/memory/constants.py:346-353` lo distingue junto con `manual_v7` como tipo protegido frente a ciertos procesos automáticos. |
| `dmn_synthesized` | Síntesis llamada durante consolidación (`core/memory/consolidation.py:388-394`; `core/dmn_engine.py:32-139`) y otra inserción durante un ciclo DMN (`core/dmn_engine.py:335-346`). | Defaults: activo, máximo 8 y peso 0,30 (`core/dmn_engine.py:27-29`; también `core/memory/constants.py:59-62`). La ruta E10 selecciona entre nodos activos de mayor peso, prioriza dimensiones comunes y tiene fallback de solapamiento de contenido; no inserta si ya existe una arista en ninguna dirección. El segundo punto inserta si hay dimensiones comunes. La fila directa es orientada, no una pareja bidireccional garantizada. |
| `rafaga_rememb` | `buscar_por_rafaga` (`core/memory/rafaga.py:297-371`), descrito en detalle en §5. | Puede crear una arista directa de peso 0,6 desde un concepto-token activo hasta un recuerdo recuperado. No equivale al término de ráfaga ni prueba utilidad semántica. |
| `hipotesis_sueno` | `core/sueno_vacios.py:26,270-312`. | Proceso de sueño separado; inserta aristas directas con tipo configurado y también filas de `sinapsis_latentes`. No forma parte del flujo ordinario demostrado de `aprender → consolidar → vincular`. |
| `rafaga_rememb` / aristas existentes en ráfaga | Si ya existe el par en cualquier dirección, la ráfaga incrementa el peso de las filas existentes y no cambia su tipo (`core/memory/rafaga.py:339-360`). | Una intervención de ráfaga puede no dejar una fila cuyo tipo sea `rafaga_rememb`. |
| `manual_v7`, `legacy_csv`, `latente_confirmada`, `test` | El código actual incluye estos nombres en protecciones o prioridades. En esta inspección no se encontró un escritor activo para `manual_v7`, `legacy_csv` ni `latente_confirmada`; `test` aparece como excepción de protección/prioridad. | La procedencia descrita en documentos históricos es histórica, no queda confirmada por un escritor actual localizado. |

`sinapsis_latentes` es otra tabla, sin campo `tipo` de sinapsis directa. `core/inferencia_transitiva.py:85-155, 236-245` la recalcula desde rutas directas con límites de saltos, filtros de peso/tipo y condiciones semánticas/PMI. No debe confundirse con `latente_confirmada`.

### Tipos y reemplazo de filas

Varios upserts de `auto_vincular` actualizan el tipo existente a la señal automática del upsert, salvo los tipos protegidos enumerados en su SQL (`core/sinapsis.py:177-182, 229-235, 290-295, 354-359`). Por eso el tipo de una fila automática no es necesariamente una procedencia histórica inmutable. En cambio, el escritor de coocurrencia de consolidación solo incrementa el peso/uso al conflicto (`core/memory/consolidation.py:97-108, 154-165`).

## 5. Ráfaga: condiciones, despertar y aristas

### Cuándo entra en el recorrido MCP

`core/mcp_server/search.py:531-550` llama a `buscar_por_rafaga` si `forzar_rafaga=True`, o si se proporcionó una lista de términos y la búsqueda ordinaria está vacía o bajo el umbral MCP. Sin `rafaga_palabras`, `forzar_rafaga=False` no basta para iniciar esa ruta. El handler añade términos de paráfrasis si los hay (`:537-546`).

### Qué recupera y qué despierta

`core/memory/rafaga.py:45-162` busca términos por FTS/palabra completa en nodos activos y también en dormidos. Para cada fila dormida recuperada, la fase 1.5 la pone en activo, incrementa su peso hasta +0,30 (tope 1,0), actualiza `ultimo_acceso` y confirma si despertó alguno (`:196-214`). Esta ruta de ráfaga puede despertar resultados aunque la consulta no haya pedido `deep=True`.

### Cuándo aporta `rafaga_rememb`

Tras puntuar, el escritor considera como máximo los resultados de `scored[:limite]`, exige score ≥0,5, una palabra de ráfaga completa en el nodo y un token de la consulta que también aparezca como concepto activo (`:297-338`). Si se satisfacen esas guardas:

1. Si no existe el par en ninguna dirección, inserta una fila orientada `token_activo → recuerdo`, tipo `rafaga_rememb`, peso 0,6 (`:339-353`).
2. Si existe, refuerza el peso de las filas en ambas direcciones hasta 0,95 y conserva su tipo (`:339-360`).
3. Marca los extremos como SDM dirty solo para inserciones nuevas (`:365-373`).

La aportación potencial de esa arista es dejar conectado el concepto-token activo con un recuerdo rescatado; el acceso al nodo recuperado y la conectividad posterior pueden depender de esa conexión. El código, por sí solo, no mide si la arista mejora recuperación ni si la asociación es útil o trivial.

## 6. Despertar por BFS y alcance por tipo

`deep` se transforma en `profundidad="profundo"` en el handler MCP (`core/mcp_server/search.py:382`). Si `context_window > 0`, `expandir_contexto_vecinos` consulta `sinapsis` en las dos orientaciones y recorre vecinos. El modo activo filtra nodos dormidos; en modo profundo, cada vecino dormido alcanzado se activa y recibe +0,15 LTP (`core/memory/synapses.py:298-318, 331-388`).

La consulta del BFS no filtra el tipo de sinapsis. El recorrido depende de la arista directa disponible, su peso/orden entre los candidatos y los topes de fan-out/profundidad, no de que su tipo sea semánticamente correcto. Por ello un `manual`, `co_nombre`, `dmn_synthesized` o `rafaga_rememb` puede servir de puente estructural. Eso no prueba que cada puente aporte una pista útil.

El despertar directo de `buscar_recuerdo_profundo` eleva peso hasta +0,15 y actualiza `estado`/`ultimo_acceso` (`core/memory/search.py:2587-2640`). `buscar_recuerdo_microsegundos` consulta solo activos y devuelve `None` si el nodo está dormido (`:2470-2516`).

## 7. Qué sincroniza y qué puede quedar desfasado

### Fuente canónica y espejo

`core/memory_service.py` declara `sinapsis` como fuente canónica y `largo_plazo.asociaciones` como espejo histórico. `_sincronizar_asociaciones` reconstruye una lista CSV de vecinos consultando las dos direcciones, sin tipo, peso ni orden semántico (`core/sinapsis.py:491-502`). Es un espejo no equivalente al grafo.

En los escritores inspeccionados, sincronizan ambos extremos:

- `establecer_asociacion`/`vincular` (`core/memory/synapses.py:151-154`).
- `auto_vincular` y `vincular_por_sinonimos`, cuando su lista de conexiones no está vacía (`core/sinapsis.py:371-373, 476-480`).
- `desvincular`, después de borrar ambas direcciones (`core/sinapsis.py:505-517`).
- Cuarentena/restauración de sinapsis directas en DMN (`core/dmn_reflexion.py:892-918, 943-966`).

No se encontró una llamada a `_sincronizar_asociaciones` en los escritores directos de coocurrencia de consolidación, `dmn_synthesized`, `rafaga_rememb`, `hipotesis_sueno` o `_upsert_sinapsis_lexica`. La poda de aristas débiles en consolidación (`core/memory/consolidation.py:450-469`) tampoco muestra una sincronización posterior de los extremos en ese bloque. Esto es una observación estática de llamadas; no se midió cuánto afecta una fixture ni si una sincronización posterior corrige cada caso.

### Consumidores y dependencias

- El BFS y `obtener_asociaciones_enriquecidas` leen `sinapsis` directamente (`core/memory/synapses.py:307-318, 405-480`). El canal enriquecido exige peso ≥0,50 por defecto, omite vecinos dormidos/inexistentes y limita la lista; tipos no reconocidos, incluido `rafaga_rememb`, reciben prioridad de tipo de fallback 9 (`:433-480`). Así, una arista `rafaga_rememb` de 0,6 puede entrar si el nodo ya está activo y cabe en el top. Una arista `dmn_synthesized` con peso predeterminado 0,30 queda fuera de ese canal por el umbral predeterminado, aunque puede ser recorrible por BFS si entra entre los vecinos seleccionados.
- El campo plano serializado por MCP procede de `largo_plazo.asociaciones` (`core/mcp_server/search.py:731-753, 1142-1156`).
- El scoring calcula `asoc_count` desde esa columna (`core/memory/search.py:1824-1846`; normalización en `core/memory/scoring.py:318`).
- `buscar_por_rafaga` lee `l.asociaciones` antes de insertar las nuevas aristas y devuelve resultados con ese valor (`core/memory/rafaga.py:107-115, 198-214, 293-353`). La nueva arista no se añade allí mediante `_sincronizar_asociaciones`. En el handler MCP, el canal enriquecido se consulta después desde `sinapsis` (`core/mcp_server/search.py:719-729`). Por tanto, el código permite discrepancia entre el mapa plano/espejo y el canal enriquecido después de una escritura de ráfaga.
- La búsqueda profunda antigua también lee el espejo CSV para parte del refuerzo y luego consulta el grafo canónico para propagar por sinapsis (`core/memory/search.py:2642-2668`). Una arista ausente del espejo no deja de existir en el grafo, pero esa parte del recorrido basado en CSV no la ve.

## 8. Fixture y criterio de utilidad

Conexiones automáticas pueden aparecer antes de `vincular` y pueden crear rutas cortas alternativas. Los nombres influyen en `co_nombre` solo cuando sus tokens cumplen regex/umbral; contenidos compartidos, sinónimos, PMI, bridges de aprendizaje, consolidación y DMN tienen sus propios caminos. El tipo final tampoco prueba de forma fiable quién fue el primer escritor, porque ciertos upserts reemplazan tipos automáticos.

Para la fixture, el protocolo ya documentado de validar el grafo temporal final y recalcular rutas mínimas es necesario. Si un atajo automático rompe la ruta gold de exactamente dos saltos, se descarta/reconstruye ese episodio conforme a la propuesta; no se apaga la generación automática. La validez de pista útil o serendipia debe anotarse con evidencia del recuerdo y la pregunta, separada de ruido trivial y del objetivo principal. Una arista o palabra compartida no basta para cambiar esas etiquetas.

## 9. Hechos comprobados en código vs. trabajo pendiente

### Comprobado por inspección estática

- Orden y puntos de llamada del flujo `aprender → consolidar` y método llamado por `vincular`.
- Escritores y guardas descritos arriba para `co_*`, `pmi_hebbiano`, `sinonimo_explicito`, `manual`, `dmn_synthesized`, `rafaga_rememb` y `hipotesis_sueno`.
- Diferencia entre las dos rutas de despertar (`deep`/BFS y ráfaga), sus incrementos de peso y filtros de nodos activos/dormidos.
- `sinapsis` es el grafo canónico; el espejo CSV se sincroniza en algunos caminos y no aparece en varios escritores directos descritos.
- Ráfaga puede reforzar una arista existente conservando su tipo, o insertar una nueva fila dirigida y marcada `rafaga_rememb` bajo sus guardas.

### No medido / no demostrado

- Frecuencia con que una fixture concreta dispara ráfaga sin `forzar_rafaga`, cuántos nodos dormidos despierta o cuántas aristas nuevas/reinforzadas produce.
- Cuánto cambia un resultado o ranking por `rafaga_rememb`, cada tipo automático, `deep=True` o sincronización tardía del espejo.
- Si las discrepancias de `asociaciones` persisten en un fixture dado, cuándo se corrigen y qué efecto neto tienen en `asoc_count`.
- Procedencia temporal exacta por arista en los conteos de la comparación aprobada; ese informe no atribuye los cambios a subfunciones internas.
- Utilidad semántica de aristas concretas, incluida toda asociación potencialmente útil que no sea la respuesta literal.

Cualquier medición o ejecución futura queda pendiente de autorización expresa de Dennys y debe seguir las guardas de QA temporal ya documentadas. No se modificó ni desactivó mecanismo alguno en esta revisión.
