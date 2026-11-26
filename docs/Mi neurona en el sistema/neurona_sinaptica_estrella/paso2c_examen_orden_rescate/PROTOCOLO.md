# Paso 2c: examen de orden (entrenamiento) + examen de rescate (validación), protocolo fijado ANTES de medir (2026-11-26)

Viene del Paso 2b (`../paso2b_examen_rescate_pud/RESULTADOS.md`, propuesta §7) y de H1 (`../h1_nacimiento_cjk/`), ya
aprobado. Pedido del usuario y su asesor: avanzar con criterios fijados antes, en el laboratorio, **sin tocar el motor**,
midiendo el sueño **tal cual** y **una variante de control sin la inhibición lateral** (H2), para saber si los dos
exámenes ya dan volumen, precisión y limpieza en es, en, zh y ja, y fijar los requisitos del ciclo de H2.
**No entrena ninguna neurona.**

## 1. Mundo (igual que el Paso 2b, con el motor de `faa4299`, que ya incluye H1)
- UD PUD es/en/zh/ja (CC BY-SA 3.0), recuerdo = frase, nombre = id de frase, sin dimensiones ni sustantivos clave.
- **D** = documentos con `sha256(doc) % 5 != 0`; **I** = el resto, para la invariancia. DI = D igual + I después.
- Construcción con el motor real (`guardar` del exp. 16, sueño cada 50 y al final).
- **Relación real, solo para auditar:** dos frases del mismo documento.
- **Partición en 3 vías por documento de B** (§9.2 del plan): `sha256("2c|" + doc) % 5`: 0 → **guardia** (sellada para
  el futuro modelo), 1 → **validación**, resto → **estudio**. En este paso nadie se entrena: la partición solo se usa
  para contar si cada parte tendrá material.

## 2. Variantes
- **T (tal cual):** el motor sin cambios.
- **C (control):** en el proceso hijo que construye la base, `consolidation.ciclo_sueno_consolidacion` se sustituye
  por una copia de su propio código fuente en la que la condición `if energia_total > limite_energia:` (bloque «4.
  Inhibición Lateral») pasa a `if False:`. Todo lo demás del sueño queda igual (LTD, dormir por peso ≤ 0,05,
  escalado homeostático, co-ocurrencia, DMN). El cambio solo vive en ese proceso; el repositorio no se toca.

## 3. Pistas y búsqueda ciega (las del Paso 2b, sin cambios)
Unidades Unicode, sueños 1–3, niveles 3/2/1, filtro sin listas (cada unidad en ≤ 10 recuerdos del mundo D).
Búsqueda en la copia limpia A4 (sin sinapsis, asociaciones ni dimensiones emergentes):
`buscar_por_frase(pista, limite=6, profundidad="profundo", usar_inferencia=False, context_window=0,
ignore_peso_sinaptico=True)`. **Piso** = la lista completa de `obtener_asociaciones_enriquecidas` del motor real
(orden a mano del canal 2), sobre una copia del grafo.

## 4. Los dos exámenes
- **Examen de rescate (validación):** igual que el Paso 2b. Caso = B fuera del top-5 ciego y un A del top-5 con B en
  su lista del canal 2 (el primer A).
- **Examen de orden (entrenamiento), nuevo:** toda pista de B y todo A ≠ B del top-5 ciego con B en su lista del
  canal 2, **con 2 o más vecinos** (si no, no hay nada que ordenar), dan una pregunta «¿B queda arriba entre los
  vecinos de A?», tanto si la búsqueda directa encontró a B como si no. **Pregunta = par (A, B) único**: varias
  pistas que dan el mismo par cuentan una sola vez (no se infla el volumen).
- **Puesto relativo a D:** el puesto de B contando solo los vecinos de A que están en D. Es el que se usa para la
  invariancia: un recuerdo nuevo de I puede, con todo derecho, ser vecino de A; lo que no debe cambiar es el orden
  entre los recuerdos que ya estaban.

## 5. Puertas (cada una en los 4 idiomas a la vez; se evalúan por separado en T y en C)
Comunes:
| id | qué | umbral |
|---|---|---|
| C2 | Invariancia de la búsqueda (NORMA MÁXIMA): pistas cuyas unidades no aparecen en ningún I, top-5 idéntico en D y DI | ≥ 98 % |
| C6 | Limpieza y reproducibilidad (P6 del 2b): segundo repaso idéntico, sha256 sin cambio, copia ciega vacía, la consulta de vecinos no escribe | todo sí |

Examen de orden:
| id | qué | umbral |
|---|---|---|
| O1 | Volumen | estudio ≥ 300 preguntas, ≥ 150 B y ≥ 100 A distintos; validación ≥ 75 y guardia ≥ 75 preguntas |
| O2 | Invariancia de la respuesta: preguntas de pistas elegibles para C2 en D, presentes en DI con el mismo puesto relativo a D | ≥ 98 % (y las que solo aparecen en DI ≤ 2 %) |
| O3 | Hubs | ningún A con más del 10 % de las preguntas; los 3 A más frecuentes ≤ 25 % |
| O4 | Margen para aprender | el piso NO pone a B primero en ≥ 20 % de las preguntas |
| O5 | Validez (precisión) | (a) B es del mismo documento que A más a menudo que un vecino cualquiera de la lista de A: diferencia media > 0 con el límite inferior del IC 95 % bootstrap por A (2000 remuestreos, semilla 2026) > 0; (b) MRR oráculo > MRR piso > MRR anti-oráculo |

Examen de rescate:
| id | qué | umbral |
|---|---|---|
| R1 | Volumen para validar | ≥ 30 casos y ≥ 20 B distintos |
| R2 | Invariancia de la respuesta (casos de pistas elegibles, mismo A y mismo puesto relativo a D) | ≥ 98 % de los casos comunes, con ≥ 1 caso común |
| R3 | Hubs | como O3 |
| R4 | Margen | como O4 |
| R5 | Validez | como P5 del 2b: fracción del mismo documento en los casos > en las aristas del grafo, y oráculo > piso > anti-oráculo |

## 6. Lectura fijada antes
- **Orden válido en una variante** = C2, C6 y O1–O5 en verde en los 4 idiomas: el examen de orden sirve para
  entrenar en esa variante. **Rescate válido** = C2, C6 y R1–R5 en verde.
- **T falla y C pasa** en C2/O2/R2: la inhibición lateral es la causa de la falta de invariancia, y el ciclo de H2
  hereda como requisito pasar esas mismas puertas con el motor real.
- **Ambas fallan C2:** hay otra fuente de variación (p. ej. estadísticas del corpus en el buscador); se diagnostica
  aparte, sin cambiar umbrales.
- **Falla O5 o R5:** el examen premia coincidencias de superficie; no se entrena con él.
- Ningún umbral se cambia después de ver los datos. La prueba en seco con pocas frases solo comprueba que el
  programa corre; sus cifras no se miran para decidir nada.
