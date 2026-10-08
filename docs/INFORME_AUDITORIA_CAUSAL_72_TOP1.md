# INFORME DE AUDITORÍA DIAGNÓSTICA Y ATRIBUCIÓN CAUSAL DE LOS 72 FALLOS TOP-1 (v32.4)

> **Misión:** Atribución cuantitativa y metodológica de los 72 casos que ingresan al Top-5 pero no obtienen la posición #1 en el benchmark QA congelado.  
> **Invariante Metodológica:** Cero modificaciones en el motor de búsqueda, pesos, umbrales, Hub, WordNet, PPMI, MMR, calibración o candidate generation. Fase exclusiva de auditoría e instrumentación.

---

## 1. Metadatos del Experimento y Reproducibilidad

### 1.1 Identificadores Criptográficos Congelados
| Parámetro | Valor Verificado |
|---|---|
| **Commit SHA** | `32657b652f6941161720a117232770f25a5feaed` |
| **Versión Oficial** | `v32.4` |
| **Snapshot SHA-256** | `c3b88ae61bda1c0d2d4b6066d253a41b68f88e8d12b338b278c8442a1228dddc` (`snapshots/qa_escape_qcr_20260811.db`) |
| **Dataset SHA-256** | `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c` (`scripts/casos_qa_baseline_v1.jsonl`) |
| **Total Casos en Dataset** | 921 casos |
| **Controles Negativos** | 40 casos (0 FP · 0.00%) |
| **Queries Ambiguas Contradictorias** | 6 casos (aisladas formalmente del Recall) |
| **Consultas de Recuperación Efectiva** | 875 consultas |
| **Recall@5 Global Observado** | **100.00% (875 / 875)** |
| **Recall@1 Global Observado** | **91.77% (803 / 875)** |
| **Total Fallos Top-1 (Gold en Top 2..5)** | **Exactamente 72 casos** |

---

### 1.2 Demostración de Reproducibilidad en 3 Réplicas Consecutivas
Se ejecutó la suite de auditoría instrumentada [`scripts/audit_72_top1_misses.py`](../scripts/audit_72_top1_misses.py) en 3 réplicas consecutivas independientes, clonando el snapshot mediante `sqlite3.backup()` y restaurando el estado inicial de nodos tras cada consulta:

| Métrica / Parámetro | Réplica #1 | Réplica #2 | Réplica #3 | Coincidencia Bit-a-Bit |
|---|---:|---:|---:|:---:|
| **Recall@5** | 875 / 875 (100.0%) | 875 / 875 (100.0%) | 875 / 875 (100.0%) | ✅ 100% Idéntico |
| **Recall@1** | 803 / 875 (91.77%) | 803 / 875 (91.77%) | 803 / 875 (91.77%) | ✅ 100% Idéntico |
| **Total Misses Top-1** | 72 | 72 | 72 | ✅ 100% Idéntico |
| **IDs de Misses (0000..0874)** | Lista idéntica | Lista idéntica | Lista idéntica | ✅ 100% Idéntico |
| **Ganador & Rango de cada Gold** | Idéntico en los 72 | Idéntico en los 72 | Idéntico en los 72 | ✅ 100% Idéntico |
| **Scores y Márgenes** | Idéntico en los 72 | Idéntico en los 72 | Idéntico en los 72 | ✅ 100% Idéntico |
| **Clasificación Causal / Temporal** | Idéntico en los 72 | Idéntico en los 72 | Idéntico en los 72 | ✅ 100% Idéntico |

> **Declaración de Reproducibilidad:** *La auditoría instrumentada es 100% reproducible bajo este entorno y protocolo.*  
> **Explicación sobre la variación histórica 71 vs. 72:** En ejecuciones sin protocolo de aislamiento estricto, la variación de 1 caso surge de empates infinitesimales en la frontera Top-5 (ej. caso 0513 con scores idénticos), donde el ordenamiento sin clave secundaria estricta (`ORDER BY score DESC, concepto ASC`) o la iteración sobre `set(tokens)` sin `PYTHONHASHSEED` fijado produce indeterminismo en el último puesto. Bajo el protocolo auditado con aislamiento de snapshot, la salida es determinista y estable en 72 fallos.

---

## 2. Marco Epistemológico Tripartito

Para evitar confusiones entre mediciones algebraicas e inferencias de causalidad, todos los datos se presentan bajo tres niveles epistemológicos rigurosos:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. NIVEL DESCRIPTIVO                                                        │
│    Diferencia cruda observada en señales (Winner - Gold: Δ_crudo)           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. NIVEL CONTRIBUTIVO (Matemático / Algebraico)                             │
│    Aporte ponderado exacto dentro de _calcular_score_hibrido():             │
│    Δ_ponderado = w_i × base_weight × Δ_crudo                                │
│    + Efecto de promoción externa posterior (piso_promocion_hub)             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. NIVEL DE HIPÓTESIS CAUSAL                                                │
│    Inferencia sobre el factor dominante del desplazamiento (requiere prueba │
│    contrafactual formal para considerarse demostración causal definitiva)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Desmitificación y Diferenciación de Mecanismos del Concept Hub (Caso 0501)

