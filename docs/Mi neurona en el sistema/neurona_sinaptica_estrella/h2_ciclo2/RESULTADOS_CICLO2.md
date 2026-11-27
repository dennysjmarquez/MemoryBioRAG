# Ciclo 2 de H2/4b: resultados del laboratorio sintético

> **Qué es esto.** Un diagnóstico en un laboratorio sintético, **no una validación con datos reales**. Se ejecuta el
> protocolo aprobado (`h2_propuesta/PROPUESTA_PROTOCOLO_CICLO2.md`, rev. 2, más el ajuste de control de R-E2) y se
> informa qué pasó. **No se cambió el motor:** `core/` y `tests/` están igual que en `d7bc5dc`. Las variantes de H2 y
> 4b existen solo dentro del proceso hijo del laboratorio, sobre una copia del código del sueño.
> Sin DB viva, snapshots, QA oficial, UD PUD ni datos privados. K9 (la suite completa) queda para el futuro, con
> autorización aparte. E3 sigue abierta.

## 0. En una frase

**Ningún brazo cumple todos los criterios.** H2-local + 4b-propio **no** consigue lo que la propuesta esperaba:

- no cumple K1, porque una arista accidental basta para que I entre en la vecindad de D (verificado);
- no cumple K6, que por construcción no puede cumplir (duerme por vecindad, no por peso propio);
- no cumple K4/K5″: al dormir cerca del 60–65 % de D se pierden aristas buenas.

−H2 −4b sigue siendo el único brazo con el estado de D invariante (K1, K3 y K8). Paga con más aristas accidentales
(K4/K5) y con un sueño más caro en el reloj comprimido (K7′). **La Neurona 1 no toca el estado, pero sí multiplica el
residual del top-k** (con −H2 −4b: 32 frente a 6 a 800, y 44 frente a 8 a 2400).

## 1. Qué se ejecutó

| elemento | valor |
|---|---|
| script | `laboratorio_ciclo2.py` (reutiliza `h2_medicion/laboratorio_h2.py` y `mundo_sintetico.py`) |
| resumen | `resumen_ciclo2.py` → `resultados/tablas.md` (todas las tablas) y `resultados/resumen.json` |
| brazos | **T** (hoy), **−H2 −4b**, **H2loc** (H2-local + 4b de hoy), **4bp** (H2 de hoy + 4b-propio), **H2loc+4bp** |
| configuraciones | **real** (Neurona 1 activa) y **ctl** (`BIORAG_NEURONA=0` durante toda la corrida); PPMI 0,15 en las dos |
| mundos | semillas 7, 11 y 23 · \|D\| = 800 y 2400 (mundos de 1000 y 3000) · reloj comprimido y diario · D, D∪I0 (sin relación) y D∪I1 (con puentes) |
| corte del buscador | fijado tras D: el motor se cierra y se reabre justo después de la fase D, en los tres mundos |
| K8 | desde DB vacía, 80 sesiones mezcladas de 5 (320 D + 80 I0), reloj diario, 3 semillas por brazo |
| novedades del §4 | consultas con la entidad puente (M3′); **sinónimos sintéticos** en el 35 % de los recuerdos (ver §1.1); C-medida (aristas por tipo × verdad) |
| registro de la Neurona 1 | por mundo, en solo lectura: campeón sí/no, ascensos, reinicios, huella |
| duración | 17 482 s (≈ 4 h 51 min): 24 configuraciones × 15 mundos + 2 K8 + controles |
| controles | construcción determinista (dos construcciones dan el mismo sha de tablas) ✔ · el orden de las consultas no cambia el top-k ✔ |

### 1.1 Decisiones de implementación (para revisar)

- **H2-local**, tal como lo define §3.1:
  - para cada recuerdo activo r con al menos un vecino activo, si la energía de N(r) ∪ {r} supera
    0,8 · |N(r) ∪ {r}|, se duerme el más débil **no inmune** de esa vecindad (desempate: acceso más antiguo y después
    el nombre);
  - todas las decisiones se toman sobre la foto previa y se aplican juntas;
  - el efecto sobre el dormido es el mismo que el de H2 de hoy (estado `dormido`, peso × 0,9 con piso 0,05).
