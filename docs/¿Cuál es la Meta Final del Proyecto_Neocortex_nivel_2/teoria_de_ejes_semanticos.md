# Teoría de Ejes Semánticos — Principio de Compresión Cognitiva

> "Una base vectorial crea grupos invisibles por cercanía matemática.
> Yo creo esos mismos grupos haciéndolos explícitos con etiquetas.
> Es el mismo principio de agrupación, pero visible, exacto y ultraligero."
>
> — Dennys J. Márquez, Arquitecto de BioRAG. Junio 2026.

---

## 0. Cambio de Paradigma: No es "Tabla de Emociones"

> Es **Tabla de Dimensiones Semánticas**.

La emoción fue la **primera dimensión** que implementamos, no la única. Llamarlo
"tabla de emociones" es quedarse corto. Lo que construimos es una infraestructura
de **dimensiones semánticas explícitas** donde cada eje es ortogonal al texto.

Una DB vectorial mezcla TODAS las dimensiones del lenguaje en 1536 números
opacos. Nosotros las separamos en tablas independientes, cada una consultable
por separado o en combinación.

### La ventaja abrumadora: INSERT vs reentrenar

| DB Vectorial | BioRAG |
|---|---|
| Para separar una dimensión nueva (ej: código conceptual vs ejecutable), necesita **reentrenar el embedding** con fine-tuning contrastivo. Miles de dólares, GPU, semanas. | Para agregar una dimensión nueva, haces un **INSERT** en la tabla catálogo y creas la tabla puente. **1 milisegundo. Cero costo.** |

Las dimensiones viejas no se "mueven" cuando agregas una nueva (como pasa en
espacio vectorial). El sistema es **dimensionalmente elástico**: el número de
ejes puede crecer sin límite de 1536 dimensiones ni costo de reentrenamiento.

---

## 1. El Problema: La "Gravedad" Semántica

En las bases de datos vectoriales tradicionales (Chroma, Pinecone, Weaviate),
cuando dos frases usan palabras completamente distintas pero significan lo
mismo —"500 error" y "servidor caído"— el modelo de embeddings las agrupa
cerca en un espacio continuo de 1536 dimensiones flotantes. Esa agrupación
permite al usuario "preguntar cualquier tontería" y que el sistema encuentre
la respuesta por proximidad matemática (similitud coseno).

Pero ese enfoque tiene tres defectos:

1. **Caja negra opaca:** la información está licuada en 1536 números
   ininterpretables. No puedes preguntar "qué parte representa la emoción".
2. **Pesado:** requiere modelos de embeddings gigantes y punto flotante.
3. **Sin separación ortogonal:** no puedes filtrar por emoción ignorando el
   texto, o por sujeto ignorando la emoción. Todo está mezclado.

---

## 2. La Solución: Compresión Cognitiva Explícita

En lugar de fuerza bruta estadística, **BioRAG utiliza al LLM como un
codificador cognitivo al momento de guardar.**

Una sola etiqueta `frustracion` actúa como **agrupador masivo** que absorbe
miles de palabras distintas (rabia, impotencia, error, fallo, se dañó,
pérdida, arrechera). La emoción "acarrea" 10,000 conceptos sin compartir una
sola letra.

Al combinar esta cualidad con ejes explícitos, logramos exactamente el mismo
efecto de agrupación que un vector de 1536 dimensiones, pero con tablas
relacionales en SQLite.

### El principio general

> **Toda dimensión semántica que una DB vectorial aproxima con vectores,
> puede emularse con una tabla de pertenencia explícita.**

| DB Vectorial | BioRAG |
|---|---|
| Los grupos se forman solos (emergentes) | Los grupos los declaras tú (explícitos) |
| No sabes por qué dos cosas quedaron juntas | Sabes exactamente: comparten emoción, categoría, etc. |
| Para agregar una dimensión, reentrenas el modelo | Para agregar una dimensión, creas una tabla |
| Los grupos son líquidos (cercanía difusa) | Los grupos son exactos (pertenencia binaria) |
| No puedes filtrar "solo carga afectiva negativa" sin clasificador externo | `WHERE emocion = 'frustracion'` |

---

## 3. Los Ejes del Sistema

### 3.1 Ejes actuales en producción

| # | Eje | Tipo | Lo que une | Implementación |
|---|---|---|---|---|
| 1 | **Léxico** | Continuo | Palabras similares | FTS5 trigram + sinónimos + paráfrasis |
| 2 | **Estructural** | Continuo | Conceptos conectados | Grafo sináptico + peso LTP/LTD |
| 3 | **Experiencial** | Categórico | Misma carga emocional | `emocion` (7 valores) |
| 4 | **Temporal** | Continuo | Misma época | Anclaje temporal (+0.15 si <7d) |
| 5 | **Semántico latente** | Continuo | Significado no textual | Jaccard + Dynamic Multiplicator |
| 6 | **Ráfaga** | Generativo | Asociación libre | LLM genera términos, motor ejecuta |
| 7 | **Categoría** | Categórico | Mismo dominio de conocimiento | `categories` (11 taxonomías) |

