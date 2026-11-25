# Auditoría: discrepancias README ↔ código, estado de las neuronas y módulos desconectados

**Fecha:** 2026-11-25 · **Rama:** `arena/da3df5df-memorybiorag` @ `a6d271a` · **Versión de trabajo:** v36.2 (candidata, sin tag)

**Alcance.** Lectura completa del `README.md` (4644 líneas), de `buscar_por_frase` (`core/memory/search.py` 58–2930),
de todo el motor de ranking en `core/memory/` y de las tres neuronas, el Concept Hub, el camino MCP
(`core/mcp_server/search.py`) y los módulos apagados. Las importaciones se rastrearon con `grep`. Las mediciones se
hicieron sobre el snapshot oficial y sobre la **DB viva del usuario** (copias en `/tmp`, en solo lectura). **No se
cambió ni una línea del motor.**

**Estado del entorno verificado:** Python 3.11.2, `requirements.txt` + `pip install .`, `install.py` (CLI y handshake
MCP OK), **`pytest tests/` → 1104 passed, 84 subtests passed**.

---

## 0. Resumen en una línea por hallazgo

| # | Hallazgo | Gravedad | Evidencia |
|---|---|---|---|
| D1 | La señal de **recencia está muerta**: pesa 0.04 en el denominador pero nunca recibe valor | Alta (afecta todos los scores) | `search.py:2272-2293` no pasa `temporal`; `scoring.py:341` |
| D2 | **El MCP no se abstiene nunca por defecto**: la calibración solo se carga con `BIORAG_CALIBRACION_ACTIVA=1` | Alta (FP) | `umbral.py:275-278`; `.env.example:141` |
| D3 | **JSD se da por "rechazado", pero el JSD adaptativo E7 está ON** | Media | `constants.py:53` |
| D4 | SDM descrito como **1024 bits** en tres sitios del README; el código y el resto del README dicen 2048 | Baja (doc) | `README.md:2534, 2693, 4192` |
| D5 | El **número de señales** no cuadra: 12, 13 o 14 en el README, "17 agujas" en la neurona, 18 términos en la fórmula | Baja (doc) | `scoring.py`, `neurona.py:F_FORMULA` |
| D6 | El **hub entra por tres vías**: peso 0.20 en la fórmula + promoción a TOP1 + salto del QCR | Media (diseño) | `scoring.py`, `search.py:2395, 2470-2537` |
| D7 | **La QA no mide lo que ve el usuario**: en la DB viva la neurona tiene campeón y reordena | Media | §2.1 |
| D8 | **Abrir el cerebro puede escribir en la DB** (síntesis DMN en el constructor) | Media (norma de invariancia) | `memory_store.py:175` |
| D9 | **ADN y Neocórtex se instancian al abrir** aunque el ranking ADN está OFF | Baja (coste) | `memory_store.py:199-203` |
| D10 | La **neurona de puentes** recibe 2 de sus 15 entradas sin información | Baja | `concept_hub.py:1262, 1265` |
| D11 | El **QCR nunca vacía el pool base**: si ningún candidato pasa, se quedan todos | Info (diseño no documentado) | `search.py:2446` |
| D12 | Restos: `print [TRACE]`, comentario de "8 señales", una consulta SQL por candidato para la señal latente | Baja | `search.py:1057, 2828, 3286` |
| D13 | Los baselines de R@1 citados no coinciden entre sí (88.76 / 91.89 / 93.03) | Baja (doc) | `AGENTS.md`, `qa_con_neurona_20261025/LEEME.md`, `README.md` |
| **D14** | ~~BUG: `recordar` nunca devuelve fecha ni caducidad~~ → **CORREGIDO** (§6). Usaba la tabla `categorias` y la columna `nombre`, que no existen | Alta → resuelto | `core/mcp_server/search.py` `_leer_antiguedad_y_categoria` |
| **D15** | ~~El olvido (LTD) se cuenta por llamada a `consolidar`, no por tiempo transcurrido~~ → **CORREGIDO** (§7.1): el olvido se escala por el tiempo real desde el ciclo anterior | Alta → resuelto | `consolidation.py` `fraccion_de_noche` |
| D16 | Falso positivo real: «receta de arepas» devuelve 3 nodos de *10596 Recetas.exe* con «confianza media» (0.53). **No se arregla encendiendo la calibración**: también se abstiene en aciertos (§7.4). Requiere recalibrar con positivos | Media (consecuencia de D2) — **decisión de Dennys** | §5, §7.4 |
| D17 | ~~Formato de `dimensiones` incoherente~~ → **CORREGIDO** (§7.3): el ejemplo del aviso de `recordar` no era JSON y el propio `recordar` lo rechazaba | Baja → resuelto | `core/mcp_server/search.py` |
| D19 | ~~No determinismo del ranking~~ → **CORREGIDO** (§7.2). Causa: `[:5]` sobre un `set` de sinónimos WordNet, cuyo orden depende de `PYTHONHASHSEED` | Media → resuelto | `search.py` Capa 4; `fallback_simbolico.py` |
| D20 | ~~Test de temporizador inestable~~ → **CORREGIDO** (§7.3): el test verifica el reinicio sin depender del reloj | Baja → resuelto | `tests/test_idle_lease_release_f2.py` |
| D21 | ~~`biorag update` ocultaba el motivo accionable~~ → **CORREGIDO** (§7.3): «rama sin upstream», «HEAD separado», etc. salían como «contact support» | Baja → resuelto | `core/updater.py` |
| D18 | Higiene de datos: hay mensajes de la cartelera guardados como nodos con nombres automáticos sin sentido | Baja (datos, no código) — **no se toca la DB viva sin permiso** | §5 |

