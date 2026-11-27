# Paso 3, capa L — tablas (generadas por `resumen_capa_L.py`)

Configuraciones: s7_n800, s7_n2400, s11_n800, s11_n2400, s23_n800, s23_n2400

## Controles de la medición

| config | pares D–D con arista | copia limpia (sinapsis/asoc./emerg. al final) | original intacta | recuerdos en corto plazo | bridges rechazados (D) | aristas manual (D) | inmunes (D) | D activos/dormidos | s por búsqueda (D) |
|---|---|---|---|---|---|---|---|---|---|
| s7_n800 | 1624 | D 0/0/0 · DI0 0/0/0 · DI1 0/0/0 · Dfa 0/0/0 | True | 0 | 0 | 88 | 15 | 343/457 | 0.0835 |
| s7_n2400 | 5770 | D 0/0/0 · DI0 0/0/0 · DI1 0/0/0 · Dfa 0/0/0 | True | 0 | 3 | 282 | 47 | 1100/1300 | 0.0901 |
| s11_n800 | 1764 | D 0/0/0 · DI0 0/0/0 · DI1 0/0/0 · Dfa 0/0/0 | True | 0 | 5 | 94 | 13 | 406/394 | 0.0740 |
| s11_n2400 | 5893 | D 0/0/0 · DI0 0/0/0 · DI1 0/0/0 · Dfa 0/0/0 | True | 0 | 7 | 287 | 39 | 1066/1334 | 0.0906 |
| s23_n800 | 1395 | D 0/0/0 · DI0 0/0/0 · DI1 0/0/0 · Dfa 0/0/0 | True | 0 | 2 | 105 | 16 | 405/395 | 0.0848 |
| s23_n2400 | 4990 | D 0/0/0 · DI0 0/0/0 · DI1 0/0/0 · Dfa 0/0/0 | True | 0 | 10 | 309 | 39 | 1082/1318 | 0.0918 |

## Top-K ciego idéntico (recuerdos de D)

| config | D∪I0 | D∪I1 | Dfa (bucle) | no-D en tops D∪I0 / D∪I1 |
|---|---|---|---|---|
| s7_n800 | 800/800 | 746/800 | 800/800 | 0 / 94 |
| s7_n2400 | 2168/2400 | 1993/2400 | 2400/2400 | 1 / 483 |
| s11_n800 | 798/800 | 748/800 | 800/800 | 0 / 96 |
| s11_n2400 | 2187/2400 | 2041/2400 | 2400/2400 | 0 / 420 |
| s23_n800 | 796/800 | 749/800 | 800/800 | 0 / 78 |
| s23_n2400 | 2139/2400 | 1993/2400 | 2400/2400 | 0 / 476 |

## Veredicto por aguja (capa L)

AUC = media sobre escrituras y configuraciones, **con filtración léxica por construcción: no cuenta para admitir**.

