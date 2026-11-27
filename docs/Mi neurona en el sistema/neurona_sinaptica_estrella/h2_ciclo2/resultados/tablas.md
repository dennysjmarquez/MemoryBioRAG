# Ciclo 2 H2/4b — tablas (laboratorio sintético; generado por resumen_ciclo2.py)

Controles: {"H2loc+4bp": {"construccion_determinista": true, "orden_consultas_indiferente": true}}


## Configuración «real» (Neurona 1 activa; PPMI 0,15; corte tras D)


### real · |D| = 800 · reloj comprimido — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 101 / 101 / 101 | 149 / 149 / 149 | 41 / 40 / 52 | 38 / 38 / 46 | 3 / 2 / 6 | no / no / no | 101→0 / 101→0 / 101→0 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 2 / 27 | 0 / 0 / 0 | 3 / 2 / 27 | sí / sí / sí | 800→800 / 800→800 / 800→800 |
| H2loc | 2 / 0 / 3 | 1 / 1 / 3 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / no / no | 299→297 / 288→288 / 332→329 |
| 4bp | 101 / 101 / 101 | 149 / 149 / 149 | 41 / 40 / 52 | 38 / 38 / 46 | 3 / 2 / 6 | no / no / no | 101→0 / 101→0 / 101→0 |
| H2loc+4bp | 2 / 0 / 3 | 1 / 1 / 3 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / no / no | 299→297 / 288→288 / 332→329 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 0.071·0.000·0.000 / 0.056·0.000·0.000 / 0.092·0.000·0.000 | 11 / 11 / 8 | 19/0 (18) / 30/2 (46) / 43/0 (26) | 0·228 / 0·287 / 0·168 | 1282·6·211·0.859·3.00 / 1222·28·349·0.782·3.20 / 1098·0·183·0.857·2.56 | 494 (0.969) / 307 (0.679) / 400 (0.887) | 817 · 0 / 817 · 0 / 817 · 0 | 0.798 / 0.746 / 0.802 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/272 / 0 · 0/275 / 0 · 26/271 | 0 · 10/272 / 0 · 3/275 / 0 · 39/271 | 0.535·0.535·0.535 / 0.544·0.544·0.542 / 0.535·0.535·0.535 | 9 / 9 / 11 | 14/0 (18) / 19/0 (46) / 26/0 (26) | 0·0 / 0·0 / 0·0 | 1347·13·240·0.850·3.20 / 1237·32·555·0.696·3.65 / 1171·16·427·0.735·3.23 | 2262 (0.899) / 2102 (0.843) / 2013 (0.856) | 0 · 0 / 0 · 0 / 0 · 0 | 1.641 / 1.601 / 1.614 (2.06 / 2.14 / 2.01) |
| H2loc | 2 · 0/214 / 0 · 0/204 / 2 · 0/225 | 0 · 0/216 / 4 · 4/200 / 4 · 0/223 | 0.217·0.217·0.217 / 0.227·0.227·0.223 / 0.219·0.215·0.215 | 10 / 5 / 3 | 3/0 (18) / 8/1 (46) / 21/0 (26) | 0·0 / 0·0 / 0·0 | 1267·4·126·0.910·2.79 / 1212·8·205·0.856·2.85 / 1101·0·86·0.927·2.37 | 601 (0.923) / 504 (0.884) / 556 (0.964) | 637 · 0 / 630 · 0 / 590 · 0 | 0.726 / 0.676 / 0.839 (0.91 / 0.91 / 1.05) |
| 4bp | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 0.071·0.000·0.000 / 0.056·0.000·0.000 / 0.092·0.000·0.000 | 11 / 11 / 8 | 19/0 (18) / 30/2 (46) / 43/0 (26) | 0·228 / 0·287 / 0·168 | 1282·6·211·0.859·3.00 / 1222·28·349·0.782·3.20 / 1098·0·183·0.857·2.56 | 494 (0.969) / 307 (0.679) / 400 (0.887) | 817 · 0 / 817 · 0 / 817 · 0 | 0.795 / 0.741 / 0.773 (1.0 / 0.99 / 0.96) |
| H2loc+4bp | 2 · 0/214 / 0 · 0/204 / 2 · 0/225 | 0 · 0/216 / 4 · 4/200 / 4 · 0/223 | 0.217·0.217·0.217 / 0.227·0.227·0.223 / 0.219·0.215·0.215 | 10 / 5 / 3 | 3/0 (18) / 8/1 (46) / 21/0 (26) | 0·0 / 0·0 / 0·0 | 1267·4·126·0.910·2.79 / 1212·8·205·0.856·2.85 / 1101·0·86·0.927·2.37 | 601 (0.923) / 504 (0.884) / 556 (0.964) | 637 · 0 / 630 · 0 / 590 · 0 | 0.712 / 0.663 / 0.834 (0.89 / 0.89 / 1.04) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 3213·8·290·0; co_semantica 247·0·3·0; dmn_synthesized 97·0·8·0; pmi_hebbiano 35·26·390·24; sinonimo_explicito 10·0·23·5 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | CCC 3/3/4·0/2/0 / ––– 0/0/0·10/10/10 / CCC 4/4/4·7/7/7 | co_ocurrencia 3203·8·445·0; co_semantica 247·0·5·0; dmn_synthesized 255·1·56·11; pmi_hebbiano 40·52·609·27; sinonimo_explicito 10·0·62·7 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 3222·4·240·0; co_semantica 247·0·2·0; dmn_synthesized 75·0·16·0; pmi_hebbiano 29·8·128·5; sinonimo_explicito 7·0·24·2 | 501/619 · 0/0 / 512/620 · 0/0 / 468/580 · 0/0 |
| 4bp | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 3213·8·290·0; co_semantica 247·0·3·0; dmn_synthesized 97·0·8·0; pmi_hebbiano 35·26·390·24; sinonimo_explicito 10·0·23·5 | 0/0 · 3440/3831 / 0/0 · 3440/3831 / 0/0 · 3440/3831 |
| H2loc+4bp | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 3222·4·240·0; co_semantica 247·0·2·0; dmn_synthesized 75·0·16·0; pmi_hebbiano 29·8·128·5; sinonimo_explicito 7·0·24·2 | 501/619 · 4395/4724 / 512/620 · 4449/4820 / 468/580 · 4799/5155 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | no cumplido | referencia (= T) | no cumplido | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido | no cumplido | cumplido | no cumplido | no cumplido | cumplido (vacuo) |
| H2loc | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido | no cumplido | no cumplido | no cumplido |
| 4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | no cumplido | cumplido | cumplido | no cumplido |
| H2loc+4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido | no cumplido | no cumplido | no cumplido |

