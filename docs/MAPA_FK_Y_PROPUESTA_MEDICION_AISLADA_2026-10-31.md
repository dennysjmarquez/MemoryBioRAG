# Mapa sanitizado de violaciones FK y propuesta de medición aislada

**Estado:** documentación y propuesta solamente. No se repararon filas, no se borraron datos, no se modificó el motor, no se ejecutaron QA ni campañas. E1 sigue abierto; W sigue pendiente.

## 1. Hallazgo de integridad y límites

En la copia SQLite restaurada, `PRAGMA quick_check` devolvió `ok`; `PRAGMA foreign_key_check` informó 156 referencias sin fila padre coincidente, repartidas así:

| Relación hija → padre | Filas reportadas |
|---|---:|
| `concept_hub_bridges.hub_id` → `concept_hubs.hub_id` | 10 |
| `corto_plazo_dimensiones.concepto` → `corto_plazo.concepto` | 17 |
| `largo_plazo_dimensiones.concepto` → `largo_plazo.concepto` | 13 |
| `nodo_grupos_semanticos.concepto` → `largo_plazo.concepto` | 116 |
| **Total** | **156** |

El volcado SQL se importó con las comprobaciones FK desactivadas. La importación transaccional terminó y la comprobación física pasó, pero no existe una comprobación FK anterior a la exportación ni se dispone de la base fuente con sus sidecars WAL/SHM. Por ello, **no se atribuye la causa**: el importador pudo conservar las referencias, pero estas también pudieron estar ya en los datos exportados. Las cuentas anteriores describen la copia, no identifican recuerdos ni justifican eliminar ninguna asociación.

Los esquemas declaran `ON DELETE CASCADE` (`core/memory/schema.py`; hubs en `core/concept_hub.py`). La conexión principal activa `PRAGMA foreign_keys=ON` (`core/memory_store.py`), y la conexión DMN también lo activa (`core/dmn_engine.py`). Eso no sanea filas preexistentes al abrir la DB; las cascadas afectan operaciones posteriores realizadas con FK habilitadas.

## 2. Mapa de lectores, escritores y posibles consecuencias

Los apartados “comprobado” describen el código inspeccionado, no que se haya observado el efecto en rankings o recuerdos de la copia. Las consecuencias se mantienen como hipótesis hasta una comparación autorizada.

### A. `concept_hub_bridges.hub_id → concept_hubs.hub_id` — 10

- **Escritura/eliminación:** `core/concept_hub.py::agregar_bridges`; `eliminar_hub`; `cargar_hubs_iniciales`; la migración `migrar_tablas`. El padre se crea/actualiza en `crear_hub`. Herramientas expuestas en `core/mcp_server/concept_hub_tools.py`.
- **Lectura:** `listar_hubs`, `_indice_hubs`, `expandir_query_con_hub`, `_expandir_a_escala`, `_indice_bridges` y `_expandir_por_cobertura_idf`.
- **Comprobado:** las lecturas que parten de `concept_hubs` o construyen el mapa de hubs no incluyen un bridge cuyo `hub_id` no tenga padre. `_firma_hubs` sí cuenta todas las filas de bridges para la firma de caché.
- **Posible consecuencia:** esas filas podrían provocar invalidación/reconstrucción de caché sin aportar expansión semántica actual. Si se vuelve a crear el mismo ID de hub, sus bridges antiguos podrían entrar en el mapa; eso no se ha probado.

### B. `corto_plazo_dimensiones.concepto → corto_plazo.concepto` — 17

- **Escritura/eliminación:** `core/memory/ingest.py::percibir_corto_plazo` inserta las dimensiones del recuerdo corto; `consolidar_concepto` y `core/memory/consolidation.py::ciclo_sueno_consolidacion` propagan las asociaciones a largo plazo y eliminan las filas de corto plazo.
- **Lectura:** `core/neurona_asociativa.py::Juez._dims` consulta ambas tablas dimensionales por concepto.
- **Comprobado:** esa lectura alimenta la señal de etiquetas que la neurona asociativa considera al decidir el peso de una asociación.
- **Posible consecuencia:** si un concepto con la misma clave vuelve a procesarse, una dimensión huérfana podría entrar en esa señal. Un huérfano sin fila padre corta no es, por sí mismo, un recuerdo que el ciclo normal pueda consolidar. No se ejecutó el Juez sobre esta copia.

### C. `largo_plazo_dimensiones.concepto → largo_plazo.concepto` — 13