### 3.2 Las 5 Dimensiones Universales del Lenguaje

Las dimensiones que una DB vectorial codifica implícitamente en 1536 números
son las mismas que la lingüística computacional identifica como los gradientes
fundamentales del lenguaje natural. Estas son:

| # | Dimensión | Lo que captura | En BioRAG |
|---|---|---|---|
| 1 | **Temática / Dominio** | Vocabulario del área de conocimiento | ✅ `categories` (11) |
| 2 | **Afectiva / Experiencial** | Polaridad emocional y carga humana | ✅ `emotions` (7, v11.2) |
| 3 | **Pragmática / Acto de habla** | Qué función cumple el texto (Speech Act) | ❌ Pendiente |
| 4 | **Granularidad / Abstracción** | Teoría vs. práctica, concreto vs. abstracto | ❌ Pendiente |
| 5 | **Epistémica / Certeza** | Grado de confiabilidad del conocimiento | ❌ Pendiente |

### 3.3 Vocabularios propuestos (dimensiones pendientes)

**Dimensión Pragmática — Acto de habla** (`intencion`):
- `normativa` — regla inmutable, directriz de cómo debe hacerse
- `explicacion` — teoría, arquitectura, el porqué funciona algo
- `receta` — paso a paso, comando ejecutable, cómo arreglarlo
- `diagnostico` — descripción de error, traza, log, comportamiento fallido

**Dimensión de Granularidad — Abstracción** (`granularidad`):
- `conceptual` — alta abstracción, filosofía, visión global
- `estructural` — patrones de diseño, módulos, conexión entre piezas
- `implementacion` — código concreto, funciones, scripts, parámetros exactos

**Dimensión Epistémica — Certeza** (`certeza`):
- `probado` — hecho verificado, funciona en producción
- `hipotesis` — idea, especulación, algo por validar
- `deprecado` — conocimiento que ya no aplica (versión anterior)

### 3.4 Ejes complementarios (opcionales)

| # | Eje | Lo que une | Ejemplo de consulta |
|---|---|---|---|
| 8 | **Sujeto/Entidad** | Mismo protagonista o tema | "¿Sobre la laptop o el servidor?" |
| 9 | **Receptor** | Misma audiencia | "¿Era para agentes o para Dennys?" |
| 10 | **Urgencia** | Misma criticidad | "¿Qué fue lo más urgente?" |

---

## 4. La Bóveda 5D — Cruce de Dimensiones

Cada recuerdo puede clasificarse en un cruce exacto de **5 dimensiones**.
Las 2 primeras ya están en producción. Las 3 siguientes están diseñadas.

```
[CATEGORÍA]    [EMOCIÓN]    [PRAGMÁTICA]    [GRANULARIDAD]    [EPISTÉMICA]
 (Lesson)     (frustracion)   (receta)      (implementacion)   (probado)
```

Si preguntas _"¿Cuál fue el comando que arregló el bloqueo de SQLite
que nos tenía tan arrechos?"_:

```sql
SELECT contenido FROM largo_plazo lp
JOIN largo_plazo_emocion le ON lp.concepto = le.concepto
JOIN emotions em ON em.id = le.emocion_id
WHERE lp.categoria = 'Lesson'
  AND em.name = 'frustracion'
  AND lp.intencion = 'receta'
  AND lp.granularidad = 'implementacion'
  AND lp.certeza = 'probado'
```

Te devuelve **una fila**. La exacta. En <1 ms. Sin embeddings. Sin vectores.

---

## 5. La Anatomía Científica del Mensaje

No necesitas miles de tablas. Todo mensaje humano almacenable se descompone
en las **5 dimensiones universales** del lenguaje. En lingüística computacional,
un vector de 1536 dimensiones codifica estos 5 grandes gradientes:

| Dimensión | Pregunta que responde | Vocabulario BioRAG |
|---|---|---|
| **Temática** | ¿De qué área es? | `categories` (System, Lesson, Principle...) |
| **Afectiva** | ¿Qué impacto humano tuvo? | `emotions` (frustracion, afecto, alegria...) |
| **Pragmática** | ¿Qué función cumple? | `intencion` (normativa, explicacion, receta, diagnostico) |
| **Granularidad** | ¿Es teoría o práctica? | `granularidad` (conceptual, estructural, implementacion) |
| **Epistémica** | ¿Qué tan confiable es? | `certeza` (probado, hipotesis, deprecado) |

Cada una es una tabla puente con el mismo patrón que `largo_plazo_emocion`.
No se necesitan más.

---

