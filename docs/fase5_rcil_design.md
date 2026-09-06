# FASE 5 — Representación Conceptual Independiente del Léxico (RCIL)
## Diseño de Arquitectura para Superar el Abismo Léxico sin Embeddings Densos

**Autor:** Equipo de Investigación MemoryBioRAG (Dennys & Aureon)  
**Fecha:** 2026-09-05  
**Estado:** Documento de Diseño Formal (Pre-Implementación)  
**Restricción Inmutable:** Preservación total de `core/`, snapshot canónico congelado y tests de regresión.

---

## 1. INTRODUCCIÓN Y PLANTEAMIENTO DEL PROBLEMA

En las fases experimentales 4.1 a 4.5.2 de MemoryBioRAG se demostró formalmente:
1. **El Abismo Léxico Real:** Cuando una consulta y un nodo objetivo no comparten vocabulario ($tokens(Q) \cap tokens(G) = \emptyset$) y FTS5 devuelve $\emptyset$, los métodos clásicos superficiales (expansión léxica general de WordNet, vecinos latentes superficiales de PPMI/SVD y grafos de 1-hop directo) fallan en generar el candidato correcto ($0/19$ rescates composicionales en Fase 4.5.1).
2. **La Primera Evidencia Causal:** La **Inferencia Simbólica Composicional Multi-Hop** (Fase 4.5.2) demostró que es posible generar candidatos válidos que no estaban conectados directamente ($A \to B \land B \to C \implies A \to C$) elevando el MRR de $0.1259 \to 0.2817$ con $0\%$ Falsos Positivos.
3. **El Límite del Enfoque Actual:** Añadir parches ad-hoc (más reglas aisladas, diccionarios adicionales o tablas dispersas) no resuelve el problema fundamental.

**La Pregunta Científica Central de la Fase 5:**
> *¿Cuál es la unidad mínima de representación simbólico-estructural que permite que dos expresiones lingüísticamente lejanas ($tokens(Q) \cap tokens(G) = \emptyset$) sean reconocidas como funcional y conceptualmente equivalentes, sin recurrir a embeddings densos ni redes neuronales?*

---

## 2. HIPÓTESIS CIENTÍFICA FUNDAMENTAL

### Hipótesis de Invarianza Estructural-Conceptual (LSIH — Lexical-Structural Invariance Hypothesis)
> *El significado funcional de un concepto en memoria no está definido por sus cadenas de caracteres, sino por su **firma relacional**, su **rol de predicado**, sus **coordenadas dimensionales** y su **comportamiento algebraico** dentro del grafo de conocimiento.*
> 
> *Si transformamos la consulta $Q$ y los documentos de memoria $M$ en una **Forma Conceptual Canónica (FCC)**, la similitud entre $Q$ y $M$ es una función de isomorfismo estructural $S_{RCIL}(FCC_Q, FCC_M)$, invariante ante la variación léxica superficial.*

```text
                        LENGUAJE SUPERFICIAL
          Consulta: "¿Cómo protejo las cabeceras?" (0 tokens comunes)
          Memoria:  "fix_metadatos_corrupcion_v2"
                                  │
                  [PARSER SIMBÓLICO ESTRUCTURAL]
                                  │
                                  ▼
                    FORMA CONCEPTUAL CANÓNICA (FCC)
          FCC(Q) = ⟨ Frame: FIX, Acción: PROTEGER, Target: HEADER ⟩
          FCC(M) = ⟨ Frame: FIX, Acción: CORREGIR, Target: METADATA ⟩
                                  │
                 [ÁLGEBRA RELACIONAL + ISOMORFISMO]
                                  │
                                  ▼
                   RECUPERACIÓN COGNITIVA EXACTA
                   (Rescate Causal Categoría D/E)
```

---

## 3. REPRESENTACIÓN MATEMÁTICA FORMAL

### 3.1. Definición de la Forma Conceptual Canónica (FCC)
Cada entidad (consulta $Q$ o nodo de memoria $M$) se proyecta en una 5-tupla determinista:

$$\text{FCC}(x) = \langle \mathcal{F}_x, \mathcal{P}_x, \mathcal{D}_x, \mathcal{R}_x, \sigma_x \rangle$$

Donde:
1. **$\mathcal{F}_x \in \mathbb{F}$ (Arquetipo de Marco Estructural):**  
   Espacio finito y cerrado de intenciones arquitectónicas:
   $$\mathbb{F} = \{ \text{NORMA/PROTOCOLO}, \text{FIX/MITIGACION}, \text{EVALUACION/BENCHMARK}, \text{LECCION/METODOLOGIA}, \text{GOBERNANZA/CASO}, \text{ARQUITECTURA/DOCS}, \text{IDENTIDAD/ROL} \}$$