---

## 1. Discrepancias en detalle

### D1 — La recencia (`temporal`) nunca llega a la fórmula
- `_calcular_score_hibrido` acepta `temporal=0.0` y le da peso **0.04** (`scoring.py:341`).
- `_kw_hibrido` (`search.py:2272-2293`) **no incluye `temporal`**, así que siempre vale 0.
- Su peso **sigue sumando en el denominador**: `T = 1.39 + 0.15 (PPMI) + 0.05 (NCD) + 0.05 (episodio) + 0 (analogía) + 0.05 (campo) = 1.69`.
  Resultado: todos los scores quedan comprimidos alrededor de un 2.4 % (0.04/1.69) sin ninguna ganancia.
- La neurona tampoco ve esta señal (no está en `F_FORMULA`).
- **Decisión pendiente (Dennys):** pasar la recencia de verdad o quitar su peso. Cualquiera de las dos opciones **cambia todos los scores**:
  habría que volver a medir el baseline, re-calibrar el umbral y la neurona descartaría su campeón (cambia `huella_motor`).

### D2 — Abstención apagada por defecto
- `_debe_responder` solo filtra si `self._umbral_conforme` existe.
- `_cargar_calibracion_persistida` retorna sin cargar nada si `BIORAG_CALIBRACION_ACTIVA != "1"` (por defecto, `0`).
- Por eso el MCP **responde siempre**, aunque la DB tenga una calibración guardada:
  - Snapshot: umbral 0.6212, α 0.10, 10 negativos.
  - **DB viva:** umbral **0.53**, α **0.025**, **50 negativos**, calculado sobre 898 nodos (hoy hay 1381).
- La calibración de la DB viva **está desactualizada**: el corpus creció un 54 % desde entonces. Si se activa la abstención,
  conviene recalibrar antes (`calibrar_y_persistir`).

### D3 — JSD: "rechazado" en el README, activo en el código
- Lo que se rechazó (−0.34 pp) fue el **JSD estático** (`BIORAG_JSD_WEIGHT=0.0`).
- El **JSD adaptativo E7** (`BIORAG_JSD_ADAPTATIVO=1` por defecto) usa base 0.05, ×2.5 en consultas de 4 tokens o más y ×0.5 en las cortas.
  Entra como `(1−jsd_w)·fórmula + jsd_w·jsd`.
- El README debería distinguir las dos variantes.

### D4 — SDM 1024 vs 2048 bits
- El código (`constants.py`, "E1: SDM Kanerva (2048 bits)") y `README.md:14, 2371, 2438-2456` dicen **2048**.
- Siguen diciendo **1024**: el diagrama de `README.md:2534`, la tabla de `README.md:2693` (además dice "128 bytes/nodo"; con 2048 bits son 256) y `README.md:4192`.

### D5 — Cuántas señales hay
- Términos reales de la fórmula: 12 base (bm25, dim, concepto, sinónimos, peso, latente/cadena, grupo, temático, temporal, asoc, pred, hub)
  + PPMI + NCD + episodio + analogía + campo + JSD = **18**.
  - De esos, **dos valen siempre 0** con la configuración de fábrica: temporal (D1) y analogía (peso 0).
- La neurona habla de "17 agujas": incluye `match_exacto` y `sin95`, que son bonos, y excluye temporal, analogía y peso.
- El README usa 12, 13 y 14 según la sección. Hace falta fijar una sola tabla canónica.

### D6 — El Concept Hub cuenta tres veces
1. Dentro de la fórmula con peso **0.20**, el mayor junto con pred y por debajo solo de bm25 (0.25).
2. Los nodos canónicos **se saltan el QCR** (`hub_canonical_set`).
3. **Promoción posterior** a TOP1 si `min(0.95, conf·0.95) ≥ mejor léxico`.
- No es un error, pero el README lo presenta como una sola señal. Con 1114 hubs y 5165 puentes en la DB viva, el motor `escala`
  (umbral 0.40) es el que decide. El motor `idf` (0.55) tiene mejor precisión en el snapshot, pero no está probado a esta escala (`concept_hub.py:929-940`).

