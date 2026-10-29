# Las islas de recuerdos: lo que ya se investigó, rescatado

> Pedido de Dennys (2026-10-29): "Los recuerdos se agrupan en islas, islas fantasma… hubo mucha investigación de eso. Cuando hice que las dimensiones fueran dinámicas vi cosas que se metieron como tema y mandé a quitarlas. Rescata eso, por lo menos en conocimiento."

Este documento junta en un solo lugar lo que estaba disperso en **la propia memoria viva** (recuerdos guardados por los agentes entre junio y octubre de 2026), en el **código** y en los **scripts de experimentos**. Se suman las mediciones nuevas del auditor sobre una copia de la viva. No se cambió nada del motor ni de ninguna base.

- **Fuente de la memoria:** copia de la base viva restaurada del dump del 26-10 (sha `a61913ce…`), solo lectura. Se citan los recuerdos por su nombre de concepto; los recuerdos personales se describen sin nombres.
- **Código:** `master` `f8c2b16`.
- **Nota:** el historial de git del repo está comprimido (127 commits; `core/auto_clustering.py` aparece de una vez en un merge), así que la historia vive en la memoria, no en git. Los hashes antiguos que se citan (`cc3fc58`, `007f69c`, `2496513`, `906b27c`, `d6678b3`) vienen de esos recuerdos y no se pueden comprobar en este repo.

---

## 1. Hay tres "islas" distintas (no confundirlas)

| | Islas por **sinapsis** (las del sueño) | Islas por **significado** (PPMI) | Grupos **WordNet** |
|---|---|---|---|
| Dónde | `core/auto_clustering.py`, llamado en el sueño (`core/memory/consolidation.py` ~556) | `scripts/experimentos/expA_topologia_semantica.py` (no está en el motor) | `core/memory/consolidation.py:183` → tablas `grupos_semanticos` / `nodo_grupos_semanticos` |
| Cómo se forman | Label Propagation (LPA) sobre las conexiones entre recuerdos (peso ≥ 0,1) | Cada recuerdo tiene un vector propio de 100 números sacado del propio corpus (PPMI+SVD, tabla `nodos`). Se une a sus 15 vecinos **mutuos** más parecidos (coseno ≥ 0,3) y sobre ese grafo corre LPA | Cada palabra del recuerdo se asigna a su "supersentido" de WordNet (`noun.time`, `verb.contact`…) |
| Qué se guarda | Una **dimensión emergente** `tema_<3 palabras>` en el eje `dominio` (antes `auto_…`) | Nada en la base (solo un JSON de experimento: `scripts/experimentos/expA_labels.json`) | 45 grupos, 200.984 enlaces recuerdo-palabra-grupo |
| Estado hoy en la viva | **Ahogadas**: 1 sola isla gigante → 0 islas nuevas | **Sanas**: 125 islas (ver §3) | Existen; uso no auditado aquí |

Lo que Dennys recuerda como "islas fantasma" son las de la primera columna: **se vieron** cuando la memoria era chica y **dejaron de verse** cuando el grafo se llenó de conexiones. Las de la segunda columna son las que la investigación de agosto encontró **sanas**.

---

## 2. Línea de tiempo rescatada de la memoria viva

