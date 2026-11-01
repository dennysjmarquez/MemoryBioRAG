# Resumen sanitizado de cobertura de lectura preliminar E1 — 2026-11-01

## Alcance y estado

Se prepararon lecturas preliminares de agente para los **28 desacuerdos**, en seis tandas: cinco elementos por tanda para las posiciones 1–25 y tres para las posiciones 26–28. Cada tanda tiene un registro privado de lectura inicial del texto presentado y otro de cotejo posterior con el original. No se incluyen aquí preguntas, textos, códigos de elemento, respuestas ni categorías individuales.

Las valoraciones son **preliminares**, no revisiones humanas independientes, decisiones de adjudicación ni gold. La cola sigue con 28 elementos pendientes. Las opiniones originales de ChatGPT y Gemini permanecen separadas en la cola y no se fusionaron.

## Cobertura e integridad de los registros privados

Los SHA-256 se verificaron de nuevo localmente. Los registros permanecen en almacenamiento privado local, no versionado, con permisos `0600` para los archivos y `0700` para el directorio. Se proporcionan nombres y hashes para auditoría; no se publica su contenido.

| Tanda / posiciones | N | Registro de lectura inicial (SHA-256) | Registro de cotejo posterior (SHA-256) |
|---|---:|---|---|
| 1–5 | 5 | `lectura_preliminar_cinco_sin_original_v1.jsonl` — `14622bf9108f1e9c6e95a678107fd786a485f55833832466c42282ae33a04a21` | `cotejo_originales_cinco_v1.jsonl` — `539ccba3297f86a127f42bdace2b263f6d2ab79b90b798b77c732f69af822b2d` |
| 6–10 | 5 | `lectura_preliminar_siguientes_cinco_sin_original_v1.jsonl` — `330606109f83e809ad8f6520141e3eb5a7c227373fe396425581ec9b268d5050` | `cotejo_originales_siguientes_cinco_v1.jsonl` — `7184850ba1a21bee76be99e2067b4b129ec7cacc56849e6648fc6da4f7144960` |
| 11–15 | 5 | `lectura_preliminar_casos_11_15_sin_original_v1.jsonl` — `016d547e44ddc89f0ebb40fef5c18cb60a83c08a0daad28040ad4068a6d78125` | `cotejo_originales_casos_11_15_v1.jsonl` — `086c9a3d40518bed62148ed43f3ff06375b81943e51760281c411895f5818e06` |
| 16–20 | 5 | `lectura_preliminar_casos_16_20_sin_original_v1.jsonl` — `c12665f3d3e08abadbc8b0ced2b923efd77266e8d9880d7c53f773332824d3fe` | `cotejo_originales_casos_16_20_v1.jsonl` — `52f9717eaaae79bb716c84aaa3eaa479d72c164f233fc8ca2972e7f691f89643` |
| 21–25 | 5 | `lectura_preliminar_casos_21_25_sin_original_v1.jsonl` — `b9455105edba6b0c483e37dabe900ec5a64da8a311cb688b8aa55c151b3d89f6` | `cotejo_originales_casos_21_25_v1.jsonl` — `269427454a5a6ebd0adc3c73d8d0329093479f7b6e6309722c0a6bc23d4dbc64` |
| 26–28 | 3 | `lectura_preliminar_casos_26_28_sin_original_v1.jsonl` — `6a15e7a59fa4701c370a945fc0d258fd82a3d3f3cb1b79ade8907770d3a9ce63` | `cotejo_originales_casos_26_28_v1.jsonl` — `8834ea29841c893b66c3c0aaac266ec51ae2fad3a1b480bfc13090d9aeefffdc` |

**Limitación temporal:** los hashes comprueban la integridad de cada archivo, pero no prueban de forma independiente que la lectura inicial ocurriera antes de consultar el original. El orden descrito corresponde al procedimiento reportado, no a una secuencia temporal certificada externamente.

## Dudas y criterios que siguen abiertos

- **Respuesta directa frente a pista indirecta:** una relación pertinente puede seguir siendo una pista útil aunque no conteste por completo; no se descarta automáticamente por ser indirecta. Sigue pendiente distinguir entre asociación temática, señal concreta y respuesta suficiente.
- **Conocimiento externo:** en la consulta sobre espaciar reintentos, Dennys aportó provisionalmente que mencionar timeout/reintento sin describir espera puede ser una pista, no una respuesta directa. También señaló que `backoff` podría ser respuesta directa para quien conoce la técnica, aunque el texto no indique tiempos ni configuración. El auditor explicó `backoff` a Dennys antes de recibir su valoración, por lo que pudo influir. Es un ejemplo de criterio, no una decisión masiva ni una etiqueta gold.
- **Preguntas vagas o con un indicador no especificado:** algunas preguntas no definen qué señal, umbral o condición concreta esperan. Se conserva la duda sobre si el contexto operativo basta como pista o si la falta de ese indicador lo deja neutral o insuficiente.
- **Encabezados y transformaciones:** títulos o marcadores retirados pueden sugerir roles y sesgar la lectura. Son indicios de encuadre, no verdad automática ni criterio para asignar gold. En ciertos textos la transformación solo quita el encabezado; en otros elimina un matiz de prioridad. La evaluación del efecto semántico debe permanecer explícita y caso por caso.

## Límites y trabajo pendiente

El cotejo preliminar separado abarca los originales asociados a los 28 desacuerdos; **no equivale a completar la revisión/adjudicación de los 156 elementos**. La evaluación sistemática de los 156 textos originales y presentados sigue pendiente, incluidos los elementos sin desacuerdo y la evaluación humana del impacto de las transformaciones. No se cambió ni aprobó etiqueta gold.

**E1 permanece abierto.** Este resumen no autoriza ni ejecuta la campaña, no modifica el manifiesto reproducible, gold, motor o bases, y no entrena neuronas.
