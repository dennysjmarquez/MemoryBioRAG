# Auditoría del inventario E3 `c9f91fb`

## Veredicto

La distinción entre los 14 estados de prueba MCP y las etiquetas almacenadas es correcta y necesaria. El inventario es documental: el commit `c9f91fb976052717cfa160152981a1174ecad7bc` añade solo `docs/e3_inventario_pendiente_20261102.md`; no cambia motor ni contiene un diff de implementación. El SHA-256 de `core/memory/search.py` sigue siendo `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`.

**Aprobado como inventario con una precisión pendiente:** la cuestión de etiquetas no debe reducirse a forma exacta/plegada, búsqueda e historia. También hay que considerar explícitamente el reemplazo de etiquetas al actualizar **un mismo concepto**, que puede hacer que una etiqueta anterior deje de figurar en sus metadatos. No equivale a fusionar o borrar recuerdos, ni autoriza modificar datos o comportamiento.

## Verificación

- `core/mcp_server/search.py` normaliza la entrada exacta y después deriva la forma plegada; `core/memory/search.py` emplea el campo plegado en las rutas inspeccionadas y `core/memory/schema.py` lo incluye en FTS. Los campos exactos se agregan sin retrorellenar las filas históricas. La ausencia de forma exacta no permite reconstruir inequívocamente los originales desde el texto plegado.
- En `core/memory/ingest.py` y `core/memory/consolidation.py`, para un mismo concepto una entrada nueva **no vacía reemplaza** los metadatos plegado y exacto; una entrada vacía conserva los anteriores. Es el comportamiento aprobado de Cambio 2, no una modificación nueva.
- Una sonda propia sobre fixture inventada en copia temporal comprobó sustitución tanto en corto plazo como al consolidar un mismo concepto en largo plazo. Fue una única prueba directa, sin inferir frecuencia ni daño real: no se abrió ninguna base viva, no se borraron asociaciones ni se cambió motor. Antes de concluir el riesgo para agentes y recuperación se necesitan comparaciones controladas en las rutas reales y medición de pistas.
- La tabla del inventario presenta como «causas distintas» la explicación de los dos FP ingleses. La auditoría `docs/auditoria_fp_ingles_etiquetas_e4ce0b3_20261102.md` confirmó ablación y trazas, pero **no demostró causa exclusiva** de FTS o de un lema concreto. Deben describirse como mecanismos compatibles con la evidencia, no causalidad cerrada.

## Continuación

Añadir a la investigación de etiquetas la semántica actual de **reemplazo frente a eventual acumulación en el mismo recuerdo**, junto con las columnas exacta/plegada y filas históricas. Distinguirla siempre de fusionar etiquetas entre recuerdos distintos, de fusionar recuerdos y de los 14 marcadores MCP. Investigar con ejemplos sintéticos, baseline, rutas de escritura/actualización/consolidación y recuperación de pistas; no proponer aplicar cambio o backfill sin revisión y autorización específica. Mantener E3 abierto y E4 en espera.

Sonda privada sintética: `auditoria_e3_inventario_c9f91fb.tar.gz`, SHA-256 `e2d46f6228703a406e2b192978ccfc90c5a8ee1cdae9676ad51724e9d12d9b98`, Drive `1LESfQSQqrEERPS2gUogT01pKdGp5Anp0`. Incluye el guion y log de la sonda, sin SQLite ni datos vivos.