- **Escritura/eliminación:** propagación en `core/memory/ingest.py::consolidar_concepto` y `core/memory/consolidation.py::ciclo_sueno_consolidacion`; cambios de dimensión en `core/dmn_reflexion.py::_aplicar_veredicto_nodo`; actualización de dimensiones en `core/mcp_server/write.py::biorag_actualizar`; membresías emergentes en `core/auto_clustering.py::asignar_dimensiones_emergentes`.
- **Lectura:** `core/memory/search.py::buscar_por_frase` usa dimensiones para señales, candidatos de fallback y puntuación temática. También las consultan `core/tematica.py::{calcular_idf_dims, calcular_perfiles_presencia}`, `core/sinapsis.py::_dimensiones_comunes`, `core/similitud_conceptual.py::score_similitud_latente`, `core/sueno_vacios.py::_dim_comun`, `core/inferencia_transitiva.py::_obtener_pares_dimension_comun`, `core/sdm.py::indexar_nodo_sdm`, `core/memory/episodes.py` y otros módulos de contexto.
- **Comprobado:** algunos caminos de recuperación hacen `JOIN largo_plazo` y por ello no proponen el concepto huérfano como recuerdo. Otros cálculos agregados leen directamente la tabla puente, sin ese `JOIN`.
- **Importante para IDF:** `core/tematica.py::calcular_idf_dims` calcula `N` contando solo `largo_plazo.estado='activo'`, pero cuenta `largo_plazo_dimensiones` por dimensión **sin filtrar estado ni unir con `largo_plazo`**. Por tanto, el numerador de frecuencia incluye filas de conceptos huérfanos y también dimensiones de nodos válidos pero dormidos/no activos. El efecto no puede atribuirse solo a las 13 filas huérfanas: las filas de nodos dormidos también participan en el conteo. Si la frecuencia supera `N`, la fórmula `log(N / count)` puede ser negativa.
- **Posible consecuencia:** las frecuencias/IDF y perfiles temáticos pueden cambiar los scores comparativos cuando se calcula similitud temática. Además, `_obtener_pares_dimension_comun` no une con `largo_plazo`; una fila huérfana podría marcar un par como dimensionalmente relacionado si el mismo par aparece en una ruta sináptica candidata. No se midió si alguna de estas condiciones afecta resultados reales de la copia.

### D. `nodo_grupos_semanticos.concepto → largo_plazo.concepto` — 116

- **Escritura/eliminación:** `core/memory/consolidation.py::_clasificar_nodo_wordnet`, invocado desde `consolidar_concepto`, `ciclo_sueno_consolidacion` y `core/mcp_server/write.py::biorag_actualizar`.
- **Lectura:** clasificación de candidatos en `core/memory/search.py::buscar_por_frase` mediante `nodo_grupos_semanticos`.
- **Comprobado:** la consulta de búsqueda limita las filas de grupos a conceptos que ya están en su lista de candidatos recuperados. Un concepto sin fila padre no entra por sí mismo en esa lista.
- **Posible consecuencia:** si más adelante se crea un `largo_plazo.concepto` con la misma clave, sus etiquetas antiguas podrían influir en la similitud por grupos. No se probó este caso.

## 3. Propuesta de medición en copias — requiere aprobación antes de ejecutarse

**Objetivo:** estimar dónde y cuánto influyen filas huérfanas y filas asociadas a nodos dormidos, conservando todos los datos y sin decidir que una relación es inútil. Esto sería diagnóstico de sensibilidad, no prueba automática de causalidad ni autorización para corregir.

1. **Preparar una copia aislada autorizada y reproducible.** Registrar origen y hashes. Para una DB SQLite en WAL, crear snapshot consistente con la API de backup de SQLite o detener/quiescer escritores y preservar DB/WAL/SHM como conjunto. Si la fuente sigue siendo el volcado SQL, documentar que es una restauración lógica y que no permite verificar cambios WAL no incluidos en el volcado. No abrir ni escribir la fuente original.
2. **Fijar acceso de solo lectura y guardar evidencia privada.** Abrir la copia en `mode=ro`, comprobar `quick_check` y `foreign_key_check`, guardar un manifiesto sanitizado con hash, método y versiones. Ninguna reparación, `DELETE`, `UPDATE`, migración, entrenamiento o escritura sobre la copia medida.
3. **Desglosar, no descartar.** Mediante consultas `SELECT` solamente, contar para cada relación las referencias con padre ausente y, donde aplique, las filas con padre existente separadas por los valores reales de `estado` (activo, dormido u otros). En dimensiones, calcular por ID los tres componentes —activos válidos, no activos válidos y huérfanos— y el IDF que produciría cada componente. Mantener visible el valor actual, que incluye tanto no activos válidos como huérfanos.
4. **Comparar sensibilidad funcional sin mutar datos.** En una fase separada y previamente aprobada, congelar un conjunto acotado de consultas diagnósticas, código, parámetros y candidatos. Calcular en memoria las señales/ordenes actuales y las variantes de lectura que separan esos componentes, siempre desde la misma copia read-only y sin crear vistas/tablas persistentes. Registrar para cada caso los cambios de score/orden y cualquier objetivo o pista que suba o baje; incluir diferencias y no solo promedios. No mezclar estas consultas con E1 ni usar su gold para entrenar.
5. **No inferir inutilidad ni causalidad.** Reportar tanto asociaciones huérfanas como dimensiones válidas de nodos dormidos; una diferencia entre variantes solo localiza sensibilidad bajo esa lectura. No borrar ni reparar. Si aparece una corrección candidata, presentar evidencia, alcance y diff para aprobación previa.
6. **Puertas de autorización.** Antes de esta medición, Dennys aprueba el conjunto de consultas, el presupuesto y el manifiesto exactos. Hasta entonces este documento es solo propuesta: no iniciar consultas de medición, QA, MCP o agentes. E1 sigue separado y sin campaña; W continúa pendiente.

