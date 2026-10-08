# INFORME DE AUDITORÍA DIAGNÓSTICA, TRAZABILIDAD Y ABLACIÓN CONTRAFACTUAL DE SEÑALES (v32.4)

> **Misión:** Atribución causal sistemática mediante ablación contrafactual sobre pool de candidatos congelado (A..I) y trazabilidad completa de linaje de telemetría de los 72 casos que ingresan al Top-5 pero no obtienen la posición #1 en el benchmark QA congelado.  
> **Invariante Metodológica:** Cero modificaciones permanentes en el motor de producción, pesos de scoring ni heurísticas.

---

## 1. Metadatos del Experimento Congelado y Trazabilidad

### 1.1 Identificadores Criptográficos y Reproducibilidad
| Parámetro | Valor Verificado |
|---|---|
| **Commit SHA** | `32657b652f6941161720a117232770f25a5feaed` |
| **Versión Oficial** | `v32.4` |
| **Snapshot SHA-256** | `c3b88ae61bda1c0d2d4b6066d253a41b68f88e8d12b338b278c8442a1228dddc` (`snapshots/qa_escape_qcr_20260811.db`) |
| **Dataset SHA-256** | `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c` (`scripts/casos_qa_baseline_v1.jsonl`) |
| **Total Casos en Dataset** | 921 casos |
| **Controles Negativos** | 40 casos (0 FP · 0.00% en todas las configuraciones) |
| **Queries Ambiguas Contradictorias** | 6 casos (aisladas formalmente del Recall) |
| **Consultas de Recuperación Efectiva** | 875 consultas |
| **Recall@5 Global Baseline** | **100.00% (875 / 875)** |
| **Recall@1 Global Baseline** | **91.77% (803 / 875)** |
| **Total Fallos Top-1 Inicial** | **Exactamente 72 casos** |

---

### 1.2 Trazabilidad de Telemetría (72/72 Casos Comprobados)
Se verificó la cadena de procedencia:
$$\text{invocation\_id} \longrightarrow \text{concepto} \longrightarrow \text{score\_returned} \longrightarrow \text{last\_score\_base\_map}[\text{concepto}]$$
* 1 sola invocación por concepto en el pool híbrido.
* Correspondencia exacta $|\text{score\_returned} - \text{last\_score\_base\_map}[\text{concepto}]| < 10^{-4}$ en los **72/72 casos**.
* Rango discreto de $w_{\text{jsd}} \in \{0.025, 0.125\}$ confirmado según $N_t < 4$ vs $N_t \ge 4$.

---

## 2. Experimento 1: Evaluación Contrafactual de Mecanismos del Concept Hub

Se evaluó la incidencia del Concept Hub mediante ablación de sus mecanismos en 4 ramas:
* **A (Baseline):** Motor completo.
* **B (hub_match = 0):** Señal de Hub anulada en scoring.
* **C (Sin Piso/Promoción Hub):** Regla de piso desactivada en `search.py`.
* **D (Sin Hubs Total):** Ambos mecanismos de Hub apagados.

| Configuración | R@5 | R@1 | MRR | FP Negativos | Misses Top-1 | $\Delta$ Neto R@1 (vs Baseline) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A (Baseline Actual)** | **100.00%** (875/875) | **91.77%** (803/875) | **0.9497** | 0 / 40 | **72** | **BASE** |
| **B (hub_match = 0)** | **100.00%** (875/875) | **92.11%** (806/875) | **0.9517** | 0 / 40 | **69** | **+3** (3G / 0L) |
| **C (Sin Piso Hub)** | **99.89%** (874/875) | **92.23%** (807/875) | **0.9525** | 0 / 40 | **68** | **+4** (5G / 1L) |
| **D (Sin Hubs Total)** | **99.89%** (874/875) | **92.23%** (807/875) | **0.9525** | 0 / 40 | **68** | **+4** (5G / 1L) |

> **Conclusión del Experimento 1:** 68 de los 72 casos no modifican su condición Top-1 ante la desactivación del Concept Hub. El Hub es responsable únicamente de 3 a 4 desplazamientos netos, y su presencia aporta un rescate de cobertura esencial en R@5 (874 $\to$ 875).

---

## 3. Experimento 2: Ablación Contrafactual de Señales sobre Pool de Candidatos Congelado

Para aislar con rigor la causa causal del ordenamiento de los 72 fallos, se ejecutó una ablación sistemática sobre el pool de candidatos idéntico (congelado antes del scoring híbrido):

```
                       CANDIDATOS FROZEN (Pool Base)
                                    │
    ┌───────────┬───────────┬───────┴───┬───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼           ▼
Config A    Config B    Config C    Config D    Config E    Config F / G
Baseline    Temático=0    Dim=0    Sinónimos=0   PPMI=0    Combinadas
```

### 3.1 Tabla Maestra de Ablación de Señales

