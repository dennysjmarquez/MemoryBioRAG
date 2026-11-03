# E3: barrido emparejado de paráfrasis MCP en fixture sintético

**Fecha:** 2026-11-03. Continuación acotada de la prueba de paráfrasis de E3. No reproduce consultas reales ni usa datos privados. No se cambia el motor, no se abren bases originales y no se avanza a E4.

## Diseño y resultado

El nuevo runner `scripts/diagnosticar_traza_parafrasis_sweep_e3.py` ejecuta cinco pares de consultas sintéticas por MCP stdio: cada par conserva el query y demás parámetros, y compara la llamada con paráfrasis contra el control sin paráfrasis. La semilla contiene un objetivo sintético y cuatro distractores. Un control FTS5 independiente consulta cada término de paráfrasis en la copia; es un control del índice, no una llamada de búsqueda MCP.

| Agregado (10 llamadas MCP, 5 pares) | Resultado |
|---|---:|
| Llamadas MCP / flags `isError` / excepciones Python capturadas | 10 / 0 / 0 |
| El control FTS5 directo encontró el objetivo por el término de paráfrasis | 5/5 brazos con paráfrasis |
| MCP encontró el objetivo con paráfrasis / sin paráfrasis | 4/5 / 4/5 |
| Pares con objetivo solo al incluir paráfrasis | 0 |
| Pares con objetivo en ambos brazos / en ninguno | 4 / 1 |
| `capa_parafrasis` en las ocho respuestas que sí contenían el objetivo | 0.0 |

Así, la matriz **no logró aislar una recuperación atribuible solo a la paráfrasis**. En cuatro pares MCP devolvió el objetivo tanto con paráfrasis como sin ella; en el quinto no lo devolvió en ninguno de los dos brazos, aunque el término sí encontró el objetivo en el control FTS5 directo. Esto demuestra que el control FTS5, por sí solo, no establece recuperación MCP. No demuestra que la paráfrasis no se haya usado en los casos con respuesta: otras rutas de recuperación pueden explicar los hits del control.

La traza cero tampoco demuestra por sí sola una atribución equivocada. En lectura estática, la primera consulta FTS compone query y paráfrasis como variantes y asigna origen `literal` a los candidatos de ese resultado combinado; una asignación posterior `parafrasis` aparece en otra rama de fallback. Esto deja una **posible limitación de atribución de la traza** para investigar, no una causa confirmada ni permiso para modificar el motor. Se conserva la distinción entre candidato encontrado por FTS, resultado efectivamente devuelto por MCP y etiqueta de origen de la traza.

## Evidencia y reproducción

Ejecución reproducible:

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python scripts/diagnosticar_traza_parafrasis_sweep_e3.py \
  --evidence-dir .private_evidence/e3_paraphrase_sweep_20261103_run01
```

La corrida privada preserva el manifiesto, parámetros sintéticos, respuestas MCP completas, controles FTS y snapshots antes/después bajo `.private_evidence/e3_paraphrase_sweep_20261103_run01/`. SHA-256: `stdio_cases_full.json` = `377c5f761ddd1f88a98702272d8c1142967858a55fa2d41990c80ffb74f1afe8`; `synthetic_manifest.json` = `cd1b93ce30357206aa67463f93d54be5c28c1c8a3d6db22575e2bc44766b7056` (suma de control local en el mismo directorio). El detalle por consulta y sus textos quedan privados.

`py_compile` del runner completó correctamente; la ejecución terminó con código 0. Los snapshots de esta prueba cubren las nueve tablas de grafo enumeradas por el harness y la proyección `largo_plazo(concepto, asociaciones)`: **no son copia completa de SQLite**.

## Estado

No se encontró en esta matriz el positivo diferencial requerido para declarar probada una ruta MCP atribuible a paráfrasis. E3 permanece abierto; no se acepta una conclusión de fallo general, no se descartan pistas y no se propone parche. Un siguiente intento debe instrumentar la atribución desde la llamada hasta el origen del candidato en una fixture que mantenga separados el hit de query, el hit de paráfrasis y los fallbacks, sin alterar el motor.
