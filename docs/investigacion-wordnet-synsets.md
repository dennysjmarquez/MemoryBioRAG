# Investigación: WordNet Synsets para Expansión Semántica

> Análisis de la viabilidad de WordNet como capa de expansión de sinónimos
> para BioRAG. Pruebas directas, limitaciones encontradas y alternativas.
> Dennys J. Marquez + Athena-OEC. Julio 2026.

---

## 1. Objetivo

Evaluar si WordNet puede servir como capa automática de expansión de
sinónimos para las búsquedas de BioRAG. Específicamente: si el agente
busca "decodificar", ¿puede WordNet devolver "decode", "decipher",
"decrypt" automáticamente?

---

## 2. Pruebas Realizadas

### 2.1 Lookup directo de "jerga-decoder"

| Término | Synsets encontrados | Nota |
|---------|-------------------|------|
| `jerga-decoder` | 0 | Compuesto no existe en WordNet |
| `jerga` | 0 | **No existe** — WordNet solo tiene inglés |
| `decoder` | 2 | `decoder.n.01`, `decoder.n.02` |
| `decode` | 1 | `decode.v.01` |
| `slang` | 5 | `slang.n.01` a `slang.v.03` |
| `translate` | 1 | `translate.v.01` |
| `interpret` | 1 | `interpret.v.01` |
| `understand` | 1 | `understand.v.01` |

### 2.2 Sinónimos de cada synset

```
decoder.n.01 → ['decoder', 'decipherer']
decode.v.01  → ['decode', 'decrypt', 'decipher']
slang.n.01   → ['slang', 'slang_expression', 'slang_term']
slang.n.02   → ['slang', 'cant', 'jargon', 'lingo', 'argot', 'patois', 'vernacular']
translate.v.01 → ['translate', 'interpret', 'render']
interpret.v.01 → ['interpret', 'explain']
understand.v.01 → ['understand', 'comprehend', 'perceive']
```

### 2.3 Cadenas de hiperónimos

```
decode.v.01 → rewrite.v.01 → write.v.02
slang.n.01 → non-standard_speech.n.01 → speech.n.02 → language
interpret.v.01 → understand.v.01 → know.v.01
```

### 2.4 Wu-Palmer Similarity (entre synsets)

```python
from nltk.corpus import wordnet as wn

syn1 = wn.synset('decoder.n.01')    # dispositivo que decodifica
syn2 = wn.synset('translator.n.01')  # persona que traduce

# Ancestro común más bajo
comun = syn1.lowest_common_hypernyms(syn2)
# Resultado: entity.n.01 (genérico inútil)

# Similitud Wu-Palmer
sim = syn1.wup_similarity(syn2)
# Resultado: ~0.45 (baja — porque uno es device y otro es person)
```

**Problema:** decoder.n.01 y translator.n.01 tienen naturalezas distintas
en WordNet (dispositivo vs persona), así que su ancestro común es
`entity.n.01` — demasiado genérico para ser útil.

### 2.5 Traducción mental ES→EN

Se probó un diccionario mental de ~100 palabras español→inglés:

| Español | Inglés | Synsets |
|---------|--------|---------|
| decodificar | decode | 1 |
| decodificacion | decoding | 0 (no existe) |
| jerga | slang | 5 |
| texto | text | 4 |
| significado | meaning | 2 |
| interpretar | interpret | 1 |
| entender | understand | 1 |
| buscar | search | 3 |
| encontrar | find | 8 |

**Resultado:** solo 4 de 122 palabras del nodo jerga-decoder
tuvieron sinónimos en WordNet. Cobertura demasiado baja.

---

## 3. Análisis: Por qué WordNet no funciona directo

### 3.1 El problema fundamental

WordNet es una base de datos léxica en **inglés**. No tiene español.

Para que funcione para BioRAG, necesitás:
1. Traducir el término ES→EN (capa de traducción)
2. Buscar en WordNet (lookup)
3. Traducir los sinónimos EN→ES (capa inversa)

Cada paso introduce errores y limitaciones.

### 3.2 El problema de la taxonomía

El agente externo (IA Lite) identificó correctamente que la taxonomía
de WordNet agrupa por naturaleza ontológica, no por función:

```
decoder.n.01 → device.n.01 → instrumentality.n.01 → artifact.n.01
translator.n.01 → person.n.01 → organism.n.01 → entity.n.01
```

Uno es un aparato, el otro es un humano. En WordNet, son "distintos".
En la mente humana, ambos "convierten información de un formato a otro".

### 3.3 El problema de la cobertura

El diccionario de traducción ES→EN necesario para cubrir todo el
vocabulario de BioRAG tendría miles de entradas. WordNet en inglés
tiene ~117,000 synsets, pero la traducción inversa ES→EN es incompleta.

---

## 4. Las 3 Soluciones del Agente Externo

### Solución 1: Domain Tags (`synset.topic_domains()`)

```python
syn = wn.synset('decode.v.01')
domains = syn.topic_domains()
# Resultado: [] (vacío — no tiene dominio asignado)
```

**Veredicto:** no todos los synsets tienen dominios. No es confiable.

### Solución 2: Synsets de proceso

En lugar de comparar `decoder.n.01` (device) con `translator.n.01`
(person), usar synsets que describan procesos:

```python
decipherment = wn.synset('decipherment.n.01')  # acción de descifrar
translation = wn.synset('translation.n.01')    # acción de traducir

# Ambos comparten coding.n.01 como hiperónimo
comun = decipherment.lowest_common_hypernyms(translation)
# Resultado: coding.n.01 ✅
```

