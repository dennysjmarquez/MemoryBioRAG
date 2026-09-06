# 📐 Memoria Composicional Relacional (RCRD) — Formalización Teórica y Matemática

**Autores:** Dennys Márquez, Aureon & Artemis (Antigravity)  
**Fecha:** 2026-09-06  
**Versión:** 1.0.0-Formal  
**Estado:** Documento Fundacional de Arquitectura Simbólica

---

## 1. Definición Formal del Espacio de Memoria Relacional

Definimos una **Memoria Composicional Relacional** $\mathcal{M}$ como la 6-tupla:

$$\mathcal{M} = \big(V,\, E,\, R,\, \Pi,\, \Theta,\, \Sigma\big)$$

donde:

1. **$V$ (Conjunto de Estados y Nodos de Concepto):**
   $$V = \{v_1, v_2, \dots, v_n\}$$
   Cada nodo $v_i \in V$ representa una memoria declarativa, procedimental, episódica o causal persistida.

2. **$E$ (Topología de Relaciones Sinápticas):**
   $$E \subseteq V \times V \times \mathcal{W} \times \mathcal{T}_{\text{edge}}$$
   donde cada arista $e = (v_i, v_j, w, \tau)$ denota una conexión con peso sináptico $w \in [0, 1]$ y tipo relacional $\tau \in \{\text{causal}, \text{jerárquico}, \text{asociativo}, \text{precedencia}, \text{antagonismo}\}$.

3. **$R$ (Asignación de Marcos de Roles Semánticos):**
   $$R: V \to \mathcal{F}_{\text{role}}$$
   donde $\mathcal{F}_{\text{role}}$ define asignaciones de agente, paciente, restricción simétrica o asimetría dirigida:
   $$\mathcal{F}_{\text{role}} = \{\langle \text{Agent}_A,\, \text{Agent}_B,\, \text{RelType},\, \text{NegativeRestriction} \rangle\}$$

4. **$Pi$ (Espacio de Restricciones y Polaridad Proposicional):**
   $$\Pi: V \to \{-1, +1\} \times \mathcal{C}_{\text{struct}}$$
   donde $\mathcal{C}_{\text{struct}}$ es el álgebra de restricciones estructurales (ej. $\text{NEGATIVE\_HIERARCHY}$, $\text{MANDATORY\_PRECONDITION}$, $\text{CORRECTIVE\_FIX}$).

5. **$\Theta$ (Modalidad Deóntica y Precedencia Temporal):**
   $$\Theta: V \to \mathcal{M}_{\text{deon}} \times \mathcal{T}_{\text{order}}$$
   donde $\mathcal{M}_{\text{deon}} \in \{\text{OBLIGATION}, \text{PERMISSION}, \text{PROHIBITION}, \text{DECLARATIVE}\}$ y $\mathcal{T}_{\text{order}} \in \{\text{TIME\_INVARIANT}, \text{PRECEDENCE\_A\_BEFORE\_B}\}$.

6. **$\Sigma$ (Dinámica Energética y Umbral de Activación):**
   $$\Sigma(v_i) = \sigma_i \in [0, 1]$$
   Un nodo solo emite resonancia cognitiva hacia la corteza si su energía $\sigma_i \ge \lambda = 0.65$.

---

## 2. El Pipeline de Recuperación Simbólico-Proposicional

Dado un estímulo lingüístico de entrada $Q$ (consulta), el proceso de recuperación no mapea $Q$ a un vector denso opaco, sino que sigue una transformación causal determinista:

$$Q \xrightarrow{\quad\text{Parser}\quad} G_Q \xrightarrow{\quad\text{Composición}\quad} C_Q \xrightarrow{\quad\text{Navegación}\quad} \mathcal{M} \xrightarrow{\quad\text{Inferencia}\quad} \text{Top-}k(V)$$

### Paso 1: Extracción del Grafo Proposicional Local ($G_Q$)
$$G_Q = \langle \text{PredicadoPrincipal},\, \text{OperadorModal},\, \text{Alcance},\, \text{Subordinada} \rangle$$
El operador modal se vincula con alcance explícito sobre la proposición dependiente:
$$\text{Scope}(\text{Operador}) \subseteq \text{Argumentos}(G_Q)$$