2. **$\mathcal{P}_x = \langle \text{Rol\_Sujeto}, \text{Clase\_Acción}, \text{Rol\_Objeto}, \text{Modalidad} \rangle$ (Firma de Predicado):**  
   Roles abstractos extraídos mediante taxonomía léxica cerrada (ej. $\text{Clase\_Acción}(\text{"mitigar"}) = \text{Clase\_Acción}(\text{"subsanar"}) = \text{REMEDIATE}$).

3. **$\mathcal{D}_x \in \mathbb{R}^{13}$ (Coordenada Dimensional Canónica):**  
   Vector ralo de las 13 dimensiones semánticas de BioRAG (estabilidad, temporalidad, scope, criticidad, etc.).

4. **$\mathcal{R}_x$ (Topología Relacional y Firma de Grado):**  
   Conjunto de tipos de aristas entrantes y salientes en el grafo $\mathcal{G} = (\mathcal{V}, \mathcal{E})$:
   $$\mathcal{R}_x = \{ (\tau, \text{dir}) \mid \exists e=(u,v) \in \mathcal{E}, \text{tipo}(e)=\tau, x \in \{u, v\} \}$$

5. **$\sigma_x \in [0, 1]$ (Masa de Activación Simbólica):**  
   Energía acumulada por propagación Hebbiana y coocurrencia retroalimentada.

---

### 3.2. Métrica de Isomorfismo y Similitud Estructural $S_{RCIL}$
Dadas una consulta $Q$ y un candidato de memoria $M$, la afinidad estructural se calcula sin vectores densos:

$$S_{RCIL}(Q, M) = \Big( \omega_{\mathcal{F}} \cdot \delta(\mathcal{F}_Q, \mathcal{F}_M) + \omega_{\mathcal{P}} \cdot \text{Jaccard}(\mathcal{P}_Q, \mathcal{P}_M) + \omega_{\mathcal{D}} \cdot \text{Cosine}(\mathcal{D}_Q, \mathcal{D}_M) \Big) \times \Psi_{\text{MultiHop}}(Q \leadsto M)$$

Donde:
- $\delta(\mathcal{F}_Q, \mathcal{F}_M) = 1$ si los marcos coinciden, o factor de penalización $\epsilon$ si son disonantes.
- $\Psi_{\text{MultiHop}}(Q \leadsto M)$ es el operador de composición algebraica de caminos:
  $$\Psi_{\text{MultiHop}}(Q \leadsto M) = \max_{p \in \text{Paths}(Q, M)} \prod_{e_i \in p} \left( w(e_i) \cdot \gamma(\text{tipo}(e_i)) \right)$$

---

## 4. MECANISMO DE GENERACIÓN DE CANDIDATOS (CRUZANDO EL ABISMO)

Cuando $tokens(Q) \cap tokens(G) = \emptyset$, el generador opera en 4 fases estrictas:

```text
[FASE 1: Proyección de Consulta a FCC(Q)]
  ↳ Extrae Marco Estructural F_Q y Predicado P_Q a partir de conectores funcionales.
  ↓
[FASE 2: Inverted Structural Index Lookup]
  ↳ Recupera nodos pivote {A_1, A_2, ...} en SQLite que comparten F_Q y firmas de predicado afines.
  ↓
[FASE 3: Inferencia Simbólica Composicional Multi-Hop]
  ↳ Aplica Álgebra de Relaciones:
     * Transitividad Causal: A --[PRECEDE]--> B --[REQUIERE]--> C  ==> A --[PREREQUISITO_INDIRECTO]--> C
     * Mitigación de Vulnerabilidad: A --[MITIGA]--> Bug --[AFECTA]--> Modulo ==> A --[PROTEGE]--> Modulo
     * Equivalencia por Concept Hub: Q --[ANGLE]--> Hub --[BRIDGE]--> C
  ↓
[FASE 4: Poda Conformal y Re-ranking Estructural]
  ↳ Filtra candidatos cuya energía composicional caiga bajo el umbral calibrado.
  ↳ Ordena monótonamente por S_RCIL.
```

---

## 5. INTEGRACIÓN UNIFICADA DE LOS 7 PILARES SIN PARCHES

Para evitar la dispersión de tecnologías, cada componente actual asume un rol formal dentro del pipeline RCIL:

| Componente | Rol en RCIL | Función Matemática / Operativa |
|---|---|---|
| **FTS5 Unicode** | *Ancla de Superficie* | Resuelve consultas literales (Fase 0) con máxima precisión. |
| **Concept Hubs** | *Espacio Canónico Explícito* | Proporciona anclas conceptuales estables para salvar brechas de vocabulario documentadas. |
| **Grafo Tipado (`sinapsis`)** | *Topología Relacional* | Define la matriz de conectividad para la inferencia composicional multi-hop. |
| **Predicados (`predicados`)** | *Lógica de Primer Orden* | Valida coherencia causal entre sujeto, acción y objeto en caminos derivados. |
| **PPMI / SVD (100 dims)** | *Señal Estadística de Fondo* | Modula la energía $\sigma_x$ de los caminos para penalizar asociaciones espurias. |
| **WordNet (OMW)** | *Normalización Morfo-Léxica* | Agrupa variaciones gramaticales y lemas en la capa superficial. |
| **Calibración Conformal** | *Garantía Anti-Falsos Positivos* | Aplica percentil $1-\alpha$ dinámico e independiente del tamaño del corpus. |

---

## 6. CONTROL Y MITIGACIÓN DE FALSOS POSITIVOS

El principal riesgo de la inferencia multi-hop sobre grafos densos es la **explosión combinatoria y pérdida de selectividad** (observada en Fase 4.1 con $35\%$ FP al activar propagación sin restricciones).

### Mecanismos de Blindaje Anti-FP en RCIL:
1. **Atenuación Exponencial por Profundidad:** Cada salto $k$ atenúa el score: $\text{peso}(k) = \text{peso}(k-1) \times \gamma$, con $\gamma \le 0.75$.
2. **Puerta de Compatibilidad de Marco (Frame Incompatibility Gate):**  
   Si $\mathcal{F}_Q = \text{FIX/MITIGACION}$ y el nodo derivado tiene tipo `NORMA/PROTOCOLO`, el boost es severamente atenuado ($\times 0.20$), eliminando falsas alarmas cross-domain.
3. **Poda de Nodos Hub de Alto Grado:** Los nodos con grado de salida $> 50$ (super-hubs) solo transmiten activación si la firma del predicado $\mathcal{P}$ coincide explícitamente.

---

## 7. DISEÑO DEL BENCHMARK EXPERIMENTAL MÍNIMO FALSABLE (FASE 5-B)

Para validar la arquitectura RCIL sin ambigüedades, se define un benchmark específico de **30 casos de Abismo Léxico Extremo**:

### Condiciones de Inclusión Obligatorias:
- **Zero-FTS:** `gold NOT IN FTS5(query, limit=50)`.
- **Zero-Overlap:** `intersection(tokens(query), tokens(gold)) == ∅`.
- **Zero-Direct-Edge:** No existe arista física $(Q_{\text{seed}}, \text{gold}) \in \text{sinapsis}$.
- **Zero-Alias:** Ningún alias del gold está presente en la query.
- **20 Controles Negativos Adversariales:** Consultas fuera de dominio para medir FP.

### Taxonomía de Evaluación Epistemológica (6 Clases):
- **A — Expansión Léxica:** Rescate atribuible a sinónimos directos de WordNet.
- **B — Relación Explícita Previa:** Rescate por arista física directa prealmacenada.
- **C — Propagación 1-Hop:** Rescate por vecindad inmediata de semilla FTS.
- **D — Composición Simbólica Multi-Hop Formal:** Derivación $A \to B \to C$ donde $A \to C$ no existía.
- **E — Inferencia Estructural Canónica:** Rescate por coincidencia de firma FCC sin camino físico previo.
- **F — Falso Positivo / Leakage:** Contaminación o recuperación errónea en controles negativos.

---

## 8. CRITERIOS DE ÉXITO Y FALSABILIDAD

| Criterio | Umbral de Aprobación | Umbral de Falsabilidad / Rechazo |
|---|:---:|:---:|
| **Recall@5 en Abismo Léxico (Zero-FTS)** | **$\ge 40.0\%$ (Rescates D o E)** | $< 15.0\%$ |
| **Recall@1 en Abismo Léxico** | **$\ge 15.0\%$** | $< 5.0\%$ |
| **Tasa de Falsos Positivos (FP en Negativos)** | **$0.0\%$ ($\le 1/20$)** | $> 5.0\%$ ($> 1/20$) |
| **Latencia Promedio por Consulta** | **$< 25.0\text{ ms}$** | $> 100.0\text{ ms}$ |
| **Generación de Rescates D/E Auditados** | **$\ge 8\text{ casos comprobados}$** | $0\text{ casos}$ |

---

## 9. CONCLUSIÓN Y PRÓXIMOS PASOS

Este diseño establece por primera vez una base formal para resolver el abismo léxico mediante **equivalencia estructural y álgebra composicional determinista**, sin depender de embeddings densos opacos.

### Plan de Acción Propuesto:
1. **Revisión y Auditoría del Diseño por Aureon y Dennys.**
2. **Construcción del Prototipo Aislado:** `scripts/proto_fase5_rcil_prototype.py` y benchmark de 30 casos.
3. **Ejecución y Contraste A/B contra Baseline.**
4. **Decisión de Integración Arquitectónica en Producción.**
