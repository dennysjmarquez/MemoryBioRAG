# Paso 3, capa L: resultados (27-11)

> **Qué es esto.** La capa L es la primera criba de las agujas candidatas para la neurona sináptica estrella. Se
> hace en un laboratorio sintético con el motor real: cada aguja se mide sobre los pares de recuerdos con arista y
> se comprueba si cumple los criterios del protocolo (`../PROTOCOLO_PASO3.md`, C3.1–C3.8) **antes** de entrenar
> nada. No toca `core/`, `tests/` ni la base viva. Solo usa datos sintéticos.
> Autorización: el agente local de Dennys («Puedes ejecutar la Capa L», 27-11). El auditor de Arena no la autorizó.
> Queda registrado.
>
> **Marcas:** [V] verificado con salida literal · [D] deducido.

## 1. Qué se corrió

- `laboratorio_capa_L.py todo`: 3 semillas (7, 11, 23) × |D| = 800 y 2400.
  - En cada configuración se construyen los mundos D, D∪I0 y D∪I1 con declaraciones deterministas idénticas
    (sueño cada 50 recuerdos), más el bucle Dfa/Dfm (aristas falsas automáticas o `manual` inyectadas en D).
  - Se miden con `BIORAG_NEURONA=0`, `BIORAG_PPMI_WEIGHT=0` y `BIORAG_DMN_SINTESIS_ACTIVA=0`. Lo que depende del
    buscador se mide sobre una copia limpia (sin sinapsis).
  - Tiempo total: 837 s para las tres de 800 y 8 333 s para las de 2400 (relanzadas, ver §5).
  - Resultados: `resultados/config_s{s}_n{n}.json`. Tablas: `resultados/tablas.md` (generadas por
    `resumen_capa_L.py`).
- `control_reloj.py 2400` (3 286 s): control añadido después de ver los datos (§3). Resultado en
  `resultados/control_reloj_n2400.json`.
- Commits: `618888a`, `18db54c`, `8cc6b89`, `0890f01`, `efec7f2` y `e5e3b57`.

## 2. Controles de la medición [V]

- **Copia limpia sin sinapsis:** 0/0/0 en todos los mundos y configuraciones. Las bases originales quedan intactas.
- **Corto plazo vacío:** sí.
- **Recuerdos inmunes en D:** 13–47 por configuración. **Aristas `manual` en D:** 88–309.
- **Top-K ciego idéntico entre D y D∪I0:**
  - en 800: 796–800 de 800;
  - en 2400: 2139–2187 de 2400, con 0–1 recuerdos ajenos.
  - Con más documentos, el buscador ya no devuelve exactamente los mismos tops: las estadísticas globales de BM25
    cambian. Por eso la aguja G_ciego falla en 2400 (§4).

## 3. El hallazgo principal: los tipos de arista y el paso del tiempo

**Lo que se vio [V].** En 800, la existencia de cada tipo de arista entre dos recuerdos de D es idéntica en D y en
D∪I (salvo `dmn_synthesized`). En 2400, no:

| tipo | mín. D→D∪I (2400) |
|---|---|
| `pmi_hebbiano` | 0,79 |
| `co_nombre` | 0,93 |
| `co_ocurrencia` | 0,98 |
| `sinonimo_explicito` | 0,976 |
| `co_semantica`, `manual` | 1,0 |

Además, **D∪I0 y D∪I1 daban exactamente las mismas cuentas**, aunque I1 tiene contenido que interfiere a propósito.

**Control de reloj [V].** El mundo D duerme 49 noches y D∪I duerme 62: escribir I lleva 13 días y 13 sueños más.
`Dt` es el mundo D más esos mismos 13 días y sueños, **sin escribir ningún documento**.
- En las 3 semillas y los 7 tipos, D→Dt da **exactamente** las mismas cuentas que D→D∪I0 y D→D∪I1 (21 de 21 celdas
  iguales; tabla en `resultados/tablas.md`).
- **Conclusión:** la parte del cambio atribuible al contenido de I es **cero**. Todo lo explica el paso del tiempo.

