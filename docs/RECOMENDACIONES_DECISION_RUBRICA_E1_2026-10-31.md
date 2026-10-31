# Recomendaciones concretas para decidir la rúbrica y avanzar con E1

**Para decisión de Dennys.** Esta nota desarrolla el plan E1 original de consultas fijas; no aprueba umbrales ni autoriza ejecución. No presupone que existan anotadores disponibles.

## 1. Recomendación de rúbrica, con ejemplos

Usar etiquetas por **recuerdo × consulta**, cada una con una cita del contenido y una justificación breve. No decidir por tipo, peso, literalidad o presencia de una arista.

| Categoría | Recomendación | Ejemplo sencillo |
|---|---|---|
| **Objetivo** | Responde directamente a la pregunta o permite ejecutar la decisión pedida. | Pregunta: “¿Cómo evitamos pedidos duplicados al reintentar?”. Recuerdo: “Reutiliza la misma clave de idempotencia en cada reintento”. Objetivo. |
| **Pista útil** | No es la respuesta completa, pero ayuda a decidir, comprobar una condición o formular una búsqueda siguiente. Puede ayudar más tarde; no tiene que ser literal ni útil de inmediato. | “La clave debe conservarse durante todo el horizonte de reintentos”. Es pista útil para el ejemplo anterior: concreta una condición necesaria. |
| **Puente/pista inesperada** | Una pista no prevista en el gold que el agente usa o que, al revisar la trayectoria completa, ayuda a orientar una búsqueda posterior. | La búsqueda inicial devuelve “el proveedor incluye `Retry-After`”; el agente pregunta luego cómo coordinar ese plazo con la misma clave idempotente y encuentra el recuerdo objetivo. Revisar el puente con toda la secuencia; no descartarlo porque no respondía la pregunta inicial. |
| **Neutral/contexto** | Tiene relación defendible, pero no se confirma un aporte concreto. | Una nota que registra solicitudes, sin mostrar cómo evita duplicados ni qué consulta posterior posibilita. No contarla como útil ni como ruido. |
| **Ruido tonto** | Hay evidencia de que es ajeno, engañoso o distractor para la tarea. | Una nota sobre el color del dashboard o una receta, sin vínculo con reintentos. |
| **No adjudicado** | Falta evidencia o no se ha resuelto el desacuerdo. | Una etiqueta vacía no significa “no existe pista” ni “es ruido”. |

**Recomendación:** un recuerdo no literal o que no lleva directamente al objetivo nunca se convierte por eso en ruido. Si no se ha confirmado su valor en el trayecto, usar `potencial_no_confirmado` o `neutral_contexto`. Anotar si fue puente, útil tarde o no atribuible. No borrar, filtrar, ocultar ni recortar conexiones para mejorar las cifras.

## 2. Recomendación para decidir umbrales

Los siguientes valores siguen **sin aprobación**. Recomiendo que Dennys decida cada punto antes del cierre del gold y de ver resultados:

1. **Recall del objetivo:** conservar `R@5 ≥95%` en `resultados` como candidato de piso, no como número aprobado. Con las 96 consultas contestables actuales equivale a por lo menos 92/96. Decidir si mantenerlo, cambiarlo o descartarlo. No mantener la tolerancia propuesta de “una pérdida”: no hay margen aprobado. En comparaciones N/G/R informar cualquier cambio pareado exacto.
2. **Recall de pistas útiles:** no fijar un mínimo global de 70% ni un piso de cobertura por episodio. Más llamadas o más asociaciones expuestas podrían inflar el número sin mejorar la memoria. Informar recall/cobertura por canal y, en secuencias, por paso; declarar las pistas etiquetadas y las no adjudicadas por separado. Una caída frente al brazo de referencia se reporta como regresión, no se compensa con más objetivos ni con más ruido visible.
3. **Ruido:** no usar porcentajes máximos de ruido (como 10%) ni de falsos positivos (como 5%) como metas para afinar el sistema. Pueden incentivar supresión de asociaciones. Reportar casos y tasas descriptivas por canal/consulta, con ejemplos y denominadores; adjudicar el supuesto daño. Neutral, no adjudicado y potencial no confirmado no entran al numerador de ruido.
4. **Principio de comparación:** no declarar una mejora global si baja el recall de objetivos o el de pistas útiles adjudicadas. Mostrar cada dimensión separada, incluidos numeradores/denominadores y regresiones. No promediar para ocultar una pérdida.
5. **Acuerdo entre anotadores:** las categorías son nominales, sin orden ordinal justificado. Como propuesta para revisión, usar acuerdo bruto y Cohen κ **no ponderado**; publicar también las tablas de confusión y acuerdo por categoría. Los candidatos de ≥85% de acuerdo bruto y κ ≥0,70 no se consideran aprobados hasta que Dennys los confirme o ajuste.