- **4b-propio**, tal como lo define §3.2: cada activo no inmune con importancia > 0,70 se multiplica por 0,98.
- **Sinónimos sintéticos**, sin listas de ningún idioma:
  - el sinónimo es una de las 2 primeras palabras inventadas del vocabulario del propio tema;
  - en 1 de cada 10 casos es de otro tema de D con la misma escritura. Es ruido a propósito, para que existan
    sinónimos accidentales;
  - es determinista por recuerdo: el mismo recuerdo lleva el mismo sinónimo en los tres mundos;
  - con esto nacen `co_semantica` (247 aristas a 800 y 615 a 2400, todas de tema salvo 1–24) y `sinonimo_explicito`.
- **Consecuencia que hay que tener presente:** al haber sinónimos de ruido, **I0 ya no está totalmente aislado de D**.
  En s7/800 hay 2 aristas D–I0, las dos `sinonimo_explicito` de ruido. En v2 no había ninguna.
- **El orden en K2′ se compara como fracción** de las consultas con lista en los dos mundos. Cuando T no tiene ninguna
  (porque H2 durmió todo D), el orden **no es comparable** y así se marca; no cuenta como fallo ni como acierto.
- **M3′ dentro de K2′:** las inserciones de I1 accidentales o ajenas en las consultas puente se suman a los falsos
  positivos de M3. Los puentes legítimos se informan, pero no son condición.

## 2. Veredictos

Leyenda: ✓ cumplido · v cumplido pero **vacuo** (no había nada que pudiera fallar) · n no cumplido · r referencia
(= T). Orden de cada celda: K1 · K2′ · K3 · K4 · K5″ · K6. Los veredictos de «real» y «ctl» coinciden en todos los
bloques salvo uno: 800 diario, −H2 −4b, K2′ (n en real, ✓ en ctl). Esa diferencia es el efecto de la neurona sobre el
orden.

| bloque (real) | T | −H2 −4b | H2loc | 4bp | H2loc+4bp |
|---|---|---|---|---|---|
| 800 comprimido | n r n r r n | ✓ n ✓ n n v | n ✓ ✓ n n n | n ✓ n ✓ ✓ n | n ✓ ✓ n n n |
| 800 diario | ✓ r ✓ r r n | ✓ n ✓ n n ✓ | n n ✓ n n n | ✓ n ✓ n n n | n n ✓ n n n |
| 2400 comprimido | n r n r r n | ✓ n ✓ n n v | n n n n n n | n ✓ n ✓ ✓ n | n n n n n n |
| 2400 diario | v r v r r n | v ✓ v n ✓ ✓ | n ✓ v n n n | v ✓ v n n n | n ✓ v n n n |

Los K2′ ✓ de H2loc, 4bp y H2loc+4bp en comprimido llevan la nota «orden no comparable en 6 de 6 mundos: T sin
listas», porque T no deja ningún recuerdo de D visible.

| final (real y ctl iguales) | T | −H2 −4b | H2loc | 4bp | H2loc+4bp |
|---|---|---|---|---|---|
| K7′ comprimido | n | n | n | n | n |
| K7′ diario | ✓ | n | n | n | n |
| K8 | n | ✓ | n | n | ✓ |
| K9 | futuro | futuro | futuro | futuro | futuro |

K7′ exige K1–K5 en los dos tamaños y un costo de ≤ 1,2 × T por sueño. Ningún brazo distinto de T lo cumple, porque
ninguno cumple K1–K5 en los dos tamaños.

## 3. Hallazgos

### 3.1 H2-local no aísla D de I: basta una arista accidental [verificado]

- **Δestado de D en D∪I0, con H2loc o H2loc+4bp** (semillas 7 / 11 / 23):
  - 800 comprimido: 2 / 0 / 3; 800 diario: 1 / 0 / 1;
  - 2400 comprimido: 5 / 2 / 3 (importancia 5 / 2 / 9); 2400 diario: 0 / 0 / 0 (importancia 0 / 0 / 2).
- **Verificación en s7 / 800 / comprimido, configuración ctl**, reconstruyendo D y D∪I0:
  - hay exactamente **2 aristas D–I0**, las dos `sinonimo_explicito` (los sinónimos de ruido);
  - los 2 recuerdos de D que cambian (`x0700504` y `x0700720`, de activo a dormido) son **justo los extremos de D de
    esas dos aristas**.
  - H2-local hace lo que dice su definición: si un vecino nuevo entra en la vecindad, la vecindad compite.
- **Lectura [D]:** la idea «un I sin aristas hacia D no cambia nada en D» es cierta. Pero en un sistema que crea
  aristas automáticas, un I sin relación de significado puede tener aristas accidentales hacia D, y entonces H2-local
  ya no es invariante. **Sin los sinónimos de ruido, en s7/800 H2-local probablemente habría cumplido K1** (no medido).
  Para las otras semillas y para 2400 se supone el mismo mecanismo, pero no se verificó uno por uno.

