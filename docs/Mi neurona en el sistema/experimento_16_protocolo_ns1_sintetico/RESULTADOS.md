# Experimento 16: resultados (mundos sintéticos; motor sin cambios)

**Fecha:** 2026-11-25. **Protocolos:** `PROTOCOLO.md` (v1, commit `3212e2b`) y `PROTOCOLO_V2.md` (v2,
commit `0fb35ac`), los dos subidos **antes** de medir. **Datos:** solo mundos sintéticos generados por
`mundo.py`, construidos con el motor real en `/tmp`. No se abrió ninguna base real ni el snapshot, y no
se cambió el motor ni los tests.

Estos resultados son **nuevos** y valen para mundos sintéticos. **No** se comparan número a número con
los experimentos 12–15, que usaron la DB real o el snapshot.

## Resumen

1. **Hoy el nacimiento de sinapsis es muy ruidoso** en estos mundos:
   - solo entre el 11 % y el 18 % de las sinapsis automáticas une recuerdos relacionados;
   - en los temas sellados de la v2, entre el 7 % y el 9 %.
2. **El nacimiento depende del orden** en que se guardan los recuerdos y de recuerdos que no tienen
   nada que ver:
   - con los mismos recuerdos guardados en otro orden, cambia la puntuación del **73–78 %** de los
     pares;
   - al agregar 400 recuerdos sin una sola palabra en común, cambia el **63–69 %**.
3. **La neurona ordena el canal 2 al máximo posible:**
   - en las semillas 1–3, su P@5 es **igual al techo** que tendría un oráculo que conoce la verdad,
     con los mismos candidatos; en G queda a 0,002;
   - es más del doble de la P@5 del piso actual;
   - no oculta nada y cuesta unos 0,12 ms por par.
4. **En el mundo v2 supera a toda fórmula fija:**
   - AUC sellado de 0,999–1,000, contra 0,91–0,95 de la mejor fórmula y 0,54–0,57 del piso;
   - la mayor parte de la ganancia viene de su **memoria semántica aprendida sin etiquetas**, que
     reconoce sinónimos que no comparten letras.
5. **Según el protocolo, NO pasa** porque falla el criterio 4 (invariancia):
   - **causa principal:** el nacimiento del piso no es invariante, y una neurona que solo ordena no lo
     puede arreglar;
   - **causa propia** de la neurona: con recuerdos nuevos de vocabulario desconocido, la memoria
     semántica congelada sobrestima su parecido (§5).

   No hay «casi pasa».

## 1. Qué se corrió

| | v1 | v2 |
|---|---|---|
| Mundos | Semillas 1, 2 y 3, cada una con 5 variantes (D, D_rep, D_Ipuro, D_Ireal y D_orden), más G (semilla 11) | Lo mismo con `generar_v2` |
| Construcciones con el motor | 16, de ~60 s por cada 400 recuerdos | 16 |
| Entrenamiento | 12 543 pares de ajuste y 12 867 de calibración, sin sellados | 10 789 de ajuste y 13 591 de calibración, sin sellados |
| Evaluación | Pares sellados: entre 5 116 y 5 694 por mundo | Entre 6 852 y 7 753 por mundo |

**Arreglos de implementación hechos durante el análisis.** Se hicieron antes de las cifras finales y
**sin tocar ningún umbral ni criterio**. Se declaran porque cambiaron números.

1. **Dimensiones que crea el motor.** La prueba de invariancia mostró que la neurona v1 cambiaba la
   puntuación de pares de D (1 163 en la semilla 1). La causa: el motor **agrega por su cuenta**
   dimensiones `tema_*` (auto-clustering, `auto_generada = 1`) que dependen de todo el corpus. Usarlas
   ya estaba prohibido en §7 («comunidad»), así que era un error de implementación. Ahora la neurona
   usa solo las dimensiones que declara quien guarda el recuerdo. Resultado: I1 de la neurona = 0 en
   todas las variantes.
