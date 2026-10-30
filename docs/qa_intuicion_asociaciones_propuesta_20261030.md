# Propuesta: QA de intuición y asociaciones

**Fecha:** 2026-10-30
**Estado:** propuesta de diseño; sin ejecución ni mediciones.
**Alcance:** definir cómo medir si una búsqueda devuelve el recuerdo principal y, aparte, recuerdos relacionados que aportan pistas útiles; distinguirlos del ruido irrelevante o engañoso.

> **Principio de evaluación — el ruido útil no se mata.** Una asociación no es falsa solo porque no sea el objetivo literal de la pregunta. Se conserva y se mide como pista útil cuando ayuda a resolver la tarea o abre una conexión pertinente. Se penaliza por separado el ruido tonto: una asociación sin relación defendible, distractora o engañosa.

## 1. Decisiones y límites

- Esta entrega **solo investiga y propone**. No modifica motor, ranking, pesos, neuronas, MCP ni datos.
- No se abrió, consultó, modificó ni copió la base viva ni el snapshot. No se ejecutó ninguna QA.
- Si Dennys autoriza una futura medición, se construirá una base sintética efímera mediante las tools MCP de escritura y vínculo. Cada brazo se ejecutará en copias temporales independientes; nunca sobre la DB viva ni sobre el snapshot original.
- La neurona se evalúa como **ordenador de candidatos**, no como generador ni eliminador de recuerdos. La cobertura y la membresía del conjunto se informan separadas del rango.
- No se inicia reparación, E4 ni E5. La eventual ejecución de esta propuesta requiere autorización posterior de Dennys.

## 2. Qué permite medir el código actual

La respuesta MCP de `biorag_recordar` separa varios canales, que la QA no debe mezclar:

1. **`resultados`**: recuerdos principales, con `concepto`, `contenido`, `score_hibrido` y metadatos. Aquí se mide el objetivo principal y su rango.
2. **`asociaciones_enriquecidas`**: canal lateral de vecinos sinápticos para cada resultado principal; expone fuerza, tipo, peso del vecino y resumen. El helper actual `obtener_asociaciones_enriquecidas` limita el canal por defecto a cinco vecinos, descarta aristas con peso menor a 0,50 y omite nodos dormidos o inexistentes.
3. **`asociaciones`**: mapa plano de vecindad, con conteo total, elementos y bandera de truncamiento. El límite de serialización por defecto es 12 nombres por resultado; no debe confundirse el orden de esta lista con relevancia.
4. **`contexto_expandido`**: vecinos BFS adjuntos después de los resultados principales. Con `context_window=0` queda vacío; la expansión no debe contarse como resultado principal ni alterar el total de la búsqueda. El modo normal busca nodos activos; `deep=True` puede despertar nodos dormidos, así que queda fuera de la QA propuesta.
5. **`trazabilidad` y avisos**: incluye, entre otros datos, origen/capas activadas, candidatos y ráfaga. Se guardan para diagnóstico, no se usan como etiqueta de relevancia.

`biorag_recordar` exige `sustantivos_clave` para consultas textuales. La corrida MCP debe invocar el servidor/protocolo real y guardar la respuesta cruda, además del JSON parseado; una llamada interna a `_recordar_impl` puede servir como prueba auxiliar, pero no sustituye el recorrido MCP.

El fallback de ráfaga puede activarse con términos proporcionados si el resultado falta o su score no alcanza el umbral; también puede forzarse. Para no mezclar hipótesis, la primera QA no lo forzará. Si se desea medir la ráfaga, será un brazo separado, con el mismo conjunto y otra copia limpia.

En `core/memory/neurona.py`, la documentación describe una neurona que reordena los primeros candidatos del motor conservando los mismos nodos y valores. Por tanto, esta QA registrará por separado **qué candidatos estaban disponibles** y **en qué orden aparecieron**; nunca llamará «eliminado» a un recuerdo por cambiar de puesto o quedar fuera de un corte de presentación.

## 3. Conjunto propuesto, fijado antes de medir

### 3.1 Tamaño y estratos