### Paso 2: Síntesis Composicional de Orden Superior ($C_Q = A \oplus B$)
Dadas dos subestructuras o dimensiones reconocidas $A, B \in \mathcal{C}_{\text{domain}}$:
$$C_Q = A \oplus B$$
donde el operador de composición $\oplus$ genera un marco de restricción conjunto:
$$\Pi(C_Q) = \Pi(A) \wedge \Pi(B), \qquad \Theta(C_Q) = \Theta(A) \circ \Theta(B)$$

### Paso 3: Función de Compatibilidad Estructural $\kappa(C_Q, v_i)$
La afinidad energética entre la composición sintetizada $C_Q$ y un nodo $v_i \in V$ se define como:

$$\kappa(C_Q, v_i) = \begin{cases}
0.0 & \text{si } \text{Incompatible}(C_Q, v_i) \lor \Pi(C_Q) \ne \Pi(v_i) \\
\alpha \cdot \mathbf{1}_{\{\text{Constraint}\}} + \beta \cdot \frac{|C_Q \cap \text{Compounds}(v_i)|}{|C_Q \cup \text{Compounds}(v_i)|} + \gamma \cdot \mathbf{1}_{\{\text{RelType}\}} + \delta \cdot \mathbf{1}_{\{\text{Modal}\}} & \text{en otro caso}
\end{cases}$$

con $\alpha = 0.40, \beta = 0.30, \gamma = 0.15, \delta = 0.10, \epsilon_{\text{temp}} = 0.05$.

---

## 3. Taxonomía de Incompatibilidad y Abstención ($\text{Score} = 0.0$)

El sistema implementa una función de colapso energético ante **incompatibilidad estructural**:

$$\text{Incompatible}(A, B) \iff \exists \phi \in \text{Axiomas}: (A \wedge B) \vdash \bot$$

1. **Paradoja Deóntica:** $\text{OBLIGATION}(\text{VIOLATE}(\text{RULES})) \implies \bot \implies \kappa = 0.0$.
2. **Contradicción Acción-Destrucción:** $\text{REPAIR}(\text{SYSTEM}) \wedge \text{DESTROY}(\text{SYSTEM}) \implies \bot \implies \kappa = 0.0$.
3. **Paradoja de Jerarquía:** $\text{EQUAL\_PEERS} \wedge \text{UNILATERAL\_TYRANNY} \implies \bot \implies \kappa = 0.0$.
4. **Contradicción Epistémica:** $\text{CAUSAL\_LESSON}(\text{PROHIBIT\_LEARNING}) \implies \bot \implies \kappa = 0.0$.

---

## 4. Taxonomía Epistemológica de Rescate

| Clase | Definición Formal | Significado Cognitivo |
|---|---|---|
| **$E_1$ (Equivalencia Directa)** | $C_Q \equiv \text{FCC}(v_i)$ preexistente en $V$. | Reconocimiento de plantilla estructural conocida. |
| **$E_2$ (Intersección de Subgrafo)** | $C_Q \cap \text{FCC}(v_i) \neq \emptyset \land \kappa \ge 0.65$. | Conexión relacional parcial o multi-hop. |
| **$E_3$ (Composición Emergente Fuerte)** | $C_Q = A \oplus B \notin \mathcal{M}_{\text{index}} \land A \text{ solo falla} \land B \text{ solo falla} \land \kappa(C_Q, v_i) \ge 0.85$. | Síntesis en runtime de una configuración relacional nunca antes indexada. |
| **$D$ (Degenerado / Coincidental)** | Rescate con $L_{\text{cue}} > 0$ o colisión por atractor genérico. | Ruido o fuga léxica superficial. |
| **$\text{Abstain}$** | $\kappa < 0.65 \lor \text{Incompatible}(Q) \implies \sigma = 0.0$. | Abstención segura ante insuficiencia o paradoja. |
| **$F$ (Falso Positivo)** | $\kappa(Q_{\text{adversarial}}, v_i) \ge 0.65$ sobre un control negativo. | Error de activación adversarial. |

---

## 5. Teorema de Invarianza Distribucional (LOTO)

$$\forall v_i \in V, \quad \kappa(C_Q, v_i) \perp \mathbf{W}_{\text{PPMI}}(v_i)$$

La función de recuperación composicional $\kappa$ opera sobre el álgebra relacional $(\Pi, \Theta, R)$, garantizando que la exclusión del vector distribucional de $v_i$ de la matriz PPMI+SVD produce una variación neta $\Delta\kappa = 0.00$.