**Mecanismo [V].** Es el decaimiento sináptico del sueño (`core/memory/consolidation.py` ~L492–511): las aristas con
`ultimo_uso` de hace más de 7 días se multiplican por 0,95 cada noche y se borran por debajo de 0,05. Las `manual`
están excluidas.
- En el laboratorio, ese umbral se compara con `strftime('%s','now')` de SQLite, que es el **reloj real** (medido:
  1 795 791 955). El reloj simulado (≈ 1,6·10⁹) no llega a SQLite.
- Por eso, en el laboratorio, toda arista que se usó una vez decae cada noche desde el primer día, sin los 7 días de
  gracia. De 0,6 a menos de 0,05 tarda unas 48 noches. D (49) apenas lo alcanza; D∪I (62) sí. En 800 (22 noches)
  no muere ninguna arista. Coincide con lo medido.
- `dmn_synthesized` no tiene `ultimo_uso`. Su cambio viene de la síntesis del DMN en el sueño, y en 800 sí depende del
  contenido (D∪I0 0,91 frente a D∪I1 0,98). Sigue fuera.

**Qué significa:**
1. Para T2 (la aguja «tipo de arista»), la invariancia **atribuible a sumar documentos** es del 100 % en los 6 tipos
   que no son DMN. La **total** (D frente a D∪I, como la pide §5.2) falla en 2400. Siguiendo la regla de separar
   (a) atribuible y (b) total, **no se declara que T2 pase §5.2**.
2. En producción el fenómeno existe, pero con otro ritmo: una arista sin usar durante 7 días reales empieza a decaer.
   Una aguja que lea «qué tipos tiene hoy este par» puede cambiar con el tiempo aunque no entre ningún documento.
3. **Limitación del laboratorio [V]:** el reloj simulado no controla el `now` de SQLite. Afecta por igual a todos los
   brazos de las mediciones anteriores (H2/4b), así que las comparaciones entre brazos siguen valiendo. Las cuentas
   absolutas de aristas después de muchos sueños, no.

## 4. Veredicto por aguja (6 configuraciones) [V]

Umbrales: C3.1 = 1,0 en las locales y en K/L1_local, ≥ 0,98 en el buscador · C3.4 ≤ 1,2 · C3.7: ρ con el grado
≤ 0,30 en cada escritura y configuración · C3.8 no vacua.

| aguja | C3.1 | C3.2 bucle | C3.4 | C3.7 ρ máx. | C3.8 | capa L |
|---|---|---|---|---|---|---|
| S_tem | 1,0 ✓ | ✓ | 0,83 ✓ | 0,19 ✓ | ✓ | **limpia** |
| S_tono | 1,0 ✓ | ✓ | ✓ | 0,14 ✓ | ✓ | **limpia** |
| S_sk | 1,0 ✓ | ✓ | ✓ | 0,13 ✓ | ✓ | **limpia** |
| S_idf | 1,0 ✓ | ✓ | ✓ | **0,34 ✗** | ✓ | no limpia |
| X_min / X_max / X_concepto / X_sk / X_contenido | 1,0 ✓ | ✓ | ✓ | ≤ 0,24 ✓ | ✓ | **limpias** |
| B_flag / B_weight / B_angulos | 1,0 ✓ | ✓ | ✓ | ≤ 0,17 ✓ | ✓ | **limpias** |
| Cat | 1,0 ✓ | ✓ | ✓ | 0,16 ✓ | ✓ | **limpia** |
| R | 0,993 ✓ | ✓ | 1,01 (búsq. 1,12) ✓ | 0,07 ✓ | ✓ | **limpia** |
| G_ciego | **0,957 ✗** | ✓ | ✓ | **0,79 ✗** | ✓ | no limpia |
| K | **0,63 ✗** | lee el grafo | **1,32 ✗** | −0,23 | ✓ | no limpia |
| L1_local | 1,0 ✓ | ✓ | 1,32 ✗ (*) | 0,06 | **vacua ✗** | no limpia |
| T2 | §3 | no cambia | 1,32 ✗ (*) | 0,09 ✓ | ✓ | no limpia (§3) |

(*) C3.4 se mide **por grupo**, no por aguja. El grupo «grafo» sube ×1,32 por K (vecindarios que crecen con el
grafo). T2 y L1_local comparten ese costo sin haberlo causado. Es una limitación de la medición: queda para medir por
aguja antes del Paso 4, sin cambiar el criterio.