### 3.1 Conjunto y presupuesto propuestos — todavía sin ejecutar

**Conjunto fijo:** todas las 921 filas/casos (IDs únicos) de `scripts/casos_qa_baseline_v1.jsonl`, usando el campo `query` tal como está en el archivo. SHA-256 del archivo: `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c`. Se conservan los 921 casos aunque haya consultas textualmente repetidas; no se copian las consultas al informe para evitar divulgar contenido. Un cambio en archivo o hash invalida este plan hasta nueva aprobación. El archivo solo se inspeccionó por metadatos: sus consultas no se han ejecutado.

**Seis condiciones de lectura, todas sobre el mismo snapshot y el mismo código/parámetros:**

| Código | Lectura propuesta |
|---|---|
| C0 | Baseline actual, sin filtrar asociaciones. |
| C1 | Igual a C0, excepto excluir de la lectura los 10 bridges sin hub padre. |
| C2 | Igual a C0, excepto excluir de la lectura las dimensiones largo plazo huérfanas; conservar todas las dimensiones con padre válido, incluidas las de nodos dormidos/no activos. |
| C3 | Leer dimensiones largo plazo solo de nodos con padre `estado='activo'`; excluye tanto huérfanas como válidas no activas. C2 frente a C3 separa la sensibilidad a estas últimas, sin llamarlas inútiles. En ambos casos, `N` de IDF conserva la definición actual de nodos activos. |
| C4 | Igual a C0, excepto excluir de la lectura las 116 membresías de grupo sin nodo padre. |
| C5 | Contraste combinado C1+C2+C4, para observar interacción; no es una recomendación de limpieza. |

El contraste funcional queda limitado a recuperación/ordenamiento con `BIORAG_NEURONA=0`, sin entrenamiento. Para `corto_plazo_dimensiones`, que alimenta una decisión asociativa y no constituye aquí un brazo de ranking de búsqueda, se propone un diagnóstico separado: comparar la lectura de dimensiones de `Juez._dims` para los 487 valores de `concepto_esperado` no vacíos y distintos del mismo archivo, con todas las asociaciones frente a la lectura que omite las 17 filas huérfanas. Son **974 lookups** como máximo; únicamente se observa la señal de entrada, no se calcula ni modifica peso alguno. Este contraste no autoriza una conclusión sobre efectos de entrenamiento, que queda fuera de alcance.

**Presupuesto cerrado propuesto:** 921 casos × 6 condiciones = **5.526 evaluaciones locales de consulta**; más 487 conceptos × 2 lecturas = **974 lookups locales**; total máximo **6.500 unidades de evaluación**. Una pasada por caso/condición, sin reintentos automáticos. **0** llamadas MCP, agentes, servicios externos o entrenamiento; no incluye ni inicia la campaña de 2.768 llamadas. No se da una estimación de tiempo de pared sin benchmark previo. El resultado privado registraría por caso cambios en objetivo/rango/pistas (incluidas pérdidas y ganancias), además de agregados; no habrá umbral aprobatorio automático ni se publicarán consultas, recuerdos ni identificadores sensibles.

**Puerta:** se solicita aprobación explícita de Dennys para este archivo/hash, estas seis condiciones, el diagnóstico Juez y el máximo de 6.500 unidades. Hasta recibirla no se ejecutan ni siquiera las evaluaciones de lectura. Si se aprueba, un preflight separado debe verificar que el acceso sea realmente de solo lectura y que los filtros sean efímeros/no persistentes; cualquier escritura de filas, migración, cambio de motor o discrepancia de hash detiene el trabajo y requiere nueva consulta.

**Sanitización:** este documento contiene únicamente tablas, funciones, conteos agregados y razonamiento de código. No incluye recuerdos, valores de filas, IDs de registro, pesos neuronales, identificadores de Drive ni hashes privados.