### real · |D| = 800 · reloj diario — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 0 / 0 / 0 | 0 / 0 / 0 | 12 / 12 / 1 | 0 / 0 / 0 | 12 / 12 / 1 | sí / sí / sí | 200→200 / 200→200 / 200→200 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 7 / 3 / 5 | 0 / 0 / 0 | 7 / 3 / 5 | sí / sí / sí | 200→200 / 200→200 / 200→200 |
| H2loc | 1 / 0 / 1 | 1 / 0 / 1 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / sí / no | 94→93 / 94→94 / 102→101 |
| 4bp | 0 / 0 / 0 | 0 / 0 / 0 | 6 / 9 / 1 | 0 / 0 / 0 | 6 / 9 / 1 | sí / sí / sí | 150→150 / 150→150 / 150→150 |
| H2loc+4bp | 1 / 0 / 1 | 1 / 0 / 1 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / sí / no | 71→70 / 73→73 / 77→76 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 0 · 10/79 / 0 · 10/72 / 0 · 0/88 | 0 · 14/79 / 0 · 15/72 / 0 · 3/88 | 0.152·0.152·0.152 / 0.123·0.123·0.121 / 0.156·0.156·0.156 | 7 / 10 / 9 | 15/0 (18) / 21/0 (46) / 42/0 (26) | 0·0 / 0·0 / 0·0 | 1328·13·277·0.829·3.24 / 1244·32·446·0.741·3.44 / 1152·0·308·0.789·2.92 | 950 (0.906) / 823 (0.894) / 791 (0.904) | 68 · 532 / 68 · 532 / 68 · 532 | 1.228 / 1.281 / 1.234 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 4/79 / 0 · 1/72 / 0 · 4/88 | 0 · 4/79 / 0 · 9/72 / 0 · 7/88 | 0.152·0.152·0.152 / 0.123·0.123·0.121 / 0.156·0.156·0.156 | 7 / 10 / 9 | 15/0 (18) / 21/0 (46) / 42/0 (26) | 0·0 / 0·0 / 0·0 | 1355·13·223·0.860·3.18 / 1244·32·484·0.725·3.52 / 1171·0·344·0.773·3.03 | 959 (0.921) / 823 (0.886) / 791 (0.903) | 0 · 600 / 0 · 600 / 0 · 600 | 1.296 / 1.302 / 1.333 (1.06 / 1.02 / 1.08) |
| H2loc | 2 · 0/67 / 0 · 0/61 / 2 · 0/79 | 0 · 1/69 / 0 · 2/61 / 4 · 0/77 | 0.077·0.077·0.077 / 0.073·0.073·0.073 / 0.069·0.065·0.065 | 5 / 4 / 3 | 5/0 (18) / 13/1 (46) / 22/0 (26) | 0·0 / 0·0 / 0·0 | 1300·4·155·0.894·2.92 / 1240·9·191·0.867·2.88 / 1117·0·96·0.921·2.43 | 473 (0.956) / 397 (0.898) / 376 (0.984) | 540 · 275 / 522 · 287 / 515 · 293 | 0.655 / 0.624 / 0.713 (0.53 / 0.49 / 0.58) |
| 4bp | 0 · 4/58 / 0 · 7/52 / 0 · 0/71 | 0 · 3/58 / 0 · 8/52 / 0 · 3/71 | 0.108·0.108·0.108 / 0.081·0.081·0.081 / 0.125·0.125·0.125 | 17 / 10 / 10 | 15/0 (18) / 21/2 (46) / 42/0 (26) | 0·0 / 0·0 / 0·0 | 1283·12·240·0.844·3.07 / 1222·28·433·0.743·3.37 / 1105·0·282·0.797·2.77 | 836 (0.918) / 707 (0.883) / 701 (0.907) | 68 · 582 / 68 · 582 / 68 · 582 | 1.148 / 1.205 / 1.172 (0.94 / 0.94 / 0.95) |
| H2loc+4bp | 2 · 0/45 / 0 · 0/43 / 2 · 0/62 | 0 · 0/47 / 0 · 5/43 / 4 · 0/60 | 0.044·0.044·0.044 / 0.054·0.054·0.050 / 0.058·0.054·0.054 | 15 / 5 / 3 | 4/0 (18) / 18/1 (46) / 22/0 (26) | 0·0 / 0·0 / 0·0 | 1266·4·137·0.903·2.81 / 1211·9·193·0.863·2.83 / 1101·0·111·0.908·2.42 | 371 (0.961) / 357 (0.911) / 333 (0.988) | 552 · 293 / 524 · 307 / 512 · 321 | 0.642 / 0.585 / 0.698 (0.52 / 0.46 / 0.57) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | CCC 5/4/5·0/0/0 / CC– 3/1/0·5/5/4 / CCC 1/1/1·0/0/0 | co_ocurrencia 3206·8·363·0; co_semantica 247·0·3·0; dmn_synthesized 224·1·41·5; pmi_hebbiano 37·36·554·21; sinonimo_explicito 10·0·38·6 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | CCC 3/4/3·0/0/0 / ––– 0/0/0·8/5/5 / CCC 1/3/5·6/7/6 | co_ocurrencia 3209·8·372·0; co_semantica 247·0·3·0; dmn_synthesized 265·1·58·11; pmi_hebbiano 39·36·533·20; sinonimo_explicito 10·0·48·6 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 3220·4·236·0; co_semantica 247·0·2·0; dmn_synthesized 154·0·24·1; pmi_hebbiano 29·9·145·10; sinonimo_explicito 7·0·22·2 | 431/539 · 0/0 / 418/514 · 0/0 / 405/503 · 0/0 |
| 4bp | CCC 3/3/2·0/0/0 / CCC 1/2/2·6/2/2 / ––– 0/0/0·0/1/0 | co_ocurrencia 3206·8·360·0; co_semantica 247·0·3·0; dmn_synthesized 110·0·9·0; pmi_hebbiano 37·32·520·19; sinonimo_explicito 10·0·38·6 | 0/0 · 2313/2863 / 0/0 · 2313/2863 / 0/0 · 2313/2863 |
| H2loc+4bp | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 3223·4·235·0; co_semantica 247·0·2·0; dmn_synthesized 72·0·4·0; pmi_hebbiano 29·9·167·9; sinonimo_explicito 7·0·22·2 | 436/546 · 1257/1539 / 420/518 · 1309/1620 / 402/501 · 1319/1626 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | cumplido | referencia (= T) | cumplido | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido | no cumplido | cumplido | no cumplido | no cumplido | cumplido |
| H2loc | no cumplido | no cumplido | cumplido | no cumplido | no cumplido | no cumplido |
| 4bp | cumplido | no cumplido | cumplido | no cumplido | no cumplido | no cumplido |
| H2loc+4bp | no cumplido | no cumplido | cumplido | no cumplido | no cumplido | no cumplido |

