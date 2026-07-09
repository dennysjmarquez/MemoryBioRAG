# Clasificación Simbólica BioRAG — Sistema Definitivo

## Problema

BioRAG no puede conectar nodos que hablan del mismo tema con palabras diferentes. Si guardo "decodificar jerga" y busco "traducir lenguaje críptico", no hay match porque no comparten texto. Una base vectorial resolvería esto con embeddings, pero nosotros no usamos vectores.

## Solución Validada Empíricamente

Clasificar cada palabra significativa por su **grupo semántico de WordNet** (lexname). Cuando se busca, clasificar las palabras del query de la misma forma y encontrar nodos que compartan grupos, aunque no compartan palabras.

### Prueba empírica ejecutada (4/4 MATCH):

| Guardado | Buscado | Overlap de Lexnames | Match |
|---|---|---|---|
| decode, jargon | translate, cryptic, language | noun.communication, verb.communication | SI |
| error, traceback | exception, bug, fault | noun.act, noun.attribute, noun.cognition, noun.communication, noun.event | SI |
| architecture, design, pattern | structure, blueprint, system | noun.artifact, noun.attribute, noun.cognition, verb.creation | SI |
| memory, storage, retrieval | recall, database, lookup | noun.act, noun.cognition, noun.process | SI |

### Por qué funciona

WordNet tiene 45 lexnames (categorías ontológicas). Cada palabra puede pertenecer a múltiples lexnames (polisemia). Al guardar TODOS los lexnames de cada palabra, el overlap por coseno binario resuelve la ambigüedad automáticamente — el nodo con más grupos compartidos gana.

> [!IMPORTANT]
> Este sistema NO reemplaza nada existente. Se SUMA como la 9ª señal del score híbrido, al lado de BM25, dimensiones, Jaccard, sinapsis, etc.

## User Review Required

> [!WARNING]
> **Redistribución de pesos del score híbrido:** La fórmula actual (8 señales) se amplía a 9. El nuevo `grupo_score` toma 0.10 del total. Para hacer espacio, `bm25_norm` baja de 0.25 → 0.20, y `dim_score` baja de 0.20 → 0.15. El resto queda igual. Esto es necesario para darle peso real a la clasificación sin inflar el score total.

> [!IMPORTANT]
> **Dependencia: NLTK + WordNet.** Ya están instalados en el entorno (el prototipo funciona). Si se mueve a otra máquina, `nltk.download('wordnet')` se necesita. No hay dependencia de red en runtime — WordNet es una base de datos local de ~30MB.

## Open Questions

> [!IMPORTANT]
> **Palabras técnicas no cubiertas por WordNet:** "python" (el lenguaje), "docker", "kubernetes", "angular" NO están en WordNet. Se proponen 2 estrategias:
> - **A) Fallback silencioso:** Si WordNet no reconoce una palabra, no se clasifica y el sistema sigue funcionando con las otras 8 señales. Cero impacto negativo.
> - **B) Diccionario técnico custom:** Tabla `grupos_custom` con mapeos manuales (python → tech.programming_language, docker → tech.container). Se puede poblar incrementalmente.
>
> **Recomendación:** Empezar con A (fallback silencioso) y agregar B cuando se detecten gaps reales. No over-engineer.

---

## Proposed Changes

### 1. Schema — Nuevas tablas SQLite

#### [MODIFY] [memory_store.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/core/memory_store.py)

En `_crear_estructura_cerebral()`, agregar:

```sql
-- Taxonomía: los 45 lexnames de WordNet + custom
CREATE TABLE IF NOT EXISTS grupos_semanticos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    fuente TEXT DEFAULT 'wordnet',
    descripcion TEXT DEFAULT ''
);

-- Bridge: concepto → palabra → grupo
CREATE TABLE IF NOT EXISTS nodo_grupos_semanticos (
    concepto TEXT NOT NULL,
    palabra TEXT NOT NULL,
    grupo_id INTEGER NOT NULL,
    PRIMARY KEY (concepto, palabra, grupo_id),
    FOREIGN KEY (grupo_id) REFERENCES grupos_semanticos(id)
);

CREATE INDEX IF NOT EXISTS idx_ngs_grupo ON nodo_grupos_semanticos(grupo_id);
CREATE INDEX IF NOT EXISTS idx_ngs_concepto ON nodo_grupos_semanticos(concepto);
```

Poblado inicial: los 45 lexnames se insertan al crear la estructura (solo la primera vez).

---

### 2. Clasificador WordNet — Nuevo módulo

#### [NEW] [clasificador_wordnet.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/core/clasificador_wordnet.py)