El caso `0501` (`"sistema de base de datos vectorial de alto rendimiento"`) ilustra la necesidad de separar explícitamente los dos efectos que el Concept Hub ejerce sobre el ranking:

```
              ┌────────────────────────────────────────────────────────┐
              │ Mecanismo A: Señal Intra-Fórmula (_calcular_score_...) │
              │ • Peso relativo: w = 0.20 × base_weight                │
              │ • Aporte aditivo dentro de la ecuación lineal híbrida   │
              └───────────────────────────┬────────────────────────────┘
                                          │
                                          ▼
                               Score Híbrido Puro: 0.3554
                                          │
                                          ▼
              ┌────────────────────────────────────────────────────────┐
              │ Mecanismo B: Regla Externa de Promoción (search.py)   │
              │ • Condición: hub_confidence = 0.5333                   │
              │ • score_forzado = min(0.95, 0.5333 × 0.95) = 0.5067    │
              │ • Promoción Delta: +0.1513                             │
              └───────────────────────────┬────────────────────────────┘
                                          │
                                          ▼
                               Score Efectivo Pre-Reranker: 0.5067
```

- **Mecanismo A (Intra-híbrido):** `hub_match` aporta al score lineal pre-promoción.
- **Mecanismo B (Post-híbrido / Piso Hub):** En `search.py:1898-1920`, si un nodo posee enlace canónico Hub con alta confianza, su score base se eleva forzadamente a `hub_confidence × 0.95`.
- **Conclusión Técnica:** `0.3554` era el score híbrido puro antes de la regla de piso; `0.5067` es el score efectivo que entró al ranking. Ambos valores son consistentes con la arquitectura y la telemetría instrumentada valida la invocación exacta.

---

## 4. Validación de Telemetría vs. Score de Ranking Real

Para garantizar que la telemetría capturada no corresponde a una invocación intermedia o sobreescrita:
1. Cada llamada a `_calcular_score_hibrido()` registra `invocation_id`, `caller_line`, `score_returned` y el vector completo de señales `kwargs`.
2. Para el 100% de los 72 casos auditados, se comprobó que `score_returned` de la última evaluación coincide con `last_score_base_map[concepto]`, demostrando correspondencia unívoca entre las señales capturadas y el score que determinó el ranking pre-reranker.

---

## 5. Formulación del Peso Efectivo (`base_weight`) y Descomposición Matemática

### 5.1 Ecuación de Normalización Real de `core/memory/scoring.py`
En el motor actual, los pesos base suman:
$$\Sigma_{\text{base}} = 0.25 + 0.14 + 0.08 + 0.08 + 0.10 + 0.10 + 0.10 + 0.08 + 0.04 + 0.02 + 0.20 + 0.20 = 1.39$$

El denominador total incluye los pesos activos de espacio latente y complementarios:
$$\text{total\_base} = \Sigma_{\text{base}} + \text{PPMI (0.15)} + \text{NCD (0.05)} + \text{Episodio (0.05)} + \text{Analogía (0.00)} + \text{Campo (0.05)} = 1.69$$

El factor de escala base adaptativo para una consulta con peso de divergencia JSD ($w_{\text{jsd}}$) es:
$$\text{base\_weight} = \frac{1.0 - w_{\text{jsd}}}{1.69}$$

Cuando $w_{\text{jsd}} = 0.0$, $\text{base\_weight} \approx 0.591716$.  
Para consultas de longitud media donde $w_{\text{jsd}} \in [0.05, 0.15]$, $\text{base\_weight} \in [0.5029, 0.5621]$.

---

### 5.2 Descomposición de Señales: Promedios en los 72 Fallos

