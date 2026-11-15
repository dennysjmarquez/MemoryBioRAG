# E3, fase A — idioma: investigación y línea base

**27 de octubre de 2026.** Solo investigación y medición: **no se ha modificado el motor**, ni el peso temático, ni la QA oficial. No se propone activar modelos embebidos. Toda posible fase B requiere el OK de Dennys antes de cambiar nada.

## 1. Resumen

1. La QA nueva tiene **120 recuerdos**, 20 por idioma, y 12 controles negativos. En esta muestra, R@5 es chino **7/20**, japonés **7/20**, coreano **19/20**, ruso **20/20**, inglés **20/20** y español **20/20**. Los 2 controles negativos ingleses devolvieron resultados no pertinentes; los otros 10 no devolvieron ninguno.
2. `ガラス` y `カラス` se vuelven idénticos en varias rutas. En la base de 120 ambos salen primero para su propia consulta; en una base pequeña de 4 recuerdos, ambos se invierten y quedan segundos. No sería correcto afirmar que siempre se equivocan ni que toda la búsqueda pierde la marca.
3. En las dos sondas de fragmentos sin espacios, el índice encuentra el recuerdo chino o japonés, pero el filtro final de prefijo lo descarta. Es una causa comprobada para esas sondas, no una explicación demostrada para todos los fallos del examen.
4. La QA original buscó directamente en el motor. La ampliación posterior llama a la implementación de `recordar` MCP con sustantivos por idioma: en chino, japonés, coreano y ruso se rechazaron **88/88 consultas** antes de abrir la base. Inglés y español sí buscaron; detalle y limitaciones en 3B.
5. Las cuatro QA oficiales son las **referencias de E2e reutilizadas**, no ejecuciones nuevas. Se verificaron motor, arnés, examen, bases y versiones principales; los resultados están en la sección 4. La copia de respaldo fue reconstruida y su huella coincide exactamente con E2e.
6. Python ≥3.11 está en el commit separado `c78c432`, solo en `pyproject.toml` e `install.py`. Dennys actualizó la matriz por la web en el commit independiente `956cd58`; el CI sobre ese commit pasó en 3.11 y 3.12.

## 2. QA multilingüe: cómo se hizo

- Gold: [`scripts/casos_qa_multilingue_e3a.jsonl`](../scripts/casos_qa_multilingue_e3a.jsonl), 20 recuerdos y 2 controles negativos por idioma. Los recuerdos y preguntas fueron redactados para esta prueba; no son una muestra representativa del uso real ni han tenido validación independiente por hablantes de cada idioma. Los hechos son deliberadamente parecidos entre idiomas, pero se mide la recuperación de **la etiqueta concreta indicada en el gold**, no la equivalencia semántica entre traducciones. No mide traducción entre idiomas.
- Se crea una base **nueva y temporal**, con la API `core.memory_service.aprender`, sin pasar por MCP ni añadir puentes o sustantivos clave. Se verificó que están exactamente los 120 textos esperados y que SQLite da `integrity_check = ok`. No se reutiliza la base de Dennys ni el snapshot para esta prueba.
- Una copia limpia de esa base para **cada consulta**. `profundidad="activos"`, `limite=5`, `ignore_peso_sinaptico=True`; `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`. El reloj de Python se fija en el mismo instante al guardar y buscar para que el tiempo de ejecución no dé ventajas por recencia; no se modifican pesos. No se ejecuta un ciclo completo de sueño/PPMI. El control es sobre la neurona de ranking especificada; no se declara apagada toda posible función neuronal del proyecto.
- Cada resultado positivo tiene un esperado; R@1/R@5 indican si aparece primero o dentro de los cinco, respectivamente. MRR@5 trata como cero al esperado fuera de esos cinco. En los negativos, **cualquier resultado** es un falso positivo de esta prueba; son solo dos por idioma, insuficientes para estimar una tasa general.
- Se repitieron las 132 consultas en orden inverso **sobre la misma base fuente**: **0 diferencias**, incluyendo listas y puntuaciones. Otra ejecución independiente reconstruyó la base y volvió a producir las mismas 132 salidas. Las huellas de los dos archivos SQLite recreados no coinciden; no se ha atribuido la diferencia a una causa. La comparación de orden dentro de la misma base no depende de que esos archivos recreados sean idénticos.

