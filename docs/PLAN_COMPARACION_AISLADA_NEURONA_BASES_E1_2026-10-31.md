# Preparación: verificación de neurona y comparación aislada entre bases

**Estado:** plan documental, no autorización. No se abrieron bases, no se crearon copias, no se ejecutó QA ni medición y no se cambió el motor. W sigue pendiente.

## 1. Revisores del gold E1: disponibilidad no confirmada

No hay en los registros disponibles nombres, aceptaciones ni declaraciones de conflicto de interés que permitan identificar como realmente independientes a dos anotadores y un adjudicador. No inventar nombres ni cerrar el gold.

Alternativa verificable si Dennys no dispone de revisores internos: solicitar tres revisores bilingües (dos anotadores independientes y una persona adjudicadora) a colaboradores externos o contratarlos para esta tarea. Antes de asignarlos, documentar sus nombres/IDs en un roster privado, competencia en español e inglés, que no participaron en preparar gold/motor, declaración de conflictos y aceptación de confidencialidad. Los anotadores no comparten decisiones hasta terminar su primera pasada; el adjudicador recibe ambas hojas y deja resolución motivada. Si no se confirman las tres personas y sus roles, el cierre semántico queda bloqueado. Dennys podría adjudicar solo si acepta explícitamente ese rol; no se presume.

## 2. Estado de neurona según código y registros existentes

### Evidencia aportada por Dennys

El recálculo de la base viva pegado por Dennys reporta una neurona activa en esa corrida y presenta fórmula frente a neurona en la misma QA. Es evidencia de que **la copia medida en ese recálculo** conservó un campeón activo y fue usado. No prueba por sí sola el estado de una copia nueva o de otra fecha; el log pegado no aporta el hash de la copia ni los valores de versión/huella para verificarlos independientemente.

### Contrato que verifica el código

- `scripts/evaluar_qa.py` ejecuta la QA sobre una copia temporal. Lee el estado guardado desde la DB de la copia y, para actuar, requiere neurona activa y campeón.
- `scripts/qa_neurona.py::leer_guardada` lee `neurona_estado` en modo solo lectura. `vale_para_este_motor` exige coincidencia de versión de neurona y huella del comportamiento de la fórmula.
- `core/memory/neurona.py::_cargar` descarta pesos cuyo `version` o `huella` no coincide, y `resumen` declara si hay campeón. Por eso un reporte de neurona usada con resultados pareados es evidencia compatible con ese contrato en el momento de la corrida.
- Esa huella identifica compatibilidad con la fórmula/version del motor, **no el hash completo de la base ni por sí sola la procedencia de entrenamiento**. La procedencia debe comprobarse aparte con el hash de origen/copias y el manifiesto del recálculo.

**Conclusión acotada:** el registro de Dennys apoya que la copia viva de aquella QA tenía una neurona activa y utilizable entonces. No se verificó una copia actual o nueva; hacerlo exigiría abrir una copia aislada con autorización. El registro de la QA congelada, en cambio, dice que esa base no tenía campeón entrenado.

## 3. Comparación planificada, sin mezclar causas

Es una investigación diagnóstica secundaria basada en copias; no reemplaza E1 ni convierte las diferencias de bases en efecto de neurona.

| Base | Fórmula sola | Neurona | Estado previo según registros |
|---|---|---|---|
| Congelada | Condición disponible. | Sin campeón en el recálculo aportado. Para completar la celda habría que autorizar y entrenar una neurona **propia de una copia aislada congelada**, con procedimiento/configuración fijados; no copiar los pesos vivos. Si no se autoriza, informar la celda como no disponible. | La copia evaluada no tenía una neurona entrenada. |
| Viva | Condición disponible. | Usar solo si una copia aislada nueva conserva campeón y pasa versión+huella; además verificar que su estado procede de esa misma base mediante hashes/manifiesto. No entrenar ni reparar ahora. | El recálculo anterior la reportó activa, pero no se aportó artefacto actual con hashes para repetir la verificación. |

Para una futura corrida autorizada:

1. Congelar la misma lista de preguntas, orden, parámetros, código y variables para ambos modos dentro de cada base. La comparación principal es pareada **dentro de cada base**; entre bases se describen diferencias, no causalidad.
2. Hacer copias nuevas bajo un temporal externo autorizado; obtener hash de cada base fuente/copias y del estado `neurona_estado`. Nunca abrir ni escribir las bases originales. Si el gold/QA o el código cambian, crear manifiesto y presupuesto nuevos.
3. Verificar primero, en la copia viva, `campeon`, versión, huella compatible y procedencia/hash. Si falta el campeón o la huella no coincide, parar esa comparación; no entrenar automáticamente, no trasplantar pesos y no llamar a la diferencia “efecto de neurona”.
4. En cada base, comparar orden de fórmula y orden servido por neurona sobre las mismas preguntas y candidatos, como hace el espía de `scripts/qa_neurona.py`. Registrar R@1/R@5/MRR y diffs **por caso**, incluidos ascensos y descensos, no solo el promedio.
5. Registrar estado de los recuerdos objetivo y vecinos antes/después por caso; distinguir los que el arnés pone dormidos de los que ya venían dormidos. Conservar el restablecimiento de estado entre casos. No inferir causa a partir de dormancia sin registro por caso.
6. Si se observa una posible corrección, entregar casos, hashes, trazas y diff del cambio candidato para decisión de Dennys antes de tocar el motor. Ningún cambio se ejecuta por este plan.

La comparación propuesta en los registros usa la QA de 921 casos. Mantenerla como análisis de diagnóstico. E1 conserva su gold completo de 88 episodios/224 consultas y los brazos originales; los 2.768 llamados E1 siguen planificados y **sin autorización**. La comparación de bases/neurona tendrá presupuesto y aprobación propios si Dennys decide ejecutarla.

## 4. Dormancia: alcance de lo observado

El recálculo EXP-Q anterior no guardó estado inicial por objetivo. Por código, los objetivos encontrados mediante búsqueda activa/BFS activo estaban activos al ser devueltos; para el caso que no apareció en el grafo de la base viva, el estado sigue sin determinar. La QA global configura algunos objetivos como dormidos, busca en profundidad y restaura estados, pero los totales publicados no identifican los tres casos EXP-Q ni los dos descensos individuales de R@1. No se asigna una causa a esos resultados.

## 5. Próximo paso para E1

Antes de cualquier preparación operativa: Dennys debe decidir la rúbrica/criterios pendientes y designar de forma verificable a dos anotadores independientes y un adjudicador. Luego revisar y cerrar el gold —también con cierre no-op si no cambia— antes de observar resultados. La comparación de copias queda planificada aparte y requiere autorización explícita; no se ejecutó ni se incluyó en el presupuesto de E1.
