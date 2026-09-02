# Diagnóstico de la corrida `./scripts/run_qa_suite.sh` (2026-09-02)

Commit analizado: `c4f2f6f` — *feat(core): upgrade to v30.0 with scale-invariant normalization*
Comparado contra: `baseline_oficial_20260826.txt` (misma suite, 921 casos, DB viva)

---

## 0. Resumen ejecutivo

La suite **terminó en verde** (`set -e` no saltó) y hay dos victorias genuinas:

| | Baseline 2026-08-26 | Corrida 2026-09-02 | Δ |
|---|---|---|---|
| Falsos positivos (`negativo`) | 33/40 = **82.5 %** | 0/40 = **0.00 %** | ✅ −82.5 pp |
| `por_tema` Recall@1 | 46.15 % | **70.77 %** | ✅ +24.6 pp |
| `por_tema` MRR | 0.652 | **0.797** | ✅ +0.145 |
| Tiempo total | 2232 s | **1165 s** | ✅ −48 % |
| **Global Recall@5** | **97.39 %** (23 fallos) | **95.23 %** (42 fallos) | ❌ **−2.16 pp / +19 fallos** |
| Global Recall@1 | 86.27 % | 86.61 % | ≈ +0.34 pp |
| Global MRR | 0.904 | 0.900 | ≈ −0.004 |
| `sinonimo` Recall@5 | 91.80 % (5) | **73.77 %** (16) | ❌ −18.03 pp |
| `typo` Recall@5 | 98.46 % (1) | **90.77 %** (6) | ❌ −7.69 pp |
| `typo` Recall@1 | 75.38 % | 66.15 % | ❌ −9.23 pp |
| `variante_gramatical` R@5 | 89.23 % (7) | 86.15 % (9) | ❌ −3.08 pp |
| `pregunta_natural` R@5 | 98.46 % (1) | 96.92 % (2) | ❌ −1.54 pp |
| `cruce_idioma` R@1 | 62.50 % | 50.00 % | ❌ |
| Spreading activation | 25/921 (2.7 %) | 15/921 (1.6 %) | ⚠️ señal casi apagada |

**El CHANGELOG de v30.0 publica las cifras nuevas (0 % FP, 95.23 %, MRR 0.797) pero no
documenta la regresión** de `sinonimo` / `typo` / `variante_gramatical` / `pregunta_natural`
ni el coste en Recall@5 global. Ese es el hallazgo más importante de este informe: no es
que la suite falle, es que **la suite no puede fallar** (ver §4.1) y el informe no compara
contra baseline, así que una regresión de +19 fallos pasó como "FINALIZADA CON ÉXITO".

Desglose de los 42 fallos:

- **3** son basura de dataset (etiquetas oro obsoletas) → §1
- **3** son basura de dataset (misma query con dos etiquetas oro distintas; 2 de ellos ya
  están en la lista de fallos) → §1
- **~9** son fallos reales de ranking en capas de rescate (typo/variante/sinónimo) → §2
- el resto son ambigüedades de una sola palabra donde la etiqueta oro es arbitraria → §1

O sea: **el Recall@5 "real" ajustado es ~95.9 %**, no 95.23 %, y sigue por debajo del 97.4 %
de la baseline.

---

## 1. Problemas de datos en `scripts/casos_qa.jsonl` (6 fallos no son del motor)

### 1.1 Tres etiquetas oro apuntan a nodos que ya no existen

Verificado contra `MemoryBioRAG_Data/memory_biorag.db` (993 nodos):

| ID | `concepto_esperado` en el JSONL | ¿Existe en DB? | Nodo real |
|---|---|---|---|
| 0268 | `lección:_guardar_todo_lo_importante_inmediatamente,_no_esperar` | ❌ | `..._inmediatamente_y_no_esperar` |
| 0368 | `plugin_biorag-remember_v8.4_-_solo_session.idle,_sin_conteo_de_edits` | ❌ | `..._session.idle_y_sin_conteo_de_edits` |
| 0371 | `plugin_v7.1_fix:_session.idle_es_un_event,_no_un_hook` | ❌ | `..._es_un_event_y_no_un_hook` |

Los tres nodos fueron renombrados (coma → `_y_`) y el JSONL no se regeneró. En dos de los
tres casos **el motor devuelve el nodo correcto en TOP1 con score 0.935** y se cuenta como
fallo. Son fallos imposibles: `evaluar_qa.py:196` compara con `==` exacto.

