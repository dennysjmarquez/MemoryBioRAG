# Entrega — fix stopwords + hipótesis 7.1 probada

Corrido y verificado contra tu DB real (`MemoryBioRAG_Data/memory_biorag.db`,
796 nodos al momento de esta entrega — creció desde el brief original).

## 1. `ppmi_svd_puro_v2_suave.py` — USAR ESTE, reemplaza al anterior

Arregla el punto 8.2 (las 3 queries degeneradas). Mismo CLI que
`ppmi_svd_puro.py`, mismo esquema de DB. Diferencia: excepción quirúrgica de
exactamente 3 palabras (`memoria`, `buscar`, `memory`) al stopword-filter,
aplicada igual a corpus y a queries. NO toca `core/stopwords.py`.

**Dónde va:** reemplazar `scripts/ppmi_svd_puro.py` (o dejarlo al lado, tu
decisión — el nombre de archivo no importa, el CLI es idéntico).

**Resultado verificado (`--eval`):**
```
por_tema top5: 15/21  (gate ≥10 ✔, mejoró desde 14/21)
sinonimo top5:  2/14  (gate ≥6 ✘, sin cambio — esperable, este fix no ataca sinonimia)
0563 'memoria', 0757 'buscar', 0799 'memory': ya NO degeneran (antes: vector
cero, empate contra los ~796 nodos)
```

Incluye la DB ya entrenada (`ppmi_svd_vectors_suave.db`) y su
`ppmi_svd_vectors_suave_eval.json` — por si querés auditar sin reentrenar.
Para reentrenar desde cero: mismo comando que ya usás, apuntando `--db` a
este script.

## 2. `ppmi_svd_ctx.py` — hipótesis 7.1, resultado NEGATIVO (documentado, no descartar el archivo)

Implementa matriz palabra-**contexto** con ventana deslizante (Levy &
Goldberg / equivalente exacto a SGNS) en vez de palabra-documento. Nuevo
flag `--window N` (default 5).

**Barrido de `--window` ∈ {1,2,3,5,8,12} — ningún valor destraba el gate de
sinonimia:**
```
window=1:  por_tema 14/21  sinonimo 2/14
window=2:  por_tema 14/21  sinonimo 2/14
window=3:  por_tema 13/21  sinonimo 2/14
window=5:  por_tema 13/21  sinonimo 2/14
window=8:  por_tema 13/21  sinonimo 1/14
window=12: por_tema 13/21  sinonimo 1/14
```
Mismos 2 aciertos de siempre (0520, 0822 — co-ocurrencia léxica, no
sinonimia limpia). Verifiqué que no es problema de vocabulario: las 12
queries de sinónimo que fallan tienen sus stems en el vocab en el 100% de
los casos — el modelo las conoce, no las rankea bien. Control de cordura
pasa en todas las variantes (sistema↔gato entre -0.03 y +0.07).

**Conclusión:** la construcción de la matriz (documento vs. contexto, y el
ancho de ventana) no es el cuello de botella. Se probó de 6 formas
distintas y sinonimia limpia real sigue en 0/14. No es "no se probó
todavía" — se probó y no funcionó, con evidencia (`ppmi_svd_vectors_ctx_eval.json`
adjunto).

## 3. Próxima hipótesis (no implementada — para que la evalúen ustedes)

La DB tiene tabla `sinapsis` (grafo de nodos relacionados, ya existe en
producción, se puede leer solo-lectura). Ningún experimento de la cadena
usó esa señal — todos partieron solo del texto. *Retrofitting* (Faruqui et
al. 2015): ajustar los vectores PPMI+SVD para que además queden cerca de
sus vecinos en el grafo de sinapsis. Cero dependencias externas (la señal
sale de la propia DB), respeta el aislamiento. Vale la pena porque ya se
descartó que el problema sea el método de co-ocurrencia — puede que sea que
71k tokens de puro texto no alcanza para que la sinonimia paradigmática
emerja, y el grafo ya tiene esa relación codificada por otro camino.

## Restricciones respetadas
Sistema aislado (solo lectura sobre `memory_biorag.db`), sin dependencias
de ML preentrenado externo, mismo CLI, `por_tema` no retrocedió del gate
en ningún experimento, no se tocó `core/stopwords.py` ni ningún archivo de
producción.