### real · |D| = 2400 · reloj comprimido — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 97 / 97 / 97 | 162 / 162 / 162 | 19 / 8 / 11 | 18 / 8 / 8 | 1 / 0 / 3 | no / no / no | 97→0 / 97→0 / 97→0 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 18 / 23 | 0 / 0 / 0 | 3 / 18 / 23 | sí / sí / sí | 2400→2400 / 2400→2400 / 2400→2400 |
| H2loc | 5 / 2 / 5 | 834 / 912 / 918 | 5 / 0 / 18 | 4 / 0 / 13 | 1 / 0 / 5 | no / no / no | 834→829 / 908→906 / 914→913 |
| 4bp | 97 / 97 / 97 | 162 / 162 / 162 | 19 / 8 / 11 | 18 / 8 / 8 | 1 / 0 / 3 | no / no / no | 97→0 / 97→0 / 97→0 |
| H2loc+4bp | 5 / 2 / 3 | 5 / 2 / 9 | 5 / 2 / 23 | 4 / 1 / 18 | 1 / 1 / 5 | no / no / no | 836→831 / 904→902 / 916→913 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 0.037·0.000·0.000 / 0.015·0.000·0.000 / 0.019·0.000·0.000 | 10 / 2 / 3 | 40/0 (75) / 15/2 (75) / 26/0 (77) | 0·209 / 0·196 / 0·353 | 3934·2·651·0.858·3.06 / 3620·0·995·0.784·3.08 / 3484·10·595·0.855·2.73 | 455 (0.929) / 452 (0.810) / 405 (0.957) | 2798 · 0 / 2798 · 0 / 2798 · 0 | 1.133 / 1.148 / 1.170 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/277 / 0 · 18/270 / 0 · 22/281 | 0 · 4/277 / 0 · 26/270 / 0 · 31/281 | 0.544·0.544·0.544 / 0.542·0.542·0.542 / 0.556·0.556·0.556 | 17 / 11 / 7 | 71/2 (75) / 70/2 (75) / 95/0 (77) | 0·0 / 0·0 / 0·0 | 4132·44·1238·0.771·3.61 / 3735·46·2481·0.604·4.17 / 3648·76·1256·0.748·3.32 | 6769 (0.867) / 6093 (0.792) / 6199 (0.854) | 0 · 0 / 0 · 0 / 0 · 0 | 2.064 / 2.013 / 2.298 (1.82 / 1.75 / 1.96) |
| H2loc | 3 · 2/236 / 0 · 0/234 / 0 · 16/225 | 0 · 3/239 / 2 · 3/232 / 1 · 14/224 | 0.190·0.185·0.190 / 0.225·0.225·0.225 / 0.148·0.144·0.146 | 5 / 4 / 0 | 36/1 (75) / 19/2 (75) / 29/0 (77) | 2·2 / 0·0 / 2·2 | 3936·2·389·0.910·2.88 / 3613·1·388·0.903·2.67 / 3476·2·420·0.892·2.60 | 1635 (0.936) / 1564 (0.938) / 1594 (0.937) | 1941 · 0 / 1873 · 0 / 1855 · 0 | 1.232 / 1.716 / 1.609 (1.09 / 1.49 / 1.38) |
| 4bp | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 0.037·0.000·0.000 / 0.015·0.000·0.000 / 0.019·0.000·0.000 | 10 / 2 / 3 | 40/0 (75) / 15/2 (75) / 26/0 (77) | 0·209 / 0·196 / 0·353 | 3934·2·651·0.858·3.06 / 3620·0·995·0.784·3.08 / 3484·10·595·0.855·2.73 | 455 (0.929) / 452 (0.810) / 405 (0.957) | 2798 · 0 / 2798 · 0 / 2798 · 0 | 1.111 / 1.156 / 1.177 (0.98 / 1.01 / 1.01) |
| H2loc+4bp | 3 · 2/236 / 0 · 2/234 / 4 · 17/221 | 0 · 2/239 / 2 · 3/232 / 1 · 18/224 | 0.190·0.185·0.190 / 0.225·0.225·0.225 / 0.148·0.144·0.146 | 5 / 4 / 0 | 37/1 (75) / 19/2 (75) / 27/0 (77) | 2·2 / 0·0 / 2·2 | 3919·2·387·0.910·2.87 / 3586·1·382·0.904·2.65 / 3463·2·422·0.891·2.59 | 1659 (0.937) / 1526 (0.937) / 1584 (0.938) | 1935 · 0 / 1879 · 0 / 1855 · 0 | 1.307 / 1.675 / 1.605 (1.15 / 1.46 / 1.37) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 10063·2·915·0; co_semantica 615·0·1·0; dmn_synthesized 235·0·13·0; pmi_hebbiano 72·10·1221·55; sinonimo_explicito 53·0·30·6 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | CCC 7/7/7·5/6/9 / CCC 7/8/8·0/0/0 / CCC 12/10/13·3/3/3 | co_ocurrencia 9888·8·2037·0; co_semantica 615·0·24·1; dmn_synthesized 893·0·111·3; pmi_hebbiano 66·158·2437·135; sinonimo_explicito 53·0·192·35 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | CCC 4/4/4·5/5/5 / CCC 4/5/4·0/0/2 / CCC 9/10/8·0/0/11 | co_ocurrencia 10089·5·717·0; co_semantica 615·0·9·0; dmn_synthesized 219·0·14·0; pmi_hebbiano 74·0·369·16; sinonimo_explicito 28·0·61·11 | 1566/1911 · 0/0 / 1492/1833 · 0/0 / 1486/1840 · 0/0 |
| 4bp | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 10063·2·915·0; co_semantica 615·0·1·0; dmn_synthesized 235·0·13·0; pmi_hebbiano 72·10·1221·55; sinonimo_explicito 53·0·30·6 | 0/0 · 11986/13488 / 0/0 · 11986/13488 / 0/0 · 11986/13488 |
| H2loc+4bp | CCC 4/4/4·6/6/6 / CCC 5/5/4·3/3/4 / CCC 9/9/7·0/4/7 | co_ocurrencia 10089·5·719·0; co_semantica 615·0·9·0; dmn_synthesized 162·0·8·0; pmi_hebbiano 74·0·368·16; sinonimo_explicito 28·0·61·10 | 1564/1912 · 15832/17850 / 1496/1841 · 16868/18941 / 1484/1838 · 16964/18984 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | no cumplido | referencia (= T) | no cumplido | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido | no cumplido | cumplido | no cumplido | no cumplido | cumplido (vacuo) |
| H2loc | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido |
| 4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | no cumplido | cumplido | cumplido | no cumplido |
| H2loc+4bp | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido |

