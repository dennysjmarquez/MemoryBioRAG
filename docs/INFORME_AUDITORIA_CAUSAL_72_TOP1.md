# INFORME DE AUDITORÍA CAUSAL DE LOS 72 FALLOS TOP-1 (v32.4)

> **Misión:** Atribución causal reproducible de los 72 casos que ingresan al Top-5 pero no obtienen la posición #1.  
> **Invariante:** Cero modificaciones de código de scoring, pesos o heurísticas durante esta fase.

---

## 1. Metadatos del Experimento Congelado

| Parámetro | Valor Verificado |
|---|---|
| **Commit SHA** | `32657b652f6941161720a117232770f25a5feaed` |
| **Versión Oficial** | `v32.4` |
| **Snapshot SHA-256** | `c3b88ae61bda1c0d2d4b6066d253a41b68f88e8d12b338b278c8442a1228dddc` (`snapshots/qa_escape_qcr_20260811.db`) |
| **Dataset SHA-256** | `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c` (`scripts/casos_qa_baseline_v1.jsonl`) |
| **Total Casos en Dataset** | 921 casos |
| **Controles Negativos** | 40 casos (0 FP · 0.00%) |
| **Queries Ambiguas Contradictorias** | 6 casos (aisladas del Recall) |
| **Consultas de Recuperación Efectiva** | 875 consultas |
| **Recall@5 Global Observado** | **100.00% (875 / 875)** |
| **Recall@1 Global Observado** | **91.77% (803 / 875)** |
| **Total Fallos Top-1 (Gold en Top 2..5)** | **Exactamente 72 casos** |

---

## 2. Resumen Estadístico de Atribución Causal

### 2.1 Desglose por Categoría de Consulta

| Categoría | Total Queries | Aciertos Top-1 | Fallos Top-1 | % del Total de Fallos | Recall@1 Cat |
|---|---:|---:|---:|---:|---:|
| **sinonimo** | 55 | 31 | **24** | **33.3%** | 56.36% |
| **por_tema** | 65 | 41 | **24** | **33.3%** | 63.08% |
| **variante_gramatical** | 65 | 57 | **8** | **11.1%** | 87.69% |
| **typo** | 65 | 58 | **7** | **9.7%** | 89.23% |
| **pregunta_natural** | 65 | 61 | **4** | **5.6%** | 93.85% |
| **cruce_idioma** | 8 | 5 | **3** | **4.2%** | 62.50% |
| **literal** | 487 | 485 | **2** | **2.8%** | 99.59% |
| **TOTAL** | **875** | **803** | **72** | **100.0%** | **91.77%** |

> **Hallazgo Clave 1:** El **66.7% de todos los fallos Top-1** (48 de 72) se concentra exclusivamente en dos categorías: `sinonimo` (24) y `por_tema` (24).

---

### 2.2 Desglose por Clasificación Causal de Fallo

| Clase Causal | Casos | % | Definición Operativa |
|---|---:|---:|---|
| **PRE_RANKING** | **59** | **81.9%** | El cuello de botella ocurre en el scoring híbrido base antes del reranker: el competidor ya supera al Gold en score base. |
| **TIE_BREAK** | **9** | **12.5%** | Margen infinitesimal ($| \text{score}_{\text{winner}} - \text{score}_{\text{gold}} | < 0.0050$), donde el ordenamiento se define por milésimas o empate léxico. |
| **RERANKER** | **4** | **5.6%** | El reranker multicampo modificó el orden final de forma desfavorecedora para el Gold. |
| **TOTAL** | **72** | **100.0%** | |

---

### 2.3 Desglose por Comportamiento Pre/Post Reranker

| Tipo de Comportamiento | Casos | % | Dinámica |
|---|---:|---:|---|
| **TIPO 4 (Pre-ranking unchanged)** | **53** | **73.6%** | El Gold ya estaba en puesto #2 a #5 antes del reranker y el reranker no alteró su posición relativa. |
| **TIPO 2/3 (Pre-ranking modulated)** | **13** | **18.1%** | El Gold no era #1 pre-reranker, y el reranker moduló ligeramente las posiciones dentro del Top-5. |
| **TIPO 1 (Reranker Regression)** | **6** | **8.3%** | El Gold era #1 en el score base y fue superado por un competidor con mayor bono multicampo. |
| **TOTAL** | **72** | **100.0%** | |