Impacto: `literal` reporta 99.38 % cuando el valor real es **100.00 % (487/487)**, y el
global está subestimado en ~0.34 pp.

### 1.2 Tres queries idénticas con etiqueta oro contradictoria

```
'dimensiones'  → {cuando_usar_dimensiones_biorag, fix_busqueda_solo_dimensiones_sin_texto}
'compromiso'   → {compromiso-real-athena-clave-de-confianza, principio-memoria-hibrida-agente-naturalidad}
'biorag'       → {auto-consulta-permanente-biorag, protocolo_busqueda_biorag_automatica}
```

Un motor determinista **nunca** puede acertar las dos. Los IDs 0520/0740 (`dimensiones`) y
0811 (`biorag`) ya están en `casos_fallidos.jsonl`: son 2 fallos estructurales garantizados.

Causa raíz: `generar_casos_qa.py:205` elige `random.choice(sinonimos)` de cada nodo sin
verificar que el sinónimo sea **discriminativo**. Los 16 fallos de `sinonimo` son todos
sinónimos registrados y válidos del nodo esperado (verificado uno por uno), pero son
sinónimos genéricos compartidos:

| query | nodos que la contienen en `sinonimos` |
|---|---|
| `biorag` | 174 |
| `memoria` | 99 |
| `identidad` | 57 |
| `regla` | 47 |
| `dimensiones` | 42 |
| `arquitectura` | 27 |
| `buscar` | 25 |
| `perfil` / `agentes` | 18 |
| `dsl` | 16 |

Con `dimensiones` mapeando a 42 nodos, exigir TOP-5 a un nodo concreto es medir el ruido
del desempate, no la calidad del motor. Ejemplos del JSONL que ilustran el problema:
`familia → prueba_integridad_dennys_20260616`, `dsl → notebooklm-chat-configure`,
`universal → protocolo_enriquecimiento_busquedas`.

**Nota de tendencia:** la baseline ya tenía 5 fallos de `sinonimo` con las mismas queries
(0563 `memoria`, 0625 `dsl`, 0757 `buscar`). El dataset siempre fue ruidoso aquí; v30.0
amplificó el ruido de 5 → 16 porque ahora el desempate depende de un BM25 re-escalado
por pool (ver §2.1).

### 1.3 Arreglo propuesto (barato, ~30 líneas)

1. Regenerar etiquetas: por cada caso, verificar que `concepto_esperado` existe en la DB;
   si no, resolver por clave normalizada (`re.sub(r'[^a-z0-9]+','', unicodedata(...)`) y
   reescribir o descartar el caso con warning.
2. Marcar `ambiguo: true` en los casos cuyo `query` aparezca ≥2 veces con esperado distinto,
   y excluirlos del Recall global (reportarlos en su propia fila, como ya se hace con
   `negativo`).
3. En `sinonimo`, filtrar los sinónimos no discriminativos: descartar el caso si el
   sinónimo elegido aparece en `sinonimos` de > K nodos (K≈5) o si otro nodo lo tiene como
   token de `concepto`. Esto convierte 61 casos ruidosos en ~35 casos que sí miden algo.
4. Fijar la semilla de `random` en `generar_casos_qa.py` y versionar el JSONL: hoy la
   baseline y la corrida no son comparables caso a caso si alguien regenera.

---

## 2. Regresión de v30.0: la normalización Min-Max intra-query

### 2.1 Qué cambió exactamente

`core/memory_store.py:5246-5255`:

```python
raw_vals = [abs(v) for v in bm25_raw.values()]
if raw_vals:
    lo, hi = min(raw_vals), max(raw_vals)
    rango  = hi - lo if hi > lo else 1.0
    escala = min(1.0, hi) if hi > 0 else 1.0
    bm25_norm_map = {c: ((abs(v) - lo) / rango) * escala for c, v in bm25_raw.items()}
```

Antes: `|v| / (|v| + 3.0)` (sigmoide absoluta, documentada en `README.md:169`).

Simulación numérica de ambas fórmulas sobre tres pools reales:

```
pool rico (literal fuerte)      raw [12.0, 9.5, 6.0, 3.0, 1.0, 0.4]
  v29 → [0.800, 0.760, 0.667, 0.500, 0.250, 0.118]
  v30 → [1.000, 0.785, 0.483, 0.224, 0.052, 0.000]

pool débil (typo / variante)    raw [0.62, 0.55, 0.41, 0.30, 0.22, 0.15]
  v29 → [0.171, 0.155, 0.120, 0.091, 0.068, 0.048]
  v30 → [0.620, 0.528, 0.343, 0.198, 0.092, 0.000]   ← ×3.6 de amplificación

pool ruido (control negativo)   raw [0.12, 0.09, 0.05, 0.02]
  v29 → [0.039, 0.029, 0.016, 0.007]
  v30 → [0.120, 0.084, 0.036, 0.000]
```

Dos efectos, uno bueno y uno malo:

- ✅ **Bueno (explica el 0 % FP):** `escala = min(1, hi)` aplasta el BM25 cuando no hay
  match léxico sólido. El ruido ya no puede fabricar score. Es un cambio bien pensado.
- ❌ **Malo (explica typo/variante/sinónimo):** en un pool débil, el mejor candidato pasa
  de aportar `0.171 × 0.187 = 0.032` a `0.62 × 0.187 = 0.116` del score final. **BM25 se
  vuelve 3.6× más dominante justo en las queries donde BM25 es menos fiable** (typos,
  variantes gramaticales, una sola palabra ambigua). Las capas de rescate —trigramas
  (`origen="typo"`), `fallback_simbolico`, `dimensional_fallback`, PPMI— quedan sepultadas
  por un match léxico parcial.

Evidencia en los fallos reales: en los 6 casos de `typo` el nodo esperado **no aparece ni
en el top-3**, y lo que gana son nodos que comparten *una* palabra correcta de la query:

```
'arquitectura memovria biroag'  → gana hormiguita_arquitectura_6_capas (0.429)
                                  'arquitectura' es el único token léxico válido
'mentalidad biora paa agentes'  → gana identidad_esencia_vs_cerebro (0.202)
'identiduad y respheto oec'     → gana hermes_oec_identidad (0.263)   ← 'oec'
```

### 2.2 Bug estructural asociado: las capas de rescate no tienen BM25

`bm25_raw` solo se pobla desde filas FTS5 (líneas 4526, 4539, 4576, 4596, 4622, 4831).
Los candidatos que entran por trigramas (`4684`), simbólico (`4930`) o dimensional
(`5233`) **nunca** reciben `bm25_raw`, así que `bm25_norm_map.get(concepto, 0.0)` los
deja en 0.0.

Con la normalización absoluta eso era inocuo (todos los débiles valían ~0.05). Con Min-Max
es letal: la normalización es **relativa al pool**, y un candidato sin BM25 queda por
construcción por debajo del peor candidato con BM25. El nodo correcto rescatado por
trigramas compite con `bm25_norm = 0` contra un match parcial con `bm25_norm = hi`.

Esto es probablemente *la* causa de los 6 fallos de `typo` y buena parte de los 9 de
`variante_gramatical`.

**Fix propuesto (mínimo, preservando el 0 % FP):** dar a los candidatos de rescate un
BM25 sintético coherente con la escala del pool:

```python
# tras calcular lo/hi/escala, poblar candidatos sin bm25_raw
for conc, (origen, sc_capa) in origen_scores.items():
    if conc not in bm25_norm_map and origen in ("typo", "simbolico", "dimensional_fallback"):
        bm25_norm_map[conc] = hi_proxy * sc_capa     # hi_proxy = hi (magnitud del pool)
```

Alternativa más conservadora: cambiar Min-Max por `|v| / max(hi, 1.0)` — invariante a N
(que era el objetivo declarado), pero sin forzar a 0 al último candidato y sin amplificar
pools débiles. Requiere re-medir el 0 % FP porque pierde parte de la compresión de ruido.

### 2.3 La calibración conforme persistida ya no es válida

`calibracion_estado` en la DB viva:

```
umbral_conforme = 0.5233 | alpha = 0.1 | n_negativos = 33 | n_positivos = 300
n_nodos_corpus  = 926   | a_platt = 2.628 | b_platt = 0.2793
rango_negativos = '0.1318,0.5695'
```

