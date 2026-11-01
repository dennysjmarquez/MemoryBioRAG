# Evidencia aportada por Dennys: recálculos QA — resumen sanitizado

**Procedencia:** salidas pegadas por Dennys en la conversación. **No verificado ni reproducido por este agente.** Este documento conserva únicamente resultados agregados necesarios para el análisis; omite recuerdos, consultas, IDs, rutas locales y el log completo.

## 1. Separación de las comparaciones

Las salidas contienen tres comparaciones distintas. No combinarlas ni atribuir a la neurona diferencias entre bases:

1. **Base congelada frente a base viva:** son estados de memoria/grafo distintos. La salida informa, respectivamente, aproximadamente **851 nodos/13.912 sinapsis** y **1.356 nodos/31.099 sinapsis**. Sus diferencias de recuperación o grafo no aíslan el efecto de la neurona.
2. **Clásica frente a honesta:** son reglas/denominadores de evaluación distintos, presentados para cada recálculo. La honesta aparta casos según sus reglas de obsolescencia/ambigüedad; por ello sus porcentajes no son una comparación pareada equivalente a la clásica ni la sustituyen. La propia salida indica que al menos un criterio de apartamiento se decidió después de observar la primera medición; tratar esta vista como análisis exploratorio, no como línea base preespecificada.
3. **Fórmula frente a neurona:** la comparación directa atribuible a ordenamiento se reporta **dentro de la misma base viva y sobre las mismas preguntas**. No se debe usar el contraste de esa base con la congelada para estimar el efecto de la neurona.

## 2. Clásica y honesta, cada una en su recálculo

| Recálculo aportado | Vista | Casos de recuperación informados | R@5 | R@1 | Nota de comparabilidad |
|---|---|---:|---:|---:|---|
| Base congelada | Clásica | 875 | 100,0% | 93,03% | Vista global de recuperación reportada. |
| Base congelada | Honesta R@5 | 865 | 100,0% | — | 14 apartados para esa métrica; denominador distinto. |
| Base congelada | Honesta R@1 | 853 | — | 95,2% | 28 apartados para esa métrica; denominador distinto. |
| Base viva | Clásica, fórmula+neurona | 875 | 98,97% | 94,29% | Resultado servido en la corrida de la base viva. |
| Base viva | Honesta R@5 | 861 | 99,7% | — | 18 apartados para esa métrica; denominador distinto. |
| Base viva | Honesta R@1 | 850 | — | 96,8% | 31 apartados para esa métrica; denominador distinto. |

Los “apartados” no son nuevos aciertos sobre los mismos denominadores: cambian el conjunto contabilizado. Por tanto, 100,0% honesta no reemplaza la clásica ni demuestra por sí solo mejora. Los porcentajes de bases distintas tampoco deben compararse como efecto de la neurona.

## 3. Fórmula frente a neurona en la misma base viva

En la sección pareada del recálculo de la base viva, la salida atribuye el cambio al reordenamiento de la neurona sobre el mismo conjunto servido:

- **Recall@5:** 98,97% con fórmula y se conserva en la salida de neurona.
- **Recall@1:** 91,31% → 94,29% (**+2,98 puntos porcentuales**).
- **MRR:** 0,943 → 0,960.
- La salida registra **28 subidas** del objetivo al primer puesto y **2 descensos** desde el primer puesto; balance neto +26. La salida pegada no identifica de forma sanitizada cuáles son esos dos casos, así que aquí se conserva el conteo sin inventar IDs ni divulgar recuerdos.
- En esa ejecución, la neurona reordenó 320 de los 875 casos; el reporte declara R@5 idéntico y cero cambios en el conteo de falsos positivos. Esto describe esa comparación aportada, no una conclusión general ni aprobación de umbrales.

Los resultados de la base congelada no tienen una neurona entrenada en esa base; no sirven como lado “fórmula” de esta comparación causal. El cambio de base y el cambio de neurona son factores diferentes.

## 4. Diferencia en los tres casos de grafo

Se conserva el orden de casos del reporte, sin reproducir consultas ni nombres de recuerdos:

| Caso | Base congelada | Base viva | Diferencia observada |
|---|---|---|---|
| 1 | Objetivo recuperado por grafo en posición 8. | No alcanzado por la expansión a profundidad evaluada. | De posición 8 a no alcanzado; ya no aparece entre los tres rescates de la base viva. |
| 2 | Posición 1. | Posición 29. | El rescate cae fuera del top-5 en la base viva. |
| 3 | Posición 56. | Posición 94. | Sigue en el pool informado, pero cae más abajo. |

**Resumen agregado:** congelada: 3/3 candidatos en pool, rescate top-5 1/3, top-1 1/3, cero fuera del pool. Viva: 2/3 en pool, top-5 0/3, top-1 0/3 y 1/3 no alcanzado.

Estas diferencias se observaron entre grafos de bases distintas y no pueden atribuirse a la neurona. En particular, la salida de la prueba de grafo se refiere a descubrimiento/rescate por expansión; la comparación fórmula/neurona es el reordenamiento de resultados en la misma base viva. Son mediciones diferentes.

## 5. Lectura limitada y custodia

- La evidencia muestra que, en la corrida viva citada, la neurona elevó el R@1 agregado frente a la fórmula en esa misma base, con dos descensos individuales informados y sin cambio en R@5. Ambos hechos deben permanecer visibles; el agregado no borra los dos descensos.
- Los cambios entre congelada y viva —incluidos los tres casos de grafo— se registran como diferencias de datos/estado de grafo entre bases. No adjudicarlos a la neurona.
- “Clásica” y “honesta” deben mostrarse con sus nombres, exclusiones y denominadores; no reemplazar retrospectivamente la línea clásica por la honesta.
- El material aportado no autoriza extrapolar a la línea base E1, aprobar la rúbrica/umbrales, ejecutar una campaña ni cambiar el motor.
- Se conserva esta síntesis agregada solamente. No se incluyen recuerdos personales, consultas literales, identificadores de casos, archivos completos ni rutas. W sigue pendiente.
