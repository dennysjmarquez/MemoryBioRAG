# Tareas — Spec 004: Pre-flight Search (Busca Antes de Aprender)

> Plan base: `plan.md`
> Invariante: ningún agente puede llamar `aprender`/`guardar` sin `busqueda_previa=True`. Sin excepción.

---

## T1: Parámetro `busqueda_previa` en `aprender` + validación primera

- **Descripción**: Agregar `busqueda_previa: bool = False` a `aprender()` en
  `core/memory_store.py` / `core/mcp_server/write.py`. Como PRIMERA validación (antes de cualquier otra comprobación o procesamiento),
  si `busqueda_previa` no es estrictamente `True`, retornar error con el mensaje de error
  accionable que explique la necesidad de buscar previamente.
- **Hecho cuando**:
  - [x] `aprender(..., busqueda_previa=False)` lanza/retorna error `BUSQUEDA_PREVIA_REQUERIDA` de inmediato
  - [x] `aprender(..., busqueda_previa=True, ...)` procede y guarda normalmente
  - [x] `pytest tests/test_preflight_busqueda_previa.py -q` → tests en verde
- [x] **Estado**: hecha

---

## T2: Quitar restricción temporal en `actualizar` y añadir soporte `sobrescribir`

- **Descripción**: En `core/mcp_server/write.py`:
  1. Localizar y eliminar el chequeo de ventana temporal en `biorag_actualizar()`. El método debe aceptar cualquier nodo activo independientemente de su `creado_en`.
  2. Añadir parámetro `sobrescribir: bool = False`. Si es `True`, reemplaza completamente el contenido, dimensiones y metadatos del nodo en vez de concatenar.
- **Hecho cuando**:
  - [x] `actualizar(concepto='nodo_antiguo', ...)` actualiza sin error de tiempo
  - [x] `actualizar(concepto='nodo', contenido='nuevo', sobrescribir=True)` sobrescribe totalmente
  - [x] `pytest tests/test_actualizar_sin_restriccion_temporal.py -q` → tests en verde
  - [x] `pytest tests/ -q` → 0 regresiones
- [x] **Estado**: hecha

---

## T3: Parámetro `vincular_con` en `aprender`

- **Descripción**: Agregar `vincular_con: list[str] | str | None = None` a `aprender()`.
  Si se pasa una lista o string de conceptos, tras crear el nodo se llama internamente a `establecer_asociacion()`
  para conectarlo bidireccionalmente con cada uno de ellos.
- **Hecho cuando**:
  - [x] `aprender(..., busqueda_previa=True, vincular_con=["nodo_a"])` crea el nodo y la sinapsis con `nodo_a` en una sola llamada
  - [x] Si un concepto de `vincular_con` no existe, se maneja limpiamente sin abortar el guardado
  - [x] `pytest tests/test_preflight_vincular_con.py -q` → tests en verde
- [x] **Estado**: hecha

---

## T4: Alias `guardar` y MCP hereda los nuevos parámetros

- **Descripción**: El alias `guardar()` en `core/memory_store.py` y su tool MCP
  en `core/mcp_server/` deben exponer también `busqueda_previa` y `vincular_con`
  con las mismas reglas que `aprender`.
- **Hecho cuando**:
  - [x] `guardar(..., busqueda_previa=False)` lanza el mismo `ValueError` que `aprender`
  - [x] `guardar(..., busqueda_previa=True, vincular_con=["x"])` funciona idéntico a `aprender`
  - [x] `pytest tests/test_preflight_guardar_alias.py -q` → tests en verde (7/7)
- [x] **Estado**: hecha

---

## T5: Actualizar `AGENTS.md` con el protocolo Pre-flight Search

- **Descripción**: Agregar sección **"Protocolo Pre-flight Search (Invariante)"**
  al `AGENTS.md` del repo con la regla inmutable, diagrama de flujo y tabla de decisiones.
- **Hecho cuando**:
  - [x] `AGENTS.md` contiene la sección "Protocolo Pre-flight Search" (Sección 10)
  - [x] El diagrama de flujo, tabla de decisión y guía de pitfalls están integrados
- [x] **Estado**: hecha

---

## Orden de ejecución

```
T1 → T2 → T3 → T4 → T5
```