2. **El canal 2 se llama con una sola raíz por vez**, como en una búsqueda real. Si se le pasan todas
   las raíces juntas, el motor solo cuenta la arista desde el origen cuando los dos extremos están en
   la lista. Con la llamada por raíz, todo lo que muestra el motor está entre los candidatos que ve la
   neurona: 404 de 404 listas en cada semilla.
3. **Empates.** Muchas aristas `sinonimo_explicito` empatan en 0,9, y el motor las desempata en el
   orden en que SQLite las lee. Por eso la P@5 del piso se toma **del motor real** y no de la réplica.

## 2. Piso (motor actual), con todos los pares de cada mundo D

| Métrica | v1 (s1 / s2 / s3) | v2 (s1 / s2 / s3) |
|---|---|---|
| Q1: AUC del peso como separador | 0,60 / 0,59 / 0,56 | 0,54 / 0,53 / 0,52 |
| Q2: sinapsis automáticas que unen recuerdos relacionados | 18 % / 17 % / 16 % | 12 % / 12 % / 11 % |
| Q3: pares del mismo subtema con alguna sinapsis | 63 % / 63 % / 60 % | 55 % / 60 % / 55 % |
| Q4: P@5 del canal 2 | 0,25 / 0,30 / 0,28 | 0,20 / 0,21 / 0,20 |
| Q5: grado máximo, mediana y recuerdos con más de 3 × la mediana | 317–331, 61–68, 4 | 297–322, 72–74, 4 |
| R1: dos construcciones idénticas | **Sí** en las tres | **Sí** en las tres |
| Q6: renacen tras `desvincular` y volver a guardar | 13, 14 y 11 de 30 | 7, 6 y 9 de 30 |

**Qué tan ruidoso es cada tipo de sinapsis** (v1, semilla 1):

| Tipo | Aristas | Fracción que une recuerdos relacionados |
|---|---|---|
| `sinonimo_explicito` | 9 710 | 13 % |
| `co_ocurrencia` | 2 312 | 14 % |
| `pmi_hebbiano` | 2 003 | 54 % |
| `co_semantica` | 166 | 45 % |
| `co_nombre` | 404 | 30 % |
| `dmn_synthesized` | 72 | 29 % |

En la v2 todos bajan: `sinonimo_explicito` queda en 9 %.

### Invariancia del piso

Contrato de §5: la puntuación de un par fijo de D no debe cambiar.

| Variante | I1: pares de D que cambian | I3: pares que existen en una sola variante | I4: lugares del canal 2 ocupados por I | I5: listas que cambian | Recuerdos de D que cambian de estado |
|---|---|---|---|---|---|
| v1, D_Ipuro | 63–64 % | ~10 000 de ~19 000 | 0 | 88–99 % | 48–77 |
| v1, D_Ireal | 47–51 % | ~5 500–6 600 | 10–15 % | 83–97 % | 43–61 |
| v1, D_orden | 73–75 % | ~12 800–14 400 | 0 | 95–97 % | 156–194 |
| v2, D_Ipuro | 64–69 % | ~10 700–11 800 | 0 | 90–96 % | 39–60 |
| v2, D_Ireal | 52–56 % | ~7 200–7 800 | 19–25 % | 87–97 % | 64–67 |
| v2, D_orden | 76–78 % | ~15 700–16 800 | 0 | 97–100 % | 164–198 |

**Causas, según el diagnóstico de aristas que aparecen o desaparecen:**
- **Con otro orden** cambian sobre todo `sinonimo_explicito` (8 000–9 900 aristas) y `co_ocurrencia`.
  Su nacimiento depende de quién ya estaba guardado.
- **Con recuerdos irrelevantes «limpios»** cambian sobre todo `pmi_hebbiano` (5 900–6 600 aristas):
  el PMI se calcula sobre todo el corpus.
- **En las dos situaciones**, la inhibición lateral del sueño (energía global) duerme recuerdos
  distintos según el total, y el canal 2 excluye a los vecinos dormidos.