### real · |D| = 2400 · reloj diario — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 0 / 0 / 0 | 0 / 0 / 0 | 2 / 1 / 2 | 0 / 0 / 0 | 2 / 1 / 2 | sí / sí / sí | 0→0 / 0→0 / 0→0 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 2 / 1 / 2 | 0 / 0 / 0 | 2 / 1 / 2 | sí / sí / sí | 0→0 / 0→0 / 0→0 |
| H2loc | 0 / 0 / 0 | 0 / 0 / 2 | 0 / 1 / 2 | 0 / 0 / 0 | 0 / 1 / 2 | sí / sí / no | 0→0 / 0→0 / 0→0 |
| 4bp | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 2 | 0 / 0 / 0 | 1 / 1 / 2 | sí / sí / sí | 0→0 / 0→0 / 0→0 |
| H2loc+4bp | 0 / 0 / 0 | 0 / 0 / 1 | 0 / 1 / 2 | 0 / 0 / 0 | 0 / 1 / 2 | sí / sí / no | 0→0 / 0→0 / 0→0 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 19 / 14 / 7 | 89/0 (75) / 70/5 (75) / 67/0 (77) | 0·0 / 0·0 / 0·0 | 4092·2·893·0.821·3.33 / 3779·0·1324·0.741·3.40 / 3671·13·532·0.874·2.81 | 1017 (0.933) / 987 (0.919) / 985 (0.967) | 68 · 2482 / 68 · 2482 / 68 · 2482 | 1.871 / 1.931 / 1.895 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 19 / 14 / 7 | 89/0 (75) / 70/5 (75) / 67/0 (77) | 0·0 / 0·0 / 0·0 | 4117·2·905·0.820·3.35 / 3786·0·1350·0.737·3.42 / 3687·13·550·0.871·2.83 | 1017 (0.933) / 987 (0.919) / 985 (0.967) | 0 · 2550 / 0 · 2550 / 0 · 2550 | 2.233 / 1.974 / 1.924 (1.19 / 1.02 / 1.02) |
| H2loc | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 7 / 7 / 1 | 51/0 (75) / 36/2 (75) / 34/0 (77) | 0·0 / 0·0 / 0·0 | 4021·2·369·0.916·2.93 / 3721·0·302·0.925·2.68 / 3547·6·319·0.918·2.58 | 502 (0.973) / 518 (0.968) / 425 (0.988) | 1568 · 1206 / 1553 · 1221 / 1553 · 1240 | 1.014 / 1.154 / 1.011 (0.54 / 0.6 / 0.53) |
| 4bp | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 15 / 10 / 5 | 59/0 (75) / 55/5 (75) / 52/0 (77) | 0·0 / 0·0 / 0·0 | 3902·2·873·0.817·3.19 / 3607·0·1288·0.737·3.26 / 3471·10·541·0.866·2.68 | 906 (0.949) / 860 (0.930) / 851 (0.966) | 68 · 2532 / 68 · 2532 / 68 · 2532 | 1.788 / 1.870 / 1.873 (0.96 / 0.97 / 0.99) |
| H2loc+4bp | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 7 / 5 / 1 | 28/0 (75) / 21/2 (75) / 27/0 (77) | 0·0 / 0·0 / 0·0 | 3891·2·352·0.917·2.83 / 3608·0·409·0.898·2.68 / 3445·6·310·0.918·2.51 | 403 (0.973) / 408 (0.967) / 360 (0.989) | 1593 · 1207 / 1588 · 1216 / 1571 · 1242 | 1.032 / 1.138 / 0.950 (0.55 / 0.59 / 0.5) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | CCC 5/5/5·16/16/16 / CCC 8/8/12·17/15/16 / CCC 2/4/2·3/3/3 | co_ocurrencia 10005·2·1152·0; co_semantica 615·0·5·0; dmn_synthesized 815·0·96·2; pmi_hebbiano 54·13·1376·60; sinonimo_explicito 53·0·46·12 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | CCC 5/5/5·3/3/3 / CCC 5/5/6·1/1/1 / CCC 7/7/7·6/6/6 | co_ocurrencia 9999·2·1176·0; co_semantica 615·0·5·1; dmn_synthesized 867·0·124·4; pmi_hebbiano 56·13·1377·60; sinonimo_explicito 53·0·46·12 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 10059·2·665·0; co_semantica 615·0·3·0; dmn_synthesized 537·0·43·3; pmi_hebbiano 50·6·239·12; sinonimo_explicito 28·0·21·4 | 1262/1561 · 0/0 / 1249/1541 · 0/0 / 1232/1533 · 0/0 |
| 4bp | CCC 3/3/3·0/0/0 / ––C 0/0/7·2/2/2 / CCC 4/6/4·0/1/6 | co_ocurrencia 10004·2·1116·0; co_semantica 615·0·5·0; dmn_synthesized 253·0·12·0; pmi_hebbiano 55·10·1439·75; sinonimo_explicito 53·0·43·12 | 0/0 · 7113/8863 / 0/0 · 7113/8863 / 0/0 · 7113/8863 |
| H2loc+4bp | ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 / ––– 0/0/0·0/0/0 | co_ocurrencia 10021·2·676·0; co_semantica 615·0·3·0; dmn_synthesized 160·0·10·0; pmi_hebbiano 120·6·341·19; sinonimo_explicito 28·0·19·3 | 1281/1582 · 3819/4772 / 1275/1571 · 3901/4869 / 1253/1564 · 3932/4868 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | cumplido (vacuo) | referencia (= T) | cumplido (vacuo) | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido (vacuo) | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | cumplido | cumplido |
| H2loc | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | no cumplido | no cumplido |
| 4bp | cumplido (vacuo) | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | no cumplido | no cumplido |
| H2loc+4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | no cumplido | no cumplido |

### real · K8: desde DB vacía (sesiones de 5 mezcladas, reloj diario, 320 D + 80 I0)

| semilla · brazo | ciclos | dormidos H2/H2-local · peso propio | dormidos > 1 vez | Δestado / Δimportancia D | activos al final |
|---|---|---|---|---|---|
| s11|T | 80 | 5 · 345 | 0 | 0 / 16 | 50 |
| s23|T | 80 | 5 · 345 | 0 | 0 / 16 | 50 |
| s7|T | 80 | 5 · 345 | 0 | 0 / 16 | 50 |
| s11|-H2-4b | 80 | 0 · 350 | 0 | 0 / 0 | 50 |
| s23|-H2-4b | 80 | 0 · 350 | 0 | 0 / 0 | 50 |
| s7|-H2-4b | 80 | 0 · 350 | 0 | 0 / 0 | 50 |
| s11|H2loc | 80 | 184 · 192 | 0 | 0 / 11 | 24 |
| s23|H2loc | 80 | 193 · 181 | 0 | 0 / 11 | 26 |
| s7|H2loc | 80 | 184 · 190 | 0 | 0 / 0 | 26 |
| s11|4bp | 80 | 5 · 350 | 0 | 0 / 1 | 45 |
| s23|4bp | 80 | 5 · 350 | 0 | 0 / 1 | 45 |
| s7|4bp | 80 | 5 · 350 | 0 | 0 / 1 | 45 |
| s11|H2loc+4bp | 80 | 185 · 193 | 0 | 0 / 0 | 22 |
| s23|H2loc+4bp | 80 | 193 · 184 | 0 | 0 / 0 | 23 |
| s7|H2loc+4bp | 80 | 184 · 193 | 0 | 0 / 0 | 23 |

### real · K7′, K8, K9

| brazo | K7′ comprimido | K7′ diario | K8 | K9 |
|---|---|---|---|---|
| T | no cumplido | cumplido | no cumplido | futuro (suite completa: autorización aparte) |
| -H2-4b | no cumplido | no cumplido | cumplido | futuro (suite completa: autorización aparte) |
| H2loc | no cumplido | no cumplido | no cumplido | futuro (suite completa: autorización aparte) |
| 4bp | no cumplido | no cumplido | no cumplido | futuro (suite completa: autorización aparte) |
| H2loc+4bp | no cumplido | no cumplido | cumplido | futuro (suite completa: autorización aparte) |

## Configuración «ctl» (BIORAG_NEURONA=0 en toda la corrida; PPMI 0,15; corte tras D)