| Fecha | Recuerdo (concepto) | Qué pasó |
|---|---|---|
| 2026-06-30 | `principio_emulacion_semantica_por_clusters_declarativos`, `teoria_ejes_semanticos_biorag` | La idea madre de Dennys: **no emular la matemática del vector, emular el resultado**. Una etiqueta como "frustración" junta miles de palabras distintas en el mismo grupo: cercanía **declarada y auditable**, no adivinada. Cada eje es un "cluster" más. |
| 2026-07-05 | `v13_2_limpieza_tabla_semantica` | Antecedente de "cosas que se metieron": el 84,9 % de la tabla semántica estaba contaminada con nombres de recuerdos usados como palabras. Se borraron 3.458 entradas. Lección: **no auto-generar desde nombres de recuerdos**. |
| 2026-07-09/11 | `biorag_v16_0_estado` | v16.0: nacen las **dimensiones emergentes**. LPA en el sueño crea dimensiones `auto_…` a partir de comunidades del grafo. |
| 2026-07-23 | `plan_dimensiones_dinamicas_hibrido` (dormido) | Plan de dimensiones dinámicas: valores nuevos dentro de los ejes existentes; **ejes nuevos solo con aprobación de Dennys**; máximo ~15 valores por eje; limpieza de huérfanas. |
| 2026-08-04 | `fca_reticulo_galois_f2_…`, `fca_chequeo_sugeridor_dimensiones_…` | Laboratorio FCA sobre dimensiones: 22 de 104 valores **sin ningún recuerdo** (dimensiones muertas). El "sugeridor automático de dimensiones" se **refutó**: elegía por frecuencia, no por significado. Quedó como **auditoría** de recuerdos mal etiquetados. |
| 2026-08-13 | `hallazgo_adn_degenerado_grafo_sin_modularidad_20260813` | Primera alarma: sobre el snapshot (866 recuerdos, 13.755 sinapsis), el LPA por sinapsis da **1 sola comunidad** (o 0 con los parámetros del motor). Causa: **grafo saturado**, no el método de significado. Regla: **no inventar ejes artificiales** (Política A). |
| 2026-08-13 | `hallazgo_adn_ppmi_modular_no_degenerado_20260813` | Hallazgo clave: con vectores de significado (k-NN mutuo k=15 + LPA) salen **105 islas sanas** (la mayor, 5,5 %). HDBSCAN y aglomerativo fallan (una comunidad se come el 80–92 %). |
| 2026-08-13 | `hallazgo_puente_sinonimia_comunidades_ppmi_20260813` | Las islas **codifican sinonimia**: la consulta y el recuerdo esperado caen en la misma isla el 41 % de las veces, contra el 1,9 % al azar (**21,5×**). Dentro de la isla, el esperado queda entre los 5 más cercanos el 87 % de las veces. |
| 2026-08-13 | `hallazgo_espectro_completo_islas_construccion_sana_proyeccion_debil_20260813` | A pedido de Dennys, "mirar hacia atrás": las islas se forman **de forma natural**, son coherentes (identidad, CV/frontend, búsqueda/typos) y ninguna pasa de 50. Techo con la isla perfecta: **9/13** fallos de sinónimo rescatados. |
| 2026-08-13/14 | `hallazgo_rrf_…`, `expe_topk_islas_union_…`, `expe2_gate_…`, `expe3_pipeline_real_…`, `fase_b_softmax_comunidades_refutada_20260814` | **Todos los intentos de usar las islas para reordenar el top-5 dieron neto negativo**: impulso por isla (2/13), restringir a la isla (0/13), unión de las k mejores islas (neto −6 a −24), RRF (neto −2), softmax (neto −23), "fallback" condicional (techo teórico +3 a +5; real, negativo). Causa: **la llave de acceso**. Desde una consulta de 1–2 palabras, el sistema elige la isla correcta solo el 41 % de las veces (67 % entre las 5 mejores). Veredicto de entonces: "línea islas para ranking **agotada**". |
| 2026-08-14 | `leccion_canal2_asociaciones_enriquecidas_cero_regresiones_20260814` | Lo que **sí** quedó: el **canal 2**, `asociaciones_enriquecidas`, separado del ranking (hoy `core/memory/synapses.py:405`). **Cero regresiones**. Usa las sinapsis, no las islas. |
| 2026-10-07 | `biorag_v32_4_dimensionhub_mundo_abierto`, `version_actual_biorag_v32_4_20261007` | v32.4, **mundo abierto**: si el agente usa un valor de dimensión que no existe, se crea solo (`auto_generada=1`, confianza 0,7) en vez de descartarse en silencio. |
| 2026-10-07/08 | `flag_migracion_autoclustering_fuera_catalogo` | **Lo que Dennys mandó a quitar.** En `listar_dimensiones` y en el árbol de la herramienta `aprender` aparecían dos nombres que no eran dimensiones de verdad: el marcador interno `migration_autoclustering_v1` y la isla `auto_umbral_v28_calibrar`. Decisión aprobada por Dennys: (1) el marcador pasa a su propia tabla `migraciones_ejecutadas`; (2) el prefijo `auto_` pasa a `tema_`, legible para humanos y agentes; (3) **salvaguarda de islas**: nunca volver a purgar las dimensiones automáticas vivas con sus recuerdos. |

---

## 3. Mediciones nuevas sobre la copia de la viva (2026-10-29, solo lectura)

