# H2 y 4b: medición del protocolo v2 en el laboratorio sintético (2026-11-26). DIAGNÓSTICO, nada implementado

[V] = verificado en los JSON de `resultados/`. [D] = deducción, sin verificar.

## 0. Qué se autorizó y qué se respetó
- **Autorizado:** medir el protocolo v2 (`../h2_propuesta/PROPUESTA_PROTOCOLO_H2.md`, `c6da148`) **solo en un laboratorio
  sintético aislado**, con los brazos T, −H2, −4b y −H2 −4b, las semillas 7, 11 y 23 y los criterios del §8.
- **Respetado:**
  - los brazos y el registro existen solo en el proceso hijo, sobre una copia del código del sueño compilada en memoria;
  - el motor y los tests no se tocaron;
  - las bases se crearon desde cero en `/tmp` con el mundo de `mundo_sintetico.py`;
  - no se usó la DB viva, ni snapshots, ni datos privados, ni UD PUD, ni la QA oficial;
  - no se corrió la suite completa (K9 queda pendiente de autorización);
  - E3 sigue abierto y no se avanza a E4.
- **Corrida:** `python laboratorio_h2.py todo`, 9707 s con 2 CPU. Después, `reanalizar` y `resumen.py`.
  - Archivos: `resultados/config_s<semilla>_n<|D|>_<reloj>.json` (12), `controles_y_k8.json`, `resumen.json` y `tablas.md`.
  - `tablas.md` contiene todas las tablas, semilla por semilla.

## 1. Diseño, tal como se ejecutó
- **Mundo:** cuatro escrituras.
  - lat_a y lat_b: latinas con diacríticos y dos inventarios distintos.
  - han: ideogramas sin espacios.
  - jpn: kanji y kana sin espacios.
  - Cada escritura tiene palabras «función» aleatorias y frecuentes, vocabulario genérico con Zipf, temas de 1–5 recuerdos (más algunos de 8–12) y variantes morfológicas.
  - **Puentes declarados:** una entidad rara compartida por dos temas.
  - **Homógrafos y prefijos casuales:** relaciones accidentales.
  - La verdad (tema, puente, accidental, ajeno) la pone el generador; el motor no la ve.
- **Conjuntos añadidos:**
  - |D| = 800 o 2400, y |I0| = |I′| = |D|/4. Los mundos son de 1000 y de 3000 recuerdos.
  - **I0, «verdaderamente irrelevante»:** inventario de caracteres disjunto del de D en cada escritura, así que no comparte con D ni un carácter. Se comprobó que es C2 frente al 100 % de las consultas.
  - **I′:** comparte inventario y palabras función con D, y trae puentes, homógrafos y prefijos casuales hacia D.
- **Calendario:**
  - Se duerme cada 50 recuerdos y al final de cada lote, primero D y después I.
  - **El mundo D recorre el mismo calendario de sueños,** con los turnos de I vacíos. Así, la única diferencia entre D y D∪I es el contenido de I.
- **Reloj simulado y determinista** (`time.time` del hijo): +1 s por recuerdo y, antes de cada sueño, +60 s (comprimido) o +86 400 s (diario).
- **Consultas:** 480 por configuración. Para 240 recuerdos de D, 60 por escritura, se toman 2 y 3 palabras de su tema, sin palabras función.
  - Se ejecutan por el **camino normal del agente:** `buscar_por_frase(profundidad="activos")`, con la importancia, es decir, `recordar` sin `deep`.
  - **Cada consulta parte del mismo estado:** tras cada búsqueda se restaura la copia, porque las búsquedas escriben.
- **Canal 2:** `obtener_asociaciones_enriquecidas`, la lista completa y la visible (top 5).

### Controles [V]
| control | resultado |
|---|---|
| El registro por ciclo no cambia la base (sha256 por tabla, con y sin registro, en los 4 brazos) | idéntico en los 4 |
| El orden de las consultas no cambia el top-k (directo frente a inverso) | idéntico |
| Cada consulta partió del mismo estado (36 mundos × 4 brazos) | sí, en todos |
| I0 es C2 frente a todas las consultas; inserciones de I0 en el top-5 | sí; 0 en todas las configuraciones |

## 2. Hallazgos principales [V]
### 2.1 H2 depende del régimen de sueño, no del contenido
- **Comprimido (sueños seguidos, sin olvido):** H2 se dispara en 22 de 22 ciclos (mundo de 1000) y en 57 de 62 (3000).
  - Al añadir I0, que **no comparte ni un carácter con D**, H2 **duerme a todos los recuerdos de D que seguían activos:** 101 → 0 (1000) y 97 → 0 (3000).
  - El resultado es idéntico en las tres semillas, porque H2 solo mira conteos y el orden de llegada.
  - La búsqueda normal del agente encontraba el recuerdo de origen en el 7 / 6 / 9 % de las consultas; con I0 pasa al **0 %**.
  - En el mundo de 3000 hay 5 ciclos en que H2 se dispara **solo con I** (`h2_solo_con_I` = 57–61).
