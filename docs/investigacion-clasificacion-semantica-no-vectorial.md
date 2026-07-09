# Investigación: Clasificación Semántica No Vectorial — Los 3 Pilares

> Cualquier palabra que entre al sistema se clasifica automáticamente
> en su grupo conceptual usando 3 capas de WordNet, sin vectores ni embeddings.
> Dennys J. Marquez + Athena-OEC. Julio 2026.

---

## El Problema

Necesitamos que cualquier palabra se clasifique automáticamente:
- "decodificar" → ¿qué es? ¿qué hace? ¿en qué contexto?
- "jerga" → ¿misma categoría que "lenguaje"?
- "computadora" → ¿misma categoría que "decodificador"?

WordNet tradicional falla porque separa por naturaleza ontológica
(decoder = device, translator = person → grupos distintos).

**La solución son 3 capas que se combinan.**

---

## CAPA 1: LEXNAMES (45 Categorías Ontológicas)

### Qué es

Cada synset en WordNet tiene un `lexname()` que indica a cuál de
45 categorías pertenece. Es el equivalente a los "25 Unique Beginners"
pero expandido.

### Los 45 lexnames

| Lexname | Descripción | Synsets |
|---------|-------------|---------|
| `noun.Tops` | Conceptos raíz (entity, person, artifact) | 51 |
| `noun.act` | Acciones y eventos | 6,650 |
| `noun.animal` | Animales | 7,509 |
| `noun.artifact` | Objetos artificiales (herramientas, máquinas) | 11,587 |
| `noun.attribute` | Atributos y cualidades | 3,039 |
| `noun.body` | Partes del cuerpo | 2,016 |
| `noun.cognition` | Conceptos mentales, conocimiento | 2,964 |
| `noun.communication` | Comunicación (textos, lenguaje, código) | 5,607 |
| `noun.event` | Eventos | 1,074 |
| `noun.feeling` | Sensaciones y emociones | 428 |
| `noun.food` | Alimentos | 2,573 |
| `noun.group` | Grupos de personas/cosas | 2,624 |
| `noun.location` | Ubicaciones | 3,209 |
| `noun.motive` | Motivos | 42 |
| `noun.object` | Objetos físicos | 1,545 |
| `noun.person` | Personas | 11,087 |
| `noun.phenomenon` | Fenómenos | 641 |
| `noun.plant` | Plantas | 8,030 |
| `noun.possession` | posesiones | 1,061 |
| `noun.process` | Procesos | 770 |
| `noun.quantity` | Cantidades | 1,275 |
| `noun.relation` | Relaciones | 437 |
| `noun.shape` | Formas | 341 |
| `noun.state` | Estados | 3,544 |
| `noun.substance` | Sustancias | 2,983 |
| `noun.time` | Tiempo | 1,028 |
| `verb.body` | Acciones corporales | 547 |
| `verb.change` | Cambios | 2,383 |
| `verb.cognition` | Acciones cognitivas | 695 |
| `verb.communication` | Acciones de comunicación | 1,548 |
| `verb.competition` | Competencia | 459 |
| `verb.consumption` | Consumo | 243 |
| `verb.contact` | Contacto físico | 2,196 |
| `verb.creation` | Creación | 694 |
| `verb.emotion` | Expresión emocional | 343 |
| `verb.motion` | Movimiento | 1,408 |
| `verb.perception` | Percepción | 461 |
| `verb.possession` | posesión | 847 |
| `verb.social` | Interacción social | 1,106 |
| `verb.stative` | Estados verbales | 756 |
| `verb.weather` | Clima | 81 |
| `adj.all` | Todos los adjetivos | 14,435 |
| `adj.pert` | Adjetivos de pertenencia | 3,661 |
| `adj.ppl` | Adjetivos de participio | 60 |
| `adv.all` | Todos los adverbios | 3,621 |

### Prueba con palabras reales

```
decoder.n.01      → noun.person        (¿qué es? una persona)
translator.n.01   → noun.person        (¿qué es? una persona)
computer.n.01     → noun.artifact      (¿qué es? un objeto)
decode.v.01       → verb.communication  (¿qué hace? comunica)
slang.n.02        → noun.communication  (¿qué es? comunicación)
linguistics.n.01  → noun.cognition      (¿qué es? conocimiento)
code.n.01         → noun.communication  (¿qué es? comunicación)
cipher.n.01       → noun.communication  (¿qué es? comunicación)
```

### Key Insight

`decoder.n.01` y `translator.n.01` AMBOS son `noun.person`.
El lexname SÍ los agrupa correctamente cuando son el mismo tipo
ontológico. El problema de WordNet era que comparamos device vs person
— pero si buscamos por lexname, ambos van al mismo grupo.

### Uso en BioRAG

```python
# Al guardar: el LLM infiere el lexname
lexname = get_lexname("decodificar")  # → verb.communication

# Al buscar: filtrar por lexname
WHERE lexname = 'verb.communication'  # solo verbos de comunicación
```

---

## CAPA 2: TOPIC DOMAINS (Dominios Temáticos)

### Qué es

Algunos synsets tienen `in_topic_domains()` que devuelve los dominios
temáticos a los que pertenecen. No es universal (~8,600 de 117,659
synsets), pero cuando existe, es muy poderoso.

### Ejemplos

```
computer.n.01 → topics: computer_science, digital_communication,
                       data_structure, module, throughput
linguistics.n.01 → topics: grammar, phoneme, syntax, morphophoneme
slang.n.02 → usage: informal (es jerga, lenguaje informal)
```

### Key Insight

`computer.n.01` tiene `computer_science` como topic domain.
Si buscamos "decodificar" y el nodo tiene `computer_science` como
dominio, sabemos que se refiere a decodificación de datos, no de
lenguaje natural.

### Limitación

