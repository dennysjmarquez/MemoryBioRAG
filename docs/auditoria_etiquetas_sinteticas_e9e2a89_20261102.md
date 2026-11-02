# Auditoría del sondeo de etiquetas E3 — `e9e2a89`

## Veredicto

**Reproducido el resultado de la sonda sintética de FTS**, no una comparación de políticas de producción. El commit `e9e2a893e683b758bf1f3d3ae256be4ebc620eef`, confirmado en la rama del operador, modifica el inventario y añade el runner; no modifica `core`. SHA-256 de `core/memory/search.py`: `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`; del runner: `d4488bec3c6ccdb6c121ee49ec3bef8eb5f7b22db44e1dd85b9a30aa33202a51`. Las rutas `core`, `middleware`, `config` y `biorag.py` coinciden con la referencia auditora `e6df5b6`.

Se ejecutó el script exacto sobre un árbol temporal extraído del commit, sin parche de motor y con HOME, estado DMN y bases aislados, neurona apagada y `PYTHONHASHSEED=0`; salida 0. El runner genera un esquema vacío y dos copias de un solo recuerdo sintético. No se usó DB real, no se fusionaron recuerdos ni se efectuó backfill.

## Resultados reproducidos

Para las 11 etiquetas históricas únicas de la fixture, una consulta directa al FTS de la columna de etiquetas encontró **3/11** en reemplazo y **11/11** en acumulación hipotética; ambas encontraron **3/3** de la última entrada. Bajo los dos supuestos expresamente hipotéticos, son ocho etiquetas históricas ausentes del índice en el primer caso y ocho adicionales en el segundo. No se concluye que esas ocho sean vigentes u obsoletas en un recuerdo real; que una pista sea antigua no la convierte automáticamente en ruido.

La primera de las cinco llamadas crea el recuerdo y las cuatro siguientes actualizan la misma fila; no se hicieron cinco actualizaciones posteriores a una creación previa. La rama reemplazo usa directamente la función interna de consolidación. La acumulación se simula en la copia mediante un `UPDATE` SQL después de esa función: **no es un diff implementado ni la ruta MCP de escritura**, y el ensayo no mide sus posibles estados intermedios o su seguridad de concurrencia.

## Límites relevantes

- Es una sola secuencia diseñada con etiquetas distintas y un único recuerdo por copia. Los porcentajes no son recall global ni prueban pérdida total de recuerdos: solo presencia de pistas mediante MATCH en la columna de etiquetas. Otras rutas, incluidos contenido y asociaciones, no se evaluaron. No se midieron ranking, vecinos, agente, MCP ni corpus real.
- La unión de 11 etiquetas sobrepasa el máximo de 10 aceptado en la herramienta MCP de escritura inspeccionada; la prueba salta esa validación mediante SQL en la copia. No demuestra que la acumulación funcione a través de esa herramienta ni que se deba eliminar su guardia.
- El campo llamado `fts_integrity` en el JSON contiene el resultado de `PRAGMA integrity_check`: verifica integridad SQLite general, no equivale a la prueba específica de integridad del índice FTS5. Los MATCH reales sí verificaron las 11 consultas de esta fixture.
- El inventario mantiene la expresión categórica «causas distintas» para los FP ingleses; según `docs/auditoria_fp_ingles_etiquetas_e4ce0b3_20261102.md`, describirlas como mecanismos compatibles con las trazas, sin afirmar causa exclusiva.

## Continuación

No elegir automáticamente una política, descartar pistas o borrar recuerdos. Continuar E3 con pruebas en copias sintéticas a través de las rutas de escritura y MCP pertinentes y recuperación agente+cerebro, incluyendo pistas, vecinos y secuencias donde el historial siga siendo útil o se contradiga. Mantener separados estado temporal y validez de los datos; cualquier candidato necesita baseline, diff aislado y autorización específica. E4 continúa en espera.

Log privado de reproducción: `auditoria_e3_etiquetas_e9e2a89.log`, SHA-256 `cf8ac2cf4ab2328e88f39504f22a831a91692817628fe55e8ac86f8643f822c9`, Drive `1mRpAI_bGMqka1jJD92kjqIrVcE_8XS3m`. No incluye SQLite ni datos vivos.