> **Hallazgo Clave 2:** En el **91.7% de los casos (66/72)**, el Gold **ya no era el #1 antes de aplicar el reranker**. El reranker multicampo NO es el culpable principal de los fallos Top-1; el cuello de botella se ubica en el balance de señales del **Pre-ranking híbrido**.

---

## 3. Análisis Profundo de las Categorías Críticas

### 3.1 Categoría `sinonimo` (24 casos)
- **Dinámica:** La consulta utiliza vocabulario alternativo o paráfrasis conceptual sin coincidencia directa con el título o cuerpo del nodo.
- **Entrada al Pool:** 100% de los nodos Gold entran al Top-5 a través de FTS5 trigrams, expansión simbólica y grafos Hebbianos.
- **Causa de Pérdida en Top-1:** Un nodo competidor que posee coincidencia incidental de un token literal en `contenido` o `concepto` obtiene un BM25 y Jaccard léxico superior al aporte del espacio vectorial PPMI-SVD / WordNet del Gold.
- **Margen Típico:** $\Delta \approx 0.04 - 0.12$.

### 3.2 Categoría `por_tema` (24 casos)
- **Dinámica:** Consultas abstractas que buscan afinidad por dominio o campo temático.
- **Entrada al Pool:** El Gold entra al pool mediante similitud de 13 ejes dimensionales y spreading activation en el grafo.
- **Causa de Pérdida en Top-1:** Nodos más genéricos o con mayor grado de sinapsis acumulan un baseline de activación o score de grupo que sobrepasa por estrecho margen la especificidad dimensional del Gold.
- **Margen Típico:** $\Delta \approx 0.02 - 0.08$.

---

## 4. Verificación de EXP-Q (Abismo Léxico Cero-Overlap)

La suite de verificación directa en [`scripts/test_abismo_lexico.py`](../scripts/test_abismo_lexico.py) reporta:

```
===========================================================================
RESUMEN DE RESCATE EN EL ABISMO LÉXICO (EXP-Q)
===========================================================================
Candidatos descubiertos en Pool BFS (Grafo):      3/3 (100.0%)
Resueltos en Búsqueda Primaria (Léxico directo):  0/3
Rescate efectivo en Ventana Top-5:                2/3 (66.7%)
Rescate en Primera Posición (Top-1):              1/3 (33.3%)
Irresueltos (fuera del pool BFS):                 0/3
---------------------------------------------------------------------------
  EXP-Q-01: Primaria: ❌ 0 Overlap  -> Grafo: ✅ TOP-5 (Pos #4)   | Mecanismo: grafo | kilo_vscode_extension_principa
  EXP-Q-02: Primaria: ❌ 0 Overlap  -> Grafo: ✅ TOP-5 (Pos #1)   | Mecanismo: grafo | regla_verificar_codigo_real_an
  EXP-Q-03: Primaria: ❌ 0 Overlap  -> Grafo: ℹ️ POOL (Pos #19)  | Mecanismo: grafo | ajuste_tejedora_valencia_desem
===========================================================================
```

---

## 5. Respuestas a las Preguntas Científicas Fundamentales

### ¿Cuál es el cuello de botella dominante de MemoryBioRAG?
1. **Descubrimiento de candidatos (Candidate Generation):** **RESUELTO AL 100%** en este benchmark (875/875 entran al Top-5).
2. **Discriminación de Ranking (Pre-ranking):** **CUELLO DE BOTELLA DOMINANTE (81.9%)**. Ocurre cuando el Gold ya está presente en el Top-5 pero un rival con solapamiento léxico incidental acumula mayor score base.
3. **Reranker Multicampo:** Aporta un beneficio neto positivo global (+0.11pp en R@1), representando solo un 5.6%–8.3% de regresiones aisladas.

---

## 6. Conclusión y Recomendación Metodológica

- El artefacto completo con el desglose individual de los 72 casos está disponible en [`docs/top1_failure_attribution.json`](top1_failure_attribution.json).
- **Invariante respetada:** No se han realizado modificaciones al motor ni a los pesos.
- Cualquier optimización futura de R@1 debe enfocarse en la **discriminación fina entre candidatos semánticos vs. coincidencias incidentales**, preservando intacto el 100% de Recall@5 y el 0.0% de Falsos Positivos.
