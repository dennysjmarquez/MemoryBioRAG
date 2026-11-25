# Experimento 18 — Resultados de E1 (protocolo v3)

**Fecha:** 2026-11-25.
**Protocolo:** `PROTOCOLO_V3.md` §3, con las enmiendas A1–A3 de §0, subido antes de medir (`de4c6d2` y `6dd66eb`).
**Datos:** `resultados/e1.json`. **Código:** `e1_mundo.py`, `e1_repaso.py` y `e1_medir.py`.
**Dónde:** todo en `/tmp`, con el motor real. No se tocó el motor del repo ni ninguna base real.
**Tiempo:** 155 s para los 4 idiomas.

Etiquetas: **[V]** verificado con una medición o leyendo el código; **[D]** deducido, es una interpretación.

## 1. Para quien llega sin contexto

- Las sinapsis automáticas del motor aciertan poco: un 11–18 % en el experimento 16. La idea es que, **durante el
  sueño**, el sistema se examine a sí mismo y decida qué enlaces valen la pena.
- Para que ese examen no se engañe, tiene que mirar los recuerdos **sin mirar los enlaces que está juzgando**. Si
  no, refuerza lo que ya cree: un bucle.
- E1 **no mide si la idea funciona.** Mide si las señales del examen son **limpias**:
  - no ven las sinapsis (bucle);
  - no cambian cuando se añaden recuerdos ajenos (invariancia);
  - dan siempre lo mismo (reproducibilidad);
  - no estropean nada (regresión).

**Las tres señales:**
- **R (resonancia):** en cuántos de 3 sueños B sale al buscar con una pista de A, o al revés.
- **U (autoexamen sináptico):** cuántas veces el enlace A–B «rescata» a B, es decir, la búsqueda directa de B
  falla pero A sí aparece.
- **S (estructura):** dimensiones y sustantivos clave compartidos.

## 2. Criterios fijados antes

| # | Criterio | es | en | zh | ja | ¿Pasa? |
|---|---|---|---|---|---|---|
| C1.1 | Invariancia D frente a DI, ≥ 98 % (271/276) | 275 | **270** | 276 | 276 | **NO** (en: 97,8 %) |
| C1.2 | Peso ×3 en 20 sinapsis → 276/276 | 276 | 276 | 276 | 276 | sí |
| C1.2b | 20 sinapsis falsas + sueño, frente a solo sueño, ≥ 98 % | 276 | 276 | 276 | 276 | sí |
| C1.3 | Dos repasos de la misma base, idénticos | sí | sí | sí | sí | sí |
| C1.4 | sha256 de la base sin cambios y 5 búsquedas normales iguales | sí | sí | sí | sí | sí |
| C1.5 | 0 sinapsis en la copia al terminar | 0 | 0 | 0 | 0 | sí |

**[V] E1 NO PASA,** por un solo par: el inglés da 270, y el umbral pide 271. No se ajusta nada: la regla se fijó
antes de medir.

## 3. Por qué falla C1.1 en inglés [V]

En inglés, 8 de las 132 búsquedas del repaso dan un top distinto entre D y DI:
- **6 son la pista genérica «plan».** `cocina_0` y `jardin_1` intercambian los puestos 5 y 6 cuando entra I. El
  BM25 depende del corpus completo, así que el empate se rompe al revés.
- **1 es una pista hecha de palabras vacías** («end of winter and»), que con I trae 2 irrelevantes.
- **1 es «morning with its siren»,** donde un resultado débil desaparece con I.

Es exactamente la causa que la lectura fijada antes preveía para un fallo de C1.1: **la invariancia del canal 1,
no la señal.** Como control, D construida dos veces da 276/276: la construcción no mete ruido.

Según esa misma regla, **E2 hereda esta tolerancia como límite conocido.** E3 sigue bloqueada, porque E1 no pasó
en sentido estricto.

## 4. Lo que funcionó [V]

- **El bucle está cerrado.**
  - Multiplicar pesos, meter 20 sinapsis falsas y dormir no cambia ni un par de R ni de U (C1.2 y C1.2b: 276/276
    en los 4 idiomas).
  - La copia del repaso empieza y termina con 0 sinapsis (C1.5).
  - Es la primera vez que hay un **repaso ciego a las sinapsis** que se puede verificar.
- **No estropea nada:** la base original sigue con el mismo sha256 y las búsquedas normales dan lo mismo (C1.4).
- **Es reproducible** (C1.3).

## 5. Lo que encontró E1 que no buscaba

### 5.1 El motor no ve las palabras de 2 caracteres en chino ni en japonés [V]

- En la base china, `buscar_por_frase("番茄")` devuelve **0 resultados**, aunque 2 recuerdos tienen «番茄» como
  sustantivo clave y en el contenido. Lo mismo pasa con «消防» y «足球». «数据库», de 3 caracteres, sí funciona.
- **Causa** (leyendo `schema.py`):
  - el índice principal es FTS5 `trigram`, que necesita al menos 3 caracteres;
  - el índice `unicode61` trata una corrida CJK entera como una sola «palabra».
