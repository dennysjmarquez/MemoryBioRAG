# FASE 5 — Representación Conceptual Independiente del Léxico (RCIL)
## Documento de Cierre RCIL v0.1 y Especificación de Diseño RCIL v0.2 (Representación Preléxica y Roles Sintácticos)

**Autores:** Equipo de Investigación MemoryBioRAG (Dennys & Aureon)  
**Fecha:** 2026-09-05  
**Estado:** Cierre Formal de RCIL v0.1 (Resultado Negativo Valioso) y Especificación Teórica de RCIL v0.2  
**Restricción Inmutable:** Preservación total de `core/`, snapshot canónico congelado y tests de producción.

---

## 1. CIERRE FORMAL DE RCIL v0.1 (RESULTADO NEGATIVO RIGUROSO)

### 1.1. Veredicto y Diagnóstico Científico
El experimento decisivo en `scripts/audit_fase5_rcil_zero_cue.py` demostró que:
1. **Colapso ante $L_{\text{cue}}(Q) = 0.0$:** Cuando se eliminan deliberadamente todas las palabras gatillo conocidas en las consultas de prueba, la extracción de $\text{FCC}$ colapsa a valores por defecto y el target cae a `RANK_GT_20` o `GOLD_ABSENT`.
2. **Clasificación Real de $\text{FCC}_{\text{v0.1}}$:** No es una representación independiente del léxico; es una **representación léxico-estructural de alto nivel** dependiente de cues morfológicos específicos.
3. **Estado de las Hipótesis en v0.1:**
   - **$H_1$ (RCIL supera al baseline bajo Zero-Lexical-Cue):** **No demostrada.**
   - **$H_2$ (Dimensiones continuas aportan sobre $\mathcal{F} + \mathcal{P}$):** **No demostrada como ventaja causal.**
   - **$H_3$ (Topología/energía aportan sobre la anterior):** **No demostrada.**

---

### 1.2. Corrección Epistemológica: Separación de Validez y Leakage
Se eliminó la ambigüedad conceptual entre contaminación experimental e idoneidad de protocolo:

- **`LEAKAGE_STATUS`:** Certifica si existió acceso ilegítimo al gold antes de la inferencia (`NONE` vs `DETECTED`).
- **`ZERO_FTS_VALIDITY`:** Certifica si la consulta cumple estrictamente $G \notin \text{FTS5}(Q)$ (`PASS` vs `FAIL`).
- **`ZERO_OVERLAP_VALIDITY`:** Certifica $tokens(Q) \cap tokens(G) = \emptyset$ (`PASS` vs `FAIL`).
- **`ZERO_ALIAS_VALIDITY`:** Certifica ausencia de identificadores o alias del gold (`PASS` vs `FAIL`).
- **`ZERO_HUB_VALIDITY`:** Certifica que ningún Concept Hub apunta directamente al gold (`PASS` vs `FAIL`).
- **`ZERO_DIRECT_EDGE_VALIDITY`:** Certifica que $(Q_{\text{seed}} \to G) \notin \text{sinapsis}$ (`PASS` vs `FAIL`).

> **Regla de Inclusión para Benchmark de Independencia Léxica:**  
> Un caso solo califica como evidencia primaria de independencia léxica si y solo si cumple:  
> $$L_{\text{cue}}(Q) = 0.0 \land \text{ZERO\_FTS} = \text{PASS} \land \text{ZERO\_OVERLAP} = \text{PASS} \land \text{ZERO\_ALIAS} = \text{PASS} \land \text{ZERO\_DIRECT\_EDGE} = \text{PASS}$$

---

## 2. RCIL v0.2 — REPRESENTACIÓN ESTRUCTURAL PRELÉXICA

### 2.1. Planteamiento Central: La Pregunta de RCIL v0.2
> *¿Cómo puede una consulta $Q$ transformarse en una estructura relacional abstracta sin que ninguna palabra individual determine por sí sola una categoría o etiqueta conceptual?*

En lugar de reglas léxicas de mapeo directo ($w \to \text{Tag}$), RCIL v0.2 introduce una **representación en capas basada en roles relacionales y cálculo de dependencias de primer orden**:

```text
                                CONSULTA SUPERFICIAL (Q)
         "como nos llevamos sin ponernos uno encima del otro al trabajar juntos"
                                           │
                                           ▼
                       [CAPA 1: ANÁLISIS SINTÁCTICO-FUNCIONAL]
                       - Agentes implicados: [1ra persona plural: "nosotros"]
                       - Relación predicativa: [Interacción mutua / Reciprocidad]
                       - Modificador de control: [Negación de dominancia / "sin ponernos encima"]
                       - Ámbito operativo: [Actividad conjunta / "trabajar juntos"]
                                           │
                                           ▼
                       [CAPA 2: ESTRUCTURA PRELÉXICA ABSTRACTA]
                       - Polaridad: [Simétrica / No jerárquica]
                       - Modalidad: [Gobernanza de interacción / Procedimental]
                       - Cardinalidad: [Multi-agente simétrico (k ≥ 2)]
                       - Temporalidad: [Estado continuo / Invariante de proceso]
                                           │
                                           ▼
                                 FORMA CONCEPTUAL CANÓNICA v2
               FCC_v2 = ⟨ Tipo_Estructura: RELACION_SIMETRICA_NO_JERARQUICA,
                          Ambito: GOBERNANZA_INTERACCION,
                          Restriccion: NEGACION_DOMINANCIA ⟩
```

---