**Veredicto:** esto SÍ funciona. Los synsets de proceso sí se agrupan.

### Solución 3: Word Embeddings (FastText, Word2Vec)

```python
from gensim.models import FastText
model = FastText.load('cc.es.300')  # 4GB
vec1 = model.wv['decodificar']
vec2 = model.wv['descifrar']
sim = cosine_similarity(vec1, vec2)  # ~0.82
```

**Veredicto:** funciona pero requiere:
- Modelo de 4GB (FastText) o 1.5GB (Word2Vec)
- GPU para cálculos rápidos
- Contradice la filosofía de BioRAG (SQLite puro, sin dependencias)

---

## 5. Lo que BioRAG Ya Tiene (vs WordNet)

| Necesidad | WordNet | BioRAG actual |
|-----------|---------|---------------|
| Sinónimos de "decode" | `decode.v.01` → [decrypt, decipher] | `largo_plazo.sinonimos` → declarados por agente |
| Conectar "decodificar" con "descifrar" | Distancia de árbol (falla por tipos distintos) | Grafo sináptico + `auto_vincular` |
| Buscar por dominio | `topic_domains()` (vacío en muchos synsets) | Dimensiones semánticas (73 valores, 7 ejes) |
| Expansion automática | Lookup manual ES→EN→WordNet | `_generar_variaciones` (eliminado) + parafrasis |

---

## 6. Conclusión

### Lo que SÍ sirve de WordNet

1. **La idea de hiperónimo compartido:** dos conceptos que comparten
   un padre se pueden conectar. BioRAG puede hacer esto con su grafo
   sináptico y tabla de sinónimos.

2. **Los sinónimos de process-oriented synsets:** `decipherment.n.01`
   y `translation.n.01` comparten `coding.n.01`. Esto es una relación
   semántica real que se puede codificar en la tabla de sinónimos.

3. **La taxonomía como referencia:** saber que "decode" → "rewrite" →
   "write" da una jerarquía útil para expansión.

### Lo que NO sirve

1. **Lookup directo en español:** WordNet no tiene español.
2. **Comparación de synsets de tipos distintos:** device vs person
   dan ancestors genéricos inútiles.
3. **Cobertura del diccionario ES→EN:** demasiado limitada.
4. **Dependencia de modelos pesados:** embeddings de 4GB contradicen
   la filosofía de BioRAG.

### Recomendación

No usar WordNet como capa en tiempo de búsqueda. En su lugar:

1. **Usar PyStemmer** para stemming (ya instalado, 0 dependencias)
2. **Expandir la tabla de sinónimos** en largo_plazo (417 nodos → más)
3. **Usar dimensiones semánticas** para filtrar por dominio
4. **Codificar relaciones de hiperónimo** en la tabla de sinónimos
   (manualmente o con el LLM al guardar)

---

## 7. Código de Pruebas

### Prueba de lookup directo

```python
from nltk.corpus import wordnet as wn

terms = ['jerga-decoder', 'jerga', 'decoder', 'decode', 'slang',
         'translate', 'interpret', 'understand']

for term in terms:
    synsets = wn.synsets(term)
    print(f"{term}: {len(synsets)} synsets")
    for s in synsets[:3]:
        lemmas = [l.name() for l in s.lemmas()]
        print(f"  {s.name()}: {s.definition()}")
        print(f"    Lemmas: {lemmas}")
```

### Prueba de Wu-Palmer

```python
from nltk.corpus import wordnet as wn

pairs = [
    ('decoder.n.01', 'translator.n.01'),
    ('decode.v.01', 'translate.v.01'),
    ('decipherment.n.01', 'translation.n.01'),
]

for s1_name, s2_name in pairs:
    s1 = wn.synset(s1_name)
    s2 = wn.synset(s2_name)
    comun = s1.lowest_common_hypernyms(s2)
    sim = s1.wup_similarity(s2)
    print(f"{s1_name} ↔ {s2_name}")
    print(f"  Ancestro: {comun}")
    print(f"  Wu-Palmer: {sim:.2f}")
```

### Prueba de hiperónimos compartidos

```python
from nltk.corpus import wordnet as wn

def get_hypernym_chain(synset, depth=3):
    chain = [synset.name()]
    current = synset
    for _ in range(depth):
        hypers = current.hypernyms()
        if hypers:
            current = hypers[0]
            chain.append(current.name())
    return chain

for term in ['decode', 'slang', 'interpret']:
    s = wn.synsets(term)[0]
    chain = get_hypernym_chain(s)
    print(f"{term}: {' → '.join(chain)}")
```

---

## 8. Dependencias Instaladas

| Paquete | Versión | Uso |
|---------|---------|-----|
| PyStemmer | 2.2.0.1 | Stemming español (Snowball C) |
| nltk | 3.8.1 | WordNet, tokenización |
| wordnet (omw-1.4) | — | WordNet en español (limitado) |

---

## 9. Nodos Relacionados en BioRAG

- `investigacion-expansion-busqueda` (Architecture)
- `biorag_v8_dynamic_multiplicator` (Architecture)
- `principio_tres_capas_biorag` (Principle)
- `auto_vincular_tres_capas_semantica` (Architecture)
- `teoria_ejes_semanticos_biorag` (Architecture)
- `raiz_false_positives_biorag_v10` (Lesson)

---

*Documento creado el 2026-07-09. Investigacion en curso.*