Reproducir con el entorno del proyecto:

```bash
python -m pip install -r requirements.txt
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_e3a.py \
  --verificar-orden --salida /tmp/e3a_resultados.json
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/diagnostico_lexico_e3a.py \
  --salida /tmp/e3a_diagnostico.json
```

La base y sus copias se eliminan al terminar; no se crean ni modifican las bases reales. [Salida completa](e3a_multilingue_20261027.log), [resultados por caso](e3a_multilingue_resultados_20261027.json), [repetición independiente](e3a_multilingue_inversa_20261027.json), [comprobación](e3a_reproducibilidad_20261027.txt), [diagnóstico](e3a_diagnostico_20261027.json) y [manifiesto SHA-256](e3a_sha256_20261027.txt).

## 3. Resultados de esta muestra

| Idioma | R@5 | R@1 | MRR@5 | FP negativos |
|---|---:|---:|---:|---:|
| Chino `zh` | 7/20 = 35 % | 7/20 = 35 % | 0,3500 | 0/2 |
| Japonés `ja` | 7/20 = 35 % | 7/20 = 35 % | 0,3500 | 0/2 |
| Coreano `ko` | 19/20 = 95 % | 18/20 = 90 % | 0,9250 | 0/2 |
| Ruso `ru` | 20/20 = 100 % | 19/20 = 95 % | 0,9750 | 0/2 |
| Inglés `en` | 20/20 = 100 % | 20/20 = 100 % | 1,0000 | 2/2 |
| Español `es` | 20/20 = 100 % | 20/20 = 100 % | 1,0000 | 0/2 |
| **Total** | **93/120 = 77,50 %** | **91/120 = 75,83 %** | **0,7667** | **2/12** |

- En chino y japonés pasaron las siete consultas de nombre exacto y fallaron las 13 restantes de cada idioma; los 26 fallos no devolvieron resultados. En coreano falló `ko-18`, también sin resultados. Hay 27 positivos sin resultado en total.
- Los controles ingleses `en-n01` y `en-n02` devolvieron `model airplane`, que no responde a ninguna de esas dos preguntas. Es un falso positivo bajo la regla indicada; no son los 40 negativos oficiales.
- Sin embargo, estas diferencias **no prueban** que ruso o coreano estén resueltos en general: son 20 casos breves por idioma y faltan más escrituras, morfologías, tamaños de base y revisión humana del gold.

### Los 7 aciertos en chino y los 7 en japonés

| Chino: caso y consulta | Japonés: caso y consulta |
|---|---|
| `zh-01` 海岸灯塔 | `ja-01` 海辺の灯台 |
| `zh-02` 蓝色望远镜 | `ja-02` 赤い望遠鏡 |
| `zh-03` 银色指南针 | `ja-03` 真鍮の方位磁針 |
| `zh-04` 桃木书架 | `ja-04` 木の本棚 |
| `zh-05` 红色风筝 | `ja-05` 青い凧 |
| `zh-19` 竹笛 | `ja-19` ガラス |
| `zh-20` 陶鼓 | `ja-20` カラス |

En los 14, **la consulta completa es exactamente el nombre del recuerdo esperado**; ninguno demuestra comprensión de una pregunta distinta ni traducción entre idiomas. La traza final registra origen simbólico en doce y `unicode` en `zh-19`/`zh-20`. En los dos últimos japoneses aparecieron **ambos** nombres, pero el correcto quedó primero en esta base. La sonda reprodujo los 14 rankings y scores originales: [trazas](e3a_aciertos_fp_20261027.json).

### Los dos falsos positivos ingleses: consulta y causa

| Caso: consulta | Motor directo: devuelto / score | Qué coincidió |
|---|---|---|
| `en-n01`: “Where does the platypus in boots play chess?” | `model airplane` / **0,1723** | La palabra `play` de la consulta aparece dentro de `dis[play]ed`, sin ser una palabra independiente. |
| `en-n02`: “Which saxophone is buried in a desert glacier?” | `model airplane` / **0,2039** | WordNet expande `buried` a `lay to rest`; se separa esa frase y `lay` coincide dentro de `disp[lay]ed`. |