### 3.2 H2-local duerme casi tanto como H2 global

- **Recuerdos de D que siguen activos al final:**

  | bloque | H2loc+4bp | −H2 −4b |
  |---|---|---|
  | 800 comprimido | 299 / 288 / 332 de 800 | 800 |
  | 800 diario | 71–77 | 200 |
  | 2400 comprimido | 836–916 de 2400 | 2400 |

- Es el riesgo que el §3.1 de la propuesta ya anticipaba: en sueños seguidos casi todas las importancias rondan 1,0, la
  condición se cumple en casi todas las vecindades y cada ciclo duerme a un miembro de cada tema.
- **Consecuencia en K4/K5″:**
  - **precisión:** sube (por ejemplo, 0,910 frente a 0,859 de T, en s7/800 comprimido);
  - **aristas buenas:** bajan los pares de tema y los de puente (puente 4 frente a 6 y 8 frente a 28 a 800 comprimido;
    2 frente a 10 en s23/2400);
  - **en diario:** el número de pares buenos visibles cae a menos de la mitad (371 frente a 950, 403 frente a 1017);
  - **recall del recuerdo de origen:** en diario baja (0,044–0,058 frente a 0,121–0,156 de T).
- **K6 no puede cumplirse con H2-local, por definición.** K6 exige que todo recuerdo dormido lo esté por su propio
  peso, y H2-local duerme por la vecindad. La línea «H2-local + 4b-propio cumple K1, K3, K6 y K8» del resultado
  esperado (§4 de la propuesta, marcada [D]) **era una deducción equivocada en K6**. Lo informo como no cumplido.

### 3.3 4b-propio, solo, no cambia nada mientras H2 global esté encendido

- **En comprimido**, 4bp sale idéntico a T en estado, top-k y aristas. H2 global duerme todo D antes de que 4b importe.
- **En diario**, 4b-propio sí actúa:
  - escala 2313–2863 veces a 800 y 7113–8863 a 2400;
  - baja un poco los pares de tema (1283 frente a 1328) y los pares buenos visibles (836 frente a 950);
  - sube las difusas de M3 (17 frente a 7 en s7/800).
  - Falla K4, K5″ y K2′ (recall del origen 0,108 frente a 0,152).
- **K8 no se cumple:** Δimportancia de D = 1 en las 3 semillas. Mejora frente a T (16), pero no llega a 0.
- **Lectura [D]:** 4b-propio elimina los cruces de la media global, como se buscaba. Pero el decaimiento extra que
  añade a los recuerdos nuevos les quita visibilidad.

### 3.4 −H2 −4b: invariante en estado; las aristas accidentales siguen siendo su costo

- **Cumple K1, K3 y K8 en todos los bloques**: estado de D idéntico en D y D∪I0 en 12 de 12 mundos.
- **Falla K4:**

  | bloque | aristas accidentales + ajenas (−H2 −4b frente a T) |
  |---|---|
  | 800 comprimido | 240 / 555 / 427 frente a 211 / 349 / 183 |
  | 2400 comprimido | 1238 / 2481 / 1256 frente a 651 / 995 / 595 |

  Sobre todo son `pmi_hebbiano`: 2437 accidentales a 2400 comprimido (suma de semillas), frente a 1221 en T.
- **Falla K5″ por la fracción, no por el número:** los pares buenos visibles son 2262 frente a 494 a 800 comprimido.
- **Costo por sueño (K7′):** 1,36–1,42 × T en ctl/800 comprimido y 2,0–2,1 × T en real. Más recuerdos activos
  implican una neurona más cara en cada sueño.
- **Coincide con la medición anterior** (`h2_medicion/RESULTADOS.md`): el problema de −H2 −4b no es la invariancia,
  sino la calidad de las aristas. Ese trabajo le toca a la neurona asociativa del Paso 3 (ordenar el canal 2), no a
  H2/4b.

### 3.5 La Neurona 1: no toca el estado; sí el top-k [verificado]

- **Estado idéntico entre real y ctl** en todos los bloques, brazos y semillas: K4, K5″, K6, activos y Δestado.
  0 diferencias. La neurona solo reordena resultados.