Ese umbral se entrenó con **33 negativos**, es decir con la distribución de scores
*anterior* a v30.0 (la misma corrida que hoy da 0/40 FP). Dos problemas:

1. `rango_negativos = 0.1318–0.5695` describe una distribución que ya no existe: ahora los
   negativos salen muy por debajo. El umbral 0.5233 es demasiado permisivo para el scoring
   nuevo → en producción (`_debe_responder` / `nivel_certeza`) se aceptarán respuestas que
   la suite mediría como correctas y viceversa.
2. El Platt `(a=2.628, b=0.279)` mapea scores viejos a probabilidades. Aplicado a scores
   nuevos, `confianza_calibrada` está sistemáticamente sesgada.

Acción: recalibrar **después** de fijar la normalización definitiva, y añadir un test que
fallé si `fecha_calibracion` es anterior que el último cambio en `_calcular_score_hibrido`
o en la normalización BM25.

### 2.4 Los scores ya no son comparables entre queries (deuda arquitectónica)

Con Min-Max intra-query, `r[4]` es una magnitud **relativa al pool de cada consulta**.
Todo el código que compara un score contra un umbral absoluto quedó semánticamente roto:

| Umbral absoluto | Ubicación | Uso |
|---|---|---|
| `BIORAG_QCR_ESCAPE_CAPA_MIN = 0.60` | `memory_store.py:~5563` | escape de la puerta QCR |
| `0.80` atractor + `×0.70`/`×0.60` | GABA, `~5662` | inhibición lateral |
| `score_forzado = min(0.95, conf×0.95)` | promoción hub, `~5606` | TOP1 forzado |
| `BIORAG_FP_THRESHOLD = 0.25` | `evaluar_qa.py:~135` | medición de FP |
| `umbral_conforme = 0.5233` | `calibracion_estado` | decisión de responder |

Y el propio README (línea 1114) sigue documentando la fórmula vieja como "la misma que usa
Lucene internamente". La afirmación de v30.0 también es más débil de lo que parece: el
término `escala = min(1, hi)` **reintroduce dependencia de N** por la vía del IDF
(`hi ≈ log(N)`), así que la invarianza es asintótica, no exacta.

Acción sugerida: separar explícitamente dos cantidades — `score_relativo` (para ranking
intra-query, lo que Min-Max hace bien) y `score_absoluto` (para umbrales, gates y
calibración). Mezclarlas en un solo `r[4]` es lo que está generando los efectos raros de
§3.

---

## 3. El orden devuelto no es monotónico respecto al score devuelto

En `casos_fallidos.jsonl` hay **9 casos** donde `scores` no viene ordenado descendente,
p. ej.:

```
0368 literal            [0.5130, 0.4012, 0.4791]
0514 sinonimo 'perfil'  [0.7562, 0.6780, 0.7523]
0592 typo               [0.4289, 0.4086, 0.4246]
0639 pregunta_natural   [0.4399, 0.3524, 0.3700]
```

El 3.º resultado puntúa más que el 2.º. Hay dos causas, ambas localizadas:

1. **Promoción del Concept Hub** (`memory_store.py:~5603-5646`): cuando `hub_gana` es
   cierto se hace `resultados_con_hibrido.insert(0, entrada)` con
   `score_forzado = min(0.95, conf×0.95)`. Pero `hub_gana` se evaluó **antes** de comparar
   contra el TOP1 definitivo, y si el canónico ya estaba en la lista con score propio alto
   se sobrescribe con `score_forzado`, que puede ser *menor* que el del segundo. Caso 0368
   encaja exacto: hub `consenso_multi_modelo` con confianza ≈0.467 → `score_forzado
   ≈ 0.444`, insertado encima de un léxico de 0.513.
2. **Filtro `PALABRA_PREFIJO` para queries de una palabra** (`~5677-5700`): reconstruye la
   lista como `literal_validos + non_literal` **sin reordenar**, así que los no-literales
   (que suelen puntuar más alto) quedan detrás. Explica 0514 (`perfil`), 0592, 0822, 0878.

Por qué importa:

- Rompe el contrato de `buscar_por_frase`: un consumidor que corte por score (MCP,
  `biorag_recordar`, el umbral conforme) toma decisiones distintas que uno que corte por
  posición. `mcp_server.py` combina y reordena pools por `r[4]`, así que frase y ráfaga
  pueden devolver órdenes distintos para la misma consulta.
