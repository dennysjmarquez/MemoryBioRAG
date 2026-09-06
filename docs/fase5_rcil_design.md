# FASE 5 — Representación Conceptual Independiente del Léxico (RCIL)
## Especificación Experimental v0.1: Formalización de la Forma Conceptual Canónica (FCC) y Protocolo de Falsabilidad

**Autores:** Equipo de Investigación MemoryBioRAG (Dennys & Aureon)  
**Fecha:** 2026-09-05  
**Versión:** 0.1 (Revisión Post-Auditoría Aureon)  
**Estado:** Especificación Experimental Formal (Pre-Implementación)  
**Restricción Inmutable:** Preservación absoluta de `core/`, snapshot canónico congelado y tests de regresión.

---

## 1. EL PROBLEMA FUNDAMENTAL: ¿QUÉ ES EL ABISMO LÉXICO?

El abismo léxico en recuperación de información sin embeddings densos ocurre cuando:
1. $tokens(Q) \cap tokens(G) = \emptyset$ (solapamiento léxico superficial nulo).
2. $G \notin \text{FTS5}(Q)$ (ausencia total de match en índices invertidos tradicionales).
3. No existe arista directa $(Q_{\text{seed}} \to G) \in \text{sinapsis}$ (ausencia de conocimiento explícito pregrabado).

**La Trampa a Evitar:**  
Si la transformación $Q \to \text{FCC}(Q)$ se reduce a un diccionario hardcodeado de sinónimos (`"sobrescribir"` $\to$ `OVERWRITE`), no habremos resuelto el abismo: simplemente habremos trasladado el léxico a un nivel léxico-canónico dependiente de cobertura manual.

**La Propuesta Científica de RCIL:**  
La **Forma Conceptual Canónica (FCC)** no sustituye palabras por lemas en inglés; extrae **relaciones funcionales de primer orden, arquetipos de intención y posiciones topológicas en el grafo**.

---

## 2. FORMALIZACIÓN MATEMÁTICA OPERACIONAL DE LA FCC

Cada consulta $Q$ y cada nodo de memoria $M$ se proyectan en una 5-tupla determinista y computable:

$$\text{FCC}(x) = \langle \mathcal{F}_x, \mathcal{P}_x, \mathcal{D}_x, \mathcal{R}_x, \sigma_x \rangle$$

### 2.1. $\mathcal{F}_x \in \mathbb{F}$ — Arquetipo de Marco Estructural (Frame)
Espacio finito y cerrado de 7 intenciones funcionales:
$$\mathbb{F} = \{ \text{NORMA/PROTOCOLO}, \text{FIX/MITIGACION}, \text{EVALUACION/BENCHMARK}, \text{LECCION/METODOLOGIA}, \text{GOBERNANZA/CASO}, \text{ARQUITECTURA/DOCS}, \text{IDENTIDAD/ROL} \}$$

**Algoritmo Determinista de Inferencia de Marco ($Q \to \mathcal{F}_Q$):**
- Se detecta la modalidad sintáctico-funcional del verbo/núcleo (deóntico $\to$ `NORMA`, mitigativo $\to$ `FIX`, métrico $\to$ `BENCHMARK`, etc.).

---

### 2.2. $\mathcal{P}_x = \langle \text{Rol\_Sujeto}, \text{Clase\_Acción}, \text{Rol\_Objeto}, \text{Modalidad} \rangle$ — Firma de Predicado
Roles relacionales abstractos de primer orden:
- $\text{Clase\_Acción} \in \{ \text{PREVENT}, \text{FIX}, \text{MEASURE}, \text{CONNECT}, \text{DEFINE}, \text{COORDINATE}, \text{SYNC} \}$
- $\text{Rol\_Objeto} \in \{ \text{HEADER/META}, \text{SYNC\_PIPELINE}, \text{LATENCY/PERF}, \text{PERMISSION/AUTHORITY}, \text{STATE/DATA} \}$
- $\text{Modalidad} \in \{ \text{MANDATORY}, \text{DESCRIPTIVE}, \text{CORRECTIVE}, \text{HISTORICAL} \}$

---

### 2.3. $\mathcal{D}_x \in \mathbb{R}^{13}$ — Coordenada Dimensional Canónica
Vector continuo ralo normalizado en el espacio de 13 ejes semánticos de BioRAG:
- Ejes: `temporalidad`, `criticidad`, `scope_arquitectonico`, `estabilidad`, `volatilidad`, `nivel_abstraccion`, `formalidad`, `contingencia_contexto`, etc.

---

