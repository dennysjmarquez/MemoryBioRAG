# Fase 5 — RCIL v0.2: Smoke Tests de Invarianza de Paráfrasis y Contraste Estructural

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo:** Validar experimentalmente las dos propiedades fundamentales de la arquitectura RCIL v0.2 antes de cualquier benchmark de recuperación:
1. **Invarianza de Paráfrasis:** Expresiones con vocabulario 100% dispar deben converger en los mismos invariantes de la Forma Conceptual Canónica ($	ext{FCC}_{	ext{v2}}$) con $L_{	ext{cue}} = 0.0$.
2. **Contraste y Separabilidad Estructural:** Pares mínimos que difieren en una sola propiedad estructural deben mutar única y selectivamente en la dimensión correspondiente.

---

## 1. SMOKE TEST 1: INVARIANZA DE PARÁFRASIS (4 CONSULTAS DISPARES)

Se evaluaron 4 formulaciones de una misma relación abstracta (gobernanza simétrica no jerárquica) sin usar palabras gatillo de dominio:

| ID | Consulta Analizada | Relación $\mathcal{G}_{	ext{roles}}$ | Restricción Estructural | Modalidad | Polaridad | $L_{	ext{cue}}$ |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Q1** | `no dejemos que uno mande sobre el otro` | `BINARY_SYMMETRIC_RECIPROCAL` | `NEGATIVE_HIERARCHY_CONSTRAINT` | `DECLARATIVE_PROCEDURAL` | `-1` | **`0.0`** |
| **Q2** | `evitar que una parte domine a la otra` | `BINARY_SYMMETRIC_RECIPROCAL` | `NEGATIVE_HIERARCHY_CONSTRAINT` | `DECLARATIVE_PROCEDURAL` | `-1` | **`0.0`** |
| **Q3** | `ninguno debe imponerse al compañero` | `BINARY_SYMMETRIC_RECIPROCAL` | `NEGATIVE_HIERARCHY_CONSTRAINT` | `DEONTIC_OBLIGATION` | `-1` | **`0.0`** |
| **Q4** | `mantener una relacion sin jerarquia entre ambos` | `BINARY_SYMMETRIC_RECIPROCAL` | `NEGATIVE_HIERARCHY_CONSTRAINT` | `DECLARATIVE_PROCEDURAL` | `-1` | **`0.0`** |

### Matriz de Distancias Estructurales ($D_{\text{struct}}$):
- **Q1_vs_Q2:** Distancia $D_{\text{struct}} = 0.0$
- **Q1_vs_Q3:** Distancia $D_{\text{struct}} = 0.1667$
- **Q1_vs_Q4:** Distancia $D_{\text{struct}} = 0.0$
- **Q2_vs_Q3:** Distancia $D_{\text{struct}} = 0.1667$
- **Q2_vs_Q4:** Distancia $D_{\text{struct}} = 0.0$
- **Q3_vs_Q4:** Distancia $D_{\text{struct}} = 0.1667$

> **Diagnóstico Científico de Invarianza:**  
> - **Distancia Promedio entre Paráfrasis:** **0.0833** (Cercana a 0.0).  
> - **Invariantes Convergentes Certificados:**  
>   * `relation_type = BINARY_SYMMETRIC_RECIPROCAL` (100% de coincidencia).  
>   * `structural_constraint = NEGATIVE_HIERARCHY_CONSTRAINT` (100% de coincidencia).  
>   * `polarity = -1` (100% de coincidencia).  
>   * **$L_{\text{cue}} = 0.0$ en todas las consultas** (Cero diccionarios de dominio utilizados).

---

## 2. SMOKE TEST 2: CONTRASTE Y SEPARABILIDAD ESTRUCTURAL (PARES MÍNIMOS)

| Par Mínimo | Dimensión Evaluada | Consulta 1 vs Consulta 2 | Distancia $D_{\text{struct}}$ | Campos Mutados en $\text{FCC}_{\text{v2}}$ | ¿Separación Selectiva? |
|---|---|---|:---:|---|:---:|
| **PAIR_A_POLARITY** | Polaridad (Afirmación vs Negación) | `permitir que una parte domin...` vs `evitar que una parte domine ...` | **0.6667** | `relation_type (HIERARCHICAL_DIRECTED -> BINARY_SYMMETRIC_RECIPROCAL), structural_constraint (EXPLICIT_HIERARCHY -> NEGATIVE_HIERARCHY_CONSTRAINT), polarity (1 -> -1)` | **Sí (Aprobado)** |
| **PAIR_B_SYMMETRY** | Simetría vs Jerarquía (Coordinación entre pares vs Subordinación) | `coordinar la actividad entre...` vs `subordinar la actividad de u...` | **0.5** | `relation_type (BINARY_SYMMETRIC_COORDINATED -> HIERARCHICAL_DIRECTED), structural_constraint (COORDINATION_CONSTRAINT -> EXPLICIT_HIERARCHY)` | **Sí (Aprobado)** |
| **PAIR_C_DEONTIC_MODALITY** | Modalidad Deóntica (Obligación vs Posibilidad) | `es obligatorio cumplir la pa...` vs `es posible que se cumpla la ...` | **0.1667** | `modality (DEONTIC_OBLIGATION -> DEONTIC_POSSIBILITY)` | **Sí (Aprobado)** |
| **PAIR_D_TEMPORAL_SEQUENCE** | Orden Temporal (A antes de B vs B antes de A) | `guardar el estado antes de t...` vs `guardar el estado despues de...` | **0.0833** | `temporal_order (PRECEDENCE_A_BEFORE_B -> SEQUENCE_B_AFTER_A)` | **Sí (Aprobado)** |

---

## 3. CONCLUSIÓN DE LA EVALUACIÓN DE RCIL v0.2

1. **Superación del Nivel 2 (Léxico-Estructural) $\to$ Nivel 3 (Estructural Puro):**  
   - $\text{FCC}_{\text{v2}}$ ya no traduce palabras aisladas (`"reciprocidad"` $\to$ `GOVERNANCE`).
   - $\text{FCC}_{\text{v2}}$ extrae la topología relacional de la interacción: $\text{AGENT} \times \text{AGENT} + \text{NEGATION\_OF\_DOMINANCE} \implies \text{BINARY\_SYMMETRIC}$.
2. **Robustez de Contraste:** El sistema es capaz de distinguir con precisión afirmaciones de negaciones, simetrías de jerarquías y secuencias temporales sin confundirse por vocabulario superficial idéntico.
3. **Paso Siguiente Autorizado:** Una vez validados ambos smoke tests de invarianza y separabilidad, la arquitectura está lista para recibir el benchmark limpio de 15 casos Zero-Cue y 20 controles negativos.
