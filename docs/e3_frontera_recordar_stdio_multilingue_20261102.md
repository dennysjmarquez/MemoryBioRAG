# E3: límite entre validación MCP y búsqueda ejecutada

**Fecha:** 2026-11-02 · **Diseño:** sintético, MCP stdio real, bases temporales aisladas. No se modificaron motor ni bases originales.

## Diseño y alcance

Se probaron nueve copias scratch independientes: seis consultas exactas a identificadores sintéticos (una por inglés, español, ruso, chino, japonés y coreano), una solicitud sin sustantivos clave, una con más del máximo permitido y una consulta válida deliberadamente ausente. Cada búsqueda se llamó por `recordar` en MCP stdio. Las dos entradas de validación y la búsqueda sin hit usaron una copia adicional aislada cada una. No hay consultas gold, datos reales ni decisión de política.

## Resultado agregado

- Las seis búsquedas exactas tuvieron respuesta con estructura de búsqueda y encontraron su nodo de fixture (**6/6**). Esto solo comprueba nombres sintéticos exactos, no morfología, traducción ni desempeño general por idioma. No es una repetición uno-a-uno de los 88 rechazos registrados en E3A: difieren fixtures/payloads y etapa de prueba, así que no reemplaza aquel resultado histórico.
- Las dos solicitudes inválidas fueron **rechazos de validación**, con los códigos `SUSTANTIVOS_CLAVE_REQUERIDOS` y `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA`. No devolvieron la estructura de resultados; en la ruta actual de `_recordar_impl`, esas validaciones retornan antes de invocar la búsqueda.
- La consulta válida ausente devolvió la estructura de búsqueda, con `total=0`: fue una **búsqueda ejecutada sin hit**, no un rechazo.
- Las siete respuestas de búsquedas ejecutadas omitieron el campo `status` crudo, sin flag MCP de error; la forma de respuesta `resultados`/`total` permite distinguirlas de los rechazos que sí devuelven `status=error`. Esa omisión no se cuenta como excepción.
- **0** excepciones Python, flags de error MCP, estados de herramienta `error` no clasificados como rechazo, respuestas `exception` o errores de consulta del snapshot.

No se inyectó una excepción interna de búsqueda; por ello el resultado no estima ese comportamiento. La medición tampoco prueba preguntas en lenguaje natural ni equivalencia semántica.

## Aclaración de los pilotos

Los pilotos privados anteriores se preservan. En el primero, dos claves latinas sintéticas superaban el máximo de caracteres y se rechazaron correctamente por formato; no eran búsquedas fallidas. En el segundo, los casos crudos mostraban dos rechazos, pero un contador agregado defectuoso decía cero. Se corrigió la clasificación y el agregado en el runner: `run03` verificó el conteo y `run04` es la corrida final que además preserva en privado los mensajes de validación. No se reescribieron ni eliminaron esos registros piloto o intermedios.

## Snapshot y trazabilidad

Cada snapshot contiene nueve tablas de grafo completas más la proyección `largo_plazo(concepto, asociaciones)`; no es una copia completa de SQLite. El detalle por caso, mensajes de rechazo y cadenas consultadas quedan privados en `.private_evidence/e3_frontera_recordar_stdio_multilingue_20261102_run04/`, con hashes. La versión agregada de esta aclaración no publica consultas, textos ni payloads.

El arnés es `scripts/diagnosticar_frontera_recordar_stdio_multilingue_e3.py`. E3 continúa abierto para morfología y otras rutas lingüísticas; no se modificó el motor, no se adjudicaron etiquetas y E4 sigue en espera.
