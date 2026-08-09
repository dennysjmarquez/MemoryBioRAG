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

## 3. Retrofitting (Faruqui et al. 2015) sobre `sinapsis` real — REFUTADO (2026-08-08)

La hipótesis de la sección previa se implementó y probó: `scripts/ppmi_svd_retro.py`
(aislado, no toca `v2_suave`). Usa la tabla `sinapsis` REAL de
`memory_biorag.db` (12.337 filas, 11.910 aristas usable, nodos con 10–96
vecinos). Dos modos:

1. **`concepto`** — retrofitea vectores de nodo contra sus vecinos directos
   (Faruqui estándar). Barrido α ∈ {0.1..0.7}, it ∈ {1..3}.
2. **`tokens`** — expande cada arista concepto→concepto a token→token
   (top-40 vecinos/token, 127.856 aristas) y retrofitea la matriz W.
   Barrido α ∈ {0.3..0.8}, it ∈ {2..5}; también `--solo-tipo`
   ∈ {sinonimo_explicito, pmi_hebbiano, manual}.

**Resultado — ninguna config destraba el gate de sinonimia:**
```
baseline (v2_suave, sin retro):     por_tema 15/21  sinonimo 2/14
concepto α=0.1 it=1-3:              15/21          2/14
concepto α=0.3:                     12–13/21       2/14
concepto α=0.7 it=5:                10/21          1/14
tokens α=0.3-0.8 it=2-5:            14–15/21       2/14
tokens solo sinonimo_explicito:     15/21          2/14
```
Los 2 aciertos de siempre (0520, 0822 — co-ocurrencia léxica). Control de
cordura pasa. `por_tema` nunca regresó por debajo del gate 10.

**Diagnóstico (no es bug, es estructural):** la señal SÍ llega — el coseno
del expected sube +0.16 a +0.24 en los 14 casos de sinónimo y el gap contra
top-5 baja de 0.36 → 0.07 promedio. Pero el grafo es **demasiado denso**
(60–96 vecinos por nodo): el retrofitting comprime TODO el pool hacia los
centroides, los competidores suben igual que el expected y los ranks quedan
congelados. Faruqui funciona con léxicos escasos (5–10 vecinos/palabra);
un grafo denso y heterogéneo (tipos mezclados) aplasta la discriminación
relativa. Consistente con la lección JSD ya guardada: señales globales
aplastan queries genéricas.

**Conclusión:** retrofitting con la sinapsis real NO es la palanca para
sinonimia limpia. Si se quisiera insistir, habría que adelgazar drásticamente
el grafo (solo edges de alta confianza tipo `manual`/`sinonimo_explicito`
de 1 salto), pero la evidencia actual dice que el problema no se resuelve
con una presión global.

## Restricciones respetadas
Sistema aislado (solo lectura sobre `memory_biorag.db`), sin dependencias
de ML preentrenado externo, mismo CLI, `por_tema` no retrocedió del gate
en ningún experimento, no se tocó `core/stopwords.py` ni ningún archivo de
producción.