El contenido del recuerdo falso es “The model airplane is displayed inside the wooden cabinet.” Las palabras inglesas de relleno se retiraron: en `en-n01`, `where/does/the/in`; en `en-n02`, `which/is/in/a`. No hay evidencia de que esas stopwords, ni el stemmer, sean la causa de estas dos entradas. El FTS trigram encuentra esos fragmentos; en la ruta FTS se construye `PALABRA_COMPLETA` pero no se aplica (`sql_con_pc = sql`), y al ser consultas de varias palabras tampoco se aplica el filtro final de prefijo de palabra única (`core/memory/search.py:379-382,481-497,2063-2075`). El motor directo no aplica umbral de abstención.

En copias aisladas, **apagar WordNet solo como diagnóstico** deja `en-n01` igual (0,1723), pero elimina el resultado de `en-n02`. Esto apoya el papel de la expansión en el segundo caso; **no propone apagar WordNet** ni demuestra que el stemmer no influya en otros casos. Se reprodujeron los rankings y scores originales en **16/16** sondas antes de hacer esa comparación: [resultado completo](e3a_aciertos_fp_20261027.json), [salida](e3a_aciertos_fp_20261027.log) y [script](../scripts/diagnostico_aciertos_fp_e3a.py).

### El par japonés

| Consulta | Base de 120: esperado / otro | Base de 4: esperado / otro |
|---|---|---|
| `ガラス` | 1.º / 2.º (0,8609 / 0,8549) | 2.º / 1.º (0,6737 / 0,8549) |
| `カラス` | 1.º / 2.º (0,8616 / 0,8542) | 2.º / 1.º (0,6763 / 0,8542) |

La mini-base contiene además `海岸灯塔` y `faro costero`; es una sonda independiente, no un resultado de la base de 120. `fallback_simbolico._normalizar` y `stemmer_es.stem` convierten ambos nombres a `カラス`. En `core/memory/search.py:1693-1695`, esa igualdad de tokens puede marcar **los dos** como coincidencia exacta; el bono correspondiente está en `core/memory/scoring.py:366-373`. La colisión está demostrada; no se afirma que sea la única causa de la inversión. [Sonda reproducible](e3a_diagnostico_20261027.json).

### Un fragmento que el índice encuentra y el filtro elimina

| Gold | Fragmento en contenido | FTS bruto | `PALABRA_PREFIJO` | Salida final |
|---|---|---|---|---|
| `zh-07` | `黑麦面粉` | encuentra `烘焙面包` | falso | vacía |
| `ja-07` | `全粒粉` | encuentra `手作りのパン` | falso | vacía |
| `es-07` | `semillas de girasol` | encuentra `pan de centeno` | verdadero | lo devuelve |

En las dos sondas asiáticas, el candidato también está en el pool previo con origen literal. El filtro de `core/memory/search.py:2063-2093` usa `PALABRA_PREFIJO`, definido con `\b` en `core/memory_store.py:113-120`. Entre caracteres chinos o japoneses adyacentes Python no ve ese límite. El filtro protege contra falsos positivos de substring en otras lenguas: **no se propone quitarlo indiscriminadamente**.

## 3B. Ampliación: `recordar` MCP con sustantivos por idioma

### Camino y condiciones

La tabla inicial de la sección 3 usó **motor directo**, sin MCP y sin sustantivos guardados ni enviados. A petición del auditor se prepararon **132 conjuntos de sustantivos**, con términos elegidos de cada pregunta sin consultar el nombre esperado; [etiquetas auditables](../scripts/casos_qa_multilingue_sustantivos_e3a.jsonl). Se llamó directamente a la implementación real `_recordar_impl` de MCP, **no** al transporte de red ni a un agente real. Sin paráfrasis, ráfaga ni dimensiones; `deep=False`, cinco resultados públicos, semilla y neurona igual que antes. Una copia nueva por llamada; reloj fijo y fuentes sin modificar.

Se hicieron dos brazos:

- **A, base directa:** los mismos 120 recuerdos de la QA, guardados por la API canónica sin `sustantivos_clave` en los nodos. Mide la validación de entrada MCP sobre los mismos recuerdos, pero no prueba el boost de sustantivos guardados.
- **B, base MCP EN/ES:** 20 recuerdos ingleses y 20 españoles con búsqueda previa real, `_aprender_impl`, categoría `General`, sin sinónimos ni dimensiones, sustantivos elegidos del contenido del recuerdo y consolidación explícita del nodo por la API del motor. Los cinco puentes por recuerdo son plantillas sintéticas que cumplen la validación, **no** puentes semánticos redactados por un agente; pueden influir en el resultado. Los otros 80 recuerdos no se guardaron en esta base; las sondas de `aprender` rechazaron ejemplos con sustantivos nativos de los cuatro idiomas, pero no se hicieron 80 intentos de guardado. Es una muestra, no una emulación completa del agente.

`recordar` no expone `ignore_peso_sinaptico`: llama al motor con su valor predeterminado `False` y pide hasta 15 candidatos internos para devolver cinco (`core/mcp_server/search.py:446-493`; `core/memory/search.py:41`). No se forzó el parámetro ni se alteró el motor para fingir equivalencia con la QA directa, que usa `True` y límite interno 5. Las métricas no son una comparación causal aislada del uso de sustantivos.

### Resultados por idioma

| Idioma | Entrada MCP: positivos / negativos rechazados | Brazo A: R@5 / R@1 / FP | Brazo B: R@5 / R@1 / FP |
|---|---|---|---|
| zh | 20/20 y 2/2 | No buscó | No buscó; recuerdos no guardados por MCP |
| ja | 20/20 y 2/2 | No buscó | No buscó; recuerdos no guardados por MCP |
| ko | 20/20 y 2/2 | No buscó | No buscó; recuerdos no guardados por MCP |
| ru | 20/20 y 2/2 | No buscó | No buscó; recuerdos no guardados por MCP |
| en | 0/20 y 0/2 | 20/20 / 20/20 / 2 de 2 | 20/20 / 19/20 / 2 de 2 |
| es | 0/20 y 0/2 | 20/20 / 20/20 / 0 de 2 | 20/20 / 20/20 / 0 de 2 |

En los 88 rechazos de cada brazo, el código es `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO` y `_get_cerebro` no llegó a abrir ninguna base. El archivo de métricas cuenta esos positivos como **0/20 recuperados de extremo a extremo**, pero no como una búsqueda ejecutada. **Un error no cuenta como abstención acertada**, por eso no se informa FP 0/2 para esos idiomas. Ejemplos de normalización previa al rechazo: `ガラス` llega a `カラス`; `바닷가` queda descompuesto en jamos. Esto no prueba que toda escritura mixta vaya a fallar, solo las etiquetas nativas de esta muestra.

Las cuatro sondas de `aprender` anteriores fueron pruebas aisladas de validación: enviaron puentes espaciados artificiales y marcaron `busqueda_previa=True` para llegar al control de sustantivos; no realizaron búsqueda previa real ni abrieron una base. Por contraste, las 40 escrituras EN/ES del brazo B sí ejecutaron la búsqueda previa en la base temporal.

En el brazo B, `en-10` (“wooden cabinet”) recuperó `model_airplane` en **2.º**, detrás de `wooden_flute`; los demás positivos inglés/español quedaron primeros. Esto no es una regresión de motor: las bases y parámetros no son idénticos. Los negativos ingleses sí fueron devueltos también por MCP:

| Caso | Sustantivos enviados | Brazo A: resultado / score | Brazo B: resultado / score |
|---|---|---|---|
| `en-n01` | `platypus,boots,chess` | `model airplane` / 0,2241 | `model_airplane` / 0,2238 |
| `en-n02` | `saxophone,desert,glacier` | `model airplane` / 0,2557 | `model_airplane` / 0,2554 |

En ambas bases nuevas se comprobó que no había umbral conforme cargado. Aunque el comentario de MCP menciona un cold-start, `_debe_responder` devuelve verdadero sin umbral (`core/memory_store.py:182-196`, `core/memory/umbral.py:202-225`). Por eso estos scores bajos no fueron filtrados; MCP sí adjuntó el aviso de brecha y `sin_evidencia_directa`. Esto describe **estas bases aisladas**, no afirma cómo está calibrada la base viva.

