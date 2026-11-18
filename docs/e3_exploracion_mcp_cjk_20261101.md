# E3: exploración MCP sintética con pistas de la pregunta

## Qué se quiso comprobar

Tras el diagnóstico de búsqueda directa, probar el transporte MCP real con consultas construidas a partir de pistas de preguntas chinas y japonesas y controles negativos. Esto **no es una evaluación ciega de un agente completo**: el guion aplica una estrategia predefinida, las etiquetas existían antes y se conocían casos y respuestas del gold. Las consultas no se eligen usando el esperado durante la ejecución, pero no hay independencia del diseñador. Tampoco es E1 ni QA oficial; presupuesto experimental terminado significa **trayectoria inconclusa**, no ausencia definitiva de recuerdos.

Se usó código `2f146e70a8a55c1dc304ffa7f8ff18693c6d217d`, Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6 y NLTK 3.9.4. No se cambió el motor ni se entrenó; sin base viva. El servidor MCP stdio real usa el lanzador `scripts/qa_stdio_server_intuicion.py`, con ruta de DB restringida al temporal. La fixture se creó **por la API del motor, no por MCP**: 120 recuerdos inventados del gold E3, sin sustantivos ni bridges introducidos por un agente y con solo una sinapsis en total. No representa una memoria bien poblada en todos sus canales.

Cada caso recibió una copia limpia de la fuente; las llamadas de su trayectoria comparten esa copia y sus posibles mutaciones. La fuente fue comprobada inalterada. Reloj fijo, `PYTHONHASHSEED=0`, neurona de ranking apagada, auto-paráfrasis y auto-dimensiones MCP apagadas, guardado heurístico y logging apagados. Se pidieron contenido completo, vecinos (`context_window=1`), asociaciones completas y hasta 120 resultados por página para una fixture de 120; ninguna respuesta indicó más de una página. No se forzó `deep` ni ráfaga; no se pretende haber agotado estrategias. No se comparan causalmente estos resultados con el motor directo: consulta, parámetros y recorrido difieren.

## Primera exploración

Se fijaron ocho casos positivos antes fallidos (`zh/ja-12`, `15`, `17`, `18`) y cuatro negativos (`zh/ja-n01`, `n02`). Las semillas provienen de `scripts/casos_qa_multilingue_sustantivos_e3a.jsonl` y se verificó que aparecen en la pregunta. Para cada caso: consulta con semillas juntas, consulta por cada semilla y búsqueda de las asociaciones expuestas por esos resultados. No se usa el gold para decidir cuál consulta ejecutar.

**43 llamadas:** 30 sin error y **13 rechazadas** con `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`. Las 13 corresponden a cuatro casos cuyas etiquetas incluían un término nativo de un solo carácter (`zh-18`, `ja-15`, `ja-17`, `ja-18`). En esos rechazos **no se ejecutó la búsqueda**, y no se cuentan como ausencia de recuerdo ni como abstención correcta. El mínimo de dos caracteres está vigente; no se cambió.

Los cuatro positivos restantes (`zh-12`, `zh-15`, `zh-17`, `ja-12`) devolvieron el esperado en la consulta de semillas juntas; las consultas de semillas individuales no lo devolvieron. Los cuatro negativos no devolvieron resultados en ninguna de sus llamadas válidas. Son solo cuatro controles negativos; no se infiere una tasa general de falsos positivos.

## Reintento tras observar los rechazos

Se escogieron de la propia pregunta cuatro conjuntos de frases de dos o más caracteres, conservando partículas y relaciones cuando aparecen; están en `scripts/casos_sustantivos_cjk_reintento_20261101.jsonl`. Esta selección ocurrió **después** de ver los errores y el gold ya era conocido: no es prueba independiente. Se reconstruyó la base; esta vez ambas fuentes reconstruidas tuvieron el mismo SHA SQLite, pero cada caso nuevamente usó su copia propia.

| Caso | Llamadas | Errores | Resultado en alguna llamada |
|---|---:|---:|---|
| `zh-18` | 3 | 0 | sin resultados |
| `ja-15` | 3 | 0 | esperado presente |
| `ja-17` | 3 | 0 | sin resultados |
| `ja-18` | 3 | 0 | esperado presente |