### ctl · |D| = 800 · reloj comprimido — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 101 / 101 / 101 | 149 / 149 / 149 | 41 / 40 / 52 | 38 / 38 / 51 | 3 / 2 / 1 | no / no / no | 101→0 / 101→0 / 101→0 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 2 / 1 | 0 / 0 / 0 | 3 / 2 / 1 | sí / sí / sí | 800→800 / 800→800 / 800→800 |
| H2loc | 2 / 0 / 3 | 1 / 1 / 3 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / no / no | 299→297 / 288→288 / 332→329 |
| 4bp | 101 / 101 / 101 | 149 / 149 / 149 | 41 / 40 / 52 | 38 / 38 / 51 | 3 / 2 / 1 | no / no / no | 101→0 / 101→0 / 101→0 |
| H2loc+4bp | 2 / 0 / 3 | 1 / 1 / 3 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / no / no | 299→297 / 288→288 / 332→329 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 0.071·0.000·0.000 / 0.056·0.000·0.000 / 0.092·0.000·0.000 | 11 / 11 / 8 | 19/0 (18) / 30/2 (46) / 43/0 (26) | 0·228 / 0·287 / 0·168 | 1282·6·211·0.859·3.00 / 1222·28·349·0.782·3.20 / 1098·0·183·0.857·2.56 | 494 (0.969) / 307 (0.679) / 400 (0.887) | 817 · 0 / 817 · 0 / 817 · 0 | 0.152 / 0.160 / 0.163 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/272 / 0 · 0/275 / 0 · 0/271 | 0 · 0/272 / 0 · 3/275 / 0 · 2/271 | 0.535·0.535·0.535 / 0.544·0.544·0.542 / 0.535·0.535·0.535 | 9 / 9 / 11 | 14/0 (18) / 19/0 (46) / 26/0 (26) | 0·0 / 0·0 / 0·0 | 1347·13·240·0.850·3.20 / 1237·32·555·0.696·3.65 / 1171·16·427·0.735·3.23 | 2262 (0.899) / 2102 (0.843) / 2013 (0.856) | 0 · 0 / 0 · 0 / 0 · 0 | 0.206 / 0.222 / 0.231 (1.36 / 1.39 / 1.42) |
| H2loc | 2 · 0/214 / 0 · 0/204 / 2 · 0/225 | 0 · 0/216 / 4 · 4/200 / 4 · 0/223 | 0.217·0.217·0.217 / 0.227·0.227·0.223 / 0.219·0.215·0.215 | 10 / 5 / 3 | 3/0 (18) / 8/1 (46) / 21/0 (26) | 0·0 / 0·0 / 0·0 | 1267·4·126·0.910·2.79 / 1212·8·205·0.856·2.85 / 1101·0·86·0.927·2.37 | 601 (0.923) / 504 (0.884) / 556 (0.964) | 637 · 0 / 630 · 0 / 590 · 0 | 0.164 / 0.188 / 0.178 (1.08 / 1.18 / 1.09) |
| 4bp | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 40 · 0/0 / 38 · 0/0 / 52 · 0/0 | 0.071·0.000·0.000 / 0.056·0.000·0.000 / 0.092·0.000·0.000 | 11 / 11 / 8 | 19/0 (18) / 30/2 (46) / 43/0 (26) | 0·228 / 0·287 / 0·168 | 1282·6·211·0.859·3.00 / 1222·28·349·0.782·3.20 / 1098·0·183·0.857·2.56 | 494 (0.969) / 307 (0.679) / 400 (0.887) | 817 · 0 / 817 · 0 / 817 · 0 | 0.146 / 0.167 / 0.159 (0.96 / 1.04 / 0.98) |
| H2loc+4bp | 2 · 0/214 / 0 · 0/204 / 2 · 0/225 | 0 · 0/216 / 4 · 4/200 / 4 · 0/223 | 0.217·0.217·0.217 / 0.227·0.227·0.223 / 0.219·0.215·0.215 | 10 / 5 / 3 | 3/0 (18) / 8/1 (46) / 21/0 (26) | 0·0 / 0·0 / 0·0 | 1267·4·126·0.910·2.79 / 1212·8·205·0.856·2.85 / 1101·0·86·0.927·2.37 | 601 (0.923) / 504 (0.884) / 556 (0.964) | 637 · 0 / 630 · 0 / 590 · 0 | 0.163 / 0.165 / 0.163 (1.07 / 1.03 / 1.0) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | sin tabla / sin tabla / sin tabla | co_ocurrencia 3213·8·290·0; co_semantica 247·0·3·0; dmn_synthesized 97·0·8·0; pmi_hebbiano 35·26·390·24; sinonimo_explicito 10·0·23·5 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | sin tabla / sin tabla / sin tabla | co_ocurrencia 3203·8·445·0; co_semantica 247·0·5·0; dmn_synthesized 255·1·56·11; pmi_hebbiano 40·52·609·27; sinonimo_explicito 10·0·62·7 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | sin tabla / sin tabla / sin tabla | co_ocurrencia 3222·4·240·0; co_semantica 247·0·2·0; dmn_synthesized 75·0·16·0; pmi_hebbiano 29·8·128·5; sinonimo_explicito 7·0·24·2 | 501/619 · 0/0 / 512/620 · 0/0 / 468/580 · 0/0 |
| 4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 3213·8·290·0; co_semantica 247·0·3·0; dmn_synthesized 97·0·8·0; pmi_hebbiano 35·26·390·24; sinonimo_explicito 10·0·23·5 | 0/0 · 3440/3831 / 0/0 · 3440/3831 / 0/0 · 3440/3831 |
| H2loc+4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 3222·4·240·0; co_semantica 247·0·2·0; dmn_synthesized 75·0·16·0; pmi_hebbiano 29·8·128·5; sinonimo_explicito 7·0·24·2 | 501/619 · 4395/4724 / 512/620 · 4449/4820 / 468/580 · 4799/5155 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | no cumplido | referencia (= T) | no cumplido | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido | no cumplido | cumplido | no cumplido | no cumplido | cumplido (vacuo) |
| H2loc | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido | no cumplido | no cumplido | no cumplido |
| 4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | no cumplido | cumplido | cumplido | no cumplido |
| H2loc+4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido | no cumplido | no cumplido | no cumplido |

