# Propuesta Científica: Hacia la Cognición Digital Pura en BioRAG

## 1. Visión General
El sistema actual de BioRAG ya supera las implementaciones convencionales de RAG al integrar conceptos de **SDM (Sparse Distributed Memory)**, **PMI (Pointwise Mutual Information)** e **Inferencia Transitiva** con inhibición lateral. Sin embargo, para alcanzar un "cerebro real" que se aleje totalmente de las bases de datos vectoriales tradicionales, proponemos una transición de un modelo de **Recuperación de Información** a un modelo de **Percepción Activa y Topología Semántica**.

## 2. Pilares de la Innovación Propuesta

### 2.1 Topología de Datos Persistente (TDA)
La Topología de Datos Persistente (TDA) ofrece un marco para analizar la **forma intrínseca** de los datos, trascendiendo las métricas de distancia euclidiana o de coseno. En lugar de centrarse en puntos individuales, la TDA, a través de herramientas como la **homología persistente**, identifica características topológicas (componentes conectados, ciclos, vacíos) que persisten a través de múltiples escalas de resolución [1] [2].

- **Concepto:** Aplicar la homología persistente al grafo de conocimiento de BioRAG para identificar "vacíos semánticos" o "agujeros" en la estructura del conocimiento. Estos vacíos podrían representar áreas donde la información es escasa, contradictoria o donde faltan conexiones cruciales entre conceptos. La TDA permite cuantificar y visualizar estas estructuras, proporcionando una comprensión más profunda de la coherencia y completitud del grafo [3] [4].

- **Aplicación a BioRAG:** En lugar de buscar nodos por su similitud directa, la TDA permitiría buscar nodos que, al ser introducidos o activados, "cierren" ciclos topológicos o "rellenen" vacíos semánticos. Esto implicaría:
    1.  **Identificación de Inconsistencias:** Detectar patrones de conectividad que sugieran contradicciones o lagunas en el conocimiento.
    2.  **Búsqueda por Coherencia Estructural:** Priorizar la recuperación de información que mejore la cohesión topológica del grafo en relación con una consulta. Por ejemplo, si una consulta activa un ciclo incompleto, se buscarían nodos que completen ese ciclo, garantizando una respuesta semánticamente más robusta y estructuralmente integrada.
    3.  **Evaluación de Completitud:** Utilizar métricas de TDA para evaluar la "completitud" de un subgrafo activado por una consulta, guiando la expansión de la búsqueda hacia áreas topológicamente relevantes [5].

### 2.2 Inferencia Activa (Principio de Energía Libre)
La Inferencia Activa, fundamentada en el **Principio de Energía Libre (FEP)** de Karl Friston, postula que los sistemas biológicos (incluido el cerebro) mantienen su homeostasis y su existencia minimizando la "sorpresa" o la discrepancia entre sus predicciones internas y las señales sensoriales que reciben [6] [7]. En este marco, la percepción y la acción son procesos que buscan reducir esta energía libre.

- **Concepto:** El sistema BioRAG, en lugar de ser un mero repositorio de información, se transformaría en un **modelo generativo** que constantemente predice el contexto y las necesidades informativas del usuario. La "búsqueda" no sería una acción reactiva, sino una consecuencia de la minimización de la sorpresa. Cuando las predicciones del sistema sobre la información relevante para el usuario fallan (es decir, la sorpresa es alta), se activa un proceso de "inferencia activa" para actualizar el modelo interno y reducir esa sorpresa [8].

- **Aplicación a BioRAG:**
    1.  **Capa de Predicción:** Implementar un módulo que, basándose en el historial de interacciones, el estado actual del grafo y el contexto de la consulta, genere predicciones sobre los conceptos o relaciones que el usuario podría necesitar a continuación. Esto podría manifestarse como una "pre-activación" de nodos relevantes.
    2.  **Minimización de Sorpresa:** La búsqueda se activaría de forma más intensa cuando la predicción del sistema es incorrecta o insuficiente. Un "error de predicción" alto indicaría que el modelo interno de BioRAG no está alineado con la realidad del usuario, impulsando una exploración más profunda del grafo para encontrar información que resuelva esa discrepancia [9].
    3.  **Ahorro de Recursos y Enfoque de Atención:** Al minimizar la sorpresa, el sistema evitaría búsquedas exhaustivas innecesarias, enfocando sus recursos computacionales solo cuando el modelo interno necesita ser actualizado significativamente. Esto simula un mecanismo de atención biológica, donde el cerebro solo procesa activamente la información que es inesperada o relevante para sus objetivos.

