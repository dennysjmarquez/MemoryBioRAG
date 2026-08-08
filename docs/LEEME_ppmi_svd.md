# ppmi_svd_puro — sistema aislado, alternativa a word2vec_puro (SGNS)

## Qué es
Igual que `word2vec_puro.py`: 100% aislado, no toca BioRAG en producción,
solo lee `MemoryBioRAG_Data/memory_biorag.db` en modo lectura y escribe su
propia DB de vectores. Mismo CLI, misma interfaz de recuperación.

Reemplaza SGNS (skip-gram + negative sampling) por **PPMI + SVD**
(Church & Hanks 1990 / Levy & Goldberg 2014-2015): factorización exacta de
una matriz de co-ocurrencia palabra-documento con Positive PMI y context
distribution smoothing (alpha=0.75), reducida con SVD truncada. Está en
`ppmi_svd_puro.py` — leer el docstring del archivo para el detalle completo
de por qué (corpus de 71k tokens es demasiado chico para que SGNS converja
de forma estable; PPMI+SVD es más robusto en corpus pequeños según Levy &
Goldberg 2015).

## Archivos en este paquete
- `ppmi_svd_puro.py` — el script (entrenamiento + recuperación + eval).
  Colocar en `scripts/` del repo.
- `ppmi_svd_puro_db/ppmi_svd_vectors.db` — DB ya entrenada (794 nodos,
  716 activos + 78 dormidos, vocab 4.654, dim 100, seed=42, min_count=2).
  Colocar en `scripts/ppmi_svd_puro/`.
- `ppmi_svd_puro_db/ppmi_svd_eval.json` — resultado de `--eval` ya corrido
  contra los 35 fallos históricos.

## Requisitos
`numpy`, `scipy`, `scikit-learn` (para `TruncatedSVD`). Nada más —
sigue siendo "cero dependencias de ML/embeddings externos": no se descarga
ni se usa ningún modelo pre-entrenado, todo se calcula desde el corpus
propio.

## Cómo usarlo
```bash
# Recuperar (con la DB ya entrenada, sin re-entrenar)
python3 scripts/ppmi_svd_puro.py "perfil de dennys" --db scripts/ppmi_svd_puro/ppmi_svd_vectors.db

# Reentrenar desde cero (por si el corpus cambió)
python3 scripts/ppmi_svd_puro.py --db scripts/ppmi_svd_puro/ppmi_svd_vectors.db

# Evaluar contra los 35 fallos históricos
python3 scripts/ppmi_svd_puro.py --db scripts/ppmi_svd_puro/ppmi_svd_vectors.db --eval

# Control de cordura: coseno entre dos tokens ya stemmeados
python3 scripts/ppmi_svd_puro.py --db scripts/ppmi_svd_puro/ppmi_svd_vectors.db --par sistema gato
```

## Resultado ya verificado (no solo reportado — reproducido en sandbox)
```
                 SGNS (completa)    PPMI+SVD
por_tema top5        10/21             15/21   (gate min 10 ✔)
sinonimo top5          1/14              2/14   (gate min 6 ✘)
```
Control de cordura (el que reventó con SGNS):
```
coseno(sistema, gato)         = -0.0333   <- más bajo que TODOS los sinónimos reales
coseno(busc, consulta)        =  0.0683
coseno(sistema, herramienta)  =  0.1341
coseno(nodo, concepto)        =  0.3129
coseno(perfil, ident)         =  0.3358
```
Con SGNS, `gato` le ganaba a los sinónimos reales — acá queda último. Hay
señal semántica real en el espacio, pero el pooling (promedio de tokens del
nodo) sigue sin traducir esa señal en victorias de ranking cuando la query
es de 1-2 palabras contra nodos de 35-300 tokens. Esa es la próxima
hipótesis a probar, NO todavía resuelta.

## Qué falta antes de hablar de integración con BioRAG
1. Probar pooling ponderado / similitud máxima token-vs-nodo en vez de
   promedio plano, para ver si eso destraba el gate de sinonimia (1/14).
2. Opcional/más caro: reconstruir con matriz palabra-**contexto** (ventana
   deslizante, como el SGNS real) en vez de palabra-**documento** — es el
   equivalente exacto que describen Levy & Goldberg, más fiel a SGNS que la
   versión actual (que es más parecida a LSA clásico).
3. Recién con eso, decidir en qué punto del pipeline de recuperación de
   BioRAG entraría esta señal (y si entra como reemplazo o como señal
   adicional al lado de FTS5/BM25/sinapsis).