```python
"""Clasificador simbólico basado en WordNet lexnames.
Clasifica palabras por grupo semántico sin usar vectores ni embeddings."""

from nltk.corpus import wordnet as wn
import re

# Cache en memoria para evitar lookups repetidos
_cache_lexnames = {}

def clasificar_palabra(palabra):
    """Retorna set de lexnames para una palabra.
    Ej: 'error' → {'noun.act', 'noun.attribute', 'noun.cognition'}
    Si WordNet no reconoce la palabra, retorna set vacío."""
    key = palabra.lower().strip()
    if key in _cache_lexnames:
        return _cache_lexnames[key]
    
    synsets = wn.synsets(key)
    lexnames = set(s.lexname() for s in synsets)
    _cache_lexnames[key] = lexnames
    return lexnames

def clasificar_texto(texto):
    """Extrae palabras significativas de un texto y las clasifica.
    Retorna dict {palabra: set(lexnames)}.
    Solo palabras de 3+ chars que WordNet reconoce."""
    palabras = set(re.findall(r'\w{3,}', texto.lower()))
    resultado = {}
    for p in palabras:
        lexnames = clasificar_palabra(p)
        if lexnames:  # Solo palabras reconocidas
            resultado[p] = lexnames
    return resultado

def obtener_lexnames_query(query, parafrasis=None):
    """Clasifica las palabras del query + paráfrasis.
    Retorna set plano de todos los lexnames encontrados."""
    texto = query
    if parafrasis:
        texto += " " + " ".join(parafrasis)
    clasificado = clasificar_texto(texto)
    todos = set()
    for lexnames in clasificado.values():
        todos |= lexnames
    return todos
```

---

### 3. Write-time: Clasificar al consolidar

#### [MODIFY] [memory_store.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/core/memory_store.py)

En `consolidar_concepto()` (línea ~997), después de `auto_vincular`, agregar:

```python
# Clasificación simbólica: WordNet lexnames
self._clasificar_nodo_wordnet(key, contenido, sinonimos or "")
```

En `ciclo_sueno_consolidacion()` (línea ~1145), después del loop de `auto_vincular`, agregar lo mismo para cada concepto consolidado.

Nuevo método en la clase:

```python
def _clasificar_nodo_wordnet(self, concepto, contenido, sinonimos=""):
    """Clasifica las palabras del nodo por grupo semántico WordNet.
    Almacena en tabla puente nodo_grupos_semanticos."""
    try:
        from core.clasificador_wordnet import clasificar_texto
    except ImportError:
        return  # WordNet no disponible — fallback silencioso
    
    texto = f"{concepto} {contenido} {sinonimos}".replace("_", " ")
    clasificado = clasificar_texto(texto)
    
    for palabra, lexnames in clasificado.items():
        for ln in lexnames:
            # Obtener o crear grupo
            self.cursor.execute(
                "SELECT id FROM grupos_semanticos WHERE nombre = ?", (ln,)
            )
            row = self.cursor.fetchone()
            if row:
                grupo_id = row[0]
            else:
                self.cursor.execute(
                    "INSERT INTO grupos_semanticos (nombre) VALUES (?)", (ln,)
                )
                grupo_id = self.cursor.lastrowid
            
            self.cursor.execute(
                "INSERT OR IGNORE INTO nodo_grupos_semanticos "
                "(concepto, palabra, grupo_id) VALUES (?, ?, ?)",
                (concepto, palabra, grupo_id)
            )
```

---

### 4. Read-time: Score de grupo en búsqueda

#### [MODIFY] [memory_store.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/core/memory_store.py)

En `buscar_por_frase()`, después del batch query de dimensiones (línea ~2320), agregar:

```python
# ─── Capa 5: Score por grupo semántico (WordNet lexnames) ───
grupo_scores_map = {}
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    query_lexnames = obtener_lexnames_query(
        frase, parafrasis_list
    )
    if query_lexnames:
        # Obtener IDs de los grupos del query
        placeholders_ln = ",".join("?" * len(query_lexnames))
        self.cursor.execute(
            f"SELECT id FROM grupos_semanticos WHERE nombre IN ({placeholders_ln})",
            tuple(query_lexnames)
        )
        query_grupo_ids = set(r[0] for r in self.cursor.fetchall())
        
        if query_grupo_ids:
            conceptos_todos = [r[1] for r in todos if r[1]]
            if conceptos_todos:
                ph_conceptos = ",".join("?" * len(conceptos_todos))
                ph_grupos = ",".join(str(g) for g in query_grupo_ids)
                self.cursor.execute(
                    f"SELECT concepto, grupo_id FROM nodo_grupos_semanticos "
                    f"WHERE concepto IN ({ph_conceptos}) "
                    f"AND grupo_id IN ({ph_grupos})",
                    tuple(conceptos_todos)
                )
                # Coseno binario: shared / sqrt(|query| × |doc|)
                import math
                concepto_grupo_ids = {}
                for concepto, gid in self.cursor.fetchall():
                    concepto_grupo_ids.setdefault(concepto, set()).add(gid)
                
                q_len = len(query_grupo_ids)
                for concepto, doc_gids in concepto_grupo_ids.items():
                    shared = len(query_grupo_ids & doc_gids)
                    if shared > 0:
                        grupo_scores_map[concepto] = shared / math.sqrt(
                            q_len * len(doc_gids)
                        )
except ImportError:
    pass  # WordNet no disponible
```

