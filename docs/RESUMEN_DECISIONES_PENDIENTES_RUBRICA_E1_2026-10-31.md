# Resumen sencillo: decisiones pendientes para cerrar rúbrica y avanzar a E1

**Estado:** guía para decisión de Dennys. Revisar `8c668bf` deja la propuesta lista para decidir; no aprueba los umbrales ni autoriza preparar fixtures, MCP o mediciones.

## Decisiones de Dennys

1. **Cerrar la rúbrica semántica.** Confirmar o ajustar las definiciones de objetivo, pista útil —incluida la útil tardía o inesperada—, neutral/contexto, ruido tonto y no adjudicado. Una pista no es ruido por ser indirecta, no literal, no seguida o no útil de inmediato. Un vacío solo cuenta como “ninguno” si fue adjudicado explícitamente.
2. **Decidir los criterios, sin tratarlos aún como aprobados.** El 95% de R@5 sigue siendo candidato; decidir si se acepta, ajusta o descarta. No hay tolerancia aprobada de una pérdida. La comparación debe mostrar cualquier regresión de recall de objetivos o pistas útiles; no presentar una ganancia en una categoría como compensación por una caída en la otra. No se proponen porcentajes máximos de ruido o mínimos de recall de pistas como metas de optimización: se informan descriptivamente para no incentivar búsquedas adicionales o filtros.
3. **Confirmar acuerdo y equipo de anotación.** Designar dos anotadores independientes y un adjudicador, competentes en español e inglés. Decidir si se adoptan como referencias el acuerdo bruto ≥85% y Cohen κ no ponderado ≥0,70. Las etiquetas son nominales, por lo que no corresponde kappa ponderado. El adjudicador resolverá todas las discrepancias antes del cierre, ciego a resultados.
4. **Cerrar el gold E1.** Confirmar el gold candidato de 88 episodios/224 consultas, o pedir una nueva versión si la revisión cambia el archivo. Exigir cierre fechado y hasheado antes de cualquier resultado **también si no hay cambios**; registrar entonces un cierre no-op. Vacíos no adjudicados no se convertirán en negativos ni se usarán para métricas de utilidad/ruido.
5. **Mantener el alcance original.** La línea base original es de consultas fijas en N0/N1/G1/G2/R. La extensión de trayectorias del agente de hasta tres llamadas es una propuesta separada; no se incorpora al plan original ni al presupuesto de 2.768 sin decisión y aprobación aparte. Llegar a un límite experimental no significa que no haya recuerdo.

## Secuencia propuesta, sin ejecutar

1. Dennys decide la rúbrica, los criterios candidatos y el equipo de anotación.
2. Los dos anotadores revisan independientemente el gold; el adjudicador resuelve diferencias.
3. Se registra el cierre no-op o la nueva versión revisada y se fija su hash antes de observar resultados.
4. Solo después, se podría preparar una propuesta/manifiesto de campaña con hashes exactos y pedir **autorización operativa separada**. La revisión del plan no la concede.

## Presupuesto y límites ya definidos

Si el gold permanece sin cambios, el presupuesto planificado —**no autorizado para ejecutar**— es **1.648 llamadas MCP de preparación** (dos construcciones de 824) más **1.120 de medición** (224 consultas × cinco brazos), **2.768 en total, sin reintentos**. Si el gold cambia, hay que recalcularlo antes de pedir autorización. W continúa pendiente y queda fuera de los brazos.

**En esta tarea solo se resume lo ya propuesto:** no se preparan bases/fixtures, no se inicia MCP, no se miden resultados ni se ejecuta QA. No se cambia el motor.