### 2.4. $\mathcal{R}_x$ — Firma Topológica y Perfil de Conectividad
Vector característico de grados y tipos de adyacencia en $\text{sinapsis}$:
$$\mathcal{R}_x = \langle d_{\text{in}}^{\tau_1}, d_{\text{out}}^{\tau_1}, d_{\text{in}}^{\tau_2}, d_{\text{out}}^{\tau_2}, \dots, d_{\text{in}}^{\tau_K}, d_{\text{out}}^{\tau_K} \rangle$$
donde $\tau_k \in \{ \text{sinonimo\_explicito}, \text{pmi\_hebbiano}, \text{co\_semantica}, \text{manual} \}$.

---

### 2.5. $\sigma_x \in [0, 1]$ — Masa de Activación y Coocurrencia Latente
Energía propagada Hebbiana acumulada desde las semillas pivote mediante atenuación exponencial.

---

## 3. FUNCIÓN DE SIMILITUD ESTRUCTURAL DETERMINISTA $S_{RCIL}$

En lugar de apelar a un "isomorfismo abstracto", definimos la afinidad mediante una combinación lineal convexa y descompuesta operacionalmente:

$$S_{RCIL}(Q, M) = w_F S_F(Q, M) + w_P S_P(Q, M) + w_D S_D(Q, M) + w_R S_R(Q, M) + w_\sigma S_\sigma(Q, M)$$

Donde los pesos satisfacen $\sum w_i = 1.0$ ($w_F=0.30, w_P=0.25, w_D=0.15, w_R=0.15, w_\sigma=0.15$) y cada término se calcula como:

1. **Similitud de Marco ($S_F$):**
   $$S_F(Q, M) = \begin{cases} 1.0 & \text{si } \mathcal{F}_Q = \mathcal{F}_M \\ 0.0 & \text{si } \mathcal{F}_Q \neq \mathcal{F}_M \land \mathcal{F}_M \neq \text{GENERAL} \\ 0.5 & \text{si } \mathcal{F}_M = \text{GENERAL} \end{cases}$$

2. **Similitud de Predicado ($S_P$):**
   $$S_P(Q, M) = \frac{|\mathcal{P}_Q \cap \mathcal{P}_M|}{|\mathcal{P}_Q \cup \mathcal{P}_M|} = \text{Jaccard\_Roles}(\mathcal{P}_Q, \mathcal{P}_M)$$

3. **Similitud Dimensional ($S_D$):**
   $$S_D(Q, M) = \frac{\mathcal{D}_Q \cdot \mathcal{D}_M}{\|\mathcal{D}_Q\| \|\mathcal{D}_M\|} \quad (\text{Coseno en el simplex de 13 ejes})$$

4. **Similitud Topológica ($S_R$):**
   $$S_R(Q, M) = 1.0 - \frac{\|\mathcal{R}_Q - \mathcal{R}_M\|_1}{\|\mathcal{R}_Q\|_1 + \|\mathcal{R}_M\|_1 + \epsilon}$$

5. **Energía Composicional Multi-Hop ($S_\sigma$):**
   $$S_\sigma(Q, M) = \max_{p \in \text{Paths}(Q, M)} \prod_{e_i \in p} \Big( w(e_i) \cdot \gamma(\text{tipo}(e_i)) \Big)$$

---

## 4. CONTROL RIGUROSO DE FALSOS POSITIVOS Y UMBRALIZACIÓN CALIBRADA

### Corrección Metodológica:
La calibración conformal **no garantiza 0% de Falsos Positivos**. Lo que proporciona es un mecanismo formal para estimar un umbral empírico $\lambda_{1-\alpha}$ a partir de una muestra de calibración negativa, acotando probabilísticamente la tasa de falsa alarma bajo la hipótesis de distribución idéntica:

$$P(\text{Score}(Q_{\text{negativo}}) \ge \lambda_{1-\alpha}) \le \alpha$$

### Batería de 6 Tipos de Negativos Adversariales Obligatorios:
Para evitar evaluaciones triviales por cambio de tema, el conjunto de prueba negativo debe incluir:
- **$N_1$ — Negativo Cross-Domain:** Consulta ajena al corpus (medicina, cocina, astronomía).
- **$N_2$ — Mismo Dominio, Marco Distinto:** Pregunta sobre normativa aplicada a un caso de benchmark.
- **$N_3$ — Mismo Marco, Objeto Distinto:** Pregunta de `FIX` sobre `SQL Injection` buscando engañar al `FIX` de `Headers`.
- **$N_4$ — Misma Estructura Parcial, Predicado Contradictorio:** Incompatibilidad lógica en la acción requerida.
- **$N_5$ — Super-Hub Adversarial:** Consulta diseñada para activar nodos de alto grado sin relevancia conceptual.
- **$N_6$ — Cercanía Topológica Espuria:** Nodos conectados por coocurrencia histórica débil pero conceptualmente disonantes.

