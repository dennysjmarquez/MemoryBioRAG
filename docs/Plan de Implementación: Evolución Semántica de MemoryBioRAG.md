# Plan de Implementación: Evolución Semántica de MemoryBioRAG

Este documento detalla la hoja de ruta técnica para transformar a `MemoryBioRAG` en un sistema de comprensión semántica funcional, integrando Etiquetado de Roles Semánticos (SRL), Inferencia en Grafos y Auto-Clustering Dimensional.

---

## Fase 1: Estructuración Relacional (SRL)

**Objetivo:** Pasar de indexar "qué se dice" a "quién hace qué".

### Acciones Técnicas:

1. **Integración de Pipeline NLP:** Incorporar un modelo ligero de procesamiento de lenguaje natural (como `spaCy` con su componente `transformer` o un modelo específico de SRL) en `core/memory_store.py`.

1. **Nueva Tabla ****`predicados`****:** Crear una tabla en SQLite que almacene la estructura tripartita de los recuerdos:
  - `id_recuerdo` (FK a `largo_plazo`)
  - `sujeto`, `accion`, `objeto`, `contexto`

1. **Refactorización de ****`percibir_corto_plazo`****:** Al guardar un recuerdo, el sistema debe extraer automáticamente estos roles y poblarlos en la base de datos.

1. **Búsqueda por Predicado:** Modificar `buscar_por_frase` para que, si detecta una estructura interrogativa (ej. "¿Quién hizo X?"), priorice la búsqueda en la tabla de predicados sobre el índice FTS5 general.

---

## Fase 2: Inteligencia Conectiva (Fuzzy Reasoning)

**Objetivo:** Permitir que el sistema "deduzca" relaciones no explícitas.

### Acciones Técnicas:

1. **Algoritmo de Propagación de Activación:** Implementar en `core/sinapsis.py` una función que recorra el grafo hasta N saltos (basado en `MAX_SALTOS_CADENA`).

1. **Cálculo de Peso Atenuado:**
  - Fórmula sugerida: `Peso_Final = Peso_Original * (Factor_Atenuacion ^ Numero_Saltos)`.
  - Esto permite que si A está conectado a B (0.9) y B a C (0.8), A y C tengan una conexión virtual de ~0.65.

1. **Caché de Inferencia:** Para no penalizar el rendimiento, los resultados de estas inferencias deben cachearse en una tabla temporal de "Sinapsis Latentes" que se refresque durante el `ciclo_sueno`.

1. **Integración en Búsqueda:** Al buscar un concepto, el sistema no solo traerá los resultados directos, sino también los "recuerdos latentes" con un score ajustado por su distancia en el grafo.

---

## Fase 3: Adaptabilidad Ontológica (Auto-Clustering)

**Objetivo:** Que el sistema cree sus propias categorías y dimensiones.

### Acciones Técnicas:

1. **Detección de Clusters:** Durante el `ciclo_sueno`, ejecutar un algoritmo de clustering (como K-Means o DBSCAN sobre los vectores de los recuerdos si se usan embeddings, o basado en densidad de sinapsis si se mantiene el enfoque no-vectorial).

1. **Emergencia de Dimensiones:**
  - Si un grupo de nodos sin categoría definida muestra una alta densidad de sinapsis entre ellos, el sistema debe crear una "Dimensión Emergente".
  - Usar un LLM o el `categorizador` actual para "nombrar" esta nueva dimensión basándose en los tokens más frecuentes del grupo.

1. **Refactorización de ****`tipos_dimension`****:** Permitir que la tabla de dimensiones acepte entradas con el flag `auto_generada = 1`.

1. **Refuerzo Dimensional:** Los nuevos recuerdos que caigan en estos clusters recibirán automáticamente el boost dimensional correspondiente sin que el agente tenga que especificarlo.

---

## Fase 4: Consolidación y Pruebas

**Objetivo:** Asegurar la estabilidad y el equilibrio biomimético.

### Acciones Técnicas:

1. **Ajuste de Inhibición Lateral:** Modificar el ciclo de sueño para que la inhibición lateral también considere la "relevancia relacional" (SRL) y no solo el peso sináptico bruto.

1. **Benchmark Cognitivo:** Crear un script de prueba que evalúe el *Recall* ante preguntas complejas que requieran inferencia (ej. "Basado en mis proyectos anteriores de Frontend, ¿qué errores de configuración suelo cometer?").

1. **Interfaz MCP:** Actualizar `mcp_server.py` para exponer estas nuevas capacidades (ej. un parámetro `usar_inferencia: bool`).

---

## Resumen de Impacto

| Característica | Estado Actual | Con este Plan |
| --- | --- | --- |
| **Comprensión** | Basada en palabras clave | Basada en acciones y roles (SRL) |
| **Recuperación** | Directa y asociativa simple | Deductiva y transitiva (Inferencia) |
| **Organización** | Taxonomía fija manual | Ontología dinámica autogenerada |

Este plan respeta la filosofía de **no depender exclusivamente de embeddings vectoriales costosos**, manteniendo la eficiencia de SQLite pero dotándolo de una lógica de grafo y procesamiento de lenguaje mucho más cercana a la inteligencia humana.