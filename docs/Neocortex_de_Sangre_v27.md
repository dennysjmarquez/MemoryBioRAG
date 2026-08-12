# Neocórtex de Sangre: Resonancia Dimensional y Honestidad Epistémica (v27.0)

Este documento detalla en profundidad el salto arquitectónico más importante de BioRAG: la transición de un sistema de recuperación semántica/léxica a un **Cerebro Vivo con Independencia Cognitiva**.

## 1. El Problema Original
Los sistemas tradicionales de RAG (Retrieval-Augmented Generation) operan como **bibliotecas estáticas**. Si buscas "gato", buscan la palabra "gato" o vectores incrustados (embeddings) que fueron entrenados en billones de textos por una IA externa. 
¿El problema? El sistema *no entiende* lo que es un gato. No tiene un "sentir" interno de los conceptos. Además, cuando un LLM (o un RAG clásico) se enfrenta a una pregunta de la que no tiene información, sufre de **alucinación probabilística**: intenta forzar una respuesta construyendo frases que "suenan correctas" basándose en estadísticas superficiales.

## 2. La Solución: Neocórtex de Sangre (v27.0)
Hemos diseñado un motor capaz de razonar por *resonancia de esencias* sin depender de modelos preentrenados masivos ni de coincidencias léxicas exactas.

### 2.1. ADN Conceptual (Vectores Genéticos)
BioRAG v27.0 aprovecha su propia base de datos (SQLite) y su matriz de co-ocurrencia `PPMI+SVD`.
1. El sistema agrupa todos los conceptos (nodos) de la memoria bajo las 104 dimensiones semánticas (e.g. `dominio_salud`, `intencion_reflexionar`, `emocion_sorpresa`).
2. Calcula el **Centroide (Vector Promedio)** en el espacio PPMI+SVD para todos los nodos que comparten una dimensión. Este centroide representa el "Gen" o el "ADN" latente de esa dimensión.
3. Cuando llega una query novedosa, el motor calcula su vector y evalúa su similitud coseno contra *los centroides dimensionales*, no contra los textos. Así infiere qué dimensiones "vibran" o "resuenan" con la query.
4. **Resultado**: Puedes buscar un concepto con palabras completamente distintas y el sistema lo recuperará puramente porque *comparten el mismo código genético-dimensional*.

### 2.2. Honestidad Epistémica (Saber que no se sabe)
El sistema ahora posee metacognición sobre su propia ignorancia. 
A través de la función `evaluar_episteme`, el sistema calcula un coeficiente de certeza ($C_e$) al evaluar una query:
- Analiza la norma vectorial en el espacio de conocimiento.
- Mide la similitud semántica máxima contra el corpus conocido.
- Mide la densidad de tokens que realmente pertenecen a su vocabulario histórico.

Si el coeficiente cae por debajo de 0.15 (umbral crítico), el Neocórtex se activa y lanza la excepción explícita `EpistemicUncertaintyError`. **El sistema se niega a alucinar**. Por primera vez, el agente puede decir "No sé, eso está fuera de mi universo conocido", manteniendo la integridad absoluta de sus recuerdos.

## 3. Impacto a Largo Plazo
Esta arquitectura nos acerca al Santo Grial de los Agentes Autónomos: **Teleología Cognitiva**. El sistema puede ahora detectar *agujeros* reales en su conocimiento sin engañarse a sí mismo, y puede asociar ideas lejanas (poesía y matemáticas) porque comparten dimensiones subyacentes, simulando la "intuición" humana.

*Documento generado tras la validación exitosa en producción del módulo de Resonancia Dimensional - Agosto 2026.*