Propongo **88 episodios sintéticos**: 48 positivos con una tarea contestable y 40 controles negativos. Cada episodio se crea en su propia fixture temporal o en un shard aislado, para evitar colisiones y contaminación entre historias.

| Estrato | Episodios | Qué pone a prueba |
|---|---:|---|
| Objetivo directo / léxico | 12 | Control de recuperación principal, sin depender de asociaciones. |
| Paráfrasis o fragmento de contexto | 12 | Recuperar el recuerdo por una formulación natural distinta o por un detalle guardado en el contenido. |
| Pista asociada a 1 salto | 12 | Exponer una conexión lateral relevante además del objetivo. |
| Pista útil de baja coincidencia / 2 saltos | 12 | Hallar una pista no obvia pero pertinente; se etiqueta como útil, no como FP. |
| Negativos: asunto ausente | 10 | Abstenerse cuando no hay recuerdo que responda. |
| Negativos: colisión léxica / homónimo | 10 | Evitar que una palabra común se haga pasar por relación semántica. |
| Negativos: arista engañosa o no pertinente | 10 | Detectar una conexión que no ayuda a la tarea aunque exista en el grafo. |
| Negativos: hub genérico / asociaciones de baja especificidad | 10 | Medir contaminación por nodos de alto grado o vecinos genéricos. |

Cada episodio positivo incluye: un objetivo principal, dos o más recuerdos de apoyo etiquetados de antemano, al menos un recuerdo potencialmente útil que no sea el objetivo y dos distractores deliberados (uno de ellos puede ser una conexión aparentemente cercana pero inútil). Los negativos se construyen para que ningún recuerdo sea una respuesta válida; sus distractores tampoco deben ser útiles para la pregunta.

La fixture incluye consultas en español y un subconjunto en inglés, etiquetadas por idioma. No se mezclan métricas entre idiomas sin mostrar también el desglose. La versión inicial no intenta ser una QA multilingüe completa.

### 3.2 Secuencia de consultas

Cada positivo tiene tres **consultas lógicas** preescritas y congeladas: (1) principal, con objetivo explícito en el gold; (2) seguimiento fijo sobre una pista o detalle; y (3) control negativo sobre una asociación engañosa o un dato ausente. Cada negativo tiene dos consultas lógicas: ausencia concreta y trampa de colisión/hub. La secuencia fija no adapta la consulta siguiente a la respuesta recibida.

El conjunto contiene **224 definiciones de consulta base** (48×3 + 40×2), no 224 invocaciones totales del protocolo: cada condición experimental vuelve a ejecutar esas definiciones en su propia copia. El conteo de invocaciones, incluidos brazos y control de orden, queda explícito en §5.4. Las respuestas nunca se usan para reescribir las consultas fijadas.

Una futura fase **adaptativa** sería un experimento distinto y no forma parte de estas 224 definiciones: en una copia limpia, un agente congelado, ciego al gold, recibiría la pista de la búsqueda inicial y elegiría un único seguimiento entre opciones permitidas. Se conservarían prompt, versión del agente, opciones, respuesta MCP y transcript; se informarían por separado sus 48 búsquedas iniciales + 48 seguimientos = **96 invocaciones por réplica**, más los controles/repeticiones que se aprueben. No sustituye ni se mezcla con la cadena fija.

### 3.3 Esquema del gold

Archivo sugerido: `scripts/casos_qa_intuicion_asociaciones_e1.jsonl`, creado únicamente si se autoriza implementación. Campos por consulta:

```json
{
  "episode_id": "timeout-01",
  "query_id": "timeout-01-main",
  "idioma": "es",
  "estrato": "pista_1_salto",
  "query": "¿Qué hacemos si el proveedor se demora y no debemos duplicar el pedido?",
  "sustantivos_clave": "proveedor,demora,pedido",
  "objetivos_principales": ["reintento_api_con_backoff"],
  "relacionados_utiles": ["idempotencia_con_clave", "circuit_breaker"],
  "pistas_serendipia_utiles": ["limite_de_reintentos_por_proveedor"],
  "ruido_tonto": ["paleta_colores_dashboard", "receta_cafe_frio"],
  "rutas_esperadas": [
    {"concepto": "idempotencia_con_clave", "saltos": 1, "tipo": "manual"}
  ],
  "evidencia": {
    "objetivo": "fragmento literal del recuerdo que responde la pregunta",
    "pista": "fragmento literal que justifica su utilidad"
  },
  "followup_id": "timeout-01-followup",
  "respuesta_followup": "usar clave idempotente para que los reintentos no dupliquen el efecto"
}
```

El JSON es ilustrativo, no es un resultado real ni contenido de la DB. Antes de ejecutar se validará automáticamente: IDs únicos; objetivo existente en la fixture; evidencia textual; etiquetas de utilidad/ruido disjuntas; ruta y número de saltos coherentes; términos `sustantivos_clave` presentes en la consulta y sin filtrar el concepto esperado; consultas negativas realmente no contestables.

### 3.4 Ejemplo de la separación que se quiere probar

Para la pregunta sobre una API lenta y pedidos duplicados:

- **Objetivo:** el recuerdo de reintentos/backoff.
- **Pista útil:** idempotencia, porque evita que repetir una petición duplique el pedido.
- **Serendipia útil:** circuit breaker, si el contenido explica cómo evitar una cascada de fallas aunque no sea la respuesta literal.
- **Ruido tonto:** una receta o el color de un dashboard sin relación con la decisión.

La pista útil no se penaliza como falso positivo por quedar fuera del objetivo literal. El distractor tampoco se convierte en «útil» solo por compartir una palabra o una arista.

## 4. Fixture y brazos MCP

### 4.1 Construcción aislada

- Construir la fixture desde cero y en temporal mediante tools MCP reales, en este orden: **preflight de búsqueda → aprender → consolidar → vincular**. Para cada nodo, llamar primero `biorag_recordar`/`biorag_buscar` sobre el tema que se va a guardar y evaluar la respuesta; luego llamar `biorag_aprender` con `busqueda_previa=True`, cinco `bridges` válidos (uno por ángulo semántico exigido) y 2–10 `sustantivos_clave`. `aprender` guarda primero en corto plazo, ejecuta `auto_vincular` (y puede crear enlaces por sinónimos); por tanto, registrar esos enlaces automáticos y no asumir que solo existen las aristas del gold.
- Tras aprender todos los nodos, llamar `biorag_consolidar` para pasarlos a largo plazo; solo después crear las aristas de ruta previstas con `biorag_vincular(a, b)`. Esa tool exige nodos existentes y crea una asociación bidireccional. No pasar `vincular_con` a `aprender` para las aristas gold, para mantener clara la etapa explícita de vinculación.
- Inspeccionar en modo de solo lectura el grafo sintético final, incluyendo enlaces automáticos y enlaces de bridges. Guardar el hash de la DB, verificar `PRAGMA integrity_check` y congelar una copia plantilla. Una ruta se etiqueta como exactamente dos saltos solo si la distancia mínima entre objetivo y pista es 2 en ese grafo final. Si un enlace automático crea atajo (distancia 1) o hace ambigua la etiqueta, descartar y reconstruir el episodio; no reparar con SQL ni tocar motor/datos fuera de la fixture temporal.
- Para cada condición y repetición, usar una copia temporal nueva de la plantilla; registrar diffs antes/después. No llamar a `biorag_feedback`, `desvincular`, `deep=True` ni herramientas de escritura durante las búsquedas.
- Usar reloj fijo, `PYTHONHASHSEED=0`, `BIORAG_DMN_ESTADO_PATH` temporal exclusivo y un proceso MCP por corrida. El servidor debe apuntar siempre al path temporal; fallar si intenta abrir otra ruta.
- Invocar por transporte MCP stdio real, conservar JSON-RPC/stdout crudos y warnings, y validar que no haya truncamiento. Vaciar y mantener inactivo el búfer de autoguardado durante recuperación; no automatizar guardados ni feedback con resultados.