Cada brazo repitió **132 consultas en orden inverso sobre la misma base**, sin diferencias en listas, scores ni respuestas. No se modificó la base de origen. Reproducir:

```bash
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_mcp_e3a.py \
  --verificar-orden --salida /tmp/e3a_mcp.json
```

[Resultado completo por llamada, incluidas respuestas MCP](e3a_mcp_resultados_20261027.json); [salida](e3a_mcp_20261027.log); [arnés](../scripts/evaluar_qa_multilingue_mcp_e3a.py); [pruebas del arnés](../tests/test_qa_multilingue_mcp_e3a.py).

## 4. QA oficial: referencias E2e, no corridas nuevas

| Condición | Snapshot: R@5 / R@1 / FP | Copia del respaldo: R@5 / R@1 / FP |
|---|---|---|
| Normal | 100,00 % / 95,31 % / 0 de 40 | 99,88 % / 93,53 % / 0 de 40 |
| Con `zzqx` añadido | 97,34 % / 88,63 % / 0 de 40 | 96,63 % / 88,12 % / 0 de 40 |

Se trata de R@5 y R@1 **honestos**, con sus diferentes denominadores E1. La segunda columna es la copia del respaldo de Drive del **26-10-2026**, no una conexión a la base actual. El snapshot tiene 866 nodos y el respaldo reconstruido 1.357.