- Enmascara fallos: el nodo correcto puede estar "presente pero fuera de orden" y el
  reporte no lo distingue.

Fix (2 líneas): reordenar tras ambos post-procesos, y si la promoción del hub debe ganar
por posición, que gane también por score (`entrada[4] = max(score_forzado, top1 + ε)`),
no solo por índice.

---

## 4. Problemas estructurales de la suite

### 4.1 La suite no puede fallar

`run_qa_suite.sh` solo ejecuta pytest, `test_regresion_scoring.py`, `test_concept_hub.py`
y `evaluar_qa.py`. **`evaluar_qa.py` no llama a `sys.exit(1)` nunca**: escribe
`casos_fallidos.jsonl`, imprime el informe y termina en 0. Con `set -e`, la suite dice
"FINALIZADA CON ÉXITO" aunque el Recall caiga 20 puntos. La corrida de hoy es la prueba:
19 fallos nuevos y mensaje verde.

Fix: umbral de regresión en la suite, p. ej.

```bash
python3 scripts/evaluar_qa.py "$@"
python3 scripts/check_gate_qa.py --min-recall5 0.97 --max-fallos 23 \
    --baseline baseline_oficial_20260826.txt --fallidos scripts/casos_fallidos.jsonl
```

y que `evaluar_qa.py` emita además un `qa_metrics.json` machine-readable (hoy solo hay
texto para humanos, lo que obliga a hacer `grep` para comparar corridas).

### 4.2 El paso [3/4] no usa la copia aislada

`run_qa_suite.sh` exporta `BIORAG_PATH=$PARENT_DIR/MemoryBioRAG_Data/memory_biorag_qa_run.db`,
pero `scripts/test_concept_hub.py:62-65` **ignora la variable** y abre a pelo:

```python
db_path = os.path.join(..., "MemoryBioRAG_Data", "memory_biorag_test.db")
```

Se ve en tu propia salida:

```
[INFO] DB: .../MemoryBioRAG_Data/memory_biorag_test.db
[INFO] Nodos activos: 880   | Concept Hubs: 12 | Bridges: 78
```

Mientras la DB viva que sí evaluó el paso [4/4] tiene **993 nodos / 927 activos / 17 hubs /
119 bridges**. Consecuencias:

- El 5/5 TOP-1 del Concept Hub se midió sobre un corpus **distinto y más viejo** que el de
  producción. No es evidencia sobre la DB viva.