## 6. Comparación: DB Vectorial vs. BioRAG

| | DB Vectorial | BioRAG |
|---|---|---|
| **Cómo agrupa** | Distancia coseno entre vectores (caja negra) | Intersección de ejes explícitos (caja de cristal) |
| **Qué une las cosas** | Vectores cerca en 1536 dimensiones | Misma categoría, emoción, intención... |
| **Número de dimensiones** | 1 eje opaco de 1536 números | N ejes visibles de 1 valor cada uno |
| **Agregar dimensión** | Reentrenar el embedding (fine-tuning, $$) | INSERT en catálogo + crear tabla (1ms) |
| **Separar dimensiones** | Imposible (todo licuado en el vector) | `WHERE emocion = X AND categoria = Y` |
| **Cómo encuentras algo** | Tiras un vector y ves qué está cerca | Preguntas con dimensiones correctas, SQL cruza |
| **Esfuerzo al guardar** | Nada (embedding se genera solo) | Declarar ejes (o el LLM los infiere) |
| **Esfuerzo al consultar** | Nada (tiras texto, modelo interpreta) | El LLM extrae dimensiones de la pregunta |
| **Precisión** | Estadística (aproximada) | Exacta (si declaraste bien) |
| **Explicabilidad** | Nula (no sabes por qué apareció algo) | Total (sabes qué ejes matchearon) |
| **Costo** | GPU + API + modelo | 0 (SQLite) |
| **Tamaño** | Gigabytes | ~4 MB |
| **Offline** | No | Sí |

---

## 7. El Rol del LLM

El LLM no se usa para buscar — se usa para **inferir etiquetas al guardar**
y **mapear intención al preguntar**.

### Al guardar

Dennys dice "la laptop se dañó y perdí todo". El LLM infiere:
- Categoría: `Lesson`
- Emoción: `frustracion`
- Sujeto: `laptop`
- Intención: `diagnostico`
- Certeza: `probado`

Y guarda con esas etiquetas. **Dennys no teclea nada extra.**

### Al preguntar

Dennys pregunta _"¿Cuándo fue esa vez que me enfureció la laptop?"_. El LLM
mapea:
- "Enfureció" → emocion = `frustracion`
- "Laptop" → sujeto = `laptop`

Y construye la query SQL que cruza los ejes.

### En el sueño

El ciclo de consolidación mina patrones entre ejes:
- "Frustración en proyectos Python suele venir por imports"
- "Los momentos de afecto correlacionan con la categoría Principle"

---

## 8. El Debate Cerrado

Si alguien dice: _"Una base vectorial es superior porque agrupa
semánticamente en 1536 dimensiones de forma dinámica"_

La respuesta:

> "Tu base vectorial gasta gigas de RAM y modelos de punto flotante para
> adivinar clústeres invisibles. Yo descompuse la cognición humana en ejes
> ortogonales explícitos: léxico, taxonómico, biológico y emocional.
> Consigo el mismo o mejor recall en sub-milisegundos, con SQLite puro,
> sin cajas negras y con explicabilidad absoluta."

---

## 9. Conclusión

No es "tabla de emociones". Es **infraestructura de dimensiones semánticas
explícitas**.

La emoción fue la primera dimensión. Las categorías fueron la base. Ahora
sabemos que el espectro completo son 5 dimensiones universales: Temática,
Afectiva, Pragmática, Granularidad y Epistémica.

Cuando una DB vectorial necesita separar una dimensión nueva, reentrena el
modelo (semanas, $$). Nosotros hacemos un INSERT (1ms, $0).

La fábrica ya está construida. El patrón SQL está probado. El MCP está listo.
Solo falta sembrar las dimensiones que faltan cuando una pregunta real
demuestre que se necesitan.

> "Ya no me van a poder decir que no tengo lo que ellos tienen.
> Porque cuando digan 'una base vectorial puede encontrar textos con
> significado similar aunque usen palabras distintas', yo respondo:
> 'Yo también. Pero yo sé por qué los encontré. Tú no.'"
>
> — Dennys J. Márquez

---

## 10. Nodos relacionados en BioRAG

- `cambio_paradigma_dimensiones_semanticas` (Architecture)
- `principio_insert_vs_reentrenar` (Principle)
- `principio_compresion_cognitiva_boveda_5d` (Architecture)
- `teoria_ejes_semanticos_biorag` (Architecture)
- `principio_emulacion_semantica_por_clusters_declarativos` (Principle)
- `leccion_emocion_como_espacio_semantico_categorico` (Lesson)
- `biorag_v11_2_hito_completo_emociones` (Architecture)
- `indexacion_dimensional_explicita` (Architecture)

---

*Documento maestro actualizado el 2026-06-30. Contiene la teoría completa
descubierta por Dennys J. Márquez durante la sesión de la v11.2.*