- La mayoría de las palabras chinas tienen 2 caracteres.
- **En el repaso,** las pistas de sustantivos clave en chino salieron vacías 54 de 60 veces.
- **[D]** Esto afecta también a **las búsquedas reales** de cualquier usuario en chino o japonés, no solo al
  experimento. Es materia del ciclo aparte de los «ojos Unicode», ya aprobado como ciclo propio. No se tocó.

### 5.2 Hay que repasar también los recuerdos dormidos (enmienda A1) [V]

- Tras 2 sueños, 9 de 24 recuerdos quedan en estado `dormido`.
- Con la búsqueda por defecto (`activos`), solo aparecen por un atajo que depende de `ultimo_acceso`, un campo que
  reescriben las búsquedas anteriores.
- Como diagnóstico, con `activos` X se encuentra a sí mismo 81 de 132 veces en es/en; con `profundo`, 129 de 132.

## 6. Valor de las señales (C1.6, informativo, sin umbral)

AUC = probabilidad de que un par del mismo tema puntúe más alto que un par sin relación. 0,5 es azar.

| Señal | es | en | zh | ja |
|---|---|---|---|---|
| **R** | 0,833 | 0,782 | 0,521 | 0,573 |
| **U** | 0,498 | 0,490 | 0,500 | 0,500 |
| **S** | 0,822 | 0,822 | 0,822 | 0,822 |
| Pares del mismo tema con R > 0 | 75 % | 62,5 % | 4,2 % | 16,7 % |
| Pares del mismo tema con U > 0 | 0 % | 0 % | 0 % | 0 % |

**Análisis posterior (no fijado antes; solo orienta):**

| | es | en | zh | ja |
|---|---|---|---|---|
| R solo con pistas de contenido (c1) | 0,631 | 0,617 | 0,500 | 0,500 |
| R solo con sustantivos clave (c2) | 0,799 | 0,747 | 0,521 | 0,573 |
| **S + R/3** (¿R aporta algo sobre S?) | **0,888** | **0,868** | 0,822 | 0,824 |

**Lectura [D]:**
- **U, el autoexamen sináptico, no da señal en este mundo.**
  - En es/en, la búsqueda directa casi siempre encuentra al propio recuerdo (129/132), así que no hay nada que
    rescatar.
  - En zh/ja, cuando falla, devuelve vacío, y vacío no rescata a nadie.
  - U solo puede valer donde la búsqueda falla **a medias**. Eso no está demostrado. Hoy U no es una entrada
    útil.
- **R aporta sobre la estructura en es/en** (0,822 → 0,868–0,888), **pero no es agnóstica al idioma en la
  práctica.** Hereda la ceguera del canal 1 para el chino y el japonés. Con el requisito de que el sistema sea
  multilingüe, R no puede ser una entrada general mientras no se arregle el 5.1.
- **S es la única señal estable entre idiomas,** porque es estructural, no textual. Esto coincide con E0: «la
  relación no está en la superficie del texto».

## 7. Qué queda y qué no

- **Sigue en pie:**
  - el repaso ciego a las sinapsis (método verificado);
  - S como base del piso;
  - R como complemento solo donde el canal 1 ve el texto.
- **Queda en duda:** U como entrada.
- **Bloqueado:** E3, hasta que pasen E1 y E2. No se tocó el motor.

## 8. ⚠️ Corrección del mismo día: el bucle no estaba cerrado del todo

**Qué dije y qué era cierto.** En §4 escribí «el bucle está cerrado». Era cierto **solo para las vías que se
probaron**: las tablas de sinapsis, los pesos y las sinapsis falsas con sueño. Una auditoría posterior encontró
dos vías más [V]:
- **`largo_plazo.asociaciones`:** copia en CSV de los vecinos. La búsqueda suma `0.02·min(1, asoc/20)`. La copia
  limpia no la vaciaba. En este mundo estaba vacía, así que no influyó.
- **Dimensiones `auto_generada = 1`:** nacen de comunidades del grafo de sinapsis y se guardan en el eje
  `dominio`.
  - C1.2b no las ejercitó: en ninguna base apareció una dimensión emergente.
  - Inyectando una a mano, el repaso cambió 6 de 276 pares en es y 5 en en.

**Arreglo:** enmienda A4 y criterio C1.2c (`PROTOCOLO_V3.md` §0), subidos antes de volver a medir (`5deb54b`).
Ahora la copia limpia también vacía `asociaciones` y quita las dimensiones emergentes.

**Resultado** (`resultados/e1_a4.json`):

| | es | en | zh | ja |
|---|---|---|---|---|
| C1.2c (dimensión emergente + `asociaciones` falsas) | 276 | 276 | 276 | 276 |
| Restos de `asociaciones` o emergentes en la copia | 0 | 0 | 0 | 0 |
| C1.1 (sin cambios) | 275 | 270 | 276 | 276 |

- Todas las demás cifras salen idénticas a las de §2 y §6.
- **El veredicto no cambia: E1 NO PASA,** por C1.1 en inglés.
- **Reproducibilidad entre sesiones:** al repetir E1 tras un reinicio del entorno, `e1.json` salió idéntico,
  salvo el campo de segundos.
- **Para el motor [D]:** cualquier S que lea la base tiene que excluir `auto_generada = 1`.