**Lectura:**
- **13 agujas limpias** en la capa L: S_tem, S_tono, S_sk, X_min, X_max, X_concepto, X_sk, X_contenido, B_flag,
  B_weight, B_angulos, Cat y R.
- La prueba en seco (n = 60) había dado ρ de 0,5–0,6 en casi todas. Con 800 y 2400 bajan a ≤ 0,24. **Aquello era
  ruido de muestra pequeña**: el fallo en seco de C3.7 no se repitió.
- **S_idf** falla C3.7 en **una sola celda de 24** (s7·800·jpn, ρ = 0,3367; el resto ≤ 0,28). El criterio es estricto y
  no se cambia, así que queda fuera.
- **G_ciego** falla por dos razones independientes: el buscador no es invariante en 2400 (§2) y depende del grado,
  sobre todo en han (ρ hasta 0,79).
- **K** lee el grafo; ya estaba previsto que fallara C3.1 y C3.2.
- **L1_local** es vacua en 4 celdas (lat_a, lat_b y jpn).
- **X_max y X_contenido** dan los mismos números en todas las columnas. Probablemente son redundantes en este mundo;
  se revisará en la capa V antes de admitir las dos.
- **AUC** (0,76–0,995): **no cuenta**. En la capa L las declaraciones se generan a partir de la verdad, así que hay
  filtración por construcción. B_angulos ≈ 1,0 lo muestra. La capacidad de separar la mide la capa V (declaraciones a
  ciegas) y, al final, C3.5.

## 5. Incidentes [V]

- **Falta de memoria en 2400:** cada construcción llega a ≈ 2,4 GB de RSS. Con dos a la vez, el OOM killer del kernel
  mató una (`dmesg`). Se pasó a un solo worker en n ≥ 2400 y a reanudar con lo ya construido: una base cuenta como
  completa si tiene su `.info.json`, que se escribe al final. Las configuraciones de 800 no se repitieron.
- Mientras corría, Dennys subió `7c035fa` (GUIA §13–20). Se integró sin conflictos.

## 6. Qué propongo [D] (ideas, sin cambiar ningún criterio aprobado)

1. **T2 y el tiempo:**
   - (a) Enmienda de §5.2 (requiere OK): comparar contra un **control de reloj** (Dt), además de D∪I. Así se separa
     «sumar documentos» (la NORMA MÁXIMA) de «pasar el tiempo».
   - (b) Como aguja alternativa: el **tipo al nacer** (la regla que creó la arista, guardada en su nacimiento). No
     decae con el tiempo y no depende de I por construcción.
   - (c) Probar T2 solo con los tipos que no decaen: `manual` (y `co_semantica`, que en 2400 no perdió ninguna).
2. **Reloj del laboratorio:** registrar en las conexiones del laboratorio una función `strftime` propia que use el
   reloj simulado (SQLite permite sustituir funciones integradas por conexión). Medir de nuevo **solo** el control de
   reloj, para ver la caducidad con los 7 días de gracia. Es un cambio del laboratorio, no del motor.
3. **Sesgo de grado (S_idf y G_ciego):** la literatura reciente lo trata como un problema conocido de la predicción de
   enlaces.
   - Aiyappa et al. (ICML 2025): un predictor que solo usa el grado ya parece casi óptimo en las evaluaciones
     habituales; proponen evaluar con **negativos corregidos por grado**.
   - PNAS 2025 (*bias-aware link prediction*): usar versiones normalizadas por grado (Jaccard frente a vecinos
     comunes) y muestreo balanceado.
   - Para nosotros:
     - (i) calcular C3.5 también con negativos emparejados por grado, como diagnóstico;
     - (ii) probar variantes normalizadas, por ejemplo S_idf dividido por el IDF medio de los dos recuerdos, o
       G_ciego como rango relativo al tamaño de la lista;
     - (iii) residualizar respecto del grado.
   - Ninguna cambia C3.7. Las variantes nuevas tendrían que pasar todos los criterios igual que las demás.
4. **C3.4 por aguja:** medir el costo de cada aguja por separado (T2 y L1_local no deberían cargar el costo de K).
5. **Siguiente:** capa V (corpus públicos con licencia, declaraciones a ciegas) con las 13 limpias. T2 queda pendiente
   de decidir sobre el punto 1.
