# E3 fase B1 — validación Unicode en `recordar`

## Estado: B1 CUMPLE LAS MEDICIONES

Las cuatro QA oficiales terminaron con la regla corregida y no muestran bajadas frente a E2e: coinciden R@5 y R@1 honestas en cada categoría, FP, MRR y fallos honestos R@5. La QA directa y las respuestas MCP de inglés y español coinciden con E3A; la suite completa aprueba **626 pruebas**. No se revirtió el candidato. B2, B3 y B4 no se han iniciado.

## Alcance

Dennys aprobó B1 y después corrigió expresamente el largo: **2–15 caracteres tras NFC, sin excepción para un único carácter ancho**. Se permite Unicode de categorías L, M y N, más `_`; el máximo de 10 términos únicos y la obligatoriedad existentes no cambian. La función pequeña `_sustantivo_valido` vive en `core/mcp_server/_shared.py`, y solo se usa en la validación de `_recordar_impl`. El alias `buscar` llama a la misma implementación y hereda la regla. `aprender` no se cambió.

[Diff exacto del candidato](e3b1_diff_candidato_20261027.patch). El HEAD base es `04d44ac`; los ensayos se hicieron con ese HEAD **más el diff de trabajo**, no con un commit B1 ya aceptado. No se tocaron `VERSION`, README, CHANGELOG ni el workflow. No se modificaron los casos de QA ni las etiquetas de sustantivos.

La nueva función usa NFC solo para medir y validar; no cambia la cadena que se entrega al motor. El normalizador compartido anterior actúa antes y sigue quitando algunas marcas. Por ejemplo, `ガラス` todavía se normaliza a `カラス` y ambos pueden deduplicarse. `हिंदी`, específicamente, **conserva sus marcas en esta sonda**; no todas las marcas se pierden. En cambio, `क़िला` se transforma en `किला`: la pérdida de identidad queda para B3, no se corrigió aquí.

El texto de ayuda/error de MCP todavía describe el formato anterior; se dejó intacto porque B1 autoriza solo la validación. Debe revisarse en una entrega autorizada aparte, sin confundir la descripción con la regla ejecutada.

## Pruebas y QA multilingüe

- [Pruebas focalizadas](e3b1_pruebas_focalizadas_20261027.log): **90 passed**. Cubren L/M/N, `_`, signos no permitidos, límites 1/2/15/16, NFC y que `aprender` mantenga su validación anterior. `水`, `本`, `문`, `a`, `я` y la cadena vacía se rechazan; `हिंदी`, `ガラス`, `чай` y `hola` pasan la función.
- [Pytest completo](e3b1_pytest_20261027.log): **626 passed in 310,38 s**, sin exportar `BIORAG_NEURONA=0` para no desactivar pruebas neuronales. Frente a las 563 de E3A, hay **63 pruebas nuevas**: 58 de validación/recordar/aprender, 1 de clasificación del hueco y 4 del comparador oficial. Cada variante parametrizada cuenta como prueba independiente: [listado completo](e3b1_desglose_pruebas_20261027.txt).
- QA directa: **132/132 casos idénticos** a E3A, con mismos resultados y scores. [Salida](e3b1_directa_20261027.log), [JSON](e3b1_directa_20261027.json).
- MCP brazo A: 118/132 llamadas llegaron a buscar; **14 rechazadas** se conservan como `pendiente hueco 1`, nunca como abstención correcta. No se alteraron las etiquetas. [Salida](e3b1_mcp_brazo_a_20261027.log), [JSON por consulta](e3b1_mcp_brazo_a_20261027.json).
- MCP inglés/español: **44/44 respuestas completas, resultados y scores idénticos** a E3A. La búsqueda MCP mantiene los dos FP ingleses de la referencia; sin umbral conforme en esta base aislada. [Comparación reproducible](e3b1_comparacion_multilingue_20261027.json), [salida](e3b1_comparacion_multilingue_20261027.log).

| Idioma | Positivos que llegaron a buscar | R@5 / R@1 sobre 20 | FP / negativos ejecutados | Pendiente hueco 1 |
|---|---:|---:|---:|---:|
| zh | 19/20 | 7/20 / 7/20 | 0/2 | 1 |
| ja | 11/20 | 6/20 / 6/20 | 0/2 | 9 |
| ko | 16/20 | 16/20 / 16/20 | 0/2 | 4 |
| ru | 20/20 | 20/20 / 19/20 | 0/2 | 0 |
| en | 20/20 | 20/20 / 20/20 | 2/2 | 0 |
| es | 20/20 | 20/20 / 20/20 | 0/2 | 0 |

### De rechazada a búsqueda: solo los cuatro idiomas afectados

Cada idioma tiene 20 preguntas positivas y 2 negativas. En E3A las **22/22** eran rechazadas antes de buscar. Esta tabla cuenta las que ahora llegan al motor y calcula R@5 y R@1 **solo sobre los positivos que sí buscaron**; las 14 pendientes no se cuentan como fallos del motor. La tabla anterior, en cambio, conserva el denominador de 20 para describir el extremo a extremo.

| Idioma | Buscó: E3A → B1, de 22 | R@5 entre positivos buscados | R@1 entre positivos buscados | FP / negativos buscados | Pendiente hueco 1 |
|---|---:|---:|---:|---:|---:|
| zh | 0 → 21 | 7/19 | 7/19 | 0/2 | 1 |
| ja | 0 → 13 | 6/11 | 6/11 | 0/2 | 9 |
| ko | 0 → 18 | 16/16 | 16/16 | 0/2 | 4 |
| ru | 0 → 22 | 20/20 | 19/20 | 0/2 | 0 |