### ctl · |D| = 800 · reloj diario — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 3 / 1 | 0 / 0 / 0 | 3 / 3 / 1 | sí / sí / sí | 200→200 / 200→200 / 200→200 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 3 / 1 | 0 / 0 / 0 | 3 / 3 / 1 | sí / sí / sí | 200→200 / 200→200 / 200→200 |
| H2loc | 1 / 0 / 1 | 1 / 0 / 1 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / sí / no | 94→93 / 94→94 / 102→101 |
| 4bp | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 2 / 1 | 0 / 0 / 0 | 3 / 2 / 1 | sí / sí / sí | 150→150 / 150→150 / 150→150 |
| H2loc+4bp | 1 / 0 / 1 | 1 / 0 / 1 | 3 / 2 / 3 | 1 / 0 / 2 | 2 / 2 / 1 | no / sí / no | 71→70 / 73→73 / 77→76 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 0 · 0/79 / 0 · 1/72 / 0 · 0/88 | 0 · 1/79 / 0 · 9/72 / 0 · 3/88 | 0.152·0.152·0.152 / 0.123·0.123·0.121 / 0.156·0.156·0.156 | 7 / 10 / 9 | 15/0 (18) / 21/0 (46) / 42/0 (26) | 0·0 / 0·0 / 0·0 | 1328·13·277·0.829·3.24 / 1244·32·446·0.741·3.44 / 1152·0·308·0.789·2.92 | 950 (0.906) / 823 (0.894) / 791 (0.904) | 68 · 532 / 68 · 532 / 68 · 532 | 0.292 / 0.299 / 0.290 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/79 / 0 · 1/72 / 0 · 0/88 | 0 · 0/79 / 0 · 9/72 / 0 · 3/88 | 0.152·0.152·0.152 / 0.123·0.123·0.121 / 0.156·0.156·0.156 | 7 / 10 / 9 | 15/0 (18) / 21/0 (46) / 42/0 (26) | 0·0 / 0·0 / 0·0 | 1355·13·223·0.860·3.18 / 1244·32·484·0.725·3.52 / 1171·0·344·0.773·3.03 | 959 (0.921) / 823 (0.886) / 791 (0.903) | 0 · 600 / 0 · 600 / 0 · 600 | 0.456 / 0.315 / 0.322 (1.56 / 1.05 / 1.11) |
| H2loc | 2 · 0/67 / 0 · 0/61 / 2 · 0/79 | 0 · 1/69 / 0 · 2/61 / 4 · 0/77 | 0.077·0.077·0.077 / 0.073·0.073·0.073 / 0.069·0.065·0.065 | 5 / 4 / 3 | 5/0 (18) / 13/1 (46) / 22/0 (26) | 0·0 / 0·0 / 0·0 | 1300·4·155·0.894·2.92 / 1240·9·191·0.867·2.88 / 1117·0·96·0.921·2.43 | 473 (0.956) / 397 (0.898) / 376 (0.984) | 540 · 275 / 522 · 287 / 515 · 293 | 0.201 / 0.214 / 0.206 (0.69 / 0.72 / 0.71) |
| 4bp | 0 · 0/58 / 0 · 0/52 / 0 · 0/71 | 0 · 1/58 / 0 · 3/52 / 0 · 3/71 | 0.108·0.108·0.108 / 0.081·0.081·0.081 / 0.125·0.125·0.125 | 17 / 10 / 10 | 15/0 (18) / 21/2 (46) / 42/0 (26) | 0·0 / 0·0 / 0·0 | 1283·12·240·0.844·3.07 / 1222·28·433·0.743·3.37 / 1105·0·282·0.797·2.77 | 836 (0.918) / 707 (0.883) / 701 (0.907) | 68 · 582 / 68 · 582 / 68 · 582 | 0.276 / 0.294 / 0.287 (0.95 / 0.99 / 0.99) |
| H2loc+4bp | 2 · 0/45 / 0 · 0/43 / 2 · 0/62 | 0 · 0/47 / 0 · 5/43 / 4 · 0/60 | 0.044·0.044·0.044 / 0.054·0.054·0.050 / 0.058·0.054·0.054 | 15 / 5 / 3 | 4/0 (18) / 18/1 (46) / 22/0 (26) | 0·0 / 0·0 / 0·0 | 1266·4·137·0.903·2.81 / 1211·9·193·0.863·2.83 / 1101·0·111·0.908·2.42 | 371 (0.961) / 357 (0.911) / 333 (0.988) | 552 · 293 / 524 · 307 / 512 · 321 | 0.195 / 0.213 / 0.212 (0.67 / 0.71 / 0.73) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | sin tabla / sin tabla / sin tabla | co_ocurrencia 3206·8·363·0; co_semantica 247·0·3·0; dmn_synthesized 224·1·41·5; pmi_hebbiano 37·36·554·21; sinonimo_explicito 10·0·38·6 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | sin tabla / sin tabla / sin tabla | co_ocurrencia 3209·8·372·0; co_semantica 247·0·3·0; dmn_synthesized 265·1·58·11; pmi_hebbiano 39·36·533·20; sinonimo_explicito 10·0·48·6 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | sin tabla / sin tabla / sin tabla | co_ocurrencia 3220·4·236·0; co_semantica 247·0·2·0; dmn_synthesized 154·0·24·1; pmi_hebbiano 29·9·145·10; sinonimo_explicito 7·0·22·2 | 431/539 · 0/0 / 418/514 · 0/0 / 405/503 · 0/0 |
| 4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 3206·8·360·0; co_semantica 247·0·3·0; dmn_synthesized 110·0·9·0; pmi_hebbiano 37·32·520·19; sinonimo_explicito 10·0·38·6 | 0/0 · 2313/2863 / 0/0 · 2313/2863 / 0/0 · 2313/2863 |
| H2loc+4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 3223·4·235·0; co_semantica 247·0·2·0; dmn_synthesized 72·0·4·0; pmi_hebbiano 29·9·167·9; sinonimo_explicito 7·0·22·2 | 436/546 · 1257/1539 / 420/518 · 1309/1620 / 402/501 · 1319/1626 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | cumplido | referencia (= T) | cumplido | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido | cumplido | cumplido | no cumplido | no cumplido | cumplido |
| H2loc | no cumplido | no cumplido | cumplido | no cumplido | no cumplido | no cumplido |
| 4bp | cumplido | no cumplido | cumplido | no cumplido | no cumplido | no cumplido |
| H2loc+4bp | no cumplido | no cumplido | cumplido | no cumplido | no cumplido | no cumplido |