**Islas por sinapsis (las del sueño):**
- 1.194 recuerdos activos y ~26.000 conexiones entre ellos (grado medio ≈ 44; 33.413 sinapsis en total, 15.219 de tipo `sinonimo_explicito`).
- LPA del motor: **1 isla de 1.194**, densidad muy por debajo de 0,3 → **0 islas por ciclo**. Es el mismo fenómeno que la alarma del 13-08, ahora con la base más grande.
- Como el sueño solo actualiza si encuentra islas (`if comunidades:`), la única que queda, `tema_umbral_v28_calibrar`, está **congelada**. Hoy tiene 5 recuerdos (7 al renombrarla, el 07-10).
- Con Louvain (otro método clásico, probado solo como medición) salen 6 continentes grandes (modularidad 0,32); sin las conexiones de sinónimos, 11 (0,40). Las islas por sinapsis existen, pero son **gruesas**.

**Islas por significado (PPMI, como en agosto):**
- 1.357 vectores (índice PPMI de la base: último rebuild completo el 2026-08-10 y fold-in incremental en cada sueño; `core/memory/consolidation.py:712`).
- **125 islas**, 99 con 4 o más recuerdos, **la mayor de 47 (3,5 %)**, mediana 11, solo 4 sueltos, **modularidad 0,72**. Siguen sanas con la base más grande.
- **Ejemplos (los mismos recuerdos de los ejercicios 1–3):**
  - El recuerdo personal de una mascota está en una isla de 6 junto a su historia personal y su vida laboral.
  - El recuerdo dormido "Dennys cree que somos vivos" está en la isla de **identidad** (25 recuerdos sobre identidad de los agentes).
  - La metodología de postulación freelance está en una isla de 20 de **postulaciones y búsqueda de trabajo**. Ahí también vive el "antipatrón de texto de postulación", **la pista exacta del ejercicio 2 y la enseñanza que la contradice** (P2).
  - El recuerdo de "recuperación dimensional sin palabras" está en una isla de 33 sobre **dimensiones semánticas** (diseño de tablas, cambio de paradigma, idea de dimensiones dinámicas…).

**Dimensiones del catálogo hoy:**
- 13 ejes y 108 valores; **6 creados automáticamente**: `tema_umbral_v28_calibrar` (la isla congelada), `protocolo`, `intencion_analizar`, `dominio_cognitivo`, `accion_documentar` e `intencion_evaluar`.
- **`protocolo` quedó dentro del eje `escala_abstraccion`** (tipo 18) con 5 recuerdos de protocolos. Un "protocolo" no es una escala de abstracción: parece una entrada del mundo abierto en el eje equivocado. Es el mismo tipo de cosa que "se metió". **Solo se registra; no se toca.**
- 3 valores sin ningún recuerdo.
- **Contador alto, sin pérdida de datos (resuelto el mismo día):** el contador interno de SQLite va por **123.866** para 108 dimensiones (y por 3.915 para 13 ejes). **No se crean ni se borran dimensiones.** Cada vez que se abre el cerebro, el `INSERT OR IGNORE` del catálogo de fábrica (`core/memory/schema.py` ~923, ejes nuevos) "gasta" números aunque no inserte nada: medido sobre una copia, **+29 por apertura** (y +6 en ejes). 123.866 / 29 ≈ 4.270 aperturas. Es inofensivo; solo hace que los ids de las dimensiones nuevas salten.

---

## 3b. ¿El cambio del 07-10 (lo que Dennys mandó a quitar) estropeó las islas? No.

Dennys mandó sacar del catálogo el marcador `migration_autoclustering_v1` y la isla `auto_umbral_v28_calibrar`, sin recordar que ahí vivían las islas automáticas. Comprobación:

1. **La isla no se borró: se renombró.** Pasó a `tema_umbral_v28_calibrar` con sus recuerdos (recuerdo `flag_migracion_autoclustering_fuera_catalogo`), y sigue en la base.
2. **El sueño siguió formando islas después del cambio.** La fecha de detección de esa isla (`generado_en`) es **2026-10-11 01:23**, tres días después de la migración (marcada en `migraciones_ejecutadas` el 2026-10-08 00:58), con densidad 0,77. El código del sueño sigue llamando a `detectar_comunidades` en cada consolidación (`core/memory/consolidation.py` ~556).
3. **Por qué hoy no salen islas nuevas:** el grafo de sinapsis se saturó. Ya en agosto, con 866 recuerdos, el LPA con los parámetros del motor daba **0 comunidades** (`hallazgo_adn_degenerado_grafo_sin_modularidad_20260813`, del 13-08, **antes** del cambio). Hoy, con 1.194 activos y ~26.000 conexiones, da 1 isla gigante. El último bolsón denso que todavía se detectaba (el del umbral v28) fue la última isla.

