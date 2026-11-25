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