---

## 5. TAXONOMÍA REFINADA DE RESCATES EXPERIMENTALES (8 CLASES)

Para certificar si un acierto proviene de memoria previa o de inferencia genuina:

| Clase | Nombre | Definición Operacional |
|---|---|---|
| **A** | Expansión Léxica | Rescate mediante sinónimos morfológicos o lemas superficiales (WordNet). |
| **B** | Relación Explícita Directa | Rescate mediante una arista preexistente $(Q_{\text{seed}} \to G) \in \text{sinapsis}$. |
| **C** | Propagación 1-Hop | Rescate en la vecindad inmediata $k=1$ de un nodo encontrado por FTS. |
| **D** | Composición Multi-Hop Formal | Derivación transitiva $A \to B \to C$ donde $(A \to C) \notin \text{sinapsis}$. |
| **$E_1$** | FCC Equivalente Preexistente | La estructura $\text{FCC}(Q)$ coincide con una estructura $\text{FCC}(G)$ ya indexada en memoria. |
| **$E_2$** | FCC Parcial + Inferencia Causal | Rescate derivado por alineación parcial de marco y predicado cruzado. |
| **$E_3$** | Inferencia Estructural Nueva | Generación pura a partir de álgebras de relaciones sin camino previo. |
| **F** | Falso Positivo / Leakage | Activación sobre controles negativos o acceso indebido al gold. |

> **Criterio de Generalización Real:** Solo las clases **D, $E_1, E_2, E_3$** cuentan como evidencia de recuperación a través del abismo léxico.

---

## 6. PLAN DE ABLACIONES Y EVALUACIÓN COMPARATIVA

El experimento contrastará 8 configuraciones sobre el mismo benchmark ciego:

1. **M0 — Baseline Actual:** FTS5 + Grafo 1-Hop tradicional.
2. **M1 — WordNet Expansion:** Expansión léxica general.
3. **M2 — Concept Hub:** Puentes ontológicos explícitos.
4. **M3 — PPMI / SVD:** Similitud latente por coocurrencia (100 dims).
5. **M4 — Inferencia Simbólica Multi-Hop:** Composición transitiva pura (Fase 4.5.2).
6. **M5 (Ablación 1) — RCIL-F:** Solo Marco Estructural ($\mathcal{F}$).
7. **M6 (Ablación 2) — RCIL-FP:** Marco Estructural + Predicado ($\mathcal{F} + \mathcal{P}$).
8. **M7 — RCIL-Full:** Pipeline Completo ($\mathcal{F} + \mathcal{P} + \mathcal{D} + \mathcal{R} + \sigma$).

---

## 7. CRITERIOS DE ÉXITO ESTADÍSTICO Y FALSABILIDAD

En lugar de umbrales arbitrarios, los criterios de decisión se basan en **ganancia neta estadísticamente significativa frente al baseline**:

1. **Criterio Primario (Poder de Rescate D/E):**
   $$\Delta \text{Recall@5}_{(D/E)} = \text{Recall@5}(\text{RCIL}) - \text{Recall@5}(\text{M0}) > 0 \quad (p < 0.05)$$
   con un mínimo de **$\ge 5$ rescates clasificados estrictamente en $D, E_1, E_2, E_3$**.

2. **Criterio de Selectividad y Seguridad:**
   $$\text{Tasa de FP en Negativos Adversariales } (N_1 \dots N_6) \le 5.0\% \quad (\le 1/20)$$

3. **Criterio de Eficiencia:**
   $$\text{Latencia Media por Consulta } \le 30.0\text{ ms}$$

4. **Criterio de Falsabilidad / Descarte Inmediato:**
   Si RCIL-Full no supera a RCIL-FP o produce $> 2/20$ Falsos Positivos en la batería adversarial $N_1 \dots N_6$, la hipótesis de representación estructural será declarada no viable en su formulación actual.

---

## 8. CONCLUSIÓN Y ESTADO DE LA FASE

Esta especificación v0.1:
1. Elimina afirmaciones no fundamentadas sobre "0% FP" y "isomorfismo absoluto".
2. Formaliza determinísticamente cada término de $S_{RCIL}$.
3. Introduce la batería de negativos adversariales estructurales ($N_1 \dots N_6$).
4. Establece las ablaciones requeridas (`RCIL-F`, `RCIL-FP`, `RCIL-Full`).

**Estado:** Documento completado para revisión y autorización previa a la fase de prototipado experimental.
