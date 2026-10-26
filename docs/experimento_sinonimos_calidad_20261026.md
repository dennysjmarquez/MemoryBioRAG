# Experimento: graduar el bono de sinónimos. Resultado NEGATIVO.

**Fecha:** 2026-10-26 · **Base:** la viva del autor (1357 nodos), subida como
`backup_memory_biorag.sql` desde Google Drive y reconstruida localmente.
**Arnés:** `scripts/evaluar_qa.py --con-neurona --si`, 921 casos, mismas
banderas que `run_qa_suite.sh`.

## La pregunta

En la categoría `sinonimo` el nodo correcto casi siempre declara la palabra en
su campo `sinonimos`. Medido sobre los 61 casos: **61 de 61**. Pero la señal es
binaria — `score_simbolico_sinonimos` devuelve 1.0 si la palabra aparece, sin
mirar nada más — y en la base viva **una mediana de 16 nodos** (media 31,4,
máximo 184) declara la misma palabra y puntúa exactamente igual.

Cuando todos empatan, decide BM25, que premia llevar la palabra en el **nombre**
sobre llevarla en el **alias**. De ahí que `perfil` devuelva
`notebooklm_perfil_dennys_id` (0.772) antes que `dennys-identidad-profunda`.

Además el empate **crece con el corpus**. Crecimiento controlado sobre el
snapshot (mismos 61 casos, conservando siempre el nodo correcto, variando solo
el número de distractores, sin neurona):

| nodos | R@1 | R@5 | puesto medio | empatados (mediana) |
|---:|---:|---:|---:|---:|
| 150 | 0.803 | 1.000 | 1.26 | 2 |
| 400 | 0.656 | 0.967 | 1.74 | 8 |
| 866 | 0.525 | 0.902 | 2.43 | 16 |

Sobre la base viva, mismo protocolo (`profundidad='activos'`, `limite=5`):

| nodos | R@1 | R@5 | fallos |
|---:|---:|---:|---:|
| 150 | 0.639 | 0.787 | 13 |
| 400 | 0.541 | 0.787 | 13 |
| 866 | 0.361 | 0.721 | 17 |
| 1357 | 0.361 | 0.656 | 21 |

## La hipótesis

Graduar el bono del piso de sinónimos (`core/memory/scoring.py`, rama
`elif sinonimos_ratio >= 0.95`) por dos hechos que el autor sí escribió:

1. **Rareza** — IDF relativo del alias: `log1p(N/df) / log1p(N)`.
2. **Posición** — el alias en posición *k* vale `1/(1+0.25·(k-1))`.

Se implementó en `core/fallback_simbolico.calidad_sinonimo` y se multiplicó el
bono logit por ese valor, con `calidad=1.0` idéntico al comportamiento anterior.
Bandera `BIORAG_SINONIMOS_CALIDAD`, apagada por defecto.

## La medición

| métrica | antes | después | delta |
|---|---:|---:|---:|
| global R@5 | 99.20 | 98.63 | **−0.57** |
| global R@1 | 92.46 | 92.11 | −0.35 |
| global MRR | 0.9516 | 0.9479 | −0.0037 |
| fallos | 7 | **12** | **+5** |
| `sinonimo` R@5 | 89.09 | **80.00** | **−9.09** |
| `sinonimo` R@1 | 52.73 | 49.09 | −3.64 |
| `sinonimo` fallos | 6 | **11** | **+5** |

El resto de categorías sin cambio (literal, typo, variante, dormido, pregunta
natural, cruce de idioma). La compuerta `[GATE]` **falla**.

## Por qué falló

El bono no es un adorno: es el piso que hace competir a un nodo con alias
perfecto contra un nodo con el nombre exacto. Al graduarlo, **bajé el piso de
todos** — también el del correcto — y los correctos que ya ganaban por el piso
cayeron por debajo de rivales con coincidencia de nombre. Gané gradiente y perdí
altura. El desempate se movió, pero hacia abajo.