Para la línea base original, mantener las consultas fijas y los cinco brazos `N0/N1/G1/G2/R`. La extensión de cadenas dinámicas del agente queda fuera de este plan. El límite experimental de tres llamadas de aquella propuesta no define cómo debe recordar el agente; si una futura evaluación lo usa y llega al tope sin resolver, la trayectoria será interrumpida/inconclusa, no evidencia de ausencia de recuerdo.

## 3. Cómo conseguir y organizar a los revisores

**No hay un equipo confirmado todavía.** Recomendación práctica:

1. Pedir a Dennys que nomine tres personas: dos anotadores independientes y una persona adjudicadora. Puede buscarlos entre colegas/collaboradores bilingües con criterio semántico y familiaridad con las tareas del gold; si no están disponibles, considerar revisores externos de corta duración bajo el acuerdo de confidencialidad que Dennys determine. No dar por hecho que nadie aceptó hasta confirmarlo.
2. Los dos anotadores deben poder revisar español e inglés, no haber preparado las etiquetas que van a revisar, y poder explicar cada decisión con texto del recuerdo. La persona adjudicadora debe dominar la rúbrica y no ver resultados de brazos. Dennys podría adjudicar si acepta ese rol; si quiere independencia también en la adjudicación, deberá nominar una tercera persona.
3. Antes de revisar todo el conjunto, proponer una calibración pequeña y equilibrada (por ejemplo, ocho ejemplos: objetivos, pistas no literales, neutralidad, ruido y casos ambiguos). Cada anotador etiqueta por separado; discuten ambigüedades solo después y aclaran la rúbrica. Las etiquetas finales se asignan luego independientemente sobre el gold completo, con las etiquetas vigentes ocultas.
4. Cada anotador registra categoría, evidencia textual, justificación y estado de listas vacías. Se conserva su versión original. El adjudicador ve ambas hojas después, resuelve cada desacuerdo y registra decisión y motivo. No se decide por mayoría automática ni por grafo/tipo/peso.
5. Si no se consiguen las tres personas, o quedan desacuerdos sin resolver, no cerrar el gold ni usar vacíos como etiquetas negativas. La tarea queda pendiente de adjudicación.

## 4. Decisiones concretas para Dennys

- [ ] Confirmar o editar las definiciones y ejemplos de objetivo, pista útil/tardía, neutral y ruido.
- [ ] Mantener, ajustar o descartar el umbral candidato de R@5 ≥95%; confirmar que no se usará una tolerancia de una pérdida.
- [ ] Confirmar que recall de pistas y ruido serán desgloses descriptivos, no porcentajes para filtrar o recortar asociaciones.
- [ ] Aprobar o ajustar acuerdo bruto ≥85% y Cohen κ no ponderado ≥0,70.
- [ ] Designar a dos anotadores y un adjudicador, o dejar pendiente la designación.
- [ ] Confirmar el gold E1 completo (88 episodios/224 consultas) o solicitar una nueva versión. En cualquiera de los casos, exigir revisión/cierre hasheado antes de observar resultados, incluso si el archivo no cambia.
- [ ] Confirmar el plan original de consultas fijas N0/N1/G1/G2/R; no añadir la extensión de cadenas del agente.

## 5. Presupuesto y autorización

Para el gold E1 sin cambios, el plan ya verificado es **1.648 llamadas MCP de preparación + 1.120 de medición = 2.768**, sin reintentos. Es un presupuesto **planificado, no autorizado** para ejecutar; si el gold cambia, debe recalcularse. La decisión sobre la rúbrica tampoco activa la medición: se necesitaría una autorización operativa separada para hashes exactos. W continúa pendiente y fuera de alcance.

## 6. Nota para la modularización posterior — no ejecutar ahora

Registrar como requisito futuro de diseño: las carpetas/nombres de módulos deben estar en **inglés** y cada neurona debe tener documentación completa que describa, como mínimo, su propósito, entradas/salidas, límites, dependencias y **piso, techo y guardianes**. Esta nota no autoriza ni implica mover, reorganizar, conectar o cablear neuronas ahora.