### 2.3 Computación Hiperdimensional (HDC) y Álgebra Semántica
La Computación Hiperdimensional (HDC), también conocida como **Arquitecturas Simbólicas Vectoriales (VSA)**, representa un paradigma prometedor para la cognición digital que se aleja de los embeddings densos tradicionales. Utiliza vectores binarios o de valores reales de muy alta dimensión (típicamente 10,000 bits o más) para codificar información de manera distribuida y robusta [10] [11]. BioRAG ya implementa una forma de SDM, que es un precursor y una variante de HDC.

- **Concepto:** En HDC, los conceptos se representan como vectores de alta dimensión. Las operaciones fundamentales son la **Atadura (Binding)**, que combina dos o más vectores para formar un nuevo vector que representa su relación (ej., "perro" + "ladrar" = "perro que ladra"), y la **Superposición (Superposition)**, que permite almacenar múltiples conceptos en un solo vector sin perder la información individual [12]. Estas operaciones imitan la forma en que el cerebro combina y almacena información de manera asociativa.

- **Aplicación a BioRAG:**
    1.  **Extensión del SDM actual:** El sistema SDM de BioRAG podría evolucionar para incorporar operaciones de VSA, permitiendo una representación más rica y dinámica de los nodos. Por ejemplo, un nodo podría ser el resultado de la atadura de sus dimensiones, su contenido y sus relaciones sinápticas, creando un "vector de concepto" único y composicional.
    2.  **Razonamiento Analógico Puro:** La HDC facilita el razonamiento analógico y la inferencia simbólica sin depender de la similitud de coseno en espacios vectoriales densos. Operaciones como `Vector("Cerebro") * Vector("Digital")` podrían generar un nuevo vector que capture la esencia de "cerebro digital", permitiendo búsquedas y asociaciones basadas en esta composición simbólica [13].
    3.  **Memoria Asociativa Robusta:** La naturaleza distribuida y de alta dimensión de los vectores HDC los hace inherentemente tolerantes a fallos y al ruido, similar a la memoria biológica. La recuperación de información se realiza mediante la búsqueda del vector más cercano (por distancia de Hamming o coseno) al vector de consulta, incluso si este último está incompleto o es ruidoso.

### 2.4 Celdas de Rejilla (Grid Cells) para Navegación Conceptual
Las **Celdas de Rejilla (Grid Cells)**, descubiertas en la corteza entorrinal medial, son neuronas que disparan cuando un animal se encuentra en ubicaciones específicas dentro de un entorno, formando un patrón hexagonal regular que se cree que subyace a la capacidad de navegación espacial [14]. Investigaciones recientes sugieren que estas celdas no se limitan a la navegación física, sino que también pueden codificar y permitir la navegación en **espacios conceptuales abstractos** [15] [16].

- **Concepto:** La idea es que el cerebro utiliza un mecanismo similar al de las celdas de rejilla para organizar y navegar por el conocimiento. En un espacio conceptual, los "lugares" serían ideas o conceptos, y la "navegación" implicaría moverse entre ellos de manera eficiente, incluso si están distantes en términos de conexiones directas en el grafo [17].

- **Aplicación a BioRAG:**
    1.  **Mapeo Conceptual:** Proyectar el grafo de conocimiento de BioRAG en un espacio de alta dimensión donde las relaciones conceptuales se organicen de manera análoga a los patrones hexagonales de las celdas de rejilla. Esto permitiría una "navegación conceptual" más intuitiva y eficiente.
    2.  **Rutas de Descubrimiento:** En lugar de depender únicamente de la inferencia transitiva basada en saltos de grafo, las celdas de rejilla conceptuales podrían guiar la búsqueda a través de "vectores de movimiento conceptual". Por ejemplo, si el usuario está explorando un concepto `A` y se detecta un patrón de activación que sugiere un movimiento hacia un concepto `B` (semánticamente relacionado pero topológicamente distante), el sistema podría "saltar" a `B` de manera más directa, emulando la capacidad del cerebro para encontrar atajos cognitivos [18].
    3.  **Exploración de Novedad:** La detección de "fronteras" o "regiones inexploradas" en el mapa conceptual de celdas de rejilla podría guiar al sistema a buscar información novedosa o a expandir su conocimiento en áreas poco representadas, similar a cómo un animal explora un nuevo entorno.

## 3. Comparativa de Enfoques