### 4.2 Condiciones pareadas

| Brazo | Llamada MCP | Propósito |
|---|---|---|
| A — objetivo solo | `asociados=False`, `context_window=0`, `limite=5`, `deep=False` | Línea de base de resultado principal. |
| B — mapa de asociaciones | `asociados=True`, `context_window=0`, `limite=5`, `deep=False` | Medir `asociaciones_enriquecidas` y el campo plano sin contexto BFS. |
| C1 — contexto 1 salto | `asociados=True`, `context_window=1`, `limite=5`, `deep=False` | Canal BFS de un salto. |
| C2 — contexto 2 saltos | `asociados=True`, `context_window=2`, `limite=5`, `deep=False` | Canal BFS de dos saltos; medir específicamente `contexto_expandido`. |
| D — cadena fija | Secuencia fija de consultas por episodio, mismos parámetros | Medir seguimiento en estado de sesión; ninguna respuesta elige la siguiente consulta. |
| D-inv — control de orden | Repetición de D en otra copia, invirtiendo el orden de ejecución de episodios y preservando el orden interno de cada cadena | Detectar efectos del orden de ejecución sin convertir la cadena fija en adaptativa. |

A, B, C1 y C2 usan copias idénticas. D conserva una copia aislada durante cada cadena de episodio; D-inv usa copia limpia. Para una pista gold de **exactamente dos saltos**, el gold debe declarar la ruta `objetivo → intermedio → pista`; un validador independiente calcula distancia mínima 2 en el grafo final congelado. Se cuenta como recuperación de dos saltos únicamente si la pista aparece en `contexto_expandido` con `context_window=2`. Se reporta aparte cualquier aparición en `resultados`, `asociaciones_enriquecidas` o `asociaciones` (canales de vecinos directos/laterales); ninguna de ellas demuestra por sí sola dos saltos. Si MCP no expone distancia/ruta, la prueba la acredita con el gold y la validación del grafo, no infiriéndola del JSON de salida. Ningún brazo usa `forzar_rafaga=True`; ráfaga queda para otro experimento aprobado.

## 5. Métricas y reglas de conteo

Se deduplican conceptos entre canales, pero se conserva el canal de primera aparición y los rangos. Una aparición en una asociación no se convierte retroactivamente en resultado principal.

### 5.1 Objetivo principal (no se sacrifica)

- R@1, R@5 y MRR@5 del objetivo, **solo sobre `resultados`**.
- Recall de objetivo por estrato, idioma y consulta principal/seguimiento.
- Comparación pareada A→B: los campos de asociaciones son laterales; se verifica que activar solo su serialización no cambie IDs ni orden de `resultados`.
- Se reportan por separado `resultados`, `contexto_expandido`, `asociaciones_enriquecidas` y `asociaciones.items`; un objetivo encontrado solo en un canal lateral no cuenta como R@5 principal.

### 5.2 Pistas y ruido

- **Recall de relacionados útiles:** relacionados útiles únicos visibles / relacionados útiles del gold, por cada canal y en la unión de canales.
- **Precisión de utilidad lateral:** relacionados útiles o serendipia útil / recuerdos laterales únicos evaluables. Neutral e irrelevante no cuentan como útiles.
- **Cobertura de pista por episodio:** proporción de positivos que expone al menos una pista útil no principal.
- **Tasa de serendipia útil:** proporción de episodios del estrato de baja coincidencia que expone al menos una pista preetiquetada como útil.
- **Ruido tonto visible:** distractores etiquetados que aparecen en `resultados`, contexto o asociaciones, con canal y rango. Separar ruido en `resultados` de ruido en canales laterales; informar número por consulta y por 100 consultas.
- **FP de control negativo:** resultados principales indebidos por consulta negativa, más una medida aparte de distractores laterales. Un vecino útil no se cuenta como FP principal; un elemento lateral irrelevante sí se cuenta como ruido de canal, no se mezcla con el FP de recuperación.
- **Utilidad del seguimiento:** proporción de episodios cuyo objetivo de seguimiento queda visible en `resultados` o en una pista lateral que el agente puede citar; también R@5 del seguimiento en su propia llamada.
- **Tamaño y coste MCP:** latencia por llamada, bytes/caracteres de salida, tokens si el cliente los informa, tamaño p50/p95/máximo, respuestas JSON incompletas o truncadas.