- **Diario:** H2 solo se dispara en los 5 primeros ciclos, con pocos recuerdos. Después manda el LTD por peso propio.
  - Añadir I0 no cambia nada en D: 0 cambios de estado y 0 de importancia en las tres semillas.
  - Pero el LTD sin uso (U0) duerme a todo recuerdo tras unas 13 noches. En el mundo de 1000 siguen activos 200 de 800; en el de 3000, **0 de 2400**. Por eso K1 y K3 son **vacuos** en el diario de 3000.
- **Consecuencia:** «cada tanda dispara H2» queda **refutado como regla general**. Es casi siempre cierto en comprimido y solo al principio en diario, como anticipaba la corrección del v2.

### 2.2 4b: los cruces del umbral 0,70 aparecen al crecer
- **Solo (brazo −H2):**
  - **Comprimido, 1000:** la media supera 0,70 en todos los ciclos de los dos mundos. El ×0,98 cae igual en D y en D∪I0, con **0 efecto** en D.
  - **Comprimido, 3000:** la media de D ronda 0,698. **I0 la hace cruzar en 5 ciclos (49, 51, 53, 56 y 58), los mismos en las tres semillas.**
    - Resultado: la importancia de **los 2400 recuerdos de D** queda distinta (suma |Δ| = 155,6), sin cambios de estado.
    - El top-5 cambia en 4 / 0 / 15 consultas; por la regla de atribución, 4 / 0 / 9.
  - **K8 (DB vacía, diario):** 20 importancias de D distintas. Con −H2 −4b son 0, así que por eliminación las causa 4b [D].
  - **Diario:** la media cae bajo 0,70 hacia el ciclo 7 en los dos mundos, sin cruces.
- **Acoplado con H2:** quitar 4b reduce los cambios de estado de T, de 101 a 48 (1000) y de 97 a 10 (3000). 4b baja la importancia de los recuerdos viejos y H2 los elige primero.

### 2.3 Aristas (K4, en D∪I′): H2 frena a la vez las accidentales y los puentes
| comprimido | accidental + ajeno, T → −H2 | puentes, T → −H2 | precisión (tema + puente), T → −H2 | temáticas |
|---|---|---|---|---|
| 1000 (s7 / s11 / s23) | 165→187 / 331→483 / 165→378 | 6→12 / 27→31 / 0→16 | 0,882→0,868 / 0,786→0,717 / 0,865→0,740 | iguales (±4) |
| 3000 | 576→968 / 885→2042 / 582→1162 | 2→44 / 0→46 / 10→70 | 0,869→0,800 / 0,798→0,634 / 0,855→0,750 | iguales (±11) |

- En diario las diferencias son mínimas: ±15 aristas.
- Se reproduce de forma **atenuada** el salto del Paso 2c (643 → 1838 en es): las accidentales se multiplican por 1,1–2,3, no por 3.
- **Sin H2, también aparecen muchos más puentes válidos.**

### 2.4 Canal 2 visible (K5)
Con T casi todo duerme, así que el canal 2 muestra muy poco. En comprimido, la **fracción** de pares buenos es mayor en T, pero T muestra **de 4 a 15 veces menos pares buenos**. Por ejemplo, en el mundo de 1000 con semilla 7: 480 en T frente a 2216 en −H2.

### 2.5 Cambio total del sistema que no se atribuye a H2/4b (brazo −H2 −4b)
- El estado de D es idéntico en los dos mundos, y aun así el top-5 cambia en **5 / 36 / 26 de 480** consultas (comprimido, 1000) y en **8 / 11 / 11** (comprimido, 3000). En diario cambian entre 0 y 1.
- Todos los cambios están en las escrituras latinas.
- I0 no comparte caracteres con D, así que la causa no es textual. [D] Lo atribuyo a estadísticas globales del buscador (el número de documentos en el IDF/BM25 o alguna normalización), sin verificar.
- **No es invariancia del sistema.** Se informa aparte y no se carga a este ciclo.

### 2.6 Costo del sueño
Sin H2, el sueño cuesta **de 2,0 a 2,4 veces más** en comprimido, porque hay muchos más activos que procesar. En diario el costo es ≈ 1,0.