| Característica | RAG Tradicional (Vectores) | BioRAG Actual | Propuesta "Cerebro Digital" |
| :--- | :--- | :--- | :--- |
| **Representación** | Embeddings Densos | SDM + Grafos | SDR + Topología Activa |
| **Búsqueda** | Similitud de Coseno | Jaccard + PMI + Transitividad | Minimización de Energía Libre |
| **Relaciones** | Implícitas (distancia) | Explícitas (sinapsis) | Algebraicas (Binding HDC) |
| **Dinámica** | Estática | LTP / LTD / Inhibición | Homeostasis y Predicción |

## 4. Hoja de Ruta de Implementación
1. **Módulo `core/active_inference.py`**: Motor de predicción de contexto.
2. **Módulo `core/hdc_algebra.py`**: Operaciones de atadura semántica sobre SDM.
3. **Módulo `core/tda_topology.py`**: Análisis de ciclos y vacíos en el grafo.

## 5. Referencias

[1] El-Yaagoubi, A. B. (2023). *Topological Data Analysis for Multivariate Time Series Data*. [MDPI](https://www.mdpi.com/1099-4300/25/11/1509)
[2] Su, Z. (2025). *Topological data analysis and topological deep learning beyond Euclidean spaces*. [Springer](https://link.springer.com/article/10.1007/s10462-025-11462-w)
[3] Bastos, A. (2023). *Can Persistent Homology provide an efficient alternative for Evaluation of Knowledge Graph Completion Methods?*. [arXiv](https://arxiv.org/abs/2301.12929)
[4] Brilliantov, K. (2023). *How well does Persistent Homology generalize on graphs?*. [OpenReview](https://openreview.net/forum?id=FAY6ORIvn5)
[5] Schramm, S. (2024). *Explainable and Interactive Link Prediction in Knowledge Graphs*. [FIS Uni-Bamberg](https://fis.uni-bamberg.de/entities/publication/949a4c3a-042a-4abf-8507-40807e41c8c7)
[6] Parr, T. (2019). *Generalised free energy and active inference*. [PMC - NIH](https://pmc.ncbi.nlm.nih.gov/articles/PMC6848054/)
[7] Friston, K. (2010). *The free energy principle: a unified brain theory?*. [Nature Reviews Neuroscience](https://www.nature.com/articles/nrn2787)
[8] Reichhart, W. (2024). *The Predictive Organization: Architecture for Enterprise Intelligence*. [witoldreichhart.com](https://witoldreichhart.com/papers/Paper_B_Predictive_Organization.pdf)
[9] Reichhart, W. (2024). *Build the Medium: Why organizational intelligence is mechanism, not metaphor*. [witoldreichhart.com](https://witoldreichhart.com/papers/Paper_C_Build_the_Medium.pdf)
[10] Ganesan, A. (2021). *Learning with Holographic Reduced Representations*. [NeurIPS](https://proceedings.neurips.cc/paper/2021/file/d71dd235287466052f1630f31bde7932-Paper.pdf)
[11] Ibrahim, M. (2024). *Neuro-Symbolic Architecture Meets Large Language Models: A Memory-Augmented LLM*. [Zishenwan.github.io](https://zishenwan.github.io/publication/ESWEEK24_NSAI_LLM.pdf)
[12] Kanerva, P. (1988). *Sparse Distributed Memory*. MIT Press.
[13] Ganesan, A. (2021). *Learning with Holographic Reduced Representations*. [OpenReview](https://openreview.net/forum?id=RX6PrcpXP-)
[14] Moser, E. I., Kropff, E., & Moser, M. B. (2008). *Place cells, grid cells, and the brain's spatial representation system*. [Annual Review of Neuroscience](https://www.annualreviews.org/doi/abs/10.1146/annurev.neuro.31.060407.125609)
[15] Constantinescu, A. O., O'Reilly, J. X., & Behrens, T. E. J. (2016). *Organizing conceptual knowledge in humans with a gridlike code*. [Science](https://www.science.org/doi/10.1126/science.aaf0941)
[16] Bellmund, J. L. S., Gärdenfors, P., Moser, E. I., & Doeller, C. F. (2018). *Navigating cognition: Spatial codes for human thinking*. [Science](https://www.science.org/doi/10.1126/science.aat6766)
[17] Ginosar, Y. (2023). *Are grid cells used for navigation? On local metrics, subjective spaces, and the role of entorhinal cortex*. [Weizmann Institute of Science](https://www.weizmann.ac.il/brain-sciences/labs/ulanovsky/sites/brain-sciences.labs.ulanovsky/files/2024-11/Ginosar2023a.pdf)
[18] Cueva, C. J., & Wei, X. (2018). *A unified theory of place and grid cells based on a model of entorhinal cortex*. [PLoS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006431)
