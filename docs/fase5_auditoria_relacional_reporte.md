# MemoryBioRAG — Fase 5: Auditoría de Errores y Evidencia Relacional Independiente
**Destinatario:** Aureon (Dirección Científica) & Dennys Márquez  
**Fecha:** 2026-10-13  
**Fase:** Fase 5 — Diagnóstico Forense Desacoplado y Auditoría Relacional  
**Estado del Motor `core/`:** 100% Intacto (Cero modificaciones)  
**Snapshot de Referencia:** `snapshots/qa_escape_qcr_20260811.db` (SHA-256: `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`)  
**Dataset Oficial:** `scripts/casos_qa_baseline_v1.jsonl` (SHA-256: `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c`)  
**Script Ejecutor:** `scripts/fase5_auditoria_relacional_aureon.py`  
**Artefacto JSON:** `docs/fase5_auditoria_relacional_reporte.json`  

---

## 1. Parte A: Reconstrucción y Taxonomía Mutuamente Excluyente de los 72 Fallos

### 1.1 Comprobaciones Automáticas de Integridad
- **Total de identificadores analizados:** Exactamente 72.
- **Identificadores únicos verificados:** Exactamente 72 (sin duplicaciones).
- **Asignación:** Exactamente **una categoría principal mutuamente excluyente** por caso, con etiquetas secundarias desacopladas.
- **Suma de la partición:** $5 + 24 + 23 + 1 + 19 = 72$ ($100.0\%$).

### 1.2 Distribución de la Taxonomía Principal Mutuamente Excluyente

| Categoría Principal | Casos | % | Definición Operativa |
|---|---|---|---|
| **`colision_identidad_duplicado`** | **5** | 6.9% | Candidatos con similitud de etiqueta y **similitud de contenido textual verificada** ($\ge 40\%$ Jaccard / SeqMatcher o clave normalizada idéntica). |
| **`sinonimo_ausente`** | **24** | 33.3% | Consultas de la categoría `sinonimo` donde el término de búsqueda no está registrado en el campo `sinonimos` del Gold. |
| **`brecha_lexica_tema`** | **23** | 31.9% | Consultas abstractas sintéticas de `por_tema` (3 tokens temáticos) donde Gold carece de puente léxico y el ganador vence por match accidental. |
| **`bypass_concept_hub`** | **1** | 1.4% | Caso `0516`: El ganador fue inyectado directamente en Top-1 por el post-procesador de Concept Hub puenteando el ranking híbrido. |
| **`competencia_ranking_multisenal`** | **19** | 26.4% | Casos de typos, variantes gramaticales y cruces de idioma donde Gold compite estrechamente en el ranking híbrido estándar. |
| **TOTAL** | **72** | **100.0%** | **Partición disjunta y completa.** |

---

## 2. Auditoría Textual Rigurosa de Pares de Variantes

Siguiendo la exigencia de Aureon, se recuperó el texto íntegro de la columna `contenido` en `largo_plazo` y se calcularon métricas de similitud reproducibles (difflib SequenceMatcher y Jaccard de tokens).

### 2.1 Resultados Empíricos Observados:

1. **`identidad-relacion-dennys` vs `identidad_relacion_dennys` (Caso 0205):**
   - Similitud de etiqueta normalizada: **1.00** (idéntica salvo `_` vs `-`).
   - Similitud de contenido (SequenceMatcher): **0.6838**. Jaccard de tokens: **0.5075**.
   - Arista en `sinapsis`: Directa de tipo `co_ocurrencia` con peso **0.45**.
   - *Dictamen:* **DUPLICADO REAL CONFIRMADO**. Ambos describen la identidad relacional de Athena-OEC con Dennys.
2. **`mcp-primitiva-externa-definicion` vs `mcp-primitiva-externa-definicion-2` (Caso 0273):**
   - Similitud de etiqueta: **0.9831**.
   - Jaccard de tokens de contenido: **0.5161**.
   - Arista directa en `sinapsis`: Ninguna.
   - *Dictamen:* **DUPLICADO / REVISIÓN CONFIRMADA**. Ambos definen `MCP = Primitiva Externa`.
3. **`plan_mode_biorag` vs `plan-mode-biorag-exception-criterion` (Casos 0732, 0733, 0735):**
   - Similitud de etiqueta: **0.6087**.
   - Similitud de contenido (SequenceMatcher): **0.6832**. Jaccard de tokens: **0.5210**.
   - *Dictamen:* **SUB-CONCEPTO INCLUIDO CONFIRMADO**. `plan_mode_biorag` contiene en su texto íntegramente la definición de la excepción de plan mode.