En los dos casos recuperados el esperado apareció en la consulta conjunta. No hubo resultados para seguir en los otros dos dentro de estas consultas; **la trayectoria queda inconclusa**, no se afirma que el recuerdo sea inalcanzable. En ninguna de las dos exploraciones se expuso una asociación a seguir desde los resultados, por lo que **no se puso a prueba el seguimiento de una pista sináptica**. El resultado no demuestra ni descarta esa capacidad en una memoria con enlaces apropiados.

## Auditoría y evidencia

Una primera versión del resumen marcaba como `esperado_visto=false` los casos en que todas las llamadas habían sido rechazadas. Se corrigió a `null`, se conservó aquella ejecución preliminar aparte y se repitieron ambas exploraciones con el script corregido. Las tablas anteriores usan únicamente la repetición corregida. El archivo preliminar privado es `mcp_cjk_primera_version_observacion_resumen.tar.gz`, SHA `bf28fd44c993469a1786b28e30f6d45bbf44a52d1b499613647c8fbe4dfde674`, Drive `1MfDAheU_nEm91juRdgpNvS2AAi8nXDFC`.

Scripts ejecutados:

- `scripts/explorar_mcp_cjk_sintetico.py`, SHA `20ecc378f5d0ca3c86fc9c2b156d66fba1b42f2ef1113d358bac17a5206585cf`.
- `scripts/reintentar_mcp_cjk_sintetico.py`, SHA `8956f60d7cda88d4ff1d610254ab836239d57ebe472c6a323a11b20962b6ecaa`.
- Etiquetas del reintento, SHA `372dc7a1d0749d06f3993fb30c25f3aa896804e79c5c97b60745fc12adfa39c8`. Gold E3, SHA `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`; etiquetas iniciales, SHA `ecadfca36f142e5f9cb00d86cce8c90bff29849c6d482c5034587d8f0a04b1dc`; fuentes de ambas corridas finales SHA `40cdc83e5c97c45a45c6ee9fc4ac166f88e5f365996c9747188045197cd80667`.

Respuestas completas sintéticas en carpeta local ignorada `google_drive/auditoria_neuronas/`, y copia privada Drive con checksum cotejado:

| Archivo | SHA-256 | Drive ID |
|---|---|---|
| `mcp_cjk_2f146e7_v2.jsonl` | `8a9bad24814a60f6d7ea4a24df1efbd37df2d772445b81f6cb4c4fd1531e8167` | `1bZV23NxkpYaVEjnCNsuMJwrbZa29volv` |
| `mcp_cjk_2f146e7_v2_resumen.json` | `aa69c7d96d208e1863cfc890c2dc9df0e46e21e1292d6d2bd3cb8b5c8a6c494d` | `1_Q13oYu58Sak2dZPrBj--v2IVLy2CMba` |
| `mcp_cjk_reintento_2f146e7_v2.jsonl` | `3cc64e4f531da3e9dc06f645d6ee07a50c55bbcfd40398965afdca085955beea` | `1ou2yKr2xexobylRxWHA9IM9tZRDLnXW8` |
| `mcp_cjk_reintento_2f146e7_v2_resumen.json` | `df86e72a2ffccf5ba3f1a62c3d1158078af94140a8fd2123d45ed091183ca66e` | `1C5uOeYLs4aSmDnppoGuGUej4wLQ9bxRC` |

Ambos scripts admiten `--evidencia` y `--resumen` con nombres nuevos; no sobrescriben salidas. Ejecutar desde la raíz con dependencias de `requirements.txt`, `PYTHONPATH=. PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_NO_LOG=1` y `BIORAG_PATH` ausente. Usar `NLTK_DATA` del repositorio y redirigir el log a la carpeta privada.

## Siguiente paso

Hace falta una fixture sintética creada por MCP con asociaciones y puentes plausibles y pocas semillas, para observar realmente una pista indirecta y su seguimiento; registrar consultas, motivos y fallos, sin tratar el presupuesto de prueba como agotamiento de memoria. E3 sigue abierto; no se ha propuesto ni aprobado aquí un cambio de motor, mínimo de caracteres ni OR global de trigramas.