---

### 5. Score híbrido: Nueva fórmula de 9 señales

#### [MODIFY] [memory_store.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/core/memory_store.py)

Modificar `_calcular_score_hibrido()` (línea ~1669):

```python
def _calcular_score_hibrido(self, bm25_norm=0.0, dim_score=0.0,
                            peso_sinaptico=0.0, concepto_ratio=0.0,
                            sinonimos_ratio=0.0, score_latente=0.0,
                            score_cadena=0.0, temporal=0.0,
                            asoc_count=0, match_exacto=False,
                            grupo_score=0.0):
    """Score híbrido unificado: 9 señales ortogonales que suman 1.0.
    grupo_score: similitud por grupo semántico WordNet (coseno binario)."""
    asoc_norm = min(1.0, asoc_count / 20.0)
    peso_norm = min(1.0, peso_sinaptico)

    score = (
        0.20 * bm25_norm +          # FTS5 BM25 (was 0.25)
        0.15 * dim_score +           # Dimensiones semánticas (was 0.20)
        0.15 * concepto_ratio +      # Match en concepto
        0.10 * sinonimos_ratio +     # Match en sinónimos
        0.10 * peso_norm +           # Peso sináptico
        0.10 * max(score_latente, score_cadena) +  # Jaccard/cadena
        0.10 * grupo_score +         # NEW: Grupo semántico WordNet
        0.05 * temporal +            # Recencia
        0.05 * asoc_norm             # Asociaciones
    )

    if match_exacto:
        score = max(0.5, score)

    return round(min(1.0, score), 4)
```

Y en la llamada dentro de `buscar_por_frase()` (línea ~2409), agregar:

```python
grupo_score=grupo_scores_map.get(concepto, 0.0),
```

---

### 6. Migración — Clasificar nodos existentes

#### [NEW] [scripts/migrar_clasificacion.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/scripts/migrar_clasificacion.py)

Script one-shot que clasifica los 454 nodos existentes:

```python
"""Migración: clasificar todos los nodos existentes con WordNet lexnames."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.memory_store import SQLiteMemoryBioRAG

cerebro = SQLiteMemoryBioRAG()
cerebro.cursor.execute(
    "SELECT concepto, contenido, sinonimos FROM largo_plazo"
)
nodos = cerebro.cursor.fetchall()
total = len(nodos)
for i, (concepto, contenido, sinonimos) in enumerate(nodos, 1):
    cerebro._clasificar_nodo_wordnet(concepto, contenido or "", sinonimos or "")
    if i % 50 == 0:
        print(f"[{i}/{total}] clasificados...")
cerebro.conn.commit()
print(f"Migración completa: {total} nodos clasificados.")
```

---

### 7. MCP Server — Sin cambios visibles

#### [MODIFY] [mcp_server.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/mcp_server.py)

No se necesitan cambios en el MCP. La clasificación es transparente:
- Se ejecuta automáticamente en `consolidar_concepto` y `ciclo_sueno_consolidacion`
- El scoring se inyecta automáticamente en `buscar_por_frase`
- Los agentes no necesitan cambiar sus llamadas a `recordar`, `aprender`, `consolidar`

---

## Diagrama de Flujo

```
WRITE PATH (guardar → consolidar):
  contenido + sinonimos
       ↓
  clasificar_texto() ← WordNet
       ↓
  INSERT nodo_grupos_semanticos (concepto, palabra, grupo_id)

READ PATH (buscar/recordar):
  query + parafrasis
       ↓
  obtener_lexnames_query() ← WordNet
       ↓
  SELECT grupo_id FROM nodo_grupos_semanticos WHERE concepto IN (candidatos)
       ↓
  coseno_binario(query_grupos, doc_grupos) → grupo_score
       ↓
  _calcular_score_hibrido(..., grupo_score=0.10)
```

---

## Verification Plan

### Automated Tests

1. **Test unitario del clasificador:**
   - `clasificar_palabra("error")` → set con `noun.act`, `noun.cognition`, etc.
   - `clasificar_palabra("xyznotaword")` → set vacío

2. **Test de integración write-path:**
   - Guardar un nodo → verificar que `nodo_grupos_semanticos` tiene filas

3. **Test de integración read-path:**
   - Guardar "decode jargon" → buscar "translate language" → verificar grupo_score > 0

4. **Test de regresión:**
   - Ejecutar `python3 -m pytest test_memory.py` → todos los tests existentes pasan

### Manual Verification

- Ejecutar `scripts/migrar_clasificacion.py` sobre los 454 nodos existentes
- Buscar en MCP: `recordar(query="traducir")` → verificar que nodos con "decode" aparecen con score elevado
- Verificar que `introspección` reporta estado normal post-migración