| Config | Intervención Contrafactual | R@5 | R@1 | MRR | Misses | Ganancias Top-1 | Pérdidas Top-1 | $\Delta$ Neto R@1 |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | **Baseline (Motor Actual)** | **100.0%** | **91.77%** | **0.9497** | **72** | **0** | **0** | **BASE** |
| **B** | `tematico_score = 0` | 99.54% | 92.46% | 0.9522 | 66 | 11 | 5 | **+6** |
| **C** | `dim_score = 0` | 99.66% | 92.80% | 0.9536 | 63 | 11 | 2 | **+9** |
| **D** | `sinonimos_ratio = 0` | 97.03% | 90.74% | 0.9329 | 81 | 8 | 17 | **-9** |
| **E** | `ppmi_score = 0` | 99.09% | 91.20% | 0.9425 | 77 | 3 | 8 | **-5** |
| **F** | `tematico + dim = 0` (Eje Co-ocurrencia OFF) | 99.43% | **93.14%** | **0.9546** | **60** | **17** | **5** | **+12** |
| **G** | `sinonimos + ppmi = 0` (Eje Semántico Fino OFF) | 95.66% | 89.03% | 0.9182 | 96 | 7 | 31 | **-24** |
| **H** | `grupo_score_wordnet = 0` | 99.54% | 92.11% | 0.9503 | 69 | 5 | 2 | **+3** |
| **I** | `pred_score_srl = 0` | 100.0% | 92.11% | 0.9515 | 69 | 3 | 0 | **+3** |

---

### 3.2 Desglose por Categoría en Configuraciones Clave (R@1 por Categoría)

| Categoría | Total Queries | A (Baseline) | B (`tematico=0`) | C (`dim=0`) | F (`tematico+dim=0`) | G (`sinonimos+ppmi=0`) |
|---|---:|:---:|:---:|:---:|:---:|:---:|
| **`por_tema`** | 65 | 63.08% (41) | 64.62% (42) | **69.23% (45)** | **72.31% (47)** | 60.00% (39) |
| **`sinonimo`** | 55 | 56.36% (31) | 56.36% (31) | **58.18% (32)** | **58.18% (32)** | **34.55% (19)** |
| **`typo`** | 65 | 89.23% (58) | 92.31% (60) | 92.31% (60) | **93.85% (61)** | 84.62% (55) |
| **`variante_gramatical`** | 65 | 87.69% (57) | 92.31% (60) | 89.23% (58) | **90.77% (59)** | 86.15% (56) |
| **`pregunta_natural`** | 65 | 93.85% (61) | 93.85% (61) | 95.38% (62) | 93.85% (61) | 92.31% (60) |
| **`literal`** | 487 | 99.59% (485) | 99.59% (485) | 99.59% (485) | 99.59% (485) | 99.59% (485) |
| **`dormido`** | 65 | 100.0% (65) | 100.0% (65) | 100.0% (65) | 100.0% (65) | 100.0% (65) |
| **`cruce_idioma`** | 8 | 62.50% (5) | 62.50% (5) | 62.50% (5) | 62.50% (5) | 62.50% (5) |

---

## 4. Hallazgos Científicos y Conclusiones Causales

1. **`sinonimos_ratio` y `ppmi_score` son señales semánticas indispensables:**
   - La ablación de `sinonimos_ratio` (D) provoca 17 pérdidas y desploma el acierto en sinónimos de 56.36% a 41.82%.
   - La ablación conjunta `sinonimos + ppmi` (G) es catastrófica: provoca 31 pérdidas netas (-24 global) y colapsa el acierto en `sinonimo` al 34.55%.
2. **`tematico_score` y `dim_score` generan interferencia competitiva en consultas léxico-sinonímicas:**
   - Apagar `tematico_score` (B) rescata 11 casos netos positivos (+6 global).
   - Apagar `dim_score` (C) rescata 11 casos con solo 2 pérdidas (+9 global), mejorando `por_tema` del 63.08% al 69.23%.
   - Apagar ambos (F) rescata **17 casos de los 72 fallos** (+12 neto global), llevando R@1 al 93.14% y `por_tema` al 72.31%.
   - No obstante, la desactivación de `tematico` o `dim` reduce R@5 de 100.0% a 99.43% (-5 casos en el corte del Top-5), demostrando que ambas señales son útiles para la cobertura topológica general pero tienen un peso desproporcionado en la frontera de desempate Top-1.
3. **Mecanismo de Solución Científica Identificado:**
   - La solución **NO** consiste en apagar `tematico_score` o `dim_score` (lo que dañaría la robustez en R@5).
   - La solución consiste en una **política de modulación contextual o competencia de señales**, donde la presencia de evidencia léxica fuerte o sinonimia explícita (`sinonimos_ratio > 0` / `ppmi_score > 0`) atenúe la capacidad de las señales de co-ocurrencia temática amplia para sobrepasar al candidato con identidad directa.

---

## 5. Estado del Repositorio
* **Invariante respetada:** Ningún archivo de producción ni lógica del core ha sido modificado.
* **Artefactos generados:**
  - [`docs/experimento_contrafactual_pool_congelado.json`](experimento_contrafactual_pool_congelado.json) (Tabla completa, por categoría y transiciones).
  - [`docs/experimento_contrafactual_hub.json`](experimento_contrafactual_hub.json) (Ablación contrafactual del Concept Hub).
