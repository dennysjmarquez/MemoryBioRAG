# Auditoría Técnica: BioRAG v18.0 — La Consolidación del conector semántico

> "Ya no es solo buscar palabras; es buscar la **esencia** bilingüe y simbólica. La v18.0 ha cerrado el círculo de la 'capa de decodificación' que faltaba."

---

## 1. El Hito de la v18.0: De la Palabra a la Esencia

En la v14.0 planteaba la necesidad de un conector conceptual que uniera de forma lógica conceptos como "decodificar password" y "decodificar jerga". En la **v18.0**, este conector se ha materializado a través de una arquitectura de **Clasificación Simbólica WordNet**.

### El "Match Perfecto" por Grupos Semánticos
Ahora, BioRAG no solo mira si las letras coinciden. Al guardar y buscar, el sistema extrae los **lexnames** (categorías ontológicas de WordNet). 

| Palabra en Query | Palabra en Memoria | Lexname compartido | ¿Hay Match? |
|---|---|---|---|
| `decodificar` | `traducir` | `verb.communication` | **SÍ (Boost 0.10)** |
| `password` | `clave` | `noun.communication` | **SÍ (Boost 0.10)** |
| `jerga` | `modismo` | `noun.communication` | **SÍ (Boost 0.10)** |

Esto es exactamente lo que buscaba: una estructura (WordNet) que devuelve el mismo identificador de grupo semántico para palabras con significado similar en diferentes contextos.

---

## 2. Las 3 Nuevas Capas de "Decodificación" en v18.0

La v18.0 no solo agrega una señal, sino un pipeline completo de **Comprensión Semántica Profunda**:

### A. Clasificación WordNet Bilingüe (`core/clasificador_wordnet.py`)
El sistema ahora es bilingüe nativo. Si se registra información en español y se consulta en inglés (o viceversa), WordNet actúa como el puente semántico. 
- **Técnica**: Coseno binario sobre 45 categorías ontológicas.
- **Impacto**: Resuelve la polisemia y la sinonimia sin usar un solo vector de embedding.

### B. Fallback Simbólico 2.1 (`core/fallback_simbolico.py`)
Cuando la búsqueda exacta FTS5 falla, entra en acción esta capa que combina:
1. **Normalización Total**: Eliminación de problemas causados por tildes y mayúsculas.
2. **Levenshtein**: Tolerancia a errores de escritura (typos).
3. **Expansión de Query**: Si se busca "hipertensión", el sistema expande la búsqueda a "presión arterial" de forma automática.

### C. Inferencia Transitiva y Auto-Clustering (`core/auto_clustering.py`)
El sistema ahora aprende de manera autónoma durante el ciclo de sueño:
- **Inferencia**: Si el nodo A está conectado al nodo B, y B al C, BioRAG deduce la relación indirecta entre A y C.
- **Comunidades**: El sistema agrupa nodos en "cliques" densos y crea **dimensiones emergentes** automáticamente (ej: `auto_python_script_error`).

---

## 3. Comparativa de Evolución: v14.0 vs v18.0

| Característica | BioRAG v14.0 | BioRAG v18.0 |
|---|---|---|
| **Señales de Scoring** | 8 señales | **9 señales (incluye `grupo_score`)** |
| **Capas de Búsqueda** | 12 capas | **13 capas (incluye Fallback Simbólico)** |
| **Semántica** | Basada en ráfaga (LLM) | **Simbólica Determinista (WordNet)** |
| **Idiomas** | Español principal | **Bilingüe real (ES + EN)** |
| **Estructura** | Plana | **SRL (Sujeto, Acción, Objeto, Contexto)** |

---

## 4. Conclusión: El conector ya es parte del ADN

La v18.0 ha resuelto el problema de la "capa de decodificación" de forma robusta:
1. **Es determinista**: Evita las alucinaciones propias de los vectores de embeddings.
2. **Es ligero**: Corre utilizando apenas ~20MB de RAM.
3. **Es explicable**: Es posible auditar exactamente qué `grupo_id` unió dos conceptos.

**Aquel concepto primario concebido en la v14.0 ahora es el motor de la v18.0.** El sistema ya no solo recupera términos literales, sino que **entiende la esencia** de la consulta y del conocimiento almacenado.

---
*Análisis técnico de la evolución de BioRAG v18.0 - Julio 2026*