| aguja | C3.1 invariancia (mín. D∪I0 / D∪I1) | C3.2 bucle (mín. Dfa / Dfm) | C3.4 costo (×, 2400 vs 800) | C3.7 ρ máx. con el grado | ρ máx. dentro de clase (diagnóstico) | C3.8 no vacua | capa L | AUC (marcada) |
|---|---|---|---|---|---|---|---|---|
| S_tem | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1946 ✓ | 0.3851 | ✓ | **limpia** | 0.9730 |
| S_tono | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1379 ✓ | 0.3329 | ✓ | **limpia** | 0.9120 |
| S_sk | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1304 ✓ | 0.2997 | ✓ | **limpia** | 0.9270 |
| S_idf | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.3367 ✗ | 0.3785 | ✓ | **no limpia** | 0.9180 |
| X_min | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1404 ✓ | 0.1859 | ✓ | **limpia** | 0.9320 |
| X_max | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.2402 ✓ | 0.2077 | ✓ | **limpia** | 0.9700 |
| X_concepto | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1052 ✓ | 0.1700 | ✓ | **limpia** | 0.8460 |
| X_sk | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1396 ✓ | 0.2149 | ✓ | **limpia** | 0.9310 |
| X_contenido | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.2402 ✓ | 0.2077 | ✓ | **limpia** | 0.9700 |
| B_flag | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1417 ✓ | 0.0948 | ✓ | **limpia** | 0.9870 |
| B_weight | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1657 ✓ | 0.2036 | ✓ | **limpia** | 0.9900 |
| B_angulos | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1452 ✓ | 0.1508 | ✓ | **limpia** | 0.9950 |
| Cat | 1.0000 / 1.0000 ✓ | 1.0000 / 1.0000 ✓ | 0.8311 ✓ | 0.1620 ✓ | 0.3789 | ✓ | **limpia** | 0.7630 |
| G_ciego | 0.9740 / 0.9574 ✗ | 1.0000 / — ✓ | 1.0149 (búsq. 1.1244) ✓ | 0.7877 ✗ | 0.8119 | ✓ | **no limpia** | 0.8690 |
| R | 0.9934 / 0.9925 ✓ | 1.0000 / — ✓ | 1.0149 (búsq. 1.1244) ✓ | 0.0697 ✓ | 0.2039 | ✓ | **limpia** | 0.9090 |
| K | 0.7626 / 0.6333 ✗ | 0.2481 / 0.2674 lee el grafo → C3.5 | 1.3242 ✗ | -0.2262 ✓ | 0.0495 | ✓ | **no limpia** | 0.8460 |
| L1_local | 1.0000 / 1.0000 ✓ | 1.0000 / 0.9977 ✓ | 1.3242 ✗ | 0.0631 ✓ | 0.0700 | ✗ (vacua en alguna escritura) | **no limpia** | 0.5020 |
| T2 | 0.9488 / 0.9488 por tipo (§5.2) | 1.0000 / 1.0000 no cambia | 1.3242 ✗ | 0.0939 ✓ | 0.2226 | ✓ | **no limpia** | 0.6050 |

## §5.2 Invariancia por tipo de arista (pares D–D: existencia del tipo idéntica en D y en D∪I)

| tipo | prioridad | mín. D∪I0 | mín. D∪I1 | aristas en D (suma) | ≥ 98 % |
|---|---|---|---|---|---|
| co_nombre | 5 | 0.9307 | 0.9307 | 2880 | ✗ |
| co_ocurrencia | 4 | 0.9800 | 0.9800 | 12306 | ✗ |
| co_semantica | 2 | 1.0000 | 1.0000 | 689 | ✓ |
| dmn_synthesized | 50 (sin prioridad) | 0.7937 | 0.7937 | 1632 | ✗ |
| manual | 0 | 1.0000 | 1.0000 | 1165 | ✓ |
| pmi_hebbiano | 9 | 0.7923 | 0.7923 | 2912 | ✗ |
| sinonimo_explicito | 1 | 0.9756 | 0.9756 | 171 | ✗ |

## Tipos por escritura y verdad (mundo D, suma de configuraciones)

| escritura | tipo | tema | puente | accidental | ajeno |
|---|---|---|---|---|---|
| han | co_ocurrencia | 2619 | 0 | 199 | 0 |
| han | co_semantica | 224 | 0 | 1 | 0 |
| han | dmn_synthesized | 118 | 0 | 34 | 0 |
| han | manual | 167 | 3 | 23 | 4 |
| han | sinonimo_explicito | 23 | 0 | 23 | 1 |
| jpn | co_ocurrencia | 3344 | 4 | 306 | 0 |
| jpn | co_semantica | 229 | 0 | 6 | 0 |
| jpn | dmn_synthesized | 150 | 0 | 41 | 11 |
| jpn | manual | 166 | 6 | 27 | 4 |
| jpn | sinonimo_explicito | 7 | 0 | 31 | 9 |
| lat_a | co_nombre | 956 | 10 | 1515 | 0 |
| lat_a | co_ocurrencia | 2285 | 0 | 47 | 0 |
| lat_a | co_semantica | 204 | 0 | 1 | 0 |
| lat_a | dmn_synthesized | 216 | 0 | 128 | 15 |
| lat_a | manual | 181 | 7 | 27 | 5 |
| lat_a | pmi_hebbiano | 156 | 66 | 2411 | 93 |
| lat_a | sinonimo_explicito | 7 | 0 | 27 | 6 |
| lat_b | co_nombre | 81 | 0 | 318 | 0 |
| lat_b | co_ocurrencia | 2269 | 6 | 1227 | 0 |
| lat_b | co_semantica | 24 | 0 | 0 | 0 |
| lat_b | dmn_synthesized | 115 | 0 | 37 | 4 |
| lat_b | manual | 179 | 1 | 32 | 3 |
| lat_b | pmi_hebbiano | 4 | 3 | 174 | 5 |
| lat_b | sinonimo_explicito | 9 | 0 | 25 | 3 |
| mixta | dmn_synthesized | 0 | 0 | 0 | 763 |
| mixta | manual | 0 | 0 | 0 | 330 |

