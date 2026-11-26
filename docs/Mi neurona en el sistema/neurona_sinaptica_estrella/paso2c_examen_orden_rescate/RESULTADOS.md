# Paso 2c: examen de orden + examen de rescate, sueño tal cual (T) y control sin inhibición lateral (C): resultados (2026-11-26)

Protocolo con umbrales fijados antes de medir: `PROTOCOLO.md` (commit `2890675`, anterior a la corrida).
Script: `examen_orden_rescate.py` (23 min con 2 CPU). Datos: `resultados/examen_2c.json` y
`resultados/preguntas_orden.json.gz`. Diagnóstico posterior, sin puerta: `diag_invariancia.py` →
`resultados/diagnostico_invariancia.json`. Motor: `faa4299` (con H1), sin tocar.
[V] = medido. [D] = deducido o propuesto.

## 1. Veredicto
**Ningún examen queda validado en ninguna variante.** Ni el examen de orden ni el de rescate pasan todas sus puertas
en T ni en C. Aun así, la corrida responde las dos preguntas del asesor:
1. **La inhibición lateral (H2) es la única causa real de la falta de invariancia** [V]. Al apagarla, la búsqueda
   pasa la NORMA MÁXIMA en los 4 idiomas (99,0–100 %), una vez que se separan los recuerdos nuevos que el motor sí
   considera coincidencias (§4). Con H2 activa: 89–96 %.
2. **El examen de orden es bueno pero PUD es pequeño** [V]. En C pasa hubs (O3), margen (O4) y validez (O5) en los 4
   idiomas, con intervalos de confianza por encima de 0. Le falta volumen (O1) en todos: 62–270 preguntas de estudio,
   frente a las 300 exigidas. Confirma §9.0c del plan: hace falta un mundo de miles de recuerdos.

## 2. Puertas [V]
| puerta | T (tal cual) | C (sin inhibición lateral) |
|---|---|---|
| C2 invariancia de la búsqueda ≥ 98 % | ❌ es 85,6 · en 87,5 · zh 95,8 · ja 89,3 | ❌ es 89,3 · en 91,5 · **zh 99,95 · ja 100** |
| C6 limpieza y reproducibilidad | ✅ | ✅ |
| O1 volumen (estudio ≥ 300 / 150 B / 100 A; val. y guardia ≥ 75) | ❌ | ❌ |
| O2 invariancia de la respuesta ≥ 98 %, solo DI ≤ 2 % | ❌ 19–67 % | ❌ es 97,0 % · en 98,9 % pero 8 % solo en DI · **zh 100 · ja 100** |
| O3 hubs | ❌ (es: un A con el 25 %) | ✅ |
| O4 margen | ✅ | ✅ |
| O5 validez (precisión) | ❌ (es: oráculo = piso) | ✅ |
| R1 volumen rescate ≥ 30 casos / 20 B | ❌ 1–3 | ❌ 9–16 |
| R2 invariancia del rescate | ❌ (sin casos comunes) | ✅ |
| R3 hubs rescate | ❌ | ❌ (por muestra pequeña: 1 de 9 ya supera el 10 %) |
| R4 margen rescate | ❌ | ✅ |
| R5 validez rescate | ❌ | ❌ (zh: oráculo < piso con 9 casos) |