- **Top-5 cambiado entre D y D∪I0** (suma de las 3 semillas; entre paréntesis, el residual no atribuido):

  | bloque | T real / ctl | −H2 −4b real / ctl | H2loc+4bp real / ctl |
  |---|---|---|---|
  | 800 comprimido | 133 (11) / 133 (6) | **32 (32) / 6 (6)** | 8 (5) / 8 (5) |
  | 800 diario | 25 (25) / 7 (7) | 15 (15) / 7 (7) | 8 (5) / 8 (5) |
  | 2400 comprimido | 38 (4) / 38 (3) | **44 (44) / 8 (8)** | 30 (7) / 12 (4) |
  | 2400 diario | 5 (5) / 5 (5) | 5 (5) / 5 (5) | 3 (3) / 3 (3) |

- **Campeón por mundo:** aparece en los mundos con muchos activos (−H2 −4b, y T en diario).
  - **Cuando aparece, aparece en D, D∪I0 y D∪I1 a la vez.** Pero con distinto número de ascensos según el mundo, por
    ejemplo, −H2 −4b, 800 comprimido, s7: 3 / 3 / 4.
  - Es decir, un campeón aprendido de un corpus distinto **reordena distinto**. Es el mismo mecanismo de R-E2, ahora
    en todos los mundos.
  - Con la neurona apagada, el residual de −H2 −4b baja a 6 / 7 / 8 / 5. Lo que queda es BM25 en el borde del corte
    (R-E2 §7).
- **Lección para la Neurona 2** (ya registrada como hallazgo abierto): todo lo que se aprenda del corpus rompe F(D, q)
  = F(D ∪ I, q) en el top-k, aunque no toque el estado.

### 3.6 Sinónimos y C-medida

- Las aristas `co_semantica` son casi todas de tema: 247 de 250 en T a 800 comprimido.
- `sinonimo_explicito` hereda el ruido sembrado (10 de tema y 23 accidentales a 800 comprimido en T). Es lo esperable
  con un 10 % de sinónimos de otro tema que coinciden con los de otros recuerdos.
- **`pmi_hebbiano` sigue siendo la fuente principal de accidentales en todos los brazos:** 390 / 609 / 128 en T /
  −H2 −4b / H2loc a 800 comprimido.
- Detalle completo por tipo × verdad y por sueño: tablas «aristas por tipo» de `resultados/tablas.md` y
  `C_medida.por_tipo_antes_de_cada_sueno_DI1` en cada JSON.

## 4. Qué está verificado y qué es deducción

| afirmación | estado |
|---|---|
| Ningún brazo cumple K1–K8 (K9 futuro) | verificado (tablas) |
| H2-local cambia D por las aristas D–I0 accidentales | verificado en s7/800/comprimido; resto [D] |
| H2-local duerme cerca del 60–65 % de D | verificado (activos al final) |
| K6 es incompatible con H2-local por definición | lógico (definición de K6) |
| La Neurona 1 no cambia el estado y sí multiplica el residual | verificado (real frente a ctl) |
| 4b-propio no importa con H2 global encendido (comprimido) | verificado (4bp = T) |
| Sin sinónimos de ruido, H2-local cumpliría K1 | **[D], no medido** |

## 5. Qué deja esto para decidir (lo decide Dennys)

1. **H2-local, tal como está definido, no sirve como sustituto invariante de H2.** Las opciones razonables son:
   - **(a)** quedarse con −H2 −4b como estado y llevar la calidad de las aristas al Paso 3 (neurona asociativa);
   - **(b)** una variante de H2-local que cuente solo las aristas «del agente» o de tipos explícitos. Rompería el
     molde de no tratar ningún tipo como especial y requiere un ciclo propio.
   - Recomiendo **(a)**.
2. **4b-propio** no aporta frente a −4b en ningún bloque; su decaimiento extra baja la visibilidad.
3. **K7′:** el costo de −H2 −4b en comprimido (1,4–2,1 × T) se debe sobre todo a que hay más recuerdos activos. El
   costo por recuerdo activo y sueño es **menor** que en T (s7, ctl: 0,00037 s frente a 0,00072 s a 800 comprimido,
   y 0,00029 s frente a 0,00074 s a 2400 comprimido; columna `K7p` de cada JSON). Hay que decidir si el umbral se aplica
   por sueño (como está aprobado) o por recuerdo activo.
4. **Neurona 1:** el residual del top-k es suyo. Sigue como hallazgo abierto para un ciclo aparte; la Neurona 2 no
   debe aprender del corpus nada que entre en el ranking.

Nada de esto se implementó en el motor. El siguiente paso, si se aprueba, es el diseño de la Neurona 2.