**Conclusión:** el cambio del 07-10 dejó el sistema bien (y fue correcto sacar el marcador del catálogo). Las islas del sueño se apagaron por **crecimiento**, no por esa limpieza. La memoria lo contaba todo: se encontró también por MCP (`recordar(query="islas comunidades")` en una copia trae **8 recuerdos de esta investigación en el top 8**).

## 3c. Causa raíz en código: por qué el grafo se saturó (2026-10-29, solo lectura)

Las islas del sueño se ahogaron porque el grafo de sinapsis se llenó de conexiones que **nacen fácil y casi nunca mueren**. Hay dos mecanismos concretos en el código (`master` `f8c2b16`), medidos sobre la copia de la viva:

**1. Las conexiones por sinónimos se crean por subcadena, no por palabra.** `core/sinapsis.py:440-470` (`vincular_por_sinonimos`) une el recuerdo nuevo con todo recuerdo cuyo nombre o sinónimos **contengan** cada sinónimo (`LIKE '%término%'`), con peso 0,9.
- Un sinónimo corto como "pe" o "je" cae dentro de "**pe**rfil", "ex**pe**rimento" o "mensa**je**".
- **Ejemplo real:** un recuerdo técnico con sinónimos como `pe`, `je` y `jne` quedó unido a **585** recuerdos. Solo **35** comparten de verdad una palabra completa. **477** uniones vienen de "pe" y **166** de "je".
- En todo el grafo, de **15.219** conexiones `sinonimo_explicito` (casi la mitad de todas):

| Tipo de unión | Conexiones | % |
|---|---|---|
| Comparten una palabra completa | 7.892 | 52 % |
| Solo por subcadena (accidentales) | 4.027 | 26 % |
| Apuntan a recuerdos que ya no existen | 738 | 5 % |
| Sin coincidencia visible hoy | 2.562 | 17 % |

De las 4.027 accidentales, **2.530** vienen solo de términos de 3 letras o menos.

**2. Las conexiones que nunca se usaron no se debilitan jamás.** El sueño solo debilita las sinapsis con `ultimo_uso IS NOT NULL` que no se usan hace 7 días (`core/memory/consolidation.py:432-438`). Pero al **crearse**, la sinapsis queda con `ultimo_uso` vacío (el `INSERT` no lo llena).
- Resultado: **29.039 de 33.413 sinapsis (87 %)** tienen `ultimo_uso` vacío. Sin contar las manuales, que se protegen a propósito, son **27.318** conexiones **inmunes al olvido**.
- Por tipo: 13.961 de 15.219 `sinonimo_explicito`, 4.133 de 4.162 `co_semantica`, todas las `dmn_synthesized` (948)…
- Parece un descuido (lo que nunca se usó es justo lo más "no usado"), pero hay que confirmarlo antes de tocar nada.

**3. Además: 862 sinapsis huérfanas** apuntan a recuerdos que no existen en `largo_plazo` (por ejemplo, un concepto inexistente con 633 conexiones, que encabeza la lista de hubs).

**Lectura biológica:** el cerebro hace dos cosas, **crear** conexiones por el uso y **podarlas/regularlas** (escalado sináptico, olvido de lo que no se usa). BioRAG tiene homeostasis para los **recuerdos** (decaimiento, dormir, inhibición lateral y escalado; `core/memory/consolidation.py:390-528`), pero casi no la tiene para las **conexiones**. Por eso se ahogaron las islas del sueño, y por eso aparecen hubs de cientos de vecinos. Es la regla 3 del Pilar 13.

**Qué NO se hizo:** no se tocó el motor ni ninguna base. Antes de cualquier cambio: conversar con Dennys y medir en copias, con la QA completa y las asociaciones, el efecto de (a) unir por palabra completa en vez de subcadena, (b) dar a las sinapsis nuevas su fecha de nacimiento como `ultimo_uso` para que el olvido las alcance, y (c) revisar las huérfanas **sin borrar las manuales**. Las conexiones forman parte de los vecinos y pistas (Pilar 12), así que cualquier poda se mide también por las pistas que se pierden.