## Conclusión

**Revertido.** El árbol queda como estaba; el código del experimento se retiró.

El diagnóstico queda en pie y es el que importa: el número de `sinonimo`
**no es una propiedad del sistema, es una propiedad del sistema × corpus**. La
ecuación está calibrada sobre un corpus concreto (pesos absolutos, señal
binaria) y se degrada sola al crecer la base. Cualquier arreglo tiene que
**conservar el piso y añadir discriminación encima**, no repartir el piso.

Variante propuesta para la próxima medición (una sola, aislada): mantener
`target = 0.70 + 0.10·ppmi` igual para todos los que declaran el alias, y sumar
un extra pequeño proporcional a la calidad (`bonus += c · calidad`, con `c` ≤ 0.1
en logit). Todos conservan su altura; el alias mejor escrito recibe un empujón
que los demás no tienen.

## Intento 2: el piso igual para todos, empujón encima (TAMBIÉN NEGATIVO)

Variante medida en la base viva, `scripts/barrido_bonus_sinonimos.py`, sobre
`sinonimo` (61 casos) y `por_tema` (65):

    bonus = logit(0.70 + 0.10·ppmi) + extra · calidad

con `extra` en espacio logit, `calidad` = rareza del alias × posición.

| extra | sinonimo R@5 | sinonimo R@1 | fallos | por_tema R@5 |
|---:|---:|---:|---:|---:|
| −3.0 | 0.443 | 0.328 | 34 | 0.785 |
| **0.0 (actual)** | **0.656** | **0.361** | **21** | 0.785 |
| +1.0 | 0.623 | 0.328 | 23 | 0.785 |
| +2.0 | 0.623 | 0.295 | 23 | 0.785 |
| +3.0 | 0.623 | 0.311 | 23 | 0.785 |

`por_tema` no se mueve en ningún valor: el cambio es local a `sinonimo`.

### Por qué también falla

El bono se aplica en logit y el score se recorta a 1.0. Sumar a todos **acerca a
todos al techo**, y cerca del techo la logística aplana: se pierde gradiente otra
vez, ahora por saturación. Restar (`extra` negativo) es peor todavía, porque el
piso es lo que hace visible al nodo de alias puro.

Conclusión: **el piso de sinónimos ya está en su punto.** No es una perilla
descalibrada, es una perilla agotada. Dos experimentos independientes lo
confirman (repartir el piso, y sumar encima del piso).

## Lo que esto significa para el diagnóstico

El bono de sinónimos no es el cuello de botella. El cuello está en otro sitio:

- Con el motor desnudo y `profundidad='activos'`, el nodo correcto **no entra al
  top-5 en 21 de 61 casos** (R@5 0.656). No está mal puntuado: no llega.
- Con la neurona de ranking, la QA real sube a R@5 0.8909 en esa categoría. O
  sea: **la neurona ya es la que rescata estos casos**, no la ecuación a mano.
- Los 491 nodos nuevos de la base viva comparten vocabulario con los viejos, así
  que la colisión crece. A igual tamaño (866 nodos), la base viva falla 17 y el
  snapshot 3.

La siguiente palanca no es "puntuar mejor el alias": es **dar a la neurona el
hecho que la ecuación no puede usar**. La calidad del alias (rareza × posición)
es un rasgo disponible y hoy no se le ofrece. Como rasgo, si no aporta, el
entrenamiento deja su peso en cero y no hay regresión; si aporta, la neurona lo
usa donde la fórmula global no llega. Eso es exactamente "neurona donde el código
no llegaría".


- `scripts/experimento_crecimiento_corpus.py` — crecimiento controlado.
- `scripts/crecimiento_corpus_resultado.json` — curva del snapshot.
- `scripts/crecimiento_viva_resultado.json` — curva de la base viva.
- `scripts/barrido_bonus_sinonimos.py` — barrido del extra de sinónimos (intento 2).