### D7 — La QA mide la fórmula; el usuario ve la fórmula más la neurona
- El snapshot **no tiene** la tabla `neurona_estado`, así que la QA oficial mide la fórmula sola.
- En la **DB viva**, la neurona tiene **campeón** y reordena:

  | Dato de la DB viva | Valor |
  |---|---|
  | Ciclos | 447 |
  | Preguntas | 580 |
  | Ascensos | 10 |
  | Retiros | 0 |
  | Reinicios | 15 |
  | Margen | 2.0 |
  | Guardia (fórmula sola → campeón) | 0.43 → **0.85** |
  | Huella | `5721b3821c3521e6`, igual a la del código actual: el campeón se carga |

- Aprende en **cada** `aprender` (`ingest.py:233`) y en cada consolidación (`consolidation.py:777`).
- La evidencia del 2026-10-25 (copia entrenada) daba R@1 91.89 → 94.97. Eso está bien, pero el número del README no es el que vive el usuario.
- `scripts/evaluar_qa.py` ya avisa; falta reflejarlo en el README.

### D8 — Abrir el cerebro puede escribir
- `SQLiteMemoryBioRAG.__init__` llama a `sintetizar_sinapsis_dmn` (`DMN_SINTESIS_ACTIVA=1` por defecto).
  Puede insertar hasta **8 sinapsis** `dmn_synthesized` (peso 0.30) entre las 40 semillas de mayor peso.
- Evidencia: 56 en el snapshot y **948 en la DB viva**.
- Al medir hoy sobre una copia de la DB viva, la apertura **no escribió nada** (948 → 948): las semillas ya están saturadas.
  No escribe siempre, pero puede hacerlo.
- **A medir:** si esto choca con la NORMA MÁXIMA `F(D,q)=F(D∪I,q)`. Una lectura (búsqueda) no debería poder alterar D.
  Proponer moverlo al ciclo de sueño o al DMN en reposo.

