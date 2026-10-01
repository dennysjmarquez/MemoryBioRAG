# Spec 004 — Pre-flight Search (Busca Antes de Aprender)

## Contexto y objetivo

El corpus de BioRAG crece dinámicamente con cada interacción de los agentes. Sin un protocolo estricto y forzado de búsqueda previa antes de la ingesta, el sistema sufre tres patologías graves:
1. **Nodos duplicados**: el mismo concepto guardado múltiples veces con variaciones léxicas mínimas.
2. **Versiones fragmentadas**: "últimas versiones" repartidas en decenas de nodos aislados sin conexión entre sí.
3. **Grafo huérfano**: conocimiento nuevo que no establece sinapsis con el conocimiento existente.

La **Spec 004** implementa el protocolo **Pre-flight Search** a nivel de arquitectura y contrato de API: ningún agente puede invocar `aprender` o `guardar` sin haber consultado previamente el corpus y pasar explícitamente `busqueda_previa=True`. Adicionalmente, flexibiliza `actualizar` (eliminando restricciones temporales y permitiendo `sobrescribir=True`) y dota a `aprender`/`guardar` de conexión sináptica atómica mediante el parámetro `vincular_con`.

---

## Usuarios / actores

- **Agentes BioRAG** (Athena, Hermes, Artemis, Kilo, Antigravity): interactúan mediante MCP o llamadas directas en Python para almacenar, actualizar y buscar conocimiento.
- **Humano (Dennys)**: supervisor y usuario del sistema de memoria asociativa.

---

## Historias de usuario

- **H1**: Como agente BioRAG, debo estar obligado por contrato a buscar antes de aprender o guardar, para garantizar que evalúo si el nodo ya existe antes de crearlo.
- **H2**: Como agente BioRAG, quiero poder actualizar cualquier nodo existente en cualquier momento sin importar cuándo fue creado, para mantener viva y actualizada la base de conocimiento.
- **H3**: Como agente BioRAG, quiero una opción `sobrescribir=True` en `actualizar` para poder reemplazar completamente un nodo cuando su contenido previo esté obsoleto.
- **H4**: Como agente BioRAG, quiero poder pasar `vincular_con` al momento de aprender o guardar, para que las sinapsis con nodos relacionados se creen atómicamente en una sola operación.
- **H5**: Como agente BioRAG, quiero que las herramientas MCP y los alias (`guardar`, `biorag_guardar`) respeten exactamente las mismas reglas de validación que `aprender`.

---

## Requisitos funcionales

- **RF-1**: CUANDO un agente o función invoca `aprender()` con `busqueda_previa=False` (o sin especificar el parámetro por omisión), EL SISTEMA DEBE rechazar la llamada de inmediato (fail-fast como primera validación) retornando/lanzando un error con código `BUSQUEDA_PREVIA_REQUERIDA` y un mensaje accionable con el protocolo de búsqueda previa.
- **RF-2**: CUANDO `busqueda_previa=True` es provisto en `aprender()`, EL SISTEMA procede con las validaciones de dimensiones, sustantivos clave y guardado normal.
- **RF-3**: CUANDO un agente invoca `actualizar()` sobre un nodo existente, EL SISTEMA DEBE permitir la actualización sin importar la fecha de creación del nodo (`creado_en`), eliminando cualquier ventana o restricción temporal histórica.
- **RF-4**: CUANDO un agente invoca `actualizar()` con `sobrescribir=True`, EL SISTEMA reemplaza íntegramente el contenido, dimensiones y metadatos del nodo, en lugar de concatenar texto.
- **RF-5**: CUANDO `aprender()` o `guardar()` recibe el parámetro `vincular_con` (lista de conceptos o string separado por comas), EL SISTEMA crea el nodo y automáticamente establece conexiones sinápticas bidireccionales con cada uno de los conceptos listados.
- **RF-6**: SI un concepto especificado en `vincular_con` no existe en la base de datos, EL SISTEMA no debe abortar la creación del nodo principal; debe registrar la advertencia y continuar con los nodos válidos.
- **RF-7**: El alias `guardar()` y la tool MCP `biorag_guardar` deben heredar y validar estrictamente `busqueda_previa` y soportar `vincular_con` con la misma semántica que `aprender()`.
- **RF-8**: EL SISTEMA documenta en `AGENTS.md` el Protocolo Pre-flight Search (Invariante) con su diagrama de flujo, tabla de decisiones y catálogo de trampas comunes.

---

## Requisitos no funcionales

- **RNF-1**: Validación Fail-Fast: La verificación de `busqueda_previa` debe ser la primera línea de ejecución antes de procesar texto o validar otros campos.
- **RNF-2**: Cero regresiones en la suite de pruebas unitarias existentes (280+ tests pasando).
- **RNF-3**: Consistencia total entre la capa Python (`core/memory_store.py`) y la capa de transporte MCP (`core/mcp_server/write.py`).

---

## Casos límite

- **CL-1**: `busqueda_previa=None` o valor truthy no booleano estricto → Rechazo inmediato con `BUSQUEDA_PREVIA_REQUERIDA`.
- **CL-2**: `vincular_con=""` o `vincular_con=[]` → Ignorado de forma limpia, nodo guardado sin sinapsis adicionales.
- **CL-3**: `vincular_con` con conceptos inexistentes → El nodo se crea con éxito y no se produce un fallo catastrófico.
- **CL-4**: Actualización de nodo con `sobrescribir=False` (default) → Mantiene comportamiento histórico de anexar o enriquecer.
