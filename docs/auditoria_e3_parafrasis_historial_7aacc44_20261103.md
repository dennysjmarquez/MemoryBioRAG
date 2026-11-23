# Auditoría E3: paráfrasis e historiales `7aacc44`

## Dictamen y alcance

Se revisó `7aacc449d754288a62cdce1605a4e67b6c32f762`, hijo de `c70b96a`. El diff añade dos informes, un runner, instrumentación del arnés de apertura y una entrada de inventario; no modifica `core/`. `git diff --check` y la compilación de los tres runners pasaron. Se reproducen los agregados indicados abajo en fixtures aislados. La investigación de paráfrasis continúa **inconclusa**; no se selecciona política de etiquetas ni se autoriza cambio de motor o E4.

## Barrido de paráfrasis

Diez sesiones MCP stdio en cinco pares, sobre copias sintéticas: FTS5 directo encontró el objetivo mediante el término de paráfrasis en 5/5 brazos con paráfrasis; MCP devolvió el objetivo en 4/5 con y 4/5 sin ella; cuatro pares recuperaron en ambos brazos y uno en ninguno. No hubo positivo exclusivo de paráfrasis y la traza observada en las respuestas con objetivo fue cero. No prueba uso, inutilidad o atribución errónea de la paráfrasis en general; FTS independiente no es el recorrido completo MCP. Las diez respuestas tuvieron estructura de búsqueda, sin `status` crudo; 10 aperturas correctas, 0 flags de error MCP, 0 excepciones escapadas, 0 errores de sonda FTS y 0 errores de snapshots. No se inyectaron fallos internos.

La huella del manifiesto sintético coincide con la publicada por el operador. El archivo completo de la réplica tiene una huella distinta a la declarada por él; no se dispone de su artefacto privado para comparar detalle o explicar la diferencia. No se afirma identidad completa de las trazas ni se rechaza la ejecución por esa diferencia.

## Apertura, orden y rutas directas

La ejecución independiente del mismo runner registró 16 sesiones stdio y 80 llamadas: 0 flags MCP, 16 escrituras `ok`, 32 respuestas de `recordar` sin `status` crudo, 28/32 consultas con objetivo. `initialize` no alteró las filas observadas, la primera herramienta coincidió con una fila `dmn_synthesized` adicional en 16/16 y preservó las filas manuales iniciales; no se detectaron altas o bajas en las etapas de escritura y búsqueda. Los ocho pares de órdenes mantuvieron la misma presencia y rango para ambas consultas. La atribución causal interna de la fila automática no se probó.

En el runner de rutas directas, distinto del transporte stdio, 8/8 escrituras y lecturas de etiquetas fueron `ok` y 22/24 consultas encontraron el objetivo. Sus resultados no se suman a las sesiones stdio. Ambas salidas reproducidas coinciden por SHA-256 con los archivos declarados por el operador (`c6d98611c15942f03acb47d457c27e86bd0dc90a3caf0498d8ac7bf97b023932` y `808e4af6572016ef298cb73456a954be32de134d1677cfb597de5645e0c461c7`).

## Evidencia y límites

La evidencia sintética de esta réplica se preserva en Drive privado como `auditoria_e3_7aacc44_20261103.tar.gz`, ID `1AQWHQDE_sMianiYorfvtPXNvZgTBc2ky`, SHA-256 `dae5dccb84ecead182b93f007530a8f6a8c454bed172d2934a651f2fb64fc0f2`. También se conserva en `google_drive/auditoria_neuronas/`. No contiene bases originales ni recuerdos reales.

Son ejecuciones de los runners del operador, no un segundo arnés independiente; no se volvió a ejecutar aquí la suite completa de 824 pruebas reportada. Los snapshots de orden cubren únicamente filas de sinapsis; los de paráfrasis, nueve tablas de grafo y una proyección, no la base completa. No se valida generalización a lenguajes o corpus reales. Instrumentar candidatos y fallbacks en copias sintéticas, sin alterar el motor ni suprimir pistas, es un siguiente paso de investigación, no un permiso para escoger política o cambiar producción.