### D9 — Coste en la apertura sin uso
- Con `PPMI_VECTOR_WEIGHT > 0` (por defecto 0.15) se instancian `NeocortexTeleologico` y `ADNConceptualEngine` (`memory_store.py:199-203`).
- El ranking ADN (#14) está OFF (`BIORAG_ADN_RANKING_ENABLED=false`) y solo `core/memory/adn.py` los usa, detrás de ese flag.

### D10 — Neurona de puentes: entradas vacías
- En `concept_hub.py:1262` se pasa `idf_total=cobertura`, que **duplica** la entrada 1.
- En `concept_hub.py:1265` se pasa `margen=0.0` siempre: la entrada 14 nunca tiene información.

### D11 — El QCR nunca vacía el pool base
- Con corte de crecimiento (`baseline_rowid`): si ningún candidato base pasa el QCR, se conservan **todos** los base sin filtrar.
  Solo el overlay se filtra estrictamente.
- Sin corte: si nadie pasa, se conserva todo.
- Es coherente con "ningún ranking puede convertirse en filtro que elimine pistas", pero no está documentado.

### D12 — Restos de código
- `search.py:1057`: queda `print(f"[TRACE] 1.8 Snap: ...")`. En MCP no rompe nada (`server.py:176` protege stdout), pero ensucia la CLI y la QA.
- `search.py:2828` y `:3286` todavía hablan de "8 señales".
- Señal latente: una consulta SQL `MAX(peso_atenuado)` por candidato, dentro del bucle (O(k) consultas).

### D13 — Baselines distintos según el documento
- `AGENTS.md`: R@1 ≥ 88.76 % (gate mínimo).
- `qa_con_neurona_20261025/LEEME.md`: R@1 91.89 (fórmula sola, código `a72d1f0`).
- `README.md` (QA v36.0): R@1 93.03 %.
- Probablemente son versiones distintas, pero ningún documento lo dice explícitamente.

---

## 2. Las neuronas: ¿terminadas?

| Neurona | ¿Terminada? | ¿Conectada? | ¿Actúa hoy? |
|---|---|---|---|
| **1. Ranking** (`core/memory/neurona.py`) | **Sí** | Sí: `search.py` (vista/reordenar), `ingest.py` y `consolidation.py` (practicar) | **Sí en la DB viva** (campeón, margen 2.0). No en el snapshot de QA |
| **2. Puentes** (`core/memory/neurona_puentes.py`) | **No.** Falta el entrenador (`scripts/entrenar_neurona_puentes.py`, "a construir"), la guardia y la medición ON/OFF en la QA | Solo desde el motor `idf` del hub (`concept_hub.py:1226`) | **No.** Inerte por partida doble: el motor de fábrica es `escala` y los pesos nacen neutros (v=0 → 1.0). No existe la tabla `neurona_puentes_estado` ni en el snapshot ni en la DB viva |
| **3. Asociativa** (`core/neurona_asociativa.py`, asoc-1) | **Sí como pieza** (calibrada, examinada, cerrada) | **No.** Ningún archivo de `core/` la importa; `Juez` nunca se instancia. Solo la usa `tests/test_neurona_asociativa_motor.py` | **No.** Su sitio propuesto (elegir qué asociaciones ve el agente, canal 2) está pendiente |

---

## 3. Módulos desconectados o fuera de la búsqueda

| Módulo | Estado real | Quién lo llama |
|---|---|---|
| `core/rrf_fusion.py` (278 líneas) | **Huérfano total** | Nadie (ni código ni tests) |
| `core/hipotesis_teleologica.py` | Huérfano en producción | Solo una demo en `docs/¿Cuál es la Meta Final…/demo_vivo_neocortex.py` (la tabla `hipotesis_teleologicas` sí está en `schema.py:305`) |
| `core/feedback_implicito.py` | Se ejecuta a mano (`python3 core/feedback_implicito.py <db>`) | `scripts/verificar_contaminacion_log.py`. En la DB viva, solo 9/149 filas de `log_busquedas` tienen `util` |
| `core/sueno_vacios.py` | Solo fuera de línea | `sleep_cycle.py:41` |
| `core/adn_conceptual.py` + `core/neocortex_teleologico.py` | Se instancian, pero el ranking ADN está OFF | `memory_store.py`, `dmn_engine.py`, `core/memory/adn.py` (con flag) |
| `core/memory/neurona_puentes.py` | Inerte (§2) | `concept_hub.py` (solo con el motor `idf`) |
| `core/neurona_asociativa.py` | Desconectada (§2) | Solo su test |

**Interruptores apagados por defecto** (`core/memory/constants.py`):
- Rerank Jaccard (`BIORAG_RERANKING_JACCARD_ENABLED=0`; α 0.25, gate 0.04, top-k 20, ventana 50).
- Convergencia multiplicativa Spec-006 (`BIORAG_CONVERGENCIA_006_ACTIVA=0`).
- Multihop, `DIM_ESCAPE`, `DIM_RESONANCIA`, analogía (peso 0), expansión de episodio, ranking ADN, BM25 bayesiano, JSD estático.
- Calibración/abstención (`BIORAG_CALIBRACION_ACTIVA=0`).
- Auto-paráfrasis y auto-dimensiones del MCP (`BIORAG_MCP_AUTO_PARAFRASIS=0`, `BIORAG_MCP_AUTO_DIMS=0`).

---

## 4. Orden real de los rerankers en `buscar_por_frase` (como referencia para corregir el README)

| # | Paso | Estado por defecto |
|---|---|---|
| 1 | Sort y promoción `lexico_aprendido` (≥ 0.88 + 0.10·conf) | ON |
| 2 | QCR (IDF, umbral 0.40; segunda oportunidad por typo con piso 0.35 y Levenshtein 2; escape 0.60) | ON |
| 3 | Promoción competitiva del canónico del hub (conf ≥ 0.4) | ON |
| 4 | Rerank Jaccard | **OFF** |
| 5 | GABA: si el top-1 ≥ 0.80, los que estén por debajo de 0.70·top se multiplican por 0.60 | ON |
| 6 | Filtro de prefijo de palabra (consultas de 1 palabra, solo orígenes literales) | ON |
| 7 | Orden monotónico | ON |
| 8 | Bono de evidencia multicampo (tope 0.085, solo dentro del top-k visible) | ON |
| 9 | Despertar de dormidos (solo `profundo`) | — |
| 10 | Neurona 1 (top-k de la página 1, solo con campeón) | ON |
| 11 | Expansión de episodio y ADN #14 | **OFF** |

**Camino MCP (`recordar`):**
1. Pool de `limite·3`; la convergencia se aplica sobre `limite`.
2. Ráfaga si `score_base_top < 0.5`; se mezcla, se reordena y se recorta.
3. `_debe_responder` (no hace nada salvo con D2 activado).
4. Filtros por fecha y autor, staleness y canal 2 (asociaciones adjuntas, sin tocar el ranking).

---

## 5. Uso real del MCP contra la DB viva (2026-11-25)

**Método.** Cliente MCP stdio real (`mcp` SDK) contra `mcp_server.py`, siguiendo el protocolo de la propia herramienta: descomponer la pregunta y llamar a `recordar` con consulta, paráfrasis, `sustantivos_clave` y, si hace falta, ráfaga y `asociados`.
- Las **lecturas** se hicieron sobre la DB viva. Solo escriben `log_busquedas`, accesos y la práctica de la neurona, igual que cualquier agente.
- Las **escrituras** (`aprender` y `consolidar`) se hicieron **solo sobre copias** en `/tmp`.

### 5.1 Recuperación: lo que funciona muy bien

| Pregunta (con palabras del agente) | Top-1 | Score | Certeza |
|---|---|---|---|
| ¿Qué es BioRAG y en qué versión va? | `version_actual_biorag` (v36.2) | 1.00 | evidencia_directa |
| ¿Qué es la Neurona? | `version_actual_biorag_v34_0_20261024` | 0.88 | evidencia_directa |
| Ingeniería inversa de un ejecutable protegido | `recetas_10596_5_parches_binarios_themida` | 0.48 | — |
| Con errata: «ingenieria socail carlos pepe busjer» | `sello_seguridad_desconocidos_no_validados` | 0.63 | confianza media |
| Multi-hop: decisión sobre el nodo basura «última versión» | `leccion_verificar_nodo_sin_nombrarlo_para_no_rescatarlo` | 0.52 | confianza media |
| Ráfaga: «cuando Dennys se emocionó» | `momento_gratitud_dennys_athena_2026-10-08` (6/6 pertinentes) | 0.52 | confianza media |
| Trampa del benchmark con nodos dormidos (en español) | `leccion_eliminacion_ppr_v251_tras_evidencia_real` | 0.46 | confianza media |
| Pregunta fuera del dominio: «capital de Mongolia» | (nada relevante) | 0.23 | **sin_evidencia_directa** ✔ |

- **Latencia:** la primera consulta tarda de 6 a 8 s (carga perezosa de índices); las siguientes, de 0.4 a 4 s.
- **Asociaciones enriquecidas:** dan una vecindad útil (familia OEC, identidades, versiones).

### 5.2 Lo que falla o se puede mejorar

**D14 — Fecha y caducidad muertas.**
- La consulta de `core/mcp_server/search.py:713-717` es `SELECT concepto, creado_en, c.nombre FROM largo_plazo l JOIN categorias c ...`.
  En el esquema real (`schema.py:125`) la tabla es `categories(id, name, ...)`, así que lanza `OperationalError` y el `except Exception: pass` lo oculta.
- Efecto en cada resultado: `fecha_legible = null`, `timestamp_creado = 0`, `edad_dias = 0` y `stale = false` siempre.
- `BIORAG_STALE_HARD_CUTOFF` (líneas 726-735) tampoco puede actuar.
- La descripción de la herramienta promete `fecha_legible` («permite razonar sobre CUÁNDO pasó algo»).
- **No hay ningún test** que lo cubra: `grep fecha_legible tests/` no devuelve nada.
- **Arreglo propuesto (una línea; no tocado):** `SELECT l.concepto, l.creado_en, c.name FROM largo_plazo l LEFT JOIN categories c ON c.id = l.categoria`, más un test que exija `fecha_legible` no nulo.
- **Antes de mergear:** con el arreglo se reactiva el marcado `stale` (más de 90 días, salvo Principle/Profile/Personal/Relation). Hay que medir su efecto en la QA.

**D15 — El olvido cuenta llamadas, no noches.**
- El LTD (`consolidation.py:407-448`) resta entre 0.01 y 0.10 × categoría × prioridad (NULL → 1.5×) por cada `consolidar`, sin mirar el tiempo real transcurrido desde el ciclo anterior.
- Después duerme todo lo que quede con peso ≤ 0.05 (línea 476).
- En la DB viva hay unos 900 nodos con peso de 0.1 a 0.3 (583 en 0.2, 174 en 0.3, 142 en 0.1).
- Medido en copia:

  | Ciclos `consolidar` seguidos | Activos | Dormidos |
  |---|---|---|
  | 0 (DB viva) | 1380 | 1 |
  | 1 | 1329 | 57 |
  | 3 (en ≈1 minuto) | 485 | **900** |

- La descripción de `consolidar` y la respuesta de `aprender` piden «consolidar después de aprender». Un agente que guarda 3 cosas y consolida 3 veces envía a dormir dos tercios de la memoria en un minuto.
- `metricas_historial` muestra el mismo patrón en la vida real: ciclos con 169, 183 y 599 dormidos y un `olvido_promedio` de 317. Después se despiertan por búsquedas o ráfaga (el «efecto observador» ya documentado en `leccion_efecto_observador_biorag_fase15_despierta_nodos`).
- **Propuesta a decidir (sin tocar):** escalar el LTD por `Δt` desde el último ciclo (por ejemplo `min(1, Δt/24h)`), o separar «fijar corto plazo» de «noche de olvido».

**D16 — Falso positivo con respuesta segura.**
- «receta arepa pabellón criollo» → `recetas_10596_extraccion_html_runtime_padre_hijo` (0.53), `..._directivas_dennys_crack_binario` (0.53) y `..._heserver_servidor_interno_wine_hosts` (0.51), todos con `nivel_certeza = relacionado_confianza_media`.
- Es un solapamiento puramente léxico («receta»). Con D2 apagado, el MCP lo entrega igual.
- En cambio, «precio del bitcoin» → `proyecto_calculadora_inversion_cripto` (0.72) es un acierto razonable.

**Recall en inglés.** «benchmark trap dormant nodes evaluated as active» no trae el nodo correcto en el top-3 (máximo 0.33). La misma idea en español lo trae en top-1. El corpus está en español; los *bridges* no cubren inglés.

**D17 — Formato de `dimensiones`.**
- `aprender` rechaza `"accion_fallar,accion_evaluar"` y exige `{"intencion":["accion_fallar",...]}`.
- El aviso que imprime `recordar` sugiere `dimensiones='intencion_aprender'`.
- Además, `aprender` exige `busqueda_previa=True`, exactamente 5 *bridges* (sinónimo, problema, solución, situación, ingenuo) y avisa si `syn` tiene menos de 8 términos.
  Todo esto está bien diseñado (obliga a pensar cómo se recuperará el recuerdo), pero cuesta 3-4 reintentos al primer uso. Convendría un único mensaje de error que liste todos los requisitos que faltan.

**Ida y vuelta (en copia).**
- Nodo guardado con 3 sinónimos y 5 *bridges* → se recupera en top-1 (0.40) con la frase del *bridge* «ingenuo».
- **No** se recupera con «quien instalo el sistema en otra computadora» («computadora» no está en ningún campo). Confirma el aviso del sistema: con menos de 8 sinónimos, el nodo queda casi isla.

**D18 — Higiene de datos.** Hay nodos cuyo contenido es un mensaje de la cartelera y cuyo nombre es una concatenación automática sin sentido:
- `identidad_sesion_dennys`, `athena_hermanas_necesito`, `athena_artemis_athena` y `activos_dormidos_athena` (este empieza con «activos:804 dormidos:489»).
- `sello_seguridad_desconocidos_no_validados_sello_seguridad` (duplicado del sello).
- `pepe_busger_reencadre`.

Aparecen como ruido en las búsquedas sobre el contador PPMI y la ingeniería social. Revisarlos a mano y fusionarlos o archivarlos lo decide Dennys.

**Otros.** `concept_hub_buscar("como empiezo una sesion nueva con la memoria")` → sin match; ningún hub cubre el arranque de sesión. `estado_dmn` → «DMN no iniciado en esta instancia».

---

## 6. Corrección aplicada — D14 (fecha y caducidad en `recordar`), 2026-11-25

**Decisión.** Se aplica el diseño ya acordado y guardado en memoria (`athena_principio_caducidad_temporal`, origen Dennys: *«ve la fecha, eso no se te entrega si es muy viejo. Es como tu cerebro.»*):
- Más de 90 días → `stale` (marca de recuerdo viejo).
- Categorías atemporales protegidas: Principle, Profile, Personal y Relation.
- No se inventan categorías nuevas: lo que pide `decision_diseno_actualizar_nodo_canonico...` es «lo más simple posible y correcto».

### 6.1 Cambio
- **Función nueva** `_leer_antiguedad_y_categoria(cursor, conceptos)` en `core/mcp_server/search.py`:
  - `largo_plazo.creado_en`, con `LEFT JOIN categories` por `name`.
  - Respaldo en `corto_plazo.timestamp` para los nodos aún no consolidados.
  - Lotes de 900 conceptos.
  - Si falla, **lo registra** con `logger.warning` en lugar del `except: pass` mudo.
- **Cobertura:** la usan los resultados primarios **y** los vecinos de `context_window`, que antes nunca tenían fecha.
- **Lo que no cambia:** el ranking, los scores, `confianza_calibrada`, `nivel_certeza`, la paginación y `BIORAG_STALE_HARD_CUTOFF` (sigue en 0, apagado).
  - El principio guardado menciona un corte duro de 365 días, pero el código lo trae apagado por defecto. No se activa: excluir resultados convertiría la edad en un filtro (decisión pendiente de Dennys; hoy el nodo más antiguo tiene unos 158 días).

### 6.2 Verificación
| Prueba | Resultado |
|---|---|
| `tests/test_recordar_fecha_y_caducidad.py` (4 tests nuevos: fecha y edad exactas; 90 días con Principle protegido; vecinos con fecha; corto plazo y error registrado) | 4/4 pasan con el arreglo; **4/4 fallan con el código anterior** (el test detecta la regresión) |
| A/B MCP real: 12 consultas (ráfaga, `deep`, página 2, `context_window`, asociados) sobre copias idénticas de la DB viva | Orden, scores y certeza idénticos. Fechas: 0/52 → **52/52**; los vecinos también traen fecha |
| Efecto en la DB viva (solo lectura) | 773 de 1381 nodos quedarían marcados `stale` (más de 90 días y no protegidos). El aviso aparece en unas 6 de cada 12 consultas |
| Suite completa con la máquina libre | **1108 passed** (1104 previos + 4 nuevos), 84 subtests, 0 fallos (319 s). Con A/B corriendo en paralelo falló una vez D20 (inestable, igual en el código original) |

### 6.3 Hallazgos durante la verificación (no causados por el arreglo)

**D19 — No determinismo.** En la consulta «version actual biorag», las posiciones 3 y 4 alternan entre dos variantes, cada una reproducible al decimal:
- `v26_4` (0.8456) y luego `v32_4` (0.7862);
- `v32_4` (0.8456) y luego `v26_4` (0.7628).

Aparece **con el código original y con el arreglado**: original 3/3 con la primera variante en una máquina libre, y la segunda variante bajo carga y en la primera llamada en frío. El campo `total` también varía entre ejecuciones del mismo código (186 frente a 152). Sospecha: algún componente con presupuesto de tiempo o carga perezosa (por ejemplo `BIORAG_NEURONA_PRESUPUESTO_S=3`, o índices que todavía no terminaron de cargar). Choca con la NORMA de determinismo de `AGENTS.md`, así que **merece una investigación propia**.

> **Actualización:** la sospecha del presupuesto de tiempo era falsa. La causa real se detalla en §7.2 y ya está corregida.

**D20 — Test inestable.** `test_idle_lease_release_f2.py::test_idle_timer_reset_on_each_access` usa `sleep(0.5)`/`sleep(0.6)` contra un temporizador de 2 s.
- Falla 3/3 al correr su archivo solo, igual con el código original.
- Pasó en las suites completas anteriores.
- En otra ejecución bajo carga falló su vecino `test_reopen_during_maintenance_raises_biorag_busy`.

Depende del tiempo de la máquina, no del código de búsqueda.

---

## 7. Correcciones aplicadas — D15, D19, D17, D20 y D21 (2026-11-25)

### 7.1 D15: olvido proporcional al tiempo real
**Problema.** `ciclo_sueno_consolidacion` resta una «noche» entera de olvido (LTD de nodos y decaimiento ×0.95 de las sinapsis) **cada vez que se llama**.
- En la DB viva hubo 753 ciclos en 5 meses (4.8 al día), con una mediana de **23 minutos** entre ciclos y 37 intervalos de menos de 1 minuto.
- Cada sesión de trabajo «envejecía» la memoria varios días.

**Cambio.**
- `fraccion_de_noche()` lee la hora del ciclo anterior (`MAX(metricas_cognitivas.timestamp)`) y devuelve `min(1, Δt / 24 h)`.
- El LTD y el decaimiento sináptico se multiplican por esa fracción. Para las sinapsis se usa `0.95 ** fracción`, que encadenado da lo mismo que una noche.
- Con fracción parcial se guarda con 4 decimales (6 en las sinapsis). Si no, `round(0.20 − 0.004, 2)` volvería a 0.20 y el olvido de los ciclos cortos se perdería en el redondeo.

**Garantías.**
- Con 24 h o más desde el ciclo anterior (o una DB sin historial) el resultado es **idéntico** al anterior.
- `BIORAG_LTD_POR_TIEMPO=0` restaura el comportamiento viejo.
- `BIORAG_LTD_NOCHE_HORAS` ajusta la duración de la «noche».

**Simulación** sobre una copia de la DB viva, con un reloj simulado: 5 ciclos cada 23 minutos y uno tras 24 h.

| Ciclo | Antes (activos / dormidos) | Ahora (activos / dormidos) |
|---|---|---|
| inicio | 1380 / 1 | 1380 / 1 |
| 1 (+23 min) | 1355 / 30 | 1384 / 1 |
| 2 (+23 min) | 748 / 637 | 1384 / 1 |
| 5 (+23 min) | 470 / 915 | 1384 / 1 |
| 6 (+24 h) | 455 / 930 | 1353 / 32 |

Antes, una tarde de trabajo dormía dos tercios de la memoria. Ahora un día real duerme 31 nodos, igual que una noche del diseño original (30).

### 7.2 D19: causa real del no determinismo
- `core/memory/search.py`, Capa 4: `palabras_sin.extend([w for w in expandir_query_wordnet(...) if len(w) >= 3][:5])`.
- `expandir_query_wordnet` devuelve un `set`, y el orden de un set de strings depende de `PYTHONHASHSEED`, que es aleatorio en cada proceso.
- Los «5 primeros sinónimos» cambiaban entre procesos:
  - semilla 4: `edition`, `verdadero`, `existent`…
  - semilla 5: `verdadero`, `edition`, `variant`…
- Eso cambiaba el pool (195 frente a 179 candidatos). Con el pool cambiaba `_afinidad_temporal_pool` (`episodio_score` de `v26_4` pasaba de 0 a 1) y, al final, el orden.
- Ni la carga de la máquina ni el presupuesto de la neurona tenían que ver.

**Cambio.**
- `expandir_palabra_wordnet_ordenada` y `expandir_query_wordnet_ordenada` (`core/fallback_simbolico.py`) siguen un orden de relevancia estable:
  - tokens en el orden de la consulta;
  - synsets en el orden de WordNet (sentido más frecuente primero);
  - lemas en español antes que en inglés.
- El conjunto de sinónimos no cambia, solo su orden.
- Las funciones antiguas basadas en `set` siguen disponibles para el resto de llamadores, que no recortan.

**Verificación.**
- Semillas 0-13: salida idéntica en las 14 (antes había 2 variantes).
- QA oficial con las semillas 4 y 5, antes y después del arreglo: ver §7.5.

### 7.3 D17, D20 y D21
- **D17.** El aviso `dimensiones=None` de `recordar` sugería `dimensiones='intencion_aprender'`, que no es JSON, y el propio `recordar` lo rechazaba. Ahora sugiere `'{"intencion": ["intencion_aprender"]}'`. El test pasa los ejemplos del aviso por el validador real.
- **D20.** La causa era que `get_cerebro` arma el temporizador **antes** del arranque en frío del singleton. Con la máquina cargada el arranque superaba los 2 s del test y el temporizador vencía. El test ahora verifica el reinicio sin depender del reloj:
  - el temporizador viejo queda cancelado;
  - el nuevo está vivo y no ha disparado.
- **D21.** Con `biorag update --dry-run` aparecía «could not safely start the update… contact support». La causa real era `UPSTREAM_REQUIRED`: la rama de trabajo no tiene upstream, algo normal en este sandbox. Ese motivo, y otros 8 accionables del preflight, ahora se muestran. Los errores desconocidos siguen con el mensaje genérico y sin filtrar detalles internos.

### 7.4 D16: por qué no se arregla con un interruptor
Prueba en una copia de la DB viva con la calibración guardada (umbral 0.53, 50 negativos, **0 positivos**, agosto de 2026):

| Consulta | Calibración OFF (hoy) | Calibración ON |
|---|---|---|
| receta de arepas | 3 falsos positivos | se abstiene ✔ |
| pizza napolitana con masa madre | 3 falsos positivos | se abstiene ✔ |
| version actual de biorag | acierto | acierto |
| neurona de ranking campeon | acierto | acierto |
| principio de caducidad temporal | **acierto exacto (top-1)** | **se abstiene ✘** |
| que piensa dennys de la memoria | resultados relevantes | **se abstiene ✘** |

Encenderla cambia falsos positivos por falsos negativos. El arreglo correcto es recalibrar con positivos reales, por ejemplo con `log_busquedas` marcado como útil. Queda como decisión de Dennys.

### 7.5 Verificación conjunta
| Prueba | Resultado |
|---|---|
| QA oficial (`casos_qa_baseline_v1`, snapshot `qa_escape_qcr_20260811`): semillas 4 y 5, antes y después | **4 de 4 ejecuciones idénticas, categoría por categoría.** R@5 100%, R@1 93.03%, MRR 0.957, FP 0/40 y gate OK. La QA no cubría la consulta afectada por D19, así que el arreglo no mueve ninguna métrica |
| Determinismo: «version actual biorag», semillas 0-13 | 14/14 idénticas (antes, 2 variantes) |
| A/B del MCP real (12 consultas, copias idénticas de la DB viva, `PYTHONHASHSEED=0`) | 12/12 con orden y scores idénticos. Única diferencia: el texto corregido del aviso D17 |
| Tests nuevos: `test_ltd_por_tiempo_y_sinonimos_estables.py` (7), `test_updater_motivo_accionable.py` (6) y el test del aviso en `test_recordar_fecha_y_caducidad.py` | Todos pasan con el arreglo y **fallan con el código anterior**. Por ejemplo, con el código anterior un `consolidar` lanzado un minuto después del anterior le quitaba 0.13 de peso a un nodo; ahora le quita menos de 0.005 |
| Tests existentes ajustados | `test_memory.py`: dos tests de LTD lanzaban `consolidar` seguidos esperando una noche de olvido; ahora simulan la noche (`metricas_cognitivas.timestamp − 24 h`). `test_idle_lease_release_f2.py`: D20 |

**Lección registrada.** Una primera versión del ejemplo D17 llevaba llaves y rompió 6 tests. Los clientes extraen el JSON de la respuesta de `recordar` desde la primera `{`, así que **los avisos que van delante del JSON no pueden contener llaves**. El test del aviso lo comprueba ahora.