## 3. Cifras por idioma [V]
| | es T | es C | en T | en C | zh T | zh C | ja T | ja C |
|---|---|---|---|---|---|---|---|---|
| recuerdos de D dormidos (de 839) | 622 | **0** | 622 | **0** | 622 | **0** | 622 | **0** |
| D que cambian de estado al añadir I | 177 | 0 | 177 | 0 | 177 | 0 | 177 | 0 |
| sinapsis en D | 643 | 1838 | 679 | 2224 | 566 | 566 | 1152 | 1152 |
| preguntas de orden (total) | 8 | **112** | 23 | **156** | 86 | **368** | 71 | **386** |
| … de estudio / validación / guardia | 7/0/1 | 62/25/25 | 15/1/7 | 99/35/22 | 59/16/11 | 250/68/50 | 40/15/16 | 270/53/63 |
| B del mismo documento que A (orden) | 87,5 % | 44,6 % | 69,6 % | 53,2 % | 69,8 % | 65,5 % | 47,9 % | 51,8 % |
| … un vecino cualquiera de A | 65,6 % | 24,6 % | 38,6 % | 27,2 % | 56,5 % | 54,7 % | 35,8 % | 34,6 % |
| O5a diferencia [IC 95 %] | +0,22 [0,05; 0,46] | +0,20 [0,13; 0,28] | +0,31 [0,16; 0,47] | +0,26 [0,19; 0,32] | +0,13 [0,07; 0,20] | +0,11 [0,08; 0,14] | +0,12 [0,03; 0,21] | +0,17 [0,13; 0,21] |
| piso R@1 (orden) | 62,5 % | 40,2 % | 52,2 % | 39,1 % | 44,2 % | 42,7 % | 45,1 % | 40,4 % |
| MRR oráculo / piso / anti (orden) | 0,81/0,81/0,64 | 0,58/0,57/0,41 | 0,74/0,71/0,46 | 0,59/0,58/0,37 | 0,71/0,67/0,58 | 0,67/0,66/0,57 | 0,67/0,67/0,56 | 0,63/0,62/0,47 |
| casos de rescate | 1 | 12 | 3 | 16 | 2 | 9 | 2 | 15 |

Lectura: en C, la pista que lleva a A señala como B a un vecino del mismo documento entre 11 y 26 puntos más a menudo
que un vecino cualquiera de A. **El examen de orden contiene señal real, no solo superficie.** El piso pone a B
primero solo en un 39–43 % de las preguntas: hay margen para que una neurona aprenda.
[D] zh/ja tienen las mismas sinapsis en T y en C, y es/en casi triplican en C. Explicación probable, leída en el
código y no medida: en zh/ja casi todo nace en la co-ocurrencia del sueño, que no mira el estado; en es/en pesan
`auto_vincular` y `pmi_hebbiano`, que solo enlazan con recuerdos **activos**.

## 4. Diagnóstico posterior de la invariancia (sin puerta) [V]
Lo pide la lectura fijada en el protocolo para el caso «ambas variantes fallan C2». Clasificación de las pistas cuyo
top-5 cambia al añadir I:

| | fallos | entra un recuerdo de I | cambia el estado de un D | mismo conjunto, otro orden | un D por otro D | **orden relativo de D idéntico** |
|---|---|---|---|---|---|---|
| T es | 232 | 156 | 53 | 17 | 6 | 94,1 % |
| T en | 207 | 128 | 53 | 17 | 9 | 94,2 % |
| T zh | 175 | 0 | 112 | 59 | 4 | 95,8 % |
| T ja | 205 | 0 | 121 | 75 | 9 | 89,3 % |
| C es | 172 | 163 | 0 | 2 | 7 | **99,1 %** |
| C en | 142 | 130 | 0 | 2 | 10 | **99,0 %** |
| C zh | 2 | 1 | 0 | 0 | 1 | **99,98 %** |
| C ja | 0 | 0 | 0 | 0 | 0 | **100 %** |

- En es/en, casi todos los fallos de C son **un recuerdo de I que entra en el top-5**. El buscador es difuso (raíces
  y trigramas) y lo considera coincidencia aunque no contenga las unidades exactas de la pista. Eso no viola la
  NORMA MÁXIMA: la norma protege frente a recuerdos que **no** coinciden con la consulta. El fallo está en la
  definición de «elegible» del examen (unidades exactas), que es más estrecha que la del motor.
- Medida como **orden relativo de los recuerdos de D** (el top de DI sin los de I debe ser un prefijo del top de D),
  C pasa en los 4 idiomas y T no. La diferencia es justo H2: cambios de estado y reordenamientos que desaparecen
  al apagarla.
- **Corrección al Paso 2b** [V]: allí se escribió que el 100 % de los fallos de P2 tocaba un recuerdo que cambió de
  estado. El conteo trataba como «cambio de estado» a los recuerdos de I (que no existen en D). Corregido: en es/en,
  156 y 128 de esos fallos son recuerdos de I que entran; los cambios de estado reales de D explican 53 en cada uno.
  En zh/ja sí son H2 (estado o reorden), y desaparecen en C. La conclusión sobre H2 se mantiene, con la cifra
  correcta. La nota queda también en el RESULTADOS del 2b.