## 3. Neurona v2 en el mundo realista (criterios de `PROTOCOLO_V2.md`, solo pares sellados)

| | s1 | s2 | s3 | G (otra familia) |
|---|---|---|---|---|
| AUC del piso | 0,557 | 0,539 | 0,575 | 0,561 |
| AUC de la mejor fórmula fija | 0,946 (B5) | 0,940 (B5) | 0,912 (B5) | 0,918 (B2) |
| **AUC de la neurona** | **1,000** | **1,000** | **1,000** | **0,999** |
| ECE / Brier de la neurona | 0,001 / 0,001 | 0,001 / 0,001 | 0,001 / 0,001 | 0,002 / 0,002 |
| P@5, piso del motor | 0,210 | 0,243 | 0,255 | 0,110 |
| P@5, mejor fórmula fija | 0,498 | 0,453 | 0,475 | 0,357 |
| **P@5, neurona** | **0,552** | **0,488** | **0,556** | **0,423** |
| P@5, techo (oráculo con los mismos candidatos) | 0,552 | 0,488 | 0,556 | 0,425 |
| Recuerdos sin asociaciones: piso / neurona | 0 / 0 | 0 / 0 | 1 / 1 | 1 / 1 |

**Ablación.** Se reporta, pero no es criterio.

| AUC sellado | s1 | s2 | s3 | G |
|---|---|---|---|---|
| B4: memoria semántica sola | 0,9996 | 0,9996 | 0,9978 | 0,9927 |
| Combinador solo con agujas léxicas | 0,982 | 0,981 | 0,981 | 0,977 |
| Neurona completa | 1,000 | 1,000 | 0,9999 | 0,9992 |

**Lectura honesta:** casi toda la ganancia sobre las fórmulas fijas viene de la **memoria semántica**.
Es significado aprendido por el uso, sin etiquetas; une sinónimos que no comparten letras. El
combinador agrega poco cuando la memoria semántica ya conoce todas las palabras. Sin ella, el
combinador léxico supera a la mejor fórmula fija por +0,04–0,06.

### Criterios v2

| Criterio | s1 | s2 | s3 | Global |
|---|---|---|---|---|
| 1. AUC ≥ piso + 0,05 y ≥ 0,80 | ✅ | ✅ | ✅ | |
| 2. P@5 ≥ piso + 0,10, sin más recuerdos vacíos | ✅ | ✅ | ✅ | |
| 3. Cobertura ≥ piso | ✅ (no toca nacimientos) | ✅ | ✅ | |
| **4. Invariancia (I1, I3, I4 e I5 = 0)** | ❌ | ❌ | ❌ | |
| 4a. Solo la puntuación propia de la neurona (I1) | ✅ 0 cambios | ✅ | ✅ | |
| 5. Determinismo | ✅ | ✅ | ✅ | |
| 6. ECE ≤ 0,05 | ✅ | ✅ | ✅ | |
| 7. Costo con N = 1600 ≤ 1,5 × el costo con N = 400 | | | | ✅ 0,134 frente a 0,119 ms (1,13 ×) |
| 8. Generalización a G (AUC ≥ piso + 0,03) | | | | ✅ |
| 9. Supera a la mejor fórmula fija + 0,03 | ✅ | ✅ | ✅ | ✅ también en G |

**Veredicto del protocolo: no pasa**, porque falla el criterio 4.

En la v1 el patrón es el mismo: pasa los criterios 1–3 y 5–8, falla el 4. Su AUC de 1,000 no prueba
nada, porque el mundo v1 era demasiado fácil.

## 4. Por qué falla el criterio 4, y qué es culpa de quién

- **I3 e I5 (nacimiento):** los mismos valores que en el piso. La neurona no decide nacimientos y no
  puede ocultar, así que hereda que la mayoría de las sinapsis dependan del orden y del resto del
  corpus. **Ninguna neurona que solo ordene puede pasar este criterio con el nacimiento actual.**