### 5.4 Conteo de invocaciones y escrituras permitidas

Las **224** son consultas lógicas base. La primera pasada ejecuta cada definición una vez en A, B, C1 y C2 (4×224), una vez en D y una vez en D-inv: **224×(4+1+1) = 1.344 llamadas de búsqueda `biorag_recordar`**. Si se repite el protocolo completo `r` veces, son **1.344×r** llamadas; cualquier brazo adicional suma `224×r` por cada condición. Este subtotal no incluye el armado MCP de la fixture: para `N` nodos y `E` enlaces gold explícitos, una construcción requiere `N` búsquedas preflight + `N` llamadas `biorag_aprender` + 1 `biorag_consolidar` + `E` `biorag_vincular`, es decir `2N+E+1` llamadas adicionales (si se reconstruye por réplica, multiplicar también ese término por `r`). La fase adaptativa, si se aprueba después, se contabiliza aparte (§3.2). Publicar siempre consultas lógicas, llamadas por tipo/condición y total efectivo, incluidas fallidas y reintentos.

En la comparación pre/post de una búsqueda, se permiten como escrituras esperadas únicamente las de telemetría/actividad que confirme el código para esa versión (por ejemplo, fila de `log_busquedas`, historial de acceso y actualización de sus parámetros), anotadas por tabla y operación. `recordar` no debe crear, borrar ni cambiar recuerdos, aristas, pesos o estado del grafo. `context_window` no equivale a `deep`; mantener `deep=False`, fixture sin nodos en cuarentena y ráfaga no forzada. Capturar diffs por tabla: toda mutación a `corto_plazo`, `largo_plazo`, sinapsis/grafo o neurona es inesperada salvo que una inspección previa del recorrido MCP identifique y apruebe explícitamente el efecto antes de medir. Registrar aparte cualquier efecto del interceptor MCP/autoguardado; con búfer vacío e inactivo no se acepta guardado heurístico como efecto normal de `recordar`. Una escritura inesperada contamina la corrida; no se borra ni corrige en sitio.

### 5.3 Neurona: eje de orden separado

Ejecutar A, B, C1, C2 y D con `BIORAG_NEURONA=0` para la medición principal de asociaciones; opcionalmente repetir una pareja en el modo de neurona que Dennys autorice. En esa pareja:

- comparar el mismo pool de candidatos y la misma consulta;
- registrar cambio de orden, R@1/R@5/MRR y pertenencia del conjunto;
- cuando la fixture tenga menos candidatos que el límite solicitado, exigir igualdad de conjunto y conteo entre apagada/encendida;
- no interpretar un desplazamiento de posición como borrado del recuerdo ni dejar que el ranking determine si una relación anotada es útil.

La neurona no recibe feedback ni se entrena durante la QA. Si una llamada modifica un nodo o arista por una ruta ajena a ordenar, la corrida se marca como contaminada y se repite solo desde otra copia limpia, después de investigar la causa; nunca se corrige en vivo.

## 6. Criterios de éxito — congelar antes de ejecutar

Estos umbrales son **propuesta**. Deben ser aprobados o ajustados por Dennys y quedar congelados antes de inspeccionar resultados.