- O2 en C es/en: las 5 y 8 preguntas «solo en DI» son pares nuevos legítimos: un A de I, o un A de D que gana un
  vecino de I y llega a 2 vecinos. Las que faltan (2 y 1) son desplazamientos por un I que entra. Ninguna pregunta
  común cambia de puesto relativo (0 en los 4 idiomas).

## 5. Requisitos para el ciclo de H2 (derivados de C, para fijarlos antes de tocar el motor) [V]/[D]
Con el motor real y la inhibición lateral rediseñada, en este mismo mundo y con este mismo script:
1. **0 recuerdos de D cambian de estado** al añadir I sin uso (hoy 177). [V: C da 0]
2. **C2 como orden relativo de D ≥ 98 %** en los 4 idiomas (hoy 89–96 %; C da 99,0–100 %).
3. **O2: ninguna pregunta común cambia de puesto relativo** y las que faltan en DI ≤ 2 % (hoy faltan 2–35, hasta
   el 81 % en ja; C da 0–2).
4. **Sin pérdida del grafo:** sinapsis en es/en al menos como en C (1838 / 2224), y dormidos solo por su propio peso.
5. Las puertas del motor (pytest, QA completa, abismo, QA multilingüe) idénticas.
[D] Dirección de diseño, a decidir en el ciclo de H2 y con Dennys: que la decisión de dormir dependa solo del propio
recuerdo (su peso y su edad absolutos), no de su puesto frente a los demás. «El 20 % más débil» cambia cuando llegan
recuerdos nuevos; «peso ≤ umbral» no. Es la homeostasis por nodo ya aprobada como principio.

## 6. Qué propongo para el siguiente protocolo del examen [D] (se fija antes de medir, en su ciclo)
- Adoptar como invariancia de la búsqueda el **orden relativo de D** (§4), que es la forma correcta de la NORMA
  MÁXIMA cuando el buscador es difuso.
- Volumen: PUD da como mucho ~0,5 preguntas de estudio por recuerdo (zh/ja) y ~0,1–0,2 (es/en). Para 300 preguntas
  de estudio en es/en hacen falta del orden de 3000–5000 recuerdos por idioma: el mundo grande del paso 3 (§9.0c).
- El rescate seguirá siendo escaso (9–16 casos en 839 recuerdos): mantenerlo como validación, contando sus casos
  juntos en un mundo grande.

## 7. Reproducir
```
cd "docs/Mi neurona en el sistema/neurona_sinaptica_estrella/paso2c_examen_orden_rescate"
python examen_orden_rescate.py        # ~23 min, deja las bases en /tmp/paso2c
python diag_invariancia.py
```

## Nota de revisión (2026-11-26, tras la revisión del usuario y su asesor)
Este paso queda como **diagnóstico**: no autoriza cambios en H2, en 4b ni en el motor. Dos precisiones de redacción:
1. Donde dice «H2 es la única causa real de la falta de invariancia», debe leerse: **H2 explica la diferencia entre T
   y C**. El escalado global de importancia (4b, `consolidation.py` L577–588, que cambia `largo_plazo.peso_sinaptico`
   y no las aristas) estaba activo en las dos variantes y no se aisló.
2. El «orden relativo de D» **no es la invariancia completa**: admite que entren recuerdos de I, y aquí no se comprobó
   si los que entraban tenían que ver con la consulta o eran falsos positivos difusos. Las definiciones previas
   (invariancia estricta S1 = 0 cambios frente a I verdaderamente irrelevante; métricas agregadas M1, M2 y M3; texto
   C0/C1/C2 separado de la verdad tema / puente / accidental / ajeno) están en
   `../h2_propuesta/PROPUESTA_PROTOCOLO_H2.md` §5 (v2).
Además, el control casi triplica las aristas en es/en (643 → 1838 y 679 → 2224) **sin ganar aristas del mismo
documento** (114 → 115 y 143 → 138): apagar H2 sin más no es una solución (criterio K4 de la propuesta).
