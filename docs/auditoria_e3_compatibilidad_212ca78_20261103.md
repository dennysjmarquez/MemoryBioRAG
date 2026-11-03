# Auditoría E3: corrección de compatibilidad `212ca78`

Se revisó `212ca78c5fbcc4915bd7e2080a4c9eb117b5550d`, hijo de `5994df8`: alinea en el runner interno tanto el valor de la etiqueta del guardia como el nombre de la métrica y su consumidor; añade documentación, sin cambios de `core/`. `git diff --check` para este commit y `py_compile` de los tres scripts pasaron.

## Réplica

Con `PYTHONHASHSEED=0`, se ejecutaron ambos runners del operador en checkouts y fixtures sintéticos aislados:

- Runner interno: **exit 0**, 24 llamadas MCP contando aperturas, 0 flags MCP; `far_query_exclusion_path_confirmed=true` y `target_excluded_by_final_single_word_prefix_guard=true`. Se corrigió la incompatibilidad reproducida en la auditoría de `5994df8`.
- Matriz de prefijos: **exit 0**, 28 llamadas MCP contando aperturas, 0 flags MCP, nueve comprobaciones pasadas, siete casos. QCR estaba desactivado por el arnés para aislar el caso multitémino.
- En los seis brazos del runner interno y siete casos de la matriz, la comparación adicional de los JSON parseados completos baseline/instrumentado coincidió 13/13. Sin cambios en snapshots de grafo observados en apertura o búsqueda; su alcance es limitado y no cubre toda la base. La equivalencia solo se ha medido en estas fixtures.

Los hashes de nuestros JSON son `1d46f3408429da4f859d0454c8e5059dd5776a58f47362f9923c16acc7654cf3` (interno) y `61ca2d220b5f4896b712dd79709f65db9f4e5a3526ff273927b7d41b1ebd364a` (matriz). Las evidencias privadas `run09` y `run10` del operador no se consultaron, por lo que no se afirma coincidencia byte a byte. La reproducción usa los mismos runners, no un segundo arnés. La suite completa no fue repetida, ni se abrieron bases originales.

Artefacto privado `auditoria_e3_212ca78_20261103.tar.gz`, Drive ID `1UtrysZoQJS3vbLrKmZsEt0dntPg-iagl`, SHA-256 `ec638a3aa4cdfe8150b7fe33d62101d5a8eb58435cc4f64a0ff0e8b893fe5acc`. E3 sigue abierto; la corrección de instrumentación no autoriza un cambio del motor ni E4.