### ctl · |D| = 2400 · reloj comprimido — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 97 / 97 / 97 | 162 / 162 / 162 | 19 / 8 / 11 | 18 / 8 / 9 | 1 / 0 / 2 | no / no / no | 97→0 / 97→0 / 97→0 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 0 / 5 | 0 / 0 / 0 | 3 / 0 / 5 | sí / sí / sí | 2400→2400 / 2400→2400 / 2400→2400 |
| H2loc | 5 / 2 / 5 | 834 / 912 / 918 | 4 / 0 / 8 | 3 / 0 / 5 | 1 / 0 / 3 | no / no / no | 834→829 / 908→906 / 914→913 |
| 4bp | 97 / 97 / 97 | 162 / 162 / 162 | 19 / 8 / 11 | 18 / 8 / 9 | 1 / 0 / 2 | no / no / no | 97→0 / 97→0 / 97→0 |
| H2loc+4bp | 5 / 2 / 3 | 5 / 2 / 9 | 4 / 0 / 8 | 3 / 0 / 5 | 1 / 0 / 3 | no / no / no | 836→831 / 904→902 / 916→913 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 0.037·0.000·0.000 / 0.015·0.000·0.000 / 0.019·0.000·0.000 | 10 / 2 / 3 | 40/0 (75) / 15/2 (75) / 26/0 (77) | 0·209 / 0·196 / 0·353 | 3934·2·651·0.858·3.06 / 3620·0·995·0.784·3.08 / 3484·10·595·0.855·2.73 | 455 (0.929) / 452 (0.810) / 405 (0.957) | 2798 · 0 / 2798 · 0 / 2798 · 0 | 0.196 / 0.200 / 0.196 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/277 / 0 · 0/270 / 0 · 4/281 | 0 · 3/277 / 0 · 6/270 / 0 · 1/281 | 0.544·0.544·0.544 / 0.542·0.542·0.542 / 0.556·0.556·0.556 | 17 / 11 / 7 | 71/2 (75) / 70/2 (75) / 95/0 (77) | 0·0 / 0·0 / 0·0 | 4132·44·1238·0.771·3.61 / 3735·46·2481·0.604·4.17 / 3648·76·1256·0.748·3.32 | 6769 (0.867) / 6093 (0.792) / 6199 (0.854) | 0 · 0 / 0 · 0 / 0 · 0 | 0.449 / 0.475 / 0.459 (2.29 / 2.38 / 2.34) |
| H2loc | 3 · 1/236 / 0 · 0/234 / 0 · 6/225 | 0 · 2/239 / 2 · 2/232 / 1 · 2/224 | 0.190·0.185·0.190 / 0.225·0.225·0.225 / 0.148·0.144·0.146 | 5 / 4 / 0 | 36/1 (75) / 19/2 (75) / 29/0 (77) | 2·2 / 0·0 / 2·2 | 3936·2·389·0.910·2.88 / 3613·1·388·0.903·2.67 / 3476·2·420·0.892·2.60 | 1635 (0.936) / 1564 (0.938) / 1594 (0.937) | 1941 · 0 / 1873 · 0 / 1855 · 0 | 0.311 / 0.320 / 0.323 (1.59 / 1.6 / 1.65) |
| 4bp | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 18 · 0/0 / 7 · 0/0 / 10 · 0/0 | 0.037·0.000·0.000 / 0.015·0.000·0.000 / 0.019·0.000·0.000 | 10 / 2 / 3 | 40/0 (75) / 15/2 (75) / 26/0 (77) | 0·209 / 0·196 / 0·353 | 3934·2·651·0.858·3.06 / 3620·0·995·0.784·3.08 / 3484·10·595·0.855·2.73 | 455 (0.929) / 452 (0.810) / 405 (0.957) | 2798 · 0 / 2798 · 0 / 2798 · 0 | 0.199 / 0.208 / 0.204 (1.02 / 1.04 / 1.04) |
| H2loc+4bp | 3 · 1/236 / 0 · 0/234 / 4 · 2/221 | 0 · 2/239 / 2 · 2/232 / 1 · 2/224 | 0.190·0.185·0.190 / 0.225·0.225·0.225 / 0.148·0.144·0.146 | 5 / 4 / 0 | 37/1 (75) / 19/2 (75) / 27/0 (77) | 2·2 / 0·0 / 2·2 | 3919·2·387·0.910·2.87 / 3586·1·382·0.904·2.65 / 3463·2·422·0.891·2.59 | 1659 (0.937) / 1526 (0.937) / 1584 (0.938) | 1935 · 0 / 1879 · 0 / 1855 · 0 | 0.279 / 0.296 / 0.302 (1.43 / 1.48 / 1.54) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | sin tabla / sin tabla / sin tabla | co_ocurrencia 10063·2·915·0; co_semantica 615·0·1·0; dmn_synthesized 235·0·13·0; pmi_hebbiano 72·10·1221·55; sinonimo_explicito 53·0·30·6 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | sin tabla / sin tabla / sin tabla | co_ocurrencia 9888·8·2037·0; co_semantica 615·0·24·1; dmn_synthesized 893·0·111·3; pmi_hebbiano 66·158·2437·135; sinonimo_explicito 53·0·192·35 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | sin tabla / sin tabla / sin tabla | co_ocurrencia 10089·5·717·0; co_semantica 615·0·9·0; dmn_synthesized 219·0·14·0; pmi_hebbiano 74·0·369·16; sinonimo_explicito 28·0·61·11 | 1566/1911 · 0/0 / 1492/1833 · 0/0 / 1486/1840 · 0/0 |
| 4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 10063·2·915·0; co_semantica 615·0·1·0; dmn_synthesized 235·0·13·0; pmi_hebbiano 72·10·1221·55; sinonimo_explicito 53·0·30·6 | 0/0 · 11986/13488 / 0/0 · 11986/13488 / 0/0 · 11986/13488 |
| H2loc+4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 10089·5·719·0; co_semantica 615·0·9·0; dmn_synthesized 162·0·8·0; pmi_hebbiano 74·0·368·16; sinonimo_explicito 28·0·61·10 | 1564/1912 · 15832/17850 / 1496/1841 · 16868/18941 / 1484/1838 · 16964/18984 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | no cumplido | referencia (= T) | no cumplido | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido | no cumplido | cumplido | no cumplido | no cumplido | cumplido (vacuo) |
| H2loc | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido |
| 4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | no cumplido | cumplido | cumplido | no cumplido |
| H2loc+4bp | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido | no cumplido |

### ctl · |D| = 2400 · reloj diario — semillas 7 / 11 / 23

| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |
|---|---|---|---|---|---|---|---|
| T | 0 / 0 / 0 | 0 / 0 / 0 | 2 / 1 / 2 | 0 / 0 / 0 | 2 / 1 / 2 | sí / sí / sí | 0→0 / 0→0 / 0→0 |
| -H2-4b | 0 / 0 / 0 | 0 / 0 / 0 | 2 / 1 / 2 | 0 / 0 / 0 | 2 / 1 / 2 | sí / sí / sí | 0→0 / 0→0 / 0→0 |
| H2loc | 0 / 0 / 0 | 0 / 0 / 2 | 0 / 1 / 2 | 0 / 0 / 0 | 0 / 1 / 2 | sí / sí / no | 0→0 / 0→0 / 0→0 |
| 4bp | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 2 | 0 / 0 / 0 | 1 / 1 / 2 | sí / sí / sí | 0→0 / 0→0 / 0→0 |
| H2loc+4bp | 0 / 0 / 0 | 0 / 0 / 1 | 0 / 1 / 2 | 0 / 0 / 0 | 0 / 1 / 2 | sí / sí / no | 0→0 / 0→0 / 0→0 |

| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |
|---|---|---|---|---|---|---|---|---|---|---|
| T | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 19 / 14 / 7 | 89/0 (75) / 70/5 (75) / 67/0 (77) | 0·0 / 0·0 / 0·0 | 4092·2·893·0.821·3.33 / 3779·0·1324·0.741·3.40 / 3671·13·532·0.874·2.81 | 1017 (0.933) / 987 (0.919) / 985 (0.967) | 68 · 2482 / 68 · 2482 / 68 · 2482 | 0.456 / 0.496 / 0.557 (1.0 / 1.0 / 1.0) |
| -H2-4b | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 19 / 14 / 7 | 89/0 (75) / 70/5 (75) / 67/0 (77) | 0·0 / 0·0 / 0·0 | 4117·2·905·0.820·3.35 / 3786·0·1350·0.737·3.42 / 3687·13·550·0.871·2.83 | 1017 (0.933) / 987 (0.919) / 985 (0.967) | 0 · 2550 / 0 · 2550 / 0 · 2550 | 0.479 / 0.543 / 0.556 (1.05 / 1.09 / 1.0) |
| H2loc | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 7 / 7 / 1 | 51/0 (75) / 36/2 (75) / 34/0 (77) | 0·0 / 0·0 / 0·0 | 4021·2·369·0.916·2.93 / 3721·0·302·0.925·2.68 / 3547·6·319·0.918·2.58 | 502 (0.973) / 518 (0.968) / 425 (0.988) | 1568 · 1206 / 1553 · 1221 / 1553 · 1240 | 0.351 / 0.371 / 0.377 (0.77 / 0.75 / 0.68) |
| 4bp | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 15 / 10 / 5 | 59/0 (75) / 55/5 (75) / 52/0 (77) | 0·0 / 0·0 / 0·0 | 3902·2·873·0.817·3.19 / 3607·0·1288·0.737·3.26 / 3471·10·541·0.866·2.68 | 906 (0.949) / 860 (0.930) / 851 (0.966) | 68 · 2532 / 68 · 2532 / 68 · 2532 | 0.454 / 0.494 / 0.484 (1.0 / 1.0 / 0.87) |
| H2loc+4bp | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0 · 0/0 / 0 · 0/0 / 0 · 0/0 | 0.000·0.000·0.000 / 0.000·0.000·0.000 / 0.000·0.000·0.000 | 7 / 5 / 1 | 28/0 (75) / 21/2 (75) / 27/0 (77) | 0·0 / 0·0 / 0·0 | 3891·2·352·0.917·2.83 / 3608·0·409·0.898·2.68 / 3445·6·310·0.918·2.51 | 403 (0.973) / 408 (0.967) / 360 (0.989) | 1593 · 1207 / 1588 · 1216 / 1571 · 1242 | 0.313 / 0.348 / 0.333 (0.69 / 0.7 / 0.6) |

Neurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1 (suma de semillas; tema/puente/accidental/ajeno):

| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |
|---|---|---|---|
| T | sin tabla / sin tabla / sin tabla | co_ocurrencia 10005·2·1152·0; co_semantica 615·0·5·0; dmn_synthesized 815·0·96·2; pmi_hebbiano 54·13·1376·60; sinonimo_explicito 53·0·46·12 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| -H2-4b | sin tabla / sin tabla / sin tabla | co_ocurrencia 9999·2·1176·0; co_semantica 615·0·5·1; dmn_synthesized 867·0·124·4; pmi_hebbiano 56·13·1377·60; sinonimo_explicito 53·0·46·12 | 0/0 · 0/0 / 0/0 · 0/0 / 0/0 · 0/0 |
| H2loc | sin tabla / sin tabla / sin tabla | co_ocurrencia 10059·2·665·0; co_semantica 615·0·3·0; dmn_synthesized 537·0·43·3; pmi_hebbiano 50·6·239·12; sinonimo_explicito 28·0·21·4 | 1262/1561 · 0/0 / 1249/1541 · 0/0 / 1232/1533 · 0/0 |
| 4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 10004·2·1116·0; co_semantica 615·0·5·0; dmn_synthesized 253·0·12·0; pmi_hebbiano 55·10·1439·75; sinonimo_explicito 53·0·43·12 | 0/0 · 7113/8863 / 0/0 · 7113/8863 / 0/0 · 7113/8863 |
| H2loc+4bp | sin tabla / sin tabla / sin tabla | co_ocurrencia 10021·2·676·0; co_semantica 615·0·3·0; dmn_synthesized 160·0·10·0; pmi_hebbiano 120·6·341·19; sinonimo_explicito 28·0·19·3 | 1281/1582 · 3819/4772 / 1275/1571 · 3901/4869 / 1253/1564 · 3932/4868 |

Veredictos de este bloque:

K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones de I′ no legítimas) e inserciones de I0 no mayores que en T.

| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |
|---|---|---|---|---|---|---|
| T | cumplido (vacuo) | referencia (= T) | cumplido (vacuo) | referencia (= T) | referencia (= T) | no cumplido |
| -H2-4b | cumplido (vacuo) | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | cumplido | cumplido |
| H2loc | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | no cumplido | no cumplido |
| 4bp | cumplido (vacuo) | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | no cumplido | no cumplido |
| H2loc+4bp | no cumplido | cumplido (orden no comparable en 6 de 6 mundos: T sin listas) | cumplido (vacuo) | no cumplido | no cumplido | no cumplido |

### ctl · K8: desde DB vacía (sesiones de 5 mezcladas, reloj diario, 320 D + 80 I0)

| semilla · brazo | ciclos | dormidos H2/H2-local · peso propio | dormidos > 1 vez | Δestado / Δimportancia D | activos al final |
|---|---|---|---|---|---|
| s11|T | 80 | 5 · 345 | 0 | 0 / 16 | 50 |
| s23|T | 80 | 5 · 345 | 0 | 0 / 16 | 50 |
| s7|T | 80 | 5 · 345 | 0 | 0 / 16 | 50 |
| s11|-H2-4b | 80 | 0 · 350 | 0 | 0 / 0 | 50 |
| s23|-H2-4b | 80 | 0 · 350 | 0 | 0 / 0 | 50 |
| s7|-H2-4b | 80 | 0 · 350 | 0 | 0 / 0 | 50 |
| s11|H2loc | 80 | 184 · 192 | 0 | 0 / 11 | 24 |
| s23|H2loc | 80 | 193 · 181 | 0 | 0 / 11 | 26 |
| s7|H2loc | 80 | 184 · 190 | 0 | 0 / 0 | 26 |
| s11|4bp | 80 | 5 · 350 | 0 | 0 / 1 | 45 |
| s23|4bp | 80 | 5 · 350 | 0 | 0 / 1 | 45 |
| s7|4bp | 80 | 5 · 350 | 0 | 0 / 1 | 45 |
| s11|H2loc+4bp | 80 | 185 · 193 | 0 | 0 / 0 | 22 |
| s23|H2loc+4bp | 80 | 193 · 184 | 0 | 0 / 0 | 23 |
| s7|H2loc+4bp | 80 | 184 · 193 | 0 | 0 / 0 | 23 |

### ctl · K7′, K8, K9

| brazo | K7′ comprimido | K7′ diario | K8 | K9 |
|---|---|---|---|---|
| T | no cumplido | cumplido | no cumplido | futuro (suite completa: autorización aparte) |
| -H2-4b | no cumplido | no cumplido | cumplido | futuro (suite completa: autorización aparte) |
| H2loc | no cumplido | no cumplido | no cumplido | futuro (suite completa: autorización aparte) |
| 4bp | no cumplido | no cumplido | no cumplido | futuro (suite completa: autorización aparte) |
| H2loc+4bp | no cumplido | no cumplido | cumplido | futuro (suite completa: autorización aparte) |