- **I4 en D_Ireal (culpa propia).** La neurona deja **más** recuerdos irrelevantes en el canal 2 que el
  piso:

  | | s1 | s2 | s3 |
  |---|---|---|---|
  | Piso | 0,19 | 0,25 | 0,24 |
  | Neurona | 0,26 | 0,31 | 0,32 |

## 5. Debilidad encontrada: palabras que la memoria semántica no conoce

`diagnostico_palabras_nuevas.py` (diagnóstico posterior, semilla 1 de la v2):

| | Recuerdos de D | Recuerdos de I_real (nuevos) |
|---|---|---|
| Palabras no comunes que conoce la memoria semántica congelada | 97 % | **23 %** |
| Coseno semántico medio con una raíz de D, siendo irrelevantes | 0,077 | **0,164** |

Un recuerdo nuevo, del que la memoria semántica conoce solo un par de palabras transversales, queda
representado **solo** por esas palabras. Por eso parece más afín de lo que es. Pasará con todo recuerdo
que llegue después de congelar la memoria semántica.

**Solución propuesta para la v3** (no aplicada, porque cambiaría la neurona después de medir):
- entrenar el combinador también con recuerdos que se dejan **fuera** de la memoria semántica, para
  simular recuerdos nuevos;
- agregar una aguja de «cobertura», para que aprenda a desconfiar cuando conoce pocas palabras;
- documentar cuándo se vuelve a calcular la memoria semántica, con versión y como decisión explícita.

## 6. Qué significa y qué no

**Sí:**
- En mundos con sinonimia y polisemia, una pieza aprendida (significado por uso más combinador
  calibrado) ordena las asociaciones **mucho mejor** que cualquier fórmula fija probada.
- Llega al techo de lo posible con los candidatos que existen.
- Es barata y su propia puntuación es invariante.

**No:**
- **No** dice nada del recall en la QA real; eso queda fuera de alcance (decisión 3).
- **No** autoriza integrar nada.
- Los mundos sintéticos son más limpios que el lenguaje real. Una AUC de 0,999 aquí no significa 0,999
  con recuerdos reales.

**El límite real está en el nacimiento:**
- el techo de P@5 es de 0,42–0,56, porque faltan entre el 40 % y el 45 % de los pares del mismo
  subtema y sobran sinapsis ruidosas;
- además, el nacimiento depende del orden de guardado.

Eso solo se arregla si alguien decide **qué nace**, es decir, las fases F2–F4 de NS-1, que siguen sin
autorización.

## 7. Archivos

- `mundo.py`: generadores v1 y v2.
- `construir.py`: el camino de `aprender` con el motor real; solo escribe en `/tmp`.
- `extraer.py`: construye todas las variantes y extrae a JSON, un proceso por mundo.
- `neurona.py`: agujas, `Referencia`, `Semantica` (PPMI + SVD) y la red con calibración isotónica.
- `analizar.py`: piso, invariancia, entrenamiento, evaluación y criterios (`main` = v1, `main_v2`).
- `diagnostico_palabras_nuevas.py`: el diagnóstico de §5.
- `resultados/resultados.json` y `resultados/resultados_v2.json`: todas las cifras.
- `resultados/neurona_ns1_pesos.npz` y `resultados/neurona_ns1_v2_pesos.npz`: pesos entrenados, solo
  con datos sintéticos.

**Reproducir** (desde la raíz del repo; ~35 minutos por versión):

```
PYTHONHASHSEED=1 HOME=/tmp/exp16/home python ".../extraer.py" /tmp/exp16          # v1
PYTHONHASHSEED=1 HOME=/tmp/exp16/home python ".../extraer.py" /tmp/exp16 v2       # v2
PYTHONHASHSEED=1 python ".../analizar.py" /tmp/exp16 ; python ".../analizar.py" /tmp/exp16 v2
```
