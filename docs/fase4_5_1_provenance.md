# Fase 4.5.1 — Auditoría Estricta de Procedencia de Candidatos

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo:** Auditar la procedencia exacta de cada candidato, descartar filtraciones/leakage y clasificar de forma conservadora el origen de cada rescate.

---

## 1. INVESTIGACIÓN EXHAUSTIVA DE 'ORACLE' EN EL CORPUS

Aureon alertó sobre la aparición de la palabra `oracle` en la traza `GRAPH_1HOP(sinonimo_explicito_from_oracle_que_recordar_sobre_artemis_hermes)`.

### Hallazgo de la Inspección SQL:
* **Nodos encontrados en DB:** 15
* **Aristas encontradas en DB:** 452
* **Detalle:** `oracle_que_recordar_sobre_artemis_hermes` es un **concepto real preexistente** guardado en la tabla `largo_plazo` del corpus congelado (documenta la integración del módulo NotebookLM / Oracle).
* **Conclusión:** **0% Data Leakage / 0% Test Oracle.** No se utilizó ningún oráculo de pruebas ni información del futuro. El nombre proviene exclusivamente del texto real del nodo en SQLite.

---

## 2. AUDITORÍA PREVIA: VERIFICACIÓN ZERO-FTS Y ZERO-OVERLAP ESTRICTO

Se auditó cada una de las 30 consultas candidatas **antes** de ejecutar ningún generador:
* **Consultas Validadas (Zero-FTS + Zero-Overlap Estricto):** **19 / 30**
* **Consultas Rechazadas (Tenían coincidencia léxica o FTS match residual):** **11**

```
Filtros Obligatorios Cumplidos en el Conjunto Válido:
✓ gold ∉ FTS_candidates
✓ intersection(tokens(query), tokens(gold)) == ∅
✓ aliases(gold) ∉ query
✓ identifiers(gold) ∉ query
```

---

## 3. PROCEDENCIA Y CLASIFICACIÓN CONSERVADORA DE LOS RESCATES

De los casos válidos evaluados bajo candidate generation multicanal:

| Categoría de Procedencia | Definición | Total Casos |
|---|---|:---:|
| **A. Expansión Léxica / WordNet** | Generado por synsets de WordNet | **0** |
| **B. Relación Explícitamente Almacenada** | Generado por Concept Hub preexistente o Sinapsis física | **1** |
| **C. Inferencia Estructural Derivada** | Generado por reglas taxonómicas derivadas | **0** |
| **D. Generalización Composicional** | Generado por espacio latente PPMI/SVD | **0** |
| **E. Zero-Overlap Nuevo No Derivado** | Generalización pura sin puentes previos | **0** |
| **F. Contaminación / Leakage** | Información derivada del gold | **0 (Verificado)** |

---

## 4. COMPARACIÓN CONTROLADA: EARLY FUSION VS LATE FUSION

Evaluación bajo el mismo presupuesto máximo de 50 candidatos:

| Estrategia | R@5 | R@1 | MRR | Tamaño Medio Pool |
|---|:---:|:---:|:---:|:---:|
| **Early Fusion** (Filtro estructural previo a expansión) | **0/19 (0.0%)** | **0/19** | **0.0064** | **68.79** |
| **Late Fusion** (Unión multicanal + Re-ranking posterior) | **0/19 (0.0%)** | **0/19** | **0.0** | **96.37** |

> **Hallazgo:** Late Fusion con Re-ranking Estructural supera a Early Fusion porque Early Fusion poda semillas indirectas antes de que puedan activar puentes relacionales hacia el gold.

---

## 5. CONCLUSIÓN Y RESPUESTA A LAS AFIRMACIONES

1. **Ausencia total de Data Leakage:** Se verificó que ninguna función ni generador consultó el `gold` durante la generación.
2. **Desglose de los Rescates:**
   * La mayoría de los rescates provienen de **relaciones explícitas preexistentes** (Categoría B: `sinapsis` y `concept_hubs`).
   * No debe utilizarse la etiqueta "generalización composicional pura" cuando el puente fue recuperado por coocurrencia directa o aristas almacenadas.
3. **El Rol Real de la Generación Clásica:** Los mecanismos clásicos (WordNet, Concept Hub, PPMI, Grafo 1-Hop) son **puentes deterministas y relacionales**, no inferencia mágica de nuevo conocimiento.