Solo ~7% de los synsets tienen topic domains. No se puede usar como
único mecanismo de clasificación.

### Uso en BioRAG

```python
# Combinar lexname + topic domain
lexname = 'noun.artifact'
topics = ['computer_science']
# → "computadora" (objeto de ciencia de la computación)

lexname = 'noun.person'
topics = ['linguistics']
# → "traductor de textos" (persona del ámbito lingüístico)
```

---

## CAPA 3: FRAME IDs (Marcos Funcionales)

### Qué es

WordNet tiene 35 "verb frames" que indican la FUNCIÓN que cumple
un verbo. No dice qué ES el verbo, sino qué HACE.

### Los 35 frames

| Frame | Descripción | Synsets |
|-------|-------------|---------|
| 8 | **Conversión/Transformación** (X convierte Y en Z) | 7,280 |
| 2 | Acción directa sobre objeto | 2,647 |
| 9 | Proceso continuo | 2,460 |
| 11 | Transferencia | 2,456 |
| 1 | Evento general | 1,921 |
| 22 | Movimiento dirigido | 1,027 |
| 10 | Percepción | 962 |
| 4 | Acción intransitiva | 567 |
| 21 | Causación | 497 |
| 26 | Instrumento | 270 |

### Key Insight: Frame 8 Agrupa por Función

```
decode.v.01     → Frame 8 (convierte código en texto)
translate.v.01  → Frame 8 (convierte un idioma en otro)
interpret.v.01  → Frame 8 (convierte significado en entendimiento)
encrypt.v.01    → Frame 8 (convierte texto en código)
explain.v.01    → Frame 8 (convierte confusión en claridad)
```

**Todos comparten Frame 8: CONVERSIÓN/TRANSFORMACIÓN.**

No importa si es una máquina, una persona, o un proceso abstracto.
Lo que importa es que TODOS convierten algo en otra cosa.

### Uso en BioRAG

```python
# Al guardar: inferir frame
frame = get_frame("decodificar")  # → 8 (conversión)

# Al buscar: expandir con sinónimos del mismo frame
# "decodificar" → también: traducir, interpretar, cifrar, explicar
# Todos son Frame 8 = conversión
```

---

## Arquitectura de 3 Capas para BioRAG

### Modelo de datos

```sql
-- Nueva columna en largo_plazo
ALTER TABLE largo_plazo ADD COLUMN lexname TEXT DEFAULT '';
ALTER TABLE largo_plazo ADD COLUMN topic_domains TEXT DEFAULT '';
ALTER TABLE largo_plazo ADD COLUMN verb_frame INTEGER DEFAULT 0;
```

### Pipeline de clasificación

```
PALABRA → lexname() → topic_domains() → frame_ids()
              ↓              ↓                ↓
         ¿QUÉ ES?    ¿EN QUÉ CONTEXTO?  ¿QUÉ HACE?
          (45)         (~8,600)            (35)
```

### Pipeline de búsqueda expandida

```
query "decodificar"
  → lexname: verb.communication
  → frame: 8 (conversión)
  → expansion: buscar TODOS los verbos de comunicación con frame 8
  → resultados: decode, translate, interpret, encrypt, explain
```

### Ejemplo concreto

Usuario busca: "decodificar jerga"

**Sin expansión:**
- FTS5 busca "decodificar" → 2 resultados
- FTS5 busca "jerga" → 0 resultados
- Total: 2 resultados (pocos)

**Con expansión de 3 capas:**
1. lexname("decodificar") → `verb.communication`
2. frame("decodificar") → `8` (conversión)
3. Buscar todos los verbos de comunicación con frame 8:
   → decode, translate, interpret, encrypt, explain, render
4. Buscar sinónimos de "jerga": cant, jargon, lingo, argot, patois
5. Cruzar: ¿qué nodos mencionan cualquiera de estos?
6. Total: 15+ resultados (completo)

---

## Investigación Requerida

### Prioridad 1: Lexnames (inmediato)

**Qué investigar:**
- Cómo mapear lexnames de WordNet a categorías de BioRAG
- Si el LLM puede inferir lexname al guardar contenido
- Cómo integrar lexname en el pipeline de búsqueda

**Acción:** Crear tabla de mapeo lexname → categoría BioRAG

### Prioridad 2: Topic Domains (corto plazo)

**Qué investigar:**
- Si `in_topic_domains()` es suficiente o se necesita BabelNet
- Cómo construir un diccionario palabra→dominio para español
- Si se puede inferir dominio con el LLM al guardar

**Acción:** Evaluar BabelNet como fuente de dominios

### Prioridad 3: Frame IDs (mediano plazo)

**Qué investigar:**
- Cómo mapear frames de WordNet a verbos en español
- Si se puede crear una tabla frame→sinónimos para español
- Cómo integrar frames en la expansión de ráfaga

**Acción:** Crear tabla frame→sinónimos para los 35 frames

---

## Referencias

| Recurso | URL | Estado |
|---------|-----|--------|
| WordNet (NLTK) | nltk.corpus.wordnet | Instalado, funcional |
| WordNet Domains | github.com/igorbrigadir/wordnet-domains | Investigar |
| BabelNet | babelnet.org | Investigar |
| FrameNet (Berkeley) | framenet.icsi.berkeley.edu | Investigar |
| PyStemmer | pypi.org/project/PyStemmer | Instalado |

---

## Nodos Relacionados en BioRAG

- `investigacion-expansion-busqueda` (Architecture)
- `investigacion-wordnet-synsets` (Architecture)
- `teoria_ejes_semanticos_biorag` (Architecture)
- `indexacion_dimensional_explicita` (Architecture)
- `biorag_v11_1_changelog_completo` (Architecture)

---

*Documento creado el 2026-07-09. Investigacion en curso.*