Comprobación adicional solicitada: `git diff 1339cfb HEAD -- core` no produce diferencias ([salida y códigos](e3a_auditoria_codigo_20261027.txt)). También `core/`, arnés `scripts/evaluar_qa.py`, `qa_neurona.py`, gold oficial, snapshot, `requirements.txt` y corpus locales WordNet no difieren del árbol E2e `9f2c0be`; los 34 elementos del manifiesto E2e verifican. El respaldo SQL descargado conserva MD5 `34650056ebcc04427ba3f9b494150026`; al reconstruirlo se obtuvo exactamente el SHA-256 de la base E2e `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a`. El snapshot conserva SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`. Ambos pasaron integridad en lectura inmutable.

El entorno de ahora coincide en los componentes principales informados en E2e: Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6 y pytest 9.1.1; NLTK está fijado en `requirements.txt`. Las dependencias directas y los corpus no cambiaron. **No se conservó un freeze completo de las dependencias transitivas de E2e**, por lo que no se afirma identidad absoluta del entorno. Se conserva el [freeze actual](e3a_entorno_python_20261027.txt) para el futuro. Detalle de verificación: [e3a_verificacion_referencias_20261027.txt](e3a_verificacion_referencias_20261027.txt). Allí figura `3af967d` porque era el HEAD **al hacer esa verificación**; después se reescribió Python como `c78c432` sin alterar `core/`. [Cuatro informes y comparación E2e](e2e_comparacion_20261027.txt).

## 5. Inventario de dependencias de idioma

`G` = guardar, consolidar o construir índice; `B` = buscar. Las consecuencias indicadas para chino/japonés/coreano/ruso se refieren a texto puro de esas escrituras; palabras latinas mezcladas pueden tomar otras rutas.

| Pieza y ubicación | Función, idiomas y efecto | G/B |
|---|---|---|
| `core/stemmer_es.py:43-46,51-80,92-104,250-283` | Raíces Snowball español/inglés; lo que la heurística no identifica como español se envía al inglés. No hay tratamiento morfológico ruso, chino, japonés ni coreano. NFKD elimina toda marca combinante: `ガ`→`カ`, `ё`→`е`, `й`→`и`; coreano se descompone en jamos. Los tokens de menos de 3 se devuelven sin esa normalización. | Ambos |
| `core/stopwords.py:8-69` | Listas españolas e inglesas, más palabras internas. No filtran palabras funcionales propias de los cuatro idiomas; tampoco separan partículas unidas. Pueden eliminar una forma latina que tenga significado distinto en un texto mezclado. | Ambos |
| `core/fallback_simbolico.py:25-47,170-205` | Quita todas las marcas, extrae `\w{2,}` y expande WordNet solo `spa`/`eng`. Unicode acepta caracteres de los cuatro idiomas, **pero no segmenta** frases chinas/japonesas sin espacios; descarta tokens de un carácter. En japonés/ruso puede unir palabras distintas; en coreano descompone sílabas. | B |
| `core/clasificador_wordnet.py:38-73`; llamadas en `core/memory/consolidation.py:181-212` y `core/memory/search.py:1470-1495` | Consulta español y luego inglés, y solo trozos de 3+ caracteres. No consulta WordNet en chino, japonés, coreano ni ruso. En el gold puro: 0/20 recuerdos de cada uno recibió grupo; inglés y español 20/20. Esto no demuestra que todo texto mixto quede sin grupo. | Ambos |
| `core/memory_store.py:104-120`; `core/memory/search.py:138-160,2063-2093` | La búsqueda divide principalmente por espacios y usa límites `\b` para palabra/prefijo. Chino y japonés continuos pueden ser un único bloque; fragmentos internos son rechazados pese a estar en FTS. Coreano con espacios y ruso pueden usar la ruta, pero flexiones/partículas siguen siendo limitaciones. | B |
| `core/memory/schema.py:963-1008,1062-1082` | Mantiene FTS trigram y `unicode61`. Trigram sí halló los dos fragmentos asiáticos de la sonda; no se debe responsabilizar al índice de esos descartes. Por diseño trigram necesita tres caracteres para esa ruta; otras rutas pueden operar para términos cortos. | Ambos |
| `core/sinapsis.py:4-16,104-110,190-195,306-313` | El autovínculo tokeniza con letras latinas y acentos españoles, y necesita al menos dos tokens. En texto puro chino, japonés, coreano o ruso no obtiene tokens de esas reglas; en esta base los 80 recuerdos de esos idiomas quedaron sin sinapsis automáticas. No implica que no puedan recibir enlaces manuales. | G, con efecto posterior en B |
| `core/pmi_semantico.py:53-71`; `core/ppmi_vectorizer.py:19-21,33-41,172-188`; `core/ppmi_hybrid_search.py:17-19,32-39,159-168`; `core/similitud_conceptual.py:28,57-65` | PMI, índice estadístico y similitud comparten o replican patrones latinos; un texto puro de los cuatro idiomas no aporta tokens a esas rutas. El índice PPMI puede omitir un recuerdo sin tokens. Esto **no** significa que el FTS general no pueda encontrarlo. | Ambos |
| `core/sdm.py:27,161-188`; `core/memory/escala.py:44-46,74-105` | SDM divide por espacios y aplica el stem ES/EN; escala usa normalización sin marcas y trigramas Unicode. Chino/japonés sin espacios quedan como bloques, coreano se descompone y japonés/ruso pueden colisionar. No se ha aislado su efecto causal en cada fallo. | Ambos |
| `core/lexical_learning.py:36-53,57-79,194-202,329-345`; `core/memory/search.py:1125-1126` | La enseñanza y recuperación de expresiones borra todo salvo ASCII y dígitos; las cuatro escrituras puras quedan vacías. La sonda `enseñar("ガラス")` devuelve `expresion vacia tras normalizar`. Las variantes `-s/-es` están pensadas para morfología latina. | Ambos |
| `core/mcp_server/write.py:212-248,877-905`; `core/mcp_server/search.py:178-200,202-246`; `core/memory/constants.py:285-301` | Los sustantivos clave se normalizan quitando marcas y solo admiten `[a-z0-9_ñ]`, de 2–15 caracteres. Los ejemplos nativos de los cuatro idiomas fueron rechazados tanto por `_aprender_impl` como por `_recordar_impl`, **antes** de abrir base; con sustantivos latinos la conclusión puede ser distinta. | Ambos, interfaz MCP |
| `core/concept_hub.py:58-66,109-135,435-457` | La validación exige dos palabras de contenido separadas por espacios y usa stopwords españolas y stem ES/EN. Cinco frases japonesas naturales sin espacios fueron rechazadas en la sonda. Chino presenta el mismo riesgo; coreano y ruso pueden separar por espacios, pero no tienen morfología propia aquí. | G de puentes y B por expansión |
| `core/memory/catalog_methods.py:15-58,134-140` | Nombres de dimensiones se reducen a ASCII; los ejemplos puros de los cuatro idiomas quedan inválidos (`None`). Los ejes internos existentes son un catálogo fijo. | Ambos cuando se usan dimensiones |
| `core/categorizador.py:1-47,49-71`; llamada en `core/mcp_server/write.py:253` | Clasificación automática por lista principalmente española y algunos términos ingleses. Texto puro de los otros cuatro suele caer en `General` salvo coincidencias; si se indica categoría explícita sigue esa otra ruta. | G |
| `core/srl_extractor.py:12-34,36-61`; `scripts/backfill_predicados.py:89-109`; `core/memory/search.py:2789-2804` | Verbos y reglas de extracción SRL están orientados al español; el extractor se usa en backfill, no se afirma que se ejecute automáticamente en cada `aprender`. La búsqueda de predicados usa ese diccionario y normalización. | G en backfill y B por predicados |
| `core/memory/constants.py:251-270`; `core/memory/scoring.py:200-210,410-421`; `core/memory/evidence_convergence.py:15-16,36-49,72-80`; `core/memory/rafaga.py:250-267,299` | La tolerancia a errores usa palabras latinas en su ruta difusa; el acierto por substring exacto se comprueba antes. JSD, convergencia y ráfaga heredan divisiones, stopwords o normalización citadas. Su intervención depende de la ruta y banderas; no se han medido aisladamente aquí. | B; ráfaga también puede crear enlaces |
| `core/auto_clustering.py:6-15,118`; `core/memory/consolidation.py:70,125-128`; `core/memory/neurona_examen.py:112-121,190-197` | Agrupación y examen automático usan longitud mínima y/o separación por espacios; el examen también valida sustantivos ASCII. Los efectos dependen de la función activada; no forman parte de esta QA con la neurona de ranking apagada. | G/consolidación y B indirecta |
| `core/neurona_asociativa.py:85-98` | El módulo tokeniza solo `[a-z0-9]`, así que pierde las cuatro escrituras puras. En este árbol no se encontró importación desde el motor; se deja como riesgo del módulo, **no** como causa medida de la QA. | Módulo no conectado al flujo examinado |

### Importadores directos solicitados

- `stemmer_es`: `core/sinapsis.py:311`, `core/sdm.py:27`, `core/ppmi_vectorizer.py:21`, `core/ppmi_hybrid_search.py:19`, `core/pmi_semantico.py:67`, `core/neocortex_teleologico.py:28`, `core/memory/search.py:21`, `core/memory/constants.py:9`, `core/memory/evidence_convergence.py:16`, `core/concept_hub.py:66,441,620,631`, `core/mcp_server/search.py:403,421`.
- `stopwords`: `core/sinapsis.py:4`, `core/similitud_conceptual.py:12`, `core/ppmi_vectorizer.py:20`, `core/ppmi_hybrid_search.py:18`, `core/pmi_semantico.py:24`, `core/neocortex_teleologico.py:27`, `core/memory/search.py:139,234`, `core/memory/scoring.py:200,410`, `core/memory/neurona_examen.py:23`, `core/fallback_simbolico.py:15`, `core/concept_hub.py:65,440,630`, `core/auto_clustering.py:6`.
- `_tokenizar_normalizado` y demás fallback: `core/memory/search.py:934,950,1083,1553`, `core/memory/scoring.py:201`, `core/memory/rafaga.py:258`, `core/memory/evidence_convergence.py:15`, `core/ppmi_hybrid_search.py:166`. Clasificador WordNet: `core/memory_store.py:23`, `core/memory/consolidation.py:185`, `core/memory/search.py:1476`, `core/mcp_server/server.py:47`, `core/dmn_reflexion.py:512`.

## 6. Propuesta para discutir, NO aplicada

No presupone idiomas fijos ni diccionarios nuevos. Orden sugerido; cada punto necesita aprobación independiente y un diff pequeño:

1. **Identidad del motor:** estudiar una sola modificación en la decisión de match exacto para distinguir `ガラス` de `カラス`, conservando la tolerancia de tildes latinas sin tocar pesos. Acordar primero el diff y probar pares con y sin marcas.
2. **Normalización de sustantivos MCP:** estudiar por separado cómo preservar letras y marcas significativas en la función compartida de normalización; hoy `ガラス` se convierte en `カラス` antes de validar. Conservar las garantías existentes de español, incluida la `ñ`.
3. **Validación de búsqueda MCP:** estudiar una sola modificación que permita sustantivos Unicode en `recordar`, sin cambiar cantidad ni otros invariantes por sorpresa. Medir el camino MCP real, además del directo.
4. **Validación de guardado MCP:** tratar la validación de `aprender` en una entrega distinta de la anterior; medir escritura, búsqueda previa y recuperación con sustantivos en cada idioma.
5. **Límite de palabra/prefijo:** estudiar un cambio acotado al filtro que excluye los dos fragmentos demostrados, conservando la protección contra substrings engañosos y la regla E1 de ambigüedad. No eliminar el filtro globalmente.
6. **Puentes MCP:** tratar por separado su validación de palabras; probar frases nativas sin espacios y también puentes españoles/ingleses engañosos. No equivale a cambiar la validación de sustantivos.
7. **Aprendizaje léxico:** estudiar conservar letras Unicode sin destruir marcas al normalizar expresiones. Probar escritura y recuperación, colisiones y compatibilidad con índices existentes.
8. **Sinapsis y PMI/PPMI/similitud:** examinar **un tokenizador por entrega**, sin listas por idioma ni modelos embebidos. No reconstruir ni migrar índices reales sin aprobación; medir copias y analizar impacto de crecimiento.
9. **Resto:** revisar por entregas independientes stopwords, stemming, WordNet, dimensiones, categorización y SRL. No eliminar automáticamente lo que protege español e inglés.

Antes de **cada** cambio B: mostrar el diff concreto y obtener OK. Después: repetir **las cuatro QA oficiales**, la multilingüe directa y la MCP cuando proceda; comparar categorías R@5 honesta, R@1 honesta, FP y resultados por idioma, usando copias equivalentes. Mantener los pesos manuales como piso: la neurona solo suma encima y con techo. **Si alguna métrica acordada baja, revertir**, no ajustar otra cosa de inmediato.

## 7. Python 3.11: alcance y CI

El commit `c78c432` contiene únicamente estos cambios, sin tocar el workflow, README, VERSION ni CHANGELOG:

```diff
-pyproject.toml: requires-python = ">=3.10"
+pyproject.toml: requires-python = ">=3.11"
-pyproject.toml: "Programming Language :: Python :: 3.10",
-install.py: if sys.version_info < (3, 10):
-install.py:     _fail("Python 3.10+ requerido")
+install.py: if sys.version_info < (3, 11):
+install.py:     _fail("Python 3.11+ requerido")
```

[Patch exacto del commit](e3a_python_311_20261027.patch). Verificación local: los metadatos son correctos y el chequeo del instalador rechaza 3.10 y admite 3.11/3.12. El primer envío del commit antiguo fue rechazado por el permiso `workflows`; el commit reescrito sí se subió, sin cambios de workflow. Después, Dennys retiró Python 3.10 de la matriz por la web en el commit independiente `956cd58`.

La [ejecución CI 40598831759](https://github.com/dennysjmarquez/MemoryBioRAG/actions/runs/40598831759) sobre `d9622fa` pasó en **Python 3.11 y 3.12**; 3.10 falló en instalación, antes de pytest. Tras el cambio web, la [ejecución 40599602755](https://github.com/dennysjmarquez/MemoryBioRAG/actions/runs/40599602755) en `956cd58` terminó **verde**, con 3.11 y 3.12 en la matriz. El CI de la ampliación posterior debe comprobarse aparte.

Pruebas locales completas tras la ampliación, Python 3.11: **563 aprobadas en 110,06 s**, incluidas [siete pruebas de QA directa](../tests/test_qa_multilingue_e3a.py) y [seis de MCP](../tests/test_qa_multilingue_mcp_e3a.py). [Salida completa](e3a_pytest_auditoria_20261027.log). Se ejecutaron sin exportar `BIORAG_NEURONA=0` para no desactivar las pruebas neuronales. La ejecución anterior fue de 557 aprobadas.
