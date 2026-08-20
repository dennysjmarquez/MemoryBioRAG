# Walkthrough: Auditoría Sistemática de los 26 Mecanismos — BioRAG

## Resultado Final
- **R@5: 97.73%** (20 fallos sobre 921 casos) — mejora de +0.23% vs baseline original
- Commit: `7395f74` — Spreading Activation proactivo

---

## Único cambio que mejoró: Auditoría #1 — Spreading Activation Proactivo

**Diagnóstico**: `_evocacion_por_cadena` solo se ejecutaba cuando `len(todos) < 3`.
Esto bloqueaba el spreading activation para la mayoría de queries que sí tienen resultados FTS.

**Fix**: Pre-computar `cadena_scores_map` desde los top-5 seeds antes del loop de scoring,
sin depender de `len(todos)`. El spreading activation actúa como señal de re-ranking
para todos los candidatos del pool.

**Resultado**: +2 casos rescatados en `sinonimo` (casos 0574, 0580).

---

## Los 13 Experimentos Descartados

| Auditoría | Cambio intentado | Resultado | Por qué falló |
|---|---|---|---|
| #2 JSD 0.05 | Bajar peso JSD | Regresión | JSD es débil como señal adicional |
| #3 SRL sin predicados | Activar sin relaciones | Neutral | Ya estaba bien calibrado |
| #4 Sinónimos 0.08→0.14 | Peso sinonimos_ratio | Regresión severa | Inflaba scores incorrectos |
| #5 PPMI cobertura | Diagnóstico | OK (100%) | Sin acción necesaria |
| #6 WordNet grupos | Diagnóstico | OK (91.6%) | Sin acción necesaria |
| #7 Similitud temática | Diagnóstico | OK cobertura | Sin acción |
| #8 Trigramas re-ranking | Re-ranking trigrama | Regresión -0.45% | Pool saturado de competidores |
| #9 PPMI 0.15→0.25 | Subir peso PPMI | Regresión -0.23% | No compensaba pérdidas |
| #10 QCR-IDF | IDF dentro del gate | Regresión catastrófica | Tokens sin match → denominador infinito |
| #11 Stemming en QCR | Stem en gate de filtro | Regresión marginal | Amplía pool → competidores incorrectos |
| #12a Label Propagation | Co-comunidad | Sin datos | No hay tabla de comunidades en DB |
| #12b Marcador somático | Valencia somática | Sin gradiente | 15.6% cobertura, todos = 1.0 |
| #13 Fix trigrama completo | qw_cortas + guard + typo-escape + Fallback 1.6b | Neutral / Regresión | Ver análisis abajo |

---

## Diagnóstico Profundo de los 20 Fallos Resistentes

### Grupo A — 4 fallos `sinonimo` (sin solución posible)

Queries: `"memoria"`, `"buscar"`, `"identidad"`, `"dimensiones"`

**Causa**: 1 sola palabra = 30+ nodos candidatos válidos. El sistema no puede
elegir el correcto sin contexto adicional. Esta es la definición matemática de
"ambigüedad irreducible". **No resolvibles con la arquitectura actual.**

---

### Grupo B — 6 fallos `variante_gramatical` (análisis de Auditoría #13)

**Cadena de bloqueos descubierta:**

1. **Trigrama (Fallback 1.7)** tiene `LIMIT 200`. El target `cuando_usar_dimensiones_biorag`
   tiene **rowid=593** → nunca entra al loop Python. Targets `patron_pensamiento...` tiene rowid=267.

2. Aunque el trigrama encuentra el target (avg_score 0.78-0.87 >> umbral 0.70),
   la guarda `qw_cortas ≤5` exige `PALABRA_COMPLETA` para 'usado' (5 chars) que falla
   porque el target tiene 'usar' — variante morfológica.

3. Aunque todo lo anterior se resuelva (qw_cortas ≤3, guard <5, typo en QCR escape),
   el **hybrid score del target es demasiado bajo** para competir:
   - BM25 = 0 (no encontrado por FTS5)
   - concepto_ratio ≈ 0.20 (pocos tokens literales)
   - score_latente = 0 ("semantica"/"typo" no están en la lista de score_latente)
   - Score total ≈ 0.28 vs competidores incorrectos con 0.32

**Causa raíz final**: El scoring híbrido es predominantemente léxico. Las 13 señales
están calibradas para matching léxico, no morfológico. Un nodo encontrado por stem
pero sin tokens literales en común recibe un hybrid score < 0.30.

**Diagnóstico de la fórmula**:
```python
score_latente = score_capa if origen in ("latente", "expansion", "contenido") else 0.0
```
`"typo"` y `"semantica"` NO activan `score_latente`. Es la señal principal que daría
boost al target morfológico. Para resolverlo habría que añadir esos orígenes a la lista
Y verificar que no introduce FPs.

---

### Grupo C — 7 fallos `por_tema`/`literal`/`pregunta_natural` (brecha léxica)

**Fallos de `literal`** (3 casos): dos nodos near-duplicados compiten — uno con coma,
otro con "y". El preprocessing elimina la coma antes del scoring. **Problema de datos.**