Los 14 IDs son `zh-18`, `ja-05`, `ja-06`, `ja-08`, `ja-10`, `ja-11`, `ja-14`, `ja-15`, `ja-17`, `ja-18`, `ko-05`, `ko-07`, `ko-18` y `ko-20`. El caso `ja-18` incluye dos sustantivos de un carácter, pero es **una** consulta rechazada. El conteo se expresa por consulta.

[Verificación de la corrección](e3b1_verificacion_correccion_20261027.txt): los ensayos oficiales con la excepción anterior se interrumpieron sin resultado; sus logs parciales fueron reemplazados. También se repitieron y reemplazaron los resultados directos y las pruebas focalizadas. El MCP guardado contiene los 14 rechazos de la regla corregida. No se entregan resultados del ensayo anterior.

La comparación entre MCP y la QA directa **no** es una pareja equivalente de motor: MCP utiliza límite interno 15 y peso sináptico predeterminado; la directa usa límite 5 e `ignore_peso_sinaptico=True`. La comparación en/es sí es entre los mismos brazos MCP de E3A y B1. Ambas QA multilingües repitieron los 132 casos en orden inverso sin diferencias sobre cada misma base.

## QA oficial y criterio

Las cuatro referencias anteriores son los resultados E2e verificados, no se presentan como mediciones B1. Las nuevas corridas miden el candidato sobre snapshot y copia viva, con y sin `zzqx`: `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, con censo temático solo en las dos con ruido. Cada corrida copia la base en un temporal; fuentes sin WAL y abiertas con `mode=ro&immutable=1`. El gold oficial y el arnés no se cambiaron. [Parámetros y huellas al inicio](e3b1_inicio_qa_oficial_20261027.txt); [comprobación final](e3b1_integridad_final_20261027.txt) y [huellas SHA-256](e3b1_sha256_20261027.txt).

| Condición | Snapshot referencia R@5 / R@1 / FP | Snapshot B1 | Viva copiada referencia R@5 / R@1 / FP | Viva B1 |
|---|---|---|---|---|
| Normal | 100,00 % / 95,31 % / 0 de 40 | 100,00 % / 95,31 % / 0 de 40 | 99,88 % / 93,53 % / 0 de 40 | 99,88 % / 93,53 % / 0 de 40 |
| Con `zzqx` | 97,34 % / 88,63 % / 0 de 40 | 97,34 % / 88,63 % / 0 de 40 | 96,63 % / 88,12 % / 0 de 40 | 96,63 % / 88,12 % / 0 de 40 |

La [comparación completa](e3b1_comparacion_oficial_20261027.json) dio **CUMPLE**: ninguna bajada ni cambio de denominador; ningún fallo honesto R@5 nuevo o recuperado. Ver [salida literal](e3b1_comparacion_oficial_20261027.log) y [tablas completas por categoría, snapshot y viva lado a lado](e3b1_categorias_oficial_20261027.md). Los censos de las dos corridas con ruido coinciden íntegramente con los de E2e.

| Corrida B1 | Métricas | Salida | Fallos |
|---|---|---|---|
| Snapshot normal | [JSON](e3b1_snapshot_normal_20261027.json) | [log](e3b1_snapshot_normal_20261027.log) | [JSONL](e3b1_snapshot_normal_fallos_20261027.jsonl) |
| Viva normal | [JSON](e3b1_viva_normal_20261027.json) | [log](e3b1_viva_normal_20261027.log) | [JSONL](e3b1_viva_normal_fallos_20261027.jsonl) |
| Snapshot con ruido | [JSON](e3b1_snapshot_ruido_20261027.json) | [log](e3b1_snapshot_ruido_20261027.log) | [JSONL](e3b1_snapshot_ruido_fallos_20261027.jsonl) |
| Viva con ruido | [JSON](e3b1_viva_ruido_20261027.json) | [log](e3b1_viva_ruido_20261027.log) | [JSONL](e3b1_viva_ruido_fallos_20261027.jsonl) |

El comparador [scripts/comparar_qa_oficial_b1.py](../scripts/comparar_qa_oficial_b1.py) verifica clasificación, denominadores, R@1, R@5, MRR y FP; pytest completo y QA multilingüe se comprueban aparte. Ambas corridas con ruido salieron con código 1 por el **gate clásico de umbral fijo**, que también falla en las dos referencias E2e con ruido. Esa alerta no se ocultó ni se desactivó: el criterio acordado es la comparación emparejada honesta, que cumple.

### Reproducir multilingüe

```bash
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_e3a.py --verificar-orden --salida /tmp/e3b1-directa.json
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_mcp_b1.py --verificar-orden --salida /tmp/e3b1-mcp-a.json
```

El comando `python scripts/comparar_qa_multilingue_b1.py --salida /tmp/e3b1-comparacion.json` verifica **los resultados archivados en `docs`**, no consume los dos archivos recién generados en `/tmp`. Esto preserva la evidencia original; para comparar una repetición hay que cotejar explícitamente sus casos con los archivados.

B2, B3 y B4 no se han aplicado. La abstención sin umbral queda para E4.