| Señal | Peso Nominal ($w_i$) | Peso Efectivo Medio | Delta Descriptivo Medio ($\Delta_{\text{crudo}}$) | Delta Contributivo Medio ($\Delta_{\text{ponderado}}$) | Comportamiento en los 72 Fallos |
|---|---:|---:|---:|---:|---|
| **`hub_match`** | 0.20 | 0.1121 | **+0.1604** | **+0.017580** | Ventaja estructural del ganador en conceptos Hub |
| **`tematico_score`** | 0.08 | 0.0448 | **+0.1972** | **+0.008701** | Densidad de co-ocurrencia temática en dimensiones |
| **`dim_score`** | 0.14 | 0.0785 | **+0.0774** | **+0.006120** | Coincidencia en ejes semánticos topológicos |
| **`pred_score_srl`** | 0.20 | 0.1121 | **+0.0451** | **+0.005167** | Coincidencia de roles semánticos |
| **`grupo_score_wordnet`** | 0.10 | 0.0560 | **+0.0592** | **+0.003457** | Afinidad léxica WordNet a favor del ganador |
| **`jaccard`** | 0.10 | 0.0560 | **+0.0387** | **+0.002211** | Similitud de trigramas difusa |
| **`concepto_ratio`** | 0.08 | 0.0448 | **+0.0006** | **+0.000446** | Prácticamente neutral |
| **`peso_sinaptico`** | 0.10 | 0.0560 | **0.0000** | **0.000000** | Neutral en benchmark estándar |
| **`ncd_score`** | 0.05 | 0.0280 | **-0.0055** | **-0.000154** | Leve ventaja Gold |
| **`jsd_score`** | adaptativo | 0.0528 | **+0.0043** | **-0.000361** | Efecto modulador distributivo |
| **`convergencia_bonus`** | reranker | 1.0000 | **-0.0005** | **-0.000464** | Bono multicampo levemente pro-Gold |
| **`bm25_norm`** | 0.25 | 0.1401 | **-0.0004** | **-0.000798** | FTS5 equilibrado |
| **`sinonimos_ratio`** | 0.08 | 0.0448 | **-0.0252** | **-0.001040** | **El Gold supera al ganador en sinónimos** |
| **`ppmi_score`** | 0.15 | 0.0841 | **-0.0169** | **-0.001336** | **El Gold supera al ganador en espacio PPMI** |

---

## 6. Clasificación Sistemática de los 72 Casos

### 6.1 Desglose por Categoría de Consulta
| Categoría | Casos Fallidos | % Fallos | Observación Descriptiva |
|---|---:|---:|---|
| **`sinonimo`** | **24** | **33.3%** | El Gold tiene mejor sinonimia léxica, pero el ganador lo supera en tema/dimensiones |
| **`por_tema`** | **24** | **33.3%** | Múltiples nodos del mismo tema compiten en vecindad dimensional |
| **`variante_gramatical`** | **8** | **11.1%** | Flexiones verbales o plurales con divergencia en trigramas |
| **`typo`** | **7** | **9.7%** | Errores ortográficos que reducen el matching léxico exacto |
| **`pregunta_natural`** | **4** | **5.6%** | Ruido sintáctico en preguntas complejas |
| **`cruce_idioma`** | **3** | **4.2%** | Desfase léxico bilingüe |
| **`literal`** | **2** | **2.8%** | Colisión de términos literales compartidos |

---

### 6.2 Relación Matemática entre Clasificación Causal y Comportamiento Temporal

Existe una correspondencia algebraica exacta entre las dimensiones de análisis:

```
TOTAL FALLOS TOP-1: 72 CASOS
│
├── Por Comportamiento Temporal Pre vs. Post Reranker:
│   ├── TIPO 1 (Gold era #1 pre-reranker y cayó tras reranking): 6 casos (8.3%)
│   └── TIPO 2/3/4 (Gold NO era #1 antes del reranker):         66 casos (91.7%)
│
└── Por Clasificación Causal Operativa (con umbral de margen 0.0050):
    ├── PRE_RANKING (Margen base ≥ 0.0050): 59 casos (81.9%)
    ├── TIE_BREAK   (Margen final < 0.0050):  9 casos (12.5%)
    │   ├── Provenientes de TIPO 1:           2 casos
    │   └── Provenientes de TIPO 2/3/4:       7 casos
    └── RERANKER    (TIPO 1 con margen ≥ 0.0050): 4 casos (5.6%)
    
    Total: 59 + 9 + 4 = 72 casos exactos.
```

---

## 7. Síntesis Diagnóstica y Estado de Hipótesis

1. **Hallazgo Descriptivo Central:** El 100% de los 875 casos son descubiertos en el Top-5 (0% fallos de cobertura). El 91.7% de los fallos Top-1 (66/72) se gesta en la fase de **Pre-ranking Híbrido**, antes de la intervención del reranker léxico.
2. **Hallazgo Contributivo Central:** Los competidores superan a los nodos Gold principalmente por la acumulación aditiva de `hub_match` (+0.0176 contribución ponderada promedio) y `tematico_score` (+0.0087 contribución ponderada promedio), aun cuando el Gold aventaja al ganador en `ppmi_score` (-0.0013) y `sinonimos_ratio` (-0.0010).
3. **Estado Epistémico de la Causalidad:** Se mantiene la calificación de **HIPÓTESIS DIAGNÓSTICA** sobre la necesidad de calibrar el equilibrio relativo entre señales temáticas/estructurales y señales semánticas finas. No se afirmará causalidad probada hasta que se ejecute una prueba contrafactual formal en la fase correspondiente.
4. **Cierre de Fase:** La instrumentación, reproductibilidad y descomposición matemática quedan verificadas y cerradas. El motor permanece 100% intacto.