## Costo

| grupo | s/par |D|=800 | s/par |D|=2400 |
|---|---|---|
| locales | 7.76e-05 | 6.45e-05 |
| buscador | 3.03e-06 | 3.08e-06 |
| grafo | 4.10e-05 | 5.43e-05 |
| búsqueda ciega (s/consulta) | 0.0808 | 0.0908 |

## Control de reloj (control_reloj_n2400.json): D frente a Dt (mismos días y sueños que D∪I, sin documentos)

Cada celda: en D / en el otro mundo / en ambos. «=» quiere decir que Dt coincide exactamente con D∪I0 y con D∪I1.

| semilla | tipo | D→Dt | D→D∪I0 | D→D∪I1 | ¿Dt = D∪I? |
|---|---|---|---|---|---|
| 7 | co_nombre | 904/860/860 | 904/860/860 | 904/860/860 | = |
| 7 | co_ocurrencia | 3119/3092/3092 | 3119/3092/3092 | 3119/3092/3092 | = |
| 7 | co_semantica | 189/189/189 | 189/189/189 | 189/189/189 | = |
| 7 | dmn_synthesized | 400/504/400 | 400/504/400 | 400/504/400 | = |
| 7 | manual | 282/282/282 | 282/282/282 | 282/282/282 | = |
| 7 | pmi_hebbiano | 922/763/763 | 922/763/763 | 922/763/763 | = |
| 7 | sinonimo_explicito | 41/40/40 | 41/40/40 | 41/40/40 | = |
| 11 | co_nombre | 772/730/730 | 772/730/730 | 772/730/730 | = |
| 11 | co_ocurrencia | 3393/3325/3325 | 3393/3325/3325 | 3393/3325/3325 | = |
| 11 | co_semantica | 156/156/156 | 156/156/156 | 156/156/156 | = |
| 11 | dmn_synthesized | 400/504/400 | 400/504/400 | 400/504/400 | = |
| 11 | manual | 287/287/287 | 287/287/287 | 287/287/287 | = |
| 11 | pmi_hebbiano | 929/736/736 | 929/736/736 | 929/736/736 | = |
| 11 | sinonimo_explicito | 44/43/43 | 44/43/43 | 44/43/43 | = |
| 23 | co_nombre | 722/672/672 | 722/672/672 | 722/672/672 | = |
| 23 | co_ocurrencia | 2947/2903/2903 | 2947/2903/2903 | 2947/2903/2903 | = |
| 23 | co_semantica | 156/156/156 | 156/156/156 | 156/156/156 | = |
| 23 | dmn_synthesized | 400/504/400 | 400/504/400 | 400/504/400 | = |
| 23 | manual | 309/309/309 | 309/309/309 | 309/309/309 | = |
| 23 | pmi_hebbiano | 477/404/404 | 477/404/404 | 477/404/404 | = |
| 23 | sinonimo_explicito | 45/45/45 | 45/45/45 | 45/45/45 | = |

**Dt = D∪I en todas las celdas: sí.** Si es sí, la parte del cambio atribuible al contenido de I es cero y lo explica el paso del tiempo (sueños).