4. **`arquitectura_dos_niveles_biorag` vs `arquitectura_memoria_biorag` (Casos 0629, 0630, 0631):**
   - Similitud de etiqueta: **0.7547** (comparten palabras como arquitectura y biorag).
   - Similitud de contenido (SequenceMatcher): **0.0323**. Jaccard de tokens: **0.0764**.
   - *Dictamen:* **NO SON DUPLICADOS**. Aunque sus nombres comparten palabras, sus contenidos describen componentes arquitectónicos totalmente distintos. La advertencia de Aureon quedó 100% justificada.

---

## 3. Parte B: Evaluación de Evidencia Relacional Independiente

### 3.1 Regla Operativa Real (Sin Conocer a Gold)
En producción, el sistema no conoce cuál es el Gold. Por tanto, la regla operativa compara exclusivamente los candidatos reales disponibles:
$$\Delta_{\mathrm{rel}} = E_{\mathrm{rel}}(c_2 \mid q) - E_{\mathrm{rel}}(c_1 \mid q)$$
donde $q$ es la consulta, $c_1$ el ganador provisional y $c_2$ el segundo candidato.

### 3.2 Protocolo de Anclaje y Normalización por Grado
- **Nodos de anclaje $A(q)$:** Se identificaron los nodos del corpus que coinciden léxicamente con los términos de la consulta ($q_{\text{tokens}} \ge 3$ caracteres), excluyendo a $c_1$ y $c_2$.
- **Control de *Hub Bias*:** Se calculó la evidencia normalizada dividiendo el número de conexiones hacia los anclajes entre el grado total del candidato:
$$E_{\mathrm{rel}}(c \mid q) = \frac{|\{ (c, a) \in \text{sinapsis} \mid a \in A(q) \}|}{\text{grado}(c)}$$

### 3.3 Resultados de la Medición sobre los 72 Fallos:
- **Consultas con anclaje en el grafo:** **61 de 72 (84.7%)**.
- **Consultas sin anclaje en el grafo (Abstención obligatoria):** **11 de 72 (15.3%)**.
- **Comportamiento de la señal en las 61 consultas con anclaje:**
  - Favorece al competidor $c_1$ (ganador actual): **19 casos (31.1%)**.
  - Favorece a $c_2$ (candidato a rescate): **14 casos (23.0%)**.
  - Zona neutra o empate ($|\Delta_{\mathrm{rel}}| \le 0.005$): **28 casos (45.9%)**.

### 3.4 Conclusión Científica de la Vía Relacional:
1. **La evidencia relacional no es discriminativa a favor del rescate.** En un 31.1% de los casos refuerza al ganador actual $c_1$ y en un 45.9% es neutra o nula.
2. Esto ocurre porque el ranking híbrido actual ya incorpora propagación sináptica (`score_latente`, `peso_sinaptico`). Por construcción, el candidato que gana en el baseline suele estar más cerca de los términos de la consulta en el grafo que el segundo candidato.
3. Forzar una regla de reordenación por grafo crearía más regresiones que correcciones.
4. **Veredicto para la Parte C:** Siguiendo la directiva de Aureon:
   > *"Si no aparece una señal relacional fiable, concluir NO-GO para esa vía y presentar las reparaciones específicas que sí estén respaldadas por los datos."*
   **Se concluye NO-GO para la reordenación por evidencia de grafo.**

---

## 4. Mapa de Reparaciones Específicas Desacopladas Respaldadas por los Datos

En lugar de una fórmula universal o un desempate global, la evidencia respalda tres intervenciones atómicas independientes:

1. **Reparación 1: Desacoplamiento de Inyección de Concept Hub (1 caso, Caso 0516)**
   - El post-procesador de Concept Hub no debe insertarse ciegamente por encima del scoring híbrido sin verificar si la consulta contiene términos que anclan directamente a otro concepto específico.
2. **Reparación 2: Aliasing y Unificación de Grafías en Duplicados Reales (5 casos)**
   - Para duplicados confirmados (como `identidad-relacion-dennys` vs `identidad_relacion_dennys`), el sistema debe unificar canónicamente las grafías normalizadas (guión y guión bajo) a nivel de índice o tabla de alias, en lugar de permitir que compitan como dos memorias separadas.
3. **Reparación 3: Puentes Léxicos Explícitos en `sinonimos` (24 casos)**
   - El 100% de los fallos de `sinonimo` ocurren porque el término consultado no está en la columna `sinonimos` del nodo Gold. La vía natural y de cero deuda técnica (Invariante 1) es registrar el sinónimo en el nodo correspondiente, sin tocar código del motor.