**Fallos de `por_tema`** (4 casos): la query y el target no comparten tokens.
Verificado con grafo sináptico: **no hay puente** entre los seeds FTS y los targets.

---

## Descubrimiento Crítico: El PPMI SÍ Funciona, Pero Se Usa Poco

**Prueba empírica directa sobre la snapshot** (PPMI puro, sin otros signals):

| Query | Target | Rank PPMI | Score coseno |
|---|---|---|---|
| "cuando usado dimensione biorags" | cuando_usar_dimensiones_biorag | **#1** | **0.7255** |
| "ráfaga después resultado" | mentalidad_biorag_para_agentes | #129 | 0.3349 |
| "relevantes biomimética mejor" | benchmark_antes_despues_fix3 | **#6** | **0.5294** |

**Para el caso de variante_gramatical 0518**: PPMI puro lo rankea **#1 con score 0.7255**.
El sistema tiene la información semántica correcta, pero el PPMI recibe solo `weight=0.15`
en la fórmula híbrida, insuficiente para vencer a BM25 (0.25) + concepto_ratio cuando
el target no matchea léxicamente.

**Para el caso de `por_tema` (ráfaga→mentalidad)**: PPMI puro falla también (#129).
Estos casos requieren embeddings semánticos densos (sentence-transformers) que BioRAG
no tiene por diseño.

---

## Ideas Para Futuras Pruebas

### 🔑 Alta prioridad: Subir peso PPMI para queries morfológicas

El PPMI rankea correctamente el caso 0518 en #1. El problema es que pierde contra
señales léxicas en la fórmula híbrida. **Hipótesis**: cuando FTS5 devuelve pocos
resultados (< 3), aumentar temporalmente el peso PPMI de 0.15 a 0.35.

```python
ppmi_weight_efectivo = PPMI_WEIGHT * (2.0 if len(todos) < 3 else 1.0)
```

**Riesgo**: puede aumentar FPs en queries con resultados escasos legítimos.
Requiere verificación rigurosa contra la categoría `negativo`.

---

### 🔑 Media prioridad: Añadir score_latente para origen "typo"

```python
score_latente = score_capa if origen in ("latente", "expansion", "contenido", "typo") else 0.0
```

El trigrama ya exige avg_score ≥ 0.70 para entrar. Activar score_latente para
resultados del trigrama daría un boost real a los targets morfológicos.

**Riesgo bajo**: solo aplica a queries donde FTS5 tiene < 3 resultados (guard actual).

---

### 💡 Innovación: Adamic-Adar sobre grafo sináptico

Para los casos de `por_tema` (brecha léxica total): los targets NO tienen sinapsis
directa con los seeds FTS5. Pero podrían compartir vecinos sinápticos de segundo grado.

Adamic-Adar = Σ 1/log(grado_del_vecino_compartido)

Un nodo C comparte vecinos con los seeds A,B → C sube en el ranking aunque
no tenga tokens comunes ni sinapsis directa con A o B.

**Costo**: O(k² * V) por query donde k=vecinos por nodo y V=tamaño del corpus.
Con 977 nodos y ~20 vecinos promedio, es manejable (~400k operaciones).

---

### 💡 Innovación: Personalized PageRank desde semillas FTS

Para `"ráfaga después resultado" → mentalidad_biorag_para_agentes`:
- Lanzar PPR desde los nodos de "ráfaga" que FTS5 devuelve
- Los nodos que PPR visita con alta frecuencia = "relacionados por estructura del grafo"
- `mentalidad_biorag_para_agentes` puede ser visitado si está a 2-3 saltos de los seeds

**Costo**: ~0.5s por query con teleport=0.15 y 20 iteraciones sobre grafo de 977 nodos.
Implementable en Python puro sobre la tabla `sinapsis`.

---

## Estado del Corpus de Vectores PPMI

- **Vocabulario**: 8,797 tokens
- **Nodos vectorizados**: 977 (100% del corpus activo)
- **Dimensionalidad**: 100 dims por nodo
- **Corpus de entrenamiento**: `concepto + sinonimos + contenido` de cada nodo
- **Calidad**: probada directamente — rankea correctamente los casos de variante morfológica
- **Limitación**: peso bajo (0.15) en la fórmula híbrida, insuficiente cuando léxico falla

---

## Lección Principal de la Sesión

> De 13 experimentos, solo 1 mejoró. El sistema está en su límite de lo que
> puede hacer con matching léxico + 13 señales híbridas.

> Los 20 fallos restantes requieren uno de tres enfoques:
> 1. **Rebalanceo dinámico de señales** (PPMI más pesado cuando léxico falla) — bajo riesgo
> 2. **Aprovechamiento del grafo sináptico** (PPR, Adamic-Adar) — medio riesgo, medio costo
> 3. **Embeddings semánticos densos** (sentence-transformers) — fuera del scope actual

> El corpus de vectores PPMI ya tiene la información correcta para varios casos.
> El problema no es la calidad de los vectores, es el peso que reciben.