- El script llama `crear_tablas()` y `cargar_hubs_iniciales()` sobre esa DB, es decir
  **escribe** fuera del aislamiento que el wrapper promete ("protección total: original
  nunca se toca").
- `memory_biorag_test.db` no está en el repo y el `trap cleanup` no la borra: la suite deja
  basura persistente cuyo estado depende del orden de ejecución.

Fix: `db_path = os.environ.get("BIORAG_PATH") or <default>`, y que la suite genere esa DB
de test como copia de la aislada (o la limpie en el trap).

### 4.3 Doble copia de 60 MB y efectos de lado sobre la DB viva

- `run_qa_suite.sh` crea `memory_biorag_qa_run.db` y `evaluar_qa.py:60-79` vuelve a
  copiar esa copia a `memory_biorag_qa_temp.db`. Dos backups completos de una DB de 60 MB
  por corrida; el segundo no aporta aislamiento adicional.
- Más grave: `evaluar_qa.py` hace `UPDATE largo_plazo SET estado='activo'/'dormido'` caso
  por caso, y `buscar_por_frase(profundidad="profundo")` **despierta nodos y les sube el
  `peso_sinaptico`** (`memory_store.py:~5750`). Todo eso ocurre sobre la copia temporal…
  pero la DB viva ya tiene **66 nodos en estado `dormido`**, que son precisamente el
  residuo de haber corrido evaluaciones contra la DB real en el pasado (la baseline del
  26-08 se ejecutó con `BIORAG_PATH` apuntando directo a `memory_biorag.db`). Esos 66
  nodos dormidos alteran hoy los resultados de *cualquier* caso cuyo esperado no sea
  reactivado explícitamente.

Fix: (a) que `evaluar_qa.py` reutilice `BIORAG_PATH` si ya apunta a una copia (flag
`--no-copy`), (b) auditar y normalizar los 66 `dormido` de la DB viva, (c) que la suite
verifique al arrancar que `BIORAG_PATH != memory_biorag.db`.

### 4.4 Comparabilidad baseline ↔ corrida

La baseline se corrió con `Usando BIORAG_PATH configurado: .../memory_biorag.db` y la
corrida actual con `BIORAG_PATH no definido -> Usando DB viva del repo`. Apuntan al mismo
archivo, pero el *camino* es distinto (la baseline no pasó por la copia aislada). Además
entre ambas cambió la DB (993 nodos hoy vs. los 926 que vio la calibración). Cualquier
comparación de recall entre 26-08 y 02-09 mezcla **cambio de motor + cambio de corpus**.
Conviene congelar un snapshot de DB versionado (`scripts/generar_snapshot.py` ya existe)
como fixture oficial de la suite.

---

## 5. Plan de acción sugerido, por prioridad

| # | Acción | Esfuerzo | Efecto esperado |
|---|---|---|---|
| 1 | Regenerar/validar etiquetas oro (§1.1) y marcar ambiguas (§1.2) | 30 min | −6 fallos espurios; `literal` → 100 % |
| 2 | Gate de regresión + `qa_metrics.json` en la suite (§4.1) | 1 h | La suite vuelve a poder fallar |
| 3 | Reordenar tras promoción-hub y filtro `PALABRA_PREFIJO` (§3) | 15 min | Orden coherente con score |
| 4 | Poblar `bm25_norm` de candidatos de rescate (§2.2) | 1-2 h | Recuperar `typo`/`variante` |
| 5 | `test_concept_hub.py` respeta `BIORAG_PATH` (§4.2) | 10 min | [3/4] mide la DB real |
| 6 | Recalibrar `calibracion_estado` con el scoring definitivo (§2.3) | 30 min | Umbral y Platt válidos |
| 7 | Filtrar sinónimos no discriminativos en el generador (§1.3) | 1 h | `sinonimo` mide algo real |
| 8 | Separar score relativo vs. absoluto para umbrales (§2.4) | ½ día | Coherencia arquitectónica |
| 9 | Quitar la doble copia y auditar los 66 nodos `dormido` (§4.3) | 1 h | Aislamiento real + menos I/O |

Experimento de validación para #4: poner la normalización detrás de un flag
(`BIORAG_BM25_NORM=abs|minmax|rescate`) y correr la suite con las tres variantes sobre el
mismo snapshot. Si la hipótesis §2.1/§2.2 es correcta, `rescate` debe devolver `typo` a
≥98 % **sin** mover el 0 % de FP.

---

## 6. Correcciones a este diagnóstico (aplicadas en v30.1)

Este informe se escribió antes de implementar los arreglos. Dos afirmaciones resultaron
inexactas y una tercera se quedó corta; se corrigen aquí para que el documento no
circule con errores conocidos.

### 6.1 §1.1 era incorrecto: el rename no fue de puntuación

Se afirmó que los 3 nodos habían sido renombrados con "coma → `_y_`" y que una clave
normalizada (sin acentos ni puntuación) bastaba para resolverlos. **Falso**: `_y_` añade
el token `y`, así que las claves normalizadas no coinciden.

```
vieja  lección:_guardar_todo_lo_importante_inmediatamente,_no_esperar
       → clave: leccionguardartodoloimportanteinmediatamentenoesperar
actual lección:_guardar_todo_lo_importante_inmediatamente_y_no_esperar
       → clave: leccionguardartodoloimportanteinmediatamenteynoesperar   ← difieren
```

Se verificó empíricamente: la primera implementación del resolver (solo normalización)
reportó las 3 etiquetas como `inexistente`. La solución definitiva es de dos niveles —
clave normalizada y, si falla, coincidencia difusa con `difflib` acotada por ratio ≥ 0.94
**y** margen ≥ 0.02 sobre el segundo candidato. Sobre los 921 casos del dataset: 918
etiquetas correctas, 3 resueltas por vía difusa, **0 falsas resoluciones**.

### 6.2 §4.3 se quedó corto: el arnés no es determinista

Se documentó que la suite muta la DB viva y que quedan 66 nodos `dormido` como residuo.
El hallazgo real es más grave: **la evaluación no es reproducible ni siquiera contra la
misma copia y el mismo código.**

Mecanismo completo:

1. El setup hace `UPDATE largo_plazo SET estado='activo'/'dormido'` sobre el esperado de
   cada caso.
2. `buscar_por_frase(profundidad="profundo")` **despierta** nodos dentro del motor
   (`estado='activo'`, `peso_sinaptico += 0.15`).
3. Ambas mutaciones se acumulan: el caso N se evalúa sobre un corpus modificado por los
   N−1 anteriores. **46 de los 921 casos** tienen su nodo esperado `dormido` en la DB
   viva, así que el pool de candidatos crece de forma irreversible durante la corrida.

Evidencia: dos corridas consecutivas del mismo código difirieron en el caso `typo` 0513
(`denys-identidad-profunda`), que pasó de PASS a FAIL y volvió a PASS al añadirse el
restaurador de estado. La causa próxima no fue el fix de etiquetas —su nodo esperado puntúa
**0.1743, empatado con otro candidato y justo en el corte del top-5**, de modo que
cualquier perturbación del pool lo deja dentro o fuera. Se descartó la hipótesis inicial
(caso 0368 reactivando un nodo que compite con `dennys`) con un experimento aislado: con y
sin ese nodo activo el resultado es idéntico.

Consecuencia metodológica: **con ruido de ±1-2 casos por corrida no se puede validar ningún
fix de motor.** Cualquier comparación A/B sobre este arnés anterior a v30.1 —incluidas las
de este informe— tiene esa barra de error.

Corrección aplicada: snapshot del estado del corpus al arrancar y restauración tras cada
caso (`_restaurar_estado_nodos`). En la corrida de validación se revirtieron **117
mutaciones**.

### 6.3 Efecto medido de los arreglos

Misma DB, mismo sandbox, corridas consecutivas (921 casos, ~910 s cada una):

| Métrica | pre (v30.0) | post (v30.1) | Δ |
|---|---|---|---|
| Global Recall@5 | 95.01 % (44 fallos) | **95.66 % (38 fallos)** | +0.65 pp / −6 |
| Global Recall@1 | 86.83 % | **87.66 %** | +0.83 pp |
| Global MRR | 0.901 | **0.909** | +0.008 |
| `literal` | 99.38 % (3) | **100.00 % (0)** | 487/487 |
| `sinonimo` | 77.05 % (14) | **80.00 % (11)** | +2.95 pp |
| Fallos con scores no monotónicos | 9 | **0** | contrato restaurado |
| `negativo` (FP) | 0.00 % | **0.00 %** | preservado |
| `typo` / `variante` / `por_tema` | 89.23 / 86.15 / 92.31 % | idéntico | sin cambio |
| Tests unitarios | 34 | **56** | +22 |

Ningún caso que pasara antes falla ahora. Los 6 fallos eliminados son 0268/0368/0371
(etiqueta obsoleta) y 0520/0740/0811 (ambigüedad).

### 6.4 Estado del plan de acción (§5)

| # | Acción | Estado |
|---|---|---|
| 1 | Validar/reparar etiquetas oro y marcar ambiguas | ✅ hecho en `evaluar_qa.py` (resolución en tiempo de evaluación, no se reescribe el JSONL) |
| 2 | Gate de regresión + `qa_metrics.json` | ✅ hecho |
| 3 | Reordenar tras hub-promotion y `PALABRA_PREFIJO` | ✅ hecho (piso de promoción + guardia final) |
| 5 | `test_concept_hub.py` respeta `BIORAG_PATH` | ✅ hecho |
| 9 (parcial) | Aislamiento de estado por caso | ✅ hecho; falta eliminar la doble copia de 60 MB |
| 4 | Poblar `bm25_norm` de candidatos de rescate | ⏸ **pendiente — es lo que falta para cerrar la regresión** |
| 6 | Recalibrar `calibracion_estado` | ⏸ pendiente (hacerlo después de #4) |
| 7 | Filtrar sinónimos no discriminativos en el generador | ⏸ pendiente (11 fallos de `sinonimo` dependen de esto) |
| 8 | Separar score relativo vs. absoluto | ⏸ pendiente |

La regresión contra la baseline oficial **sigue abierta**: 95.66 % frente a 97.39 %. El
gate queda en rojo a propósito (`exit 1`) hasta que se resuelva el item 4.
