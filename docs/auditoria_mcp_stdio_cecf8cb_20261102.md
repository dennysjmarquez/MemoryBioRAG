# Auditoría MCP stdio de apertura y orden — `cecf8cb`

## Veredicto

**Reproducidos los resultados principales de las 16 sesiones sintéticas por transporte MCP stdio.** La apertura añadió una arista automática en estas copias; las asociaciones manuales y los resultados por orden se conservaron en los controles descritos. Esto no decide la política de etiquetas ni cierra E3, no mide un agente autónomo y no autoriza cambiar el motor o avanzar a E4.

El commit `cecf8cb1849cc6d657cb8a33f2db02a5cbc351c6` es la cabeza del operador cotejada. Frente a `caf2dfd` solo modifica el inventario y añade el arnés. Las rutas `core`, `middleware`, `config`, `biorag.py` y launcher MCP inspeccionadas coinciden con la rama auditora `890d837`. SHA-256 del arnés: `90f74f6c5b6b13f82ecc2b6e785e503e3fb164d1b0ef493bc1fccfcceacef1b7`; `core/memory/search.py`: `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`.

## Reproducción

Se ejecutó el script exacto desde árbol temporal, con entorno aislado, `PYTHONHASHSEED=0`, neurona apagada, recursos NLTK locales y bases inventadas. El runner usa cliente MCP, handshake y servidor FastMCP por stdio con el launcher `qa_stdio_server_intuicion.py`, que restringe las bases a su raíz temporal y no inicia el daemon global. La semilla desactiva síntesis DMN y el hijo la activa expresamente; esto es parte del diseño, no una medición de todas las configuraciones de producción. No se usaron datos reales, no se fusionaron recuerdos ni se aplicaron parches.

En las 16 sesiones:

- El grafo registrado no cambió durante `initialize`. Tras el primer `sustantivos`, se observó una fila adicional `dmn_synthesized`; las cuatro filas de las dos asociaciones manuales siguieron presentes. Que el grafo no cambiara durante `initialize` **no demuestra por sí solo que no se abriera una base**.
- Las escrituras y consultas no cambiaron el grafo en los campos capturados por el runner; las rutas de escritura y lecturas reportaron éxito. Repetimos las 16 sesiones con un observador que captura **todas las columnas y rowid** de `sinapsis`, sin redondear: 16/16 sin cambios durante escritura y consultas y 16/16 con filas manuales iniciales intactas.
- La pista histórica útil no recuperó el objetivo como primario con reemplazo; la lista acumulada suministrada explícitamente por MCP sí lo recuperó en rango 1. En el caso contradicho se recuperó con ambas listas. Las pistas nuevas recuperaron el objetivo en rango 1. Al recuperarse el objetivo, los dos vecinos manuales figuraron en asociaciones y el contexto incluyó además el vecino de la arista automática.
- Para cada una de las ocho combinaciones escenario/política/ruta, invertir los dos términos preservó resultados por rol, rangos, scores y vecinos capturados. Esto cubre solo estas copias, orden y consultas, no establece invariancia general.
- El runner no conserva el estado completo de `recordar` ni si un objetivo no primario apareció en contexto. Una tercera repetición auditora de 16 sesiones observó las respuestas completas: **32/32 llamadas sin error MCP**, cuatro sin objetivo primario y ninguna de esas cuatro con objetivo en contexto. No se confundió el resultado vacío de estas cuatro llamadas con un fallo de herramienta.

## Alcance y causalidad

La comparación de cargas muestra una diferencia emparejada para la fixture, pero no aísla cada término ni instrumenta la ruta exacta de generación y puntuación. El caso contradicho contiene la pista histórica y es **compatible** con una recuperación por contenido; no se hizo una ablación que demuestre que esa coincidencia fuera su causa exclusiva. Igualmente, ver la nueva arista al abrir y el vecino en contexto no demuestra por sí solo la causa exclusiva del ranking o la contribución de cada enlace. No se clasifican automáticamente las pistas antiguas como ruido.

La lista acumulada fue proporcionada expresamente a la ruta MCP: no hay acumulación automática implementada. `asociados=True` y `context_window=1` son parte de este experimento controlado; no se ha evaluado un agente independiente ni una base real. El informe del operador sigue empleando «causas distintas» para los FP ingleses: ver `docs/auditoria_fp_ingles_etiquetas_e4ce0b3_20261102.md`; son mecanismos compatibles, no causalidad exclusiva demostrada.

## Continuación

Las observaciones de apertura y orden quedan verificadas para esta fixture. Mantener E3 abierto y retomar el inventario con hipótesis y baseline; preservar pistas y no escoger reemplazo o acumulación por estos ejemplos. Cualquier posible cambio requiere diff aislado, evaluación suficiente y autorización específica. No avanzar a E4 ni entrenar por este resultado.

Evidencia privada `auditoria_e3_stdio_cecf8cb.tar.gz`, SHA-256 `f2572546452e8f3bf8ef72ca39ab6e0b335729a4b6773d5631654f4801aa930e`, Drive `1sPgtPvghRGRfd5lsMYxehO9c6OZimL5t`. Contiene las tres ejecuciones y los observadores, sin bases SQLite ni datos vivos.
