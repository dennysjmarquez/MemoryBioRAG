# Experimento 06: capas de protección y "primero no dañar"

**Objetivo (Dennys):** poder decir "sí, funcional al 100 %". Que haga su trabajo real de neurona y que **toda falla que una neurona puede tener en nuestro sistema** esté cubierta por una capa y por una prueba automática. "Si la capa no existe, se integra y, si no existe la capa que necesitamos, se crea, se inventa." Tu tabla QA es el piso: ninguna categoría puede bajar.

Todo corre sobre copias. No se tocó el snapshot congelado ni la DB viva, y no se borró ningún nodo.

## Mapa de fallas → capa → prueba

Las pruebas viven en `tests/test_neurona.py` (32 pruebas). La suite completa del repo pasa: **378 pruebas** (`resultados/pytest.txt`).

| # | Falla posible | Capa | Prueba |
|---|---|---|---|
| 1 | Baja el recall (saca la respuesta del top-5) | Solo reordena el top-5 que eligió la fórmula | `test_reordenar_solo_permuta_el_top5` |
| 2 | Cambia los números que ven los umbrales (GABA, abstención, FP, certeza) | Mismos nodos, mismos números por posición; **también se permutan los mapas de score del MCP** (hallazgo nuevo, ver abajo) | `test_mcp_ve_los_mismos_numeros_por_posicion` + prueba MCP de punta a punta |
| 3 | Empeora las búsquedas literales | Regla de identidad | `test_regla_de_identidad` |
| 4 | Memoriza en vez de aprender | Guardia del 20 % que nunca se estudia + reinicio anti-memorización | `test_memoriza_lo_estudiado_pero_la_guardia_lo_delata` |
| 5 | Daña una categoría | Piso por categoría (aciertos #1 y MRR) | `test_campeon_que_dana_una_categoria_sube_su_margen_o_se_retira` |
| 6 | **Daña preguntas humanas que el autoexamen no ve** | **Nuevo: margen "primero no dañar"** | `test_primero_no_danar_elige_el_menor_margen_seguro`, `test_el_margen_se_respeta_al_servir` |
| 7 | Campeón que solo empata o solo daña | Debe ganar estrictamente a la fórmula; si no, se retira | `test_campeon_que_solo_dana_se_retira` |
| 8 | La DB cambia y lo aprendido deja de servir | Se recalibra en cada consolidación; si ningún margen lo deja sin dañar, se retira | mismas pruebas 5–7 |
| 9 | Pesos NaN/Inf o que explotan | `_sano` al servir, guardar y cargar | `test_pesos_rotos_no_se_usan_ni_se_cargan` |
| 10 | El entrenamiento diverge | Vuelve a los pesos anteriores | `test_entrenamiento_que_diverge_se_descarta` |
| 11 | Estado guardado corrupto (JSON, blob o margen inválido) | Carga estricta: estado nuevo desde los pesos a mano. Un margen negativo (que la haría *más* atrevida) nunca se acepta | `test_estado_corrupto_arranca_limpio`, `test_el_margen_se_guarda_y_uno_corrupto_no_se_usa` |
| 12 | Cambió la fórmula del motor (otra versión de BioRAG) | Huella del motor por comportamiento: lo viejo se descarta y se reaprende | `test_si_cambia_la_formula_del_motor_se_reaprende` |
| 13 | El autoexamen ensucia el sistema (log, accesos ACT-R, DMN) | Silencio **por hilo** | `test_practica_es_silenciosa`, `test_silencio_es_por_hilo` |
| 14 | Dos prácticas a la vez (DMN + consolidación) | Candado no bloqueante: si está ocupada, se salta el ciclo | `test_dos_practicas_a_la_vez_no_se_bloquean` |
| 15 | Varios procesos sobre la misma DB | Refresco por marca de tiempo, guardado atómico | `test_varios_procesos_sobre_la_misma_db` |
| 16 | Falla repetida que tumba el motor | Disyuntor: tras 3 errores seguidos, pausa | `test_cortacircuitos_tras_tres_fallas`, `test_los_ganchos_nunca_rompen_la_escritura` |
| 17 | El costo crece con los datos | N.º fijo de búsquedas y presupuesto de tiempo por ciclo | `test_numero_de_busquedas_acotado`, `test_presupuesto_de_tiempo` |
| 18 | Un recuerdo acapara el examen | Sin duplicados y tope por recuerdo | `test_un_recuerdo_no_acapara_el_examen` |
| 19 | Recuerdos olvidados siguen en el examen | Purga (muestreo sin reemplazo) | `test_recuerdos_olvidados_salen_del_examen` |
| 20 | DB vacía, de solo lectura o sin datos suficientes | No hay campeón: motor idéntico | `test_db_vacia_no_falla`, `test_db_de_solo_lectura_no_rompe`, `test_sin_datos_suficientes_no_entrena` |
| 21 | Apagado | `BIORAG_NEURONA=0` | `test_apagada` |

## La capa nueva: "primero no dañar" (margen)

**Problema encontrado (v3, sin margen).** Con todas las capas anteriores, en una DB que nunca vio (documentación de Python en español), el examen con **preguntas humanas** empeoró: R@1 de 42.07 a 41.46 (4 casos ganados, 5 perdidos). El piso por categoría no lo detecta, porque mira el autoexamen y no las preguntas humanas.

**Idea.** La neurona solo puede mover un puesto si su ventaja supera un margen ε. A cada puesto de la fórmula se le suma ε·(k − puesto). Así cambia solo donde está segura y la fórmula dudaba.

**El margen lo elige ella sola, en cada consolidación.** Es el **menor** ε de `(0, .25, .5, 1, 1.5, 2, 3, 5, 8)` que cumple todo esto:

- no pierde **ningún** caso de la guardia que la fórmula acertaba;
- en todo el examen pierde menos del 5 % de lo que gana;
- cumple el piso por categoría;
- sigue ganando a la fórmula.

Si ningún ε lo logra, el campeón se retira. No hace falta QA ni configuración: funciona igual con una DB nueva.

Análisis por caso (`margen_por_caso.py`, guardia: ganados / perdidos frente a la fórmula):

| ε | pydocs | snapshot |
|---|---|---|
| 0 | +17 / −1 | +21 / −2 |
| 1 | +9 / −1 | +18 / −2 |
| 1.5 | — | **+15 / −0** |
| 3 | **+6 / −0** | +9 / −0 |

La regla eligió ε = 1.5 en el snapshot y ε = 3 en pydocs (`calibrar_margen.py`).

## Resultados

### QA oficial (921 casos) frente a tu tabla base: R@1 / MRR

| Categoría | Base | v3 (sin margen) | ε = 1.5 fijo | ε = 3 fijo | **v4 (margen automático)** |
|---|---|---|---|---|---|
| cruce_idioma (8) | 62.50 / .740 | 100 / 1.000 | 75.00 / .875 | 62.50 / .792 | **75.00 / .875** |
| dormido (65) | 100 / 1.000 | 100 / 1.000 | 100 / 1.000 | 100 / 1.000 | **100 / 1.000** |
| literal (487) | 99.59 / .998 | 99.79 / .999 | 99.59 / .998 | 99.59 / .998 | **99.59 / .998** |
| por_tema (65) | 63.08 / .772 | 84.62 / .910 | 81.54 / .881 | 73.85 / .832 | **80.00 / .879** |
| pregunta_natural (65) | 93.85 / .964 | 96.92 / .985 | 96.92 / .985 | 96.92 / .985 | **95.38 / .977** |
| sinonimo (55) | 56.36 / .721 | 60.00 / .738 | 61.82 / .744 | 56.36 / .721 | **60.00 / .734** |
| typo (65) | 87.69 / .924 | 98.46 / .992 | 96.92 / .985 | 95.38 / .972 | **96.92 / .982** |
| variante_gramatical (65) | 87.69 / .932 | 92.31 / .958 | 93.85 / .965 | 93.85 / .963 | **93.85 / .959** |
| **Global** | 91.89 / .950 | 95.31 / .971 | 94.86 / .968 | 93.71 / .961 | **94.51 / .966** |

En todas las corridas: R@5 100, FP 0/40, GATE OK. **Ninguna categoría baja de la base.** Las columnas "ε fijo" usan el campeón de v3 (`BIORAG_NEURONA_MARGEN`). La columna v4 es todo el proceso desde cero, con el margen elegido solo. Archivos: `resultados/qa/`.

### Preguntas humanas en una DB que nunca vio (pydocs, 164 preguntas)

| | R@1 | R@5 | MRR | Gana / pierde |
|---|---|---|---|---|
| Pesos a mano | 42.07 | 56.1 | .481 | — |
| v3, sin margen | 41.46 ❌ | 56.1 | .471 | 4 / 5 |
| ε forzado = 1 / 2 / 3 / 5 (campeón v3) | 43.90 / 43.29 / 42.68 / 42.07 | 56.1 | .485 / .484 / .483 / .481 | 4/1, 3/1, 2/1, idéntico |
| **v4, margen automático** | **43.29** ✅ | 56.1 | **.483** | **3 / 1** |

Ninguna pregunta sale del top-5. Queda 1 caso perdido ("¿Podemos deshacernos del *Global Interpreter Lock*?"): es la parte honesta. El margen deja el daño muy por debajo de la ganancia, pero no lo hace cero.

### Uso simulado (v4)

- **Snapshot, 500 consolidaciones:** 20 ascensos, 0 retiros, 45 reinicios anti-memorización. Guardia: a mano 72.5 % → campeón 79.4 %. Margen final ε = 1.0.
- **Pydocs, 585 consolidaciones** (279 al construir + 300 de uso): 22 ascensos, 1 retiro, 37 recuerdos purgados. Guardia 84.1 % → 89.7 %. Termina *tranquila* (techo) con ε = 1.5.
- **Costo por consolidación:** snapshot p50 1.6 s / p95 3.3 s; pydocs p50 0.26 s / p95 0.94 s. Igual que v3: el margen no agrega costo apreciable.

### De punta a punta por el MCP

`mcp_con_y_sin_neurona.py` llama a la herramienta `recordar` del servidor MCP real, sobre una copia de la DB de v4, con 120 consultas del QA. Cada consulta se corre con la neurona apagada, encendida y apagada otra vez (para medir el ruido propio del motor).

| Campeón | Consultas | Ruido | Top-5 reordenado | Violaciones (nombres / números por posición / globales) |
|---|---|---|---|---|
| v2, sin margen (`resultados/mcp_con_y_sin_neurona.json`) | 120 | 0 | 103 | 0 / 0 / 0 |
| **v4, margen automático** (`resultados/v4/mcp_con_y_sin_neurona.json`) | 120 | 0 | **52** | **0 / 0 / 0** |

Con o sin neurona, el MCP devuelve los mismos recuerdos y, en cada posición, los mismos `score_hibrido`, `confianza_calibrada` y `nivel_certeza`, con el mismo `total` y la misma `trazabilidad`. Solo cambia el orden. Con margen, la neurona mueve la mitad de veces: solo donde está segura.

### Neurona cableada sin nada aprendido

Con el código final y el snapshot sin estado de neurona, la QA es **idéntica** a la del código de `master` (worktree sin cambios): R@5 100, R@1 91.89, MRR .950, FP 0/40, GATE OK. Coinciden la tabla completa, el JSON de métricas (solo difieren la hora y la duración) y la lista de casos fallidos **byte a byte**. Archivos: `resultados/qa/qa_base_codigo_master.*` y `resultados/qa/qa_sin_pesos.*`.

Una DB nueva o de un tercero arranca exactamente con el motor de siempre.

## Hallazgos del camino (para el auditor)

1. **Mapas de score del MCP.** Reordenar el top-5 sin permutar `last_score_base_map` y `last_score_bonus_map` cambiaba decisiones del gate del MCP. La QA no pasa por ese camino, por eso no se veía. Corregido con `_permutar_mapas`; la prueba MCP lo cubre.
2. **`consolidar_concepto` deja un INSERT de predicados sin commit** (comportamiento previo del motor). Eso bloquea otras conexiones a la DB. Con la neurona activa, su `_guardar` hace el commit. No se cambió el motor; queda anotado.
3. **Huella del motor.** Los estados guardados por código anterior (sin huella) se descartan y se reaprende desde los pesos a mano. Es lo esperado. Para probar un campeón viejo hay que estampar la huella en una **copia**.
4. **El autoexamen por contenido solo no alcanzó** para las preguntas humanas (v3). Lo que lo arregló fue el margen.
5. **Nota abierta:** la memoria de examen (≈1.5–2 MB) se reescribe en cada ciclo.

## Archivos

| Archivo | Qué es |
|---|---|
| `correr_validacion.sh` | Reproduce todo el experimento (≈1 h, 2 CPUs) sobre copias en `$LAB`. Usa los simuladores del experimento 05. |
| `mcp_con_y_sin_neurona.py` | Corre cada consulta por el MCP real con la neurona apagada / encendida / apagada y compara nombres, números por posición y globales. |
| `margen_por_caso.py`, `calibrar_margen.py`, `_cargar_estado.py` | Diagnóstico de solo lectura del margen sobre un estado guardado. |
| `resultados/qa/` | Salidas completas de `evaluar_qa.py`. |
| `resultados/v3/`, `resultados/v4/` | Curvas de uso, construcción de pydocs, examen humano y prueba MCP. |