1. **Objetivo principal:** R@5 ≥ 95% en los 48 positivos; diferencia B vs A de R@5 no menor que −2 puntos porcentuales. R@1 y MRR se publican por separado; no ocultar una caída detrás de una mejora de pistas.
2. **Pistas:** al menos una pista útil visible en ≥75% de los episodios positivos; recall de relacionados útiles ≥70% global y ≥60% en el estrato de 2 saltos/baja coincidencia.
3. **Ruido útil preservado:** ≥60% de los episodios preetiquetados de serendipia exponen al menos una pista útil. Una asociación serendípica útil no aumenta el FP, aunque no sea la respuesta principal.
4. **Ruido tonto acotado:** ≤10% de los conceptos laterales visibles se etiqueta como ruido tonto; en los 40 negativos, ≤1/40 con falso positivo en `resultados` (y cero top-1 de alta confianza). El ruido lateral se informa aparte y no se disfraza como abstención correcta.
5. **Cadena de varias búsquedas:** el objetivo de seguimiento aparece en R@5 de su consulta en ≥80% de los episodios donde existe en la fixture; al menos 70% de esos episodios debe exponer antes una pista útil en la consulta principal.
6. **MCP y datos:** 100% de respuestas parseables, cero llamadas a rutas de DB fuera de temporales, cero mutaciones no previstas del grafo y cero truncamientos silenciosos. Si el cliente no informa un límite de salida, tamaño se reporta descriptivamente y no se inventa un umbral.
7. **Estabilidad:** mismo orden de resultados bajo orden de episodios original/inverso en las condiciones deterministas; si hay diferencias, se publican por caso, sin volver a etiquetar ni reordenar el gold después de medir.

Los intervalos de confianza se calculan por episodio (bootstrap estratificado) y se muestran junto a porcentajes. Con 48 positivos/40 negativos, se describe esta QA como evaluación de aceptación de la fixture, no como estimación de producción ni prueba estadística universal.

## 7. Anotación ciega y revisión

- El gold se congela antes de ejecutar y se acompaña con evidencia textual y una justificación breve de cada pista útil/ruido tonto.
- Dos revisores etiquetan las salidas sin ver brazo, score ni rango. Escala: `0=irrelevante/engañoso`, `1=contexto relacionado pero no accionable`, `2=pista útil para el seguimiento`, `3=hallazgo no obvio que cambia o amplía una acción válida`.
- Se informa acuerdo ordinal (kappa ponderado). Si es <0,60, se revisa la rúbrica y se vuelve a anotar a ciegas; no se modifica el gold para favorecer una condición.
- La hoja de revisión conserva consulta, memoria candidata, canal, evidencia del recuerdo, rating y motivo. Los desacuerdos se adjudican y quedan visibles.

## 8. Entregables de una futura ejecución autorizada

1. Gold JSONL y su SHA-256, rúbrica y protocolo de anotación.
2. Script de QA que construye fixture y copias temporales, invoca MCP real y falla si detecta ruta no temporal.
3. Salidas crudas JSON-RPC/log, métricas agregadas por canal/estrato/idioma, latencia/tamaño y hashes de las DB sintéticas.
4. Comparación directa del objetivo primario A/B y tabla aparte de pistas útiles vs ruido tonto.
5. Veredicto que distinga **mejora de pistas**, **regresión del objetivo**, **ruido dañino** y **serendipia útil**. Sin editar motor, ranking ni gold; cualquier cambio posterior sería otra propuesta y requeriría autorización.

## 9. Archivos revisados

- `core/mcp_server/search.py`: interfaz `biorag_recordar`, campos MCP, fallback/ráfaga, serialización de asociaciones y contexto.
- `core/memory/synapses.py`: expansión BFS y `obtener_asociaciones_enriquecidas` (filtros, priorización y límite de vecinos).
- `core/memory/neurona.py`: invariantes de reordenamiento y vistas de ranking.
- `scripts/evaluar_qa_multilingue_e3a.py`, `scripts/evaluar_qa_multilingue_mcp_e3a.py` y `tests/test_qa_multilingue_mcp_e3a.py`: patrones existentes de gold congelado, fixture temporal, copias por caso y llamada MCP.
- `core/mcp_server/README.md`: mapa del adaptador MCP y campos expuestos.
- `core/mcp_server/write.py`, `core/mcp_server/consolidation.py` y `core/mcp_server/synapses.py`: contrato real de preflight/aprendizaje, consolidación y vinculación MCP.

**No se ejecutó ninguna medición ni se abrió ninguna base de datos en esta investigación.** La DB viva y el snapshot no se tocaron; solo se inspeccionó código fuente.