### Postura de Dennys sobre las sinapsis (2026-10-29)
- **Hay dos tipos de sinapsis.**
  - **La verdadera sinapsis** la hace el agente en vivo: antes de guardar, busca lo que va a guardar (`aprender` exige `busqueda_previa=True`, `core/mcp_server/write.py:80-103`) y, si encuentra recuerdos relacionados, los **vincula**. Esas conexiones (`manual`, 1.801 en la viva) ya están protegidas del olvido (`constants.SQL_NO_ES_DEL_AGENTE`).
  - **Las automáticas** se hacen solas por detrás: sinónimos, co-ocurrencia, sueño…
- **Las automáticas no se matan: se mejoran.** Son las aristas que permiten el **salto** de un recuerdo a otro. Sin ellas no llega el recuerdo vecino y no hay ruido útil (Pilar 12). El código lo confirma: los saltos del grafo usan `sinonimo_explicito` (`core/ppmi_hybrid_search.py:29`, `TIPOS_HOP`), y la inferencia transitiva también.
- **Ruido sí, ruido tonto no.** Lo que sobra son las uniones accidentales ("pe" dentro de "perfil"), no los sinónimos reales (7.892 que comparten palabra completa).
- **Orden:** primero el algoritmo, la mecánica y el motor tienen que hacer bien las conexiones; después las neuronas.
- **La visión:** BioRAG es un grafo y además un cerebro. Cada recuerdo es como una neurona, y las conexiones son el tejido que las une.

## 4. Lo que se aprendió y sigue en pie

1. **Construir islas sí; reordenar el top-5 con ellas, no (medido seis veces).** Encaja con el Pilar 12 y con la regla de Dennys: las islas sirven para **asociar y dar pistas**, no para filtrar ni reordenar a la fuerza.
2. **El LPA sobre sinapsis se ahoga cuando la memoria crece; el de significado (k-NN mutuo) no**, hasta ahora (105 islas con 866 recuerdos → 125 con 1.357).
3. **El cuello de botella es la llave:** pasar de una consulta corta a la isla correcta. Lo que nunca se probó es **expandir la consulta antes de proyectarla a la isla** (sinónimos, un salto sináptico, contexto de las búsquedas anteriores). Eso es justamente lo que hace el ciclo agente + cerebro: el agente ya trae contexto.
4. **Cobertura no es rescate:** que la isla contenga la respuesta no significa que el ranking mejore. Hay que medir siempre el neto (rescatados menos rotos).
5. **No inventar ejes** (Política A), y lo que el sistema crea solo **tiene que ser legible y no meterse en el catálogo como si fuera de fábrica** (decisión del 07-10).

---

## 5. Qué se podría sacar de las islas (ideas, todavía no medidas; conversar antes)

1. **Pistas por isla en el canal 2:** junto a `asociaciones_enriquecidas`, mostrar 2–3 recuerdos de la misma isla de significado que no estén ya conectados por sinapsis. Es ruido útil con sentido y no toca el orden.
2. **Que el sueño vuelva a ver islas:** que las dimensiones `tema_…` salgan de las islas de significado (o de un LPA con freno) en vez del LPA sobre sinapsis saturadas. Se recuperarían las "islas fantasma" como coordenadas para buscar sin texto.
3. **Higiene por isla:** dentro de una isla, señalar recuerdos que se contradicen por fecha (como el caso de postulación) para revisar, **sin borrar nada**.
4. **Corrección:** la idea de "desempate por isla del contexto" que el auditor propuso en la visión §2v **ya se probó en agosto como impulso de ranking y dio negativo**. Solo tendría sentido de otra forma (con el contexto de varias búsquedas como llave y midiendo el neto), y siempre ordenando, sin quitar nada.

**Primera medición que propondría (solo lectura, sobre copias, sin tocar el motor):**
- ¿Las islas de significado son **estables** entre sueños y entre bases distintas?
- En los ejercicios 1–3, ¿cuántas veces la pista útil o el recuerdo buscado estaba en la **misma isla** que el #1?

Todo con el OK de Dennys.

---

## 6. Huecos de conocimiento (todavía no investigados)

- Si `protocolo` en `escala_abstraccion` vino del mundo abierto o de otro camino.
- Para qué se usan hoy los 45 grupos WordNet en la búsqueda.
- Si existe en el disco de Dennys el documento "Ruta de madurez" que citan los scripts de agosto (no está en el repo).
