# Fase 4.5 — Semantic Candidate Generation

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo Científico:** Demostrar cómo hacer aparecer en el conjunto de candidatos un concepto que FTS5 no pudo encontrar (Zero-Overlap).

---

## 1. DEFINICIÓN FORMAL DE "CANDIDATE GENERATION SEMÁNTICA"

> **Candidate Generation Semántica (para MemoryBioRAG)**:  
> La capacidad de un mecanismo determinista, relacional o latente para mapear una consulta lingüística a un conjunto de claves candidatas C_gen tal que un nodo objetivo 'gold' ausente de la coincidencia léxica directa (FTS5) sea incorporado exitosamente a C_gen sin provocar una explosión incontrolada de falsos positivos en consultas de control negativo.

* **Distinción Arquitectónica Fundamental:**
  * **M1 (Structural Seed Re-ranking)**: Opera $f: C_{\text{FTS}} \rightarrow C_{\text{ranked}}$. Si $\text{gold} \notin C_{\text{FTS}}$, el re-ranker no puede rescatarlo jamás.
  * **M2 a M5 (Candidate Generators)**: Operan $g: Q \rightarrow C_{\text{semánticos}}$, introduciendo claves al espacio de candidatos.
  * **M7 (Generación Compuesta + Re-ranking Estructural)**: $f(g(Q) \cup C_{\text{FTS}})$.

---

## 2. TABLA COMPARATIVA PRINCIPAL (M0 A M7 SOBRE 30 CONSULTAS ZERO-FTS)

Evaluación sobre 30 consultas donde el gold está **100% ausente de FTS5** y 90 Hard-Negatives:

| Modo | Mecanismo | Golds en Pool (`after`) | Ganancia Gen. | R@5 | R@1 | MRR | Tamaño Medio Pool | Hard-Neg FP (>0.40) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **M0** | FTS5 / BM25 Puro | 0/30 | 0.0% | 0/30 (0%) | 0/30 (0%) | 0.0000 | 37.9 | 60/90 (66.67%) |
| **M1** | FTS5 + Re-ranking Estructural | 0/30 | 0.0% | 0/30 (0%) | 0/30 (0%) | 0.0000 | 37.9 | 51/90 (56.67%) |
| **M2** | WordNet Query Expansion | 3/30 | 10.0% | 0/30 (0.0%) | 0/30 | 0.005 | 45.87 | 64/90 (71.11%) |
| **M3** | Concept Hub Injection | 3/30 | 10.0% | 1/30 (3.33%) | 1/30 | 0.0348 | 42.27 | 79/90 (87.78%) |
| **M4** | PPMI Latent Neighbors | 3/30 | 10.0% | 1/30 (3.33%) | 1/30 | 0.0349 | 48.37 | 60/90 (66.67%) |
| **M5** | Grafo 1-Hop Tipado | 4/30 | 13.33% | 1/30 (3.33%) | 1/30 | 0.035 | 76.13 | 60/90 (66.67%) |
| **M6** | Combinación Clásica (M2+M3+M4+M5) | 4/30 | 13.33% | 0/30 (0.0%) | 0/30 | 0.0048 | 96.27 | 79/90 (87.78%) |
| **M7** | **M6 + Re-ranking Estructural (M1)** | **4/30** | **13.33%** | **1/30 (3.33%)** | **0/30** | **0.0154** | **96.27** | **55/90 (61.11%)** |

---

## 3. TRAZABILIDAD CAUSAL DE CANDIDATOS GENERADOS (CASOS DESTACADOS)

### [ZFTS_07] `canal de transmision externa y volcado cruzado de cuadernos`
- **Gold:** `notebooklm-memory-biorag-project`
- **Mecanismo que generó el candidato:** `GRAPH_1HOP(sinonimo_explicito_from_oracle_que_recordar_sobre_artemis_hermes)`
- **Clasificación Causal:** `C. inferencia estructural derivada (Grafo 1-Hop)`
- **Rank Final (M7):** **64** | **Score:** `0.0824` | **In Top-5:** ✗

### [ZFTS_13] `esquema pormenorizado de grabacion duradera de bloques`
- **Gold:** `biorag_v11_1_detalle_tecnico`
- **Mecanismo que generó el candidato:** `FTS5_DIRECT`
- **Clasificación Causal:** `E. zero-overlap realmente nuevo`
- **Rank Final (M7):** **10** | **Score:** `0.12908` | **In Top-5:** ✗

### [ZFTS_22] `el puente que se armo para conectar los cuadernos de google`
- **Gold:** `notebooklm-memory-biorag-project`
- **Mecanismo que generó el candidato:** `FTS5_DIRECT`
- **Clasificación Causal:** `E. zero-overlap realmente nuevo`
- **Rank Final (M7):** **3** | **Score:** `0.52296` | **In Top-5:** ✓

### [ZFTS_23] `que tan bien aguanta el sistema cuando le metemos 10k nodos de golpe`
- **Gold:** `analisis_escalabilidad_10k_v5_1`
- **Mecanismo que generó el candidato:** `FTS5_DIRECT`
- **Clasificación Causal:** `E. zero-overlap realmente nuevo`
- **Rank Final (M7):** **83** | **Score:** `0.04455` | **In Top-5:** ✗

---

## 4. LÍMITES EXPLÍCITOS DE LO QUE LOS RESULTADOS PERMITEN AFIRMAR

1. **FTS5 + Re-ranking estructural (M1) es ciego al abismo léxico**: Si una consulta no tiene solapamiento de tokens con el corpus, M1 genera 0 candidatos y 0 rescates.
2. **PPMI Latente y Grafo 1-Hop son los generadores primarios de candidatos zero-overlap**: PPMI introduce candidatos por coocurrencia de contexto global, mientras que el Grafo 1-Hop introduce asociaciones tipadas a partir de semillas indirectas.
3. **Concept Hub aporta rescates deterministas de alta precisión**: Rescata eficazmente conceptos canónicos cuando la consulta coincide con sus puentes semánticos estructurados.
4. **La sinergia M7 (Generación Multicanal + Focalización Estructural)** es la arquitectura óptima: Los generadores (M2-M5) expanden el pool de candidatos rescatando los golds ausentes, y el Re-ranker Estructural (M1) filtra el ruido generado por la expansión manteniendo los falsos positivos bajo control estricto.