### 2.7 Límites de esta medición
- **CJK:** las consultas de 2–3 palabras pegadas casi nunca devuelven el recuerdo (recall del 6–12 %, incluso con todo activo). Es la limitación conocida de las frases CJK en el canal 1, que sigue pendiente. Las señales del top-k vienen sobre todo de las latinas. Estados, K3, K4 y K6 no dependen del texto.
- **M1 y M2 de T están inflados:** sus top-5 quedan vacíos (recall 0), y «vacío = vacío» cuenta como idéntico. Por eso K2, que exige «no peor que T», **no es informativo** en comprimido.
- **Regla de atribución con interacciones:** en −H2 a 1000, el estado de D es idéntico y aun así la regla atribuye 1 / 4 / 1 cambios a H2/4b. Por construcción solo pueden venir del buscador combinado con importancias distintas.
- **M3:** ninguna inserción legítima por puente llegó al top-5 (las consultas no contienen la entidad puente), así que no se pudo evaluar esa parte. Todas las inserciones de I′ fueron difusas (accidentales) y no hubo violaciones C2-ajeno. En T hubo más inserciones difusas (26 / 28 / 19, frente a 2 / 0 / 1 en −H2), porque con D dormido solo I′ ocupa el top-5.
- **Mundo sintético:** no reproduce todas las coocurrencias del lenguaje natural. El salto de aristas del 2c aparece atenuado.

## 3. Criterios K1–K9 por brazo
«Cumplido» exige las tres semillas. «Vacuo» significa que no había nada que pudiera fallar. Para K2, K4 y K5, T es la referencia.

| brazo | K1 comp. 1000 / 3000 | K1 diario 1000 / 3000 | K3 comp. / diario 1000 | K2 | K4 | K5 | K6 | K7 comp. / diario | K8 | K9 |
|---|---|---|---|---|---|---|---|---|---|---|
| T | ✗ / ✗ | ✓ / ✓ vacuo | ✗ / ✓ | ref. | ref. | ref. | ✗ (duerme por H2: 817 de 1000) | ✗ / ✓ (con K1 vacuo a 3000) | ✗ (16 importancias distintas) | no medible |
| −H2 | ✗ (regla: 1/4/1 con estado idéntico) / ✗ (cruces de 4b) | ✓ / ✓ vacuo | ✓ / ✓ | ✗ comp. (T inflado); ✓ diario | ✗ (accidentales) | ✗ comp. (fracción); ✓ diario | ✓ (vacuo en comp.) | ✗ (costo 2×) / ✗ (K4) | ✗ (20 importancias, 4b) | no medible |
| −4b | ✗ / ✗ | ✗ (regla: 2 con estado idéntico) / ✓ vacuo | ✗ / ✓ | ✓ comp.; ✗ diario 1000 | ✗ (✓ comp. 3000) | ✗ (✓ diario 3000) | ✗ | ✗ / ✗ | ✗ (3) | no medible |
| −H2 −4b | ✓ / ✓ | ✓ / ✓ vacuo | ✓ / ✓ | ✗ comp. (T inflado); ✓ diario | ✗ (accidentales) | ✗ (✓ diario 3000) | ✓ | ✗ (costo 2×, K4) / ✗ (K4) | ✓ | no medible |

**K9** queda como no medible en esta etapa: la suite completa necesita aislamiento y una autorización aparte. El detalle bloque a bloque está en `resultados/tablas.md` y `resultados/resumen.json`.

## 4. Lectura [D]
- **H2 es la causa principal de la falta de invariancia cuando los sueños son seguidos.** Duerme recuerdos por su puesto frente a los recién llegados, incluso si estos no comparten nada con ellos. Pero también frena las aristas accidentales y abarata el sueño, así que **retirarla sin más falla K4 y K7**.
- **4b es inocuo mientras la media está lejos de 0,70.** Cuando ronda el umbral, como en el mundo de 3000 sin H2, añadir recuerdos ajenos cambia la importancia de **todos** los recuerdos de D. Acoplado con H2, empeora los cambios de estado.
- **El brazo −H2 −4b cumple todos los criterios absolutos** (K1, K3, K6 y K8), pero falla K4 (accidentales) y el costo de K7. Esto apoya los candidatos ya escritos en el §7 del protocolo:
  - H2-b y 4b-a: homeostasis **por recuerdo**;
  - un control de las aristas accidentales **en el nacimiento**, en un ciclo aparte.
- Nada de esto autoriza cambios.

## 5. Para la revisión
1. ¿Se aceptan estos resultados como diagnóstico?
2. **Ajustes propuestos al protocolo, sin aplicar:**
   - K2: medir M1 y M2 solo sobre consultas con top-k no vacío en los dos mundos, o exigir además que el recall no baje.
   - Atribución: cuando el estado de D es idéntico, contar el cambio como del buscador.
   - M3: añadir consultas que contengan la entidad puente.
3. ¿Se autoriza un protocolo siguiente para diseñar y medir H2-b, 4b-a y el control de aristas en el mismo laboratorio, todavía sin tocar el motor?
4. El cambio del buscador del §2.5 toca el ranking. ¿Se abre un ciclo aparte solo para diagnosticarlo?