## 3. REPRESENTACIÓN MATEMÁTICA DE LA $\text{FCC}_{\text{v2}}$

La Forma Conceptual Canónica v2 se define como un grafo de roles abstractos independientes de lemas específicos:

$$\text{FCC}_{\text{v2}}(x) = \langle \mathcal{G}_{\text{roles}}, \mathcal{M}, \Pi, \mathcal{T}_{\text{temp}}, \kappa \rangle$$

Donde:
1. **$\mathcal{G}_{\text{roles}} = (\mathcal{V}_R, \mathcal{E}_R)$ (Grafo de Roles Preléxicos):**  
   Nodos $\mathcal{V}_R \in \{ \text{AGENT}, \text{RESOURCE}, \text{STATE}, \text{TRANSITION}, \text{CONSTRAINT} \}$.  
   Aristas $\mathcal{E}_R \in \{ \text{MODIFIES}, \text{RESTRICTS}, \text{COORDINATES\_WITH}, \text{PRECEDES} \}$.
2. **$\mathcal{M} \in \{ \text{DEONTIC\_OBLIGATION}, \text{CORRECTIVE\_ACTION}, \text{SYMMETRIC\_RECIPROCITY}, \text{DESCRIPTIVE\_STATE} \}$ (Modalidad Estructural):**  
   Extraída de la configuración de relaciones gramaticales (verbos modales, negaciones, pronombres recíprocos), no de palabras aisladas.
3. **$\Pi \in \{ +1, -1, 0 \}$ (Polaridad y Restricción):**  
   Preservación vs Eliminación/Mitigación.
4. **$\mathcal{T}_{\text{temp}} \in \{ \text{INVARIANT}, \text{DISCRETE\_EVENT}, \text{SEQUENCE} \}$ (Temporalidad de Proceso).**
5. **$\kappa \in \{ \text{UNARY}, \text{BINARY\_SYMMETRIC}, \text{HIERARCHICAL}, \text{DISTRIBUTED} \}$ (Cardinalidad Estructural).**

---

## 4. ALGORITMO $Q \to \text{FCC}_{\text{v2}}(Q)$ (SEPARACIÓN LÉXICA vs ESTRUCTURAL)

| Capa de Extracción | ¿Depende de Cues Léxicos Específicos? | ¿Qué Información Extrae? |
|---|:---:|---|
| **Morfosintaxis y Deixis** | No (Estructura gramatical universal) | Pronombres recíprocos (`nos`, `mutuo`), negaciones (`sin`, `no`), conjunciones condicionales (`para que`). |
| **Topología de Relaciones** | No | Estructura de transitividad: ¿Quién actúa sobre qué? ¿Hay jerarquía o simetría? |
| **Polaridad y Modalidad** | No | ¿Se busca habilitar, restringir o reparar? |
| **Vocabulario de Dominio** | **Sí (Solo como señal opcional $S_{\text{lex}}$)** | Lemas y nombres propios (si existen, se usan; si no, la estructura $S_{\text{struct}}$ opera autónomamente). |

---

## 5. MÉTRICA DE SIMILITUD PRELÉXICA $S_{\text{RCIL-v2}}$

La afinidad entre una consulta $Q$ y un nodo de memoria $M$ se calcula desacoplando la señal estructural de la señal léxica:

$$S_{\text{RCIL-v2}}(Q, M) = \alpha \cdot \text{GraphIsomorphism}(\mathcal{G}_{\text{roles}}^Q, \mathcal{G}_{\text{roles}}^M) + \beta \cdot \delta(\mathcal{M}_Q, \mathcal{M}_M) + \gamma \cdot \delta(\kappa_Q, \kappa_M)$$

Si $L_{\text{cue}}(Q) = 0.0$, el sistema opera exclusivamente con los componentes estructurales $\alpha, \beta, \gamma$.

---

## 6. PROTOCOLO DEL EXPERIMENTO MÍNIMO FALSABLE (FASE 5-B)

### 6.1. Requisitos del Benchmark de Independencia Léxica:
1. **15 Casos Certificados:**
   - $L_{\text{cue}}(Q) = 0.0$ estricto (ningún término de la consulta coincide con palabras de las reglas de memoria).
   - $\text{ZERO\_FTS} = \text{PASS}$
   - $\text{ZERO\_OVERLAP} = \text{PASS}$
   - $\text{ZERO\_ALIAS} = \text{PASS}$
   - $\text{ZERO\_DIRECT\_EDGE} = \text{PASS}$
2. **20 Controles Negativos Adversariales:**
   - Evaluados con el umbral congelado $\lambda = 0.65$.

### 6.2. Criterios de Falsabilidad / Éxito para RCIL v0.2:
- **Éxito:** $\text{Recall@5} \ge 25.0\%$ sobre los casos certificados con $L_{\text{cue}}(Q) = 0.0$ y $\text{FP} \le 1/20$ ($5.0\%$).
- **Falsabilidad / Rechazo:** Si $\text{Recall@5} < 10.0\%$ cuando $L_{\text{cue}} = 0.0$, se rechazará la hipótesis de que la estructura preléxica es suficiente para recuperar conceptos en este corpus sin embeddings.

---

## 7. CONCLUSIÓN Y ESTADO

- **Fase 5 v0.1:** Cerrada formalmente como resultado negativo útil (diagnóstico de dependencia léxica).
- **Fase 5 v0.2:** Especificada formalmente para evaluación de representaciones preléxicas sin hardcoding de diccionarios.
- **Producción:** Preservada al 100% sin modificaciones.
