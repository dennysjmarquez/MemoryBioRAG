# E3B4b — diagnóstico de los dos falsos positivos

**Solo investigación.** No se cambió el motor para B4b ni se hizo merge. El motor medido es el commit `94c372d` de la PR #12. La compuerta probada más abajo se ejecutó únicamente en memoria sobre una copia y **se descarta** por una regresión.

## 1. Trazas de las dos consultas

La prueba usa el motor B4a, búsqueda directa con `profundidad="activos"`, `limite=5` e `ignore_peso_sinaptico=True`. Los recuerdos y consultas de E3A son sintéticos; cada búsqueda abre una copia independiente.

| Caso | Cómo entra `model airplane` | Resultado con WordNet | Resultado con WordNet desactivado |
|---|---|---|---|
| `en-n01`: “Where does the platypus in boots play chess?” | La consulta aporta `play`; FTS lo encuentra dentro de `dis[play]ed`. | Posición 1, score `0,1723`. | Posición 1, score `0,1723`: **persiste**. |
| `en-n02`: “Which saxophone is buried in a desert glacier?” | WordNet expande `buried` a `lay to rest`; FTS separa `lay` y lo encuentra dentro de `disp[lay]ed`. | Posición 1, score `0,2039`. | **Vacío**: desaparece el falso positivo. |

Las trazas reales identificaron la entrada en `core/memory/search.py:518–527`. Aunque el comentario de esa etapa dice “AND”, la expresión utilizada para consultas multipalabra sin paráfrasis se construye con **OR** (`:379–380`). En ambos casos el origen final es `literal`. El filtro final de B4a actúa solo con una palabra (`:2073–2074`); estas consultas tienen cuatro y no pasan por ese filtro.

Se contrastó cada traza con otra búsqueda sin observador: mismo top-5 y scores. La desactivación se ejecutó en un proceso independiente iniciado con `BIORAG_WORDNET_ENABLED=0`. El flag desactiva la expansión y la capa de puntuación WordNet de la búsqueda; **la base sintética ya se había creado con WordNet activado**. No se presenta esta ablación como propuesta de apagar WordNet.

**Detalle de reproducibilidad:** alternar la variable dentro de un mismo proceso puede reutilizar expansiones de la caché del fallback simbólico. Una primera corrida que alternaba la variable se conservó solo como exploratoria y **no se usa para estas conclusiones**. Los tres brazos definitivos arrancaron en procesos separados, cada uno con la variable fija antes de importar el motor.

## 2. Por qué no conviene restaurar el filtro global

`git log`, `git show` y `git blame` identifican el commit histórico [`b957a633`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/b957a633acbe313b5caedf6f089aa597c0b37f02), v30.2. Allí se retiró `pc_clause` de FTS NEAR/AND/OR y se introdujo el Quality Gate del fallback 2.1.

La razón documentada era que la antigua cláusula añadía una palabra corta como condición **obligatoria para toda la búsqueda OR**. Por ejemplo, en el caso histórico `0693`, la consulta incluía `info` y `dennys-working-style`: el recuerdo correcto coincidía con los términos largos, pero no contenía `info`, y el filtro lo eliminaba antes de puntuarlo. La investigación histórica registró 23 recuerdos esperados bloqueados en FTS; eso no significa necesariamente 23 pérdidas finales, y no se ha repetido ese benchmark para B4b.

El Quality Gate actual (`search.py:930–948`) decide cuándo activar el rescate simbólico por cantidad o cobertura de tokens. **No es un filtro que elimine candidatos FTS.** En las dos trazas inglesas estuvo activo, pero el candidato literal `model airplane` permaneció en la lista. La condición adicional de escala para palabras desconocidas sigue intacta.

## 3. Ensayo contrafactual: filtro B4a global en FTS

Se probó la idea de volver a exigir en FTS que alguna palabra corta cumpla `PALABRA_INICIO_ANCHO`. Para cada término de hasta cuatro caracteres, el ensayo comprobó ese predicado en contenido, concepto o sinónimos; reunió esas comprobaciones con `OR` y las añadió con `AND` a la búsqueda FTS completa. Si no había términos cortos, no añadía condición. El código se compiló **solo en memoria**, en un proceso separado y sobre una copia limpia del commit B4a. La condición se colocó en el SQL antes del resultado, no en un filtro posterior al límite. Es un experimento para medir riesgo, **no un cambio aprobado**.

Los tres brazos usaron la misma base sintética de **120 recuerdos**, creada una sola vez, con SHA-256 `b1e6049082db2d07b8c5940915d52789eef441ca52d7f69480767686be18b2a8`. Se hicieron 132 búsquedas por brazo: 20 positivos y 2 negativos por idioma. `R@5 / R@1` son cantidades sobre 20; FP son cantidades sobre 2. No son los 40 negativos de la QA oficial.

Para reproducir el contexto: Python 3.11.2, SQLite 3.40.1, NLTK 3.9.4, NumPy 2.4.6; `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, reloj fijo `1793059200`, una copia de la base por consulta y un estado auxiliar independiente por búsqueda. El gold ya publicado `scripts/casos_qa_multilingue_e3a.jsonl` tiene SHA-256 `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`; la base se generó con `crear_base` del evaluador E3A. Las comprobaciones de FTS y la ablación se hicieron en procesos separados.

| Idioma | B4a: R@5 / R@1 / FP | Filtro hipotético | WordNet desactivado |
|---|---|---|---|
| zh | 12 / 12 / 0 | 12 / 12 / 0 | 12 / 12 / 0 |
| ja | 12 / 12 / 0 | 12 / 12 / 0 | 12 / 12 / 0 |
| ko | 19 / 18 / 0 | 19 / 18 / 0 | 19 / 18 / 0 |
| ru | 20 / 19 / 0 | **19 / 19 / 0** | 20 / 19 / 0 |
| en | 20 / 20 / 2 | 20 / 20 / **0** | 20 / 20 / 1 |
| es | 20 / 20 / 0 | 20 / 20 / 0 | 20 / 20 / 0 |

**Regresión `ru-17`:** la búsqueda `шестизначное число для замка` recupera `кодовый замок` en posición 2 con B4a. La pareja observada que lo recupera por FTS es **`число`** (consulta) / **`числом`** (contenido), con la coincidencia resaltada como `[число]м`. El recuerdo también contiene las otras formas `замок` y `шестизначным`, frente a `замка` y `шестизначное` en la consulta; esas dos parejas no fueron el match FTS observado en esta traza. La pérdida no la causa `число`/`числом`: la compuerta global exige además la única palabra corta, `для`, ausente del recuerdo correcto. Por eso el resultado desaparece del top-5. `ko-08`, en cambio, conserva posición 1 por la ruta de contenido.

El filtro hipotético elimina los dos FP ingleses del conjunto sintético, pero causa esa pérdida R@5 en ruso. Cambia además scores de tres controles positivos. **Se descarta: no cumple el requisito de no perder controles.** WordNet apagado elimina solo `en-n02` y cambia listas o scores en 40 de las 132 búsquedas; no se observan pérdidas de R@1/R@5 en este conjunto pequeño, lo que no demuestra seguridad en otros datos.

### Diff del experimento descartado — NO APLICAR

Se muestra para que el auditor pueda revisar exactamente lo ensayado, no como una propuesta lista para integrar:

```diff
--- a/core/memory/search.py
+++ b/core/memory/search.py
@@ -488,13 +488,12 @@
     if palabras_pc:
         pc_clauses = []
         for p in palabras_pc:
-            pc_clauses.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
+            pc_clauses.append("(PALABRA_INICIO_ANCHO(?, l.contenido) = 1 OR PALABRA_INICIO_ANCHO(?, l.concepto) = 1 OR PALABRA_INICIO_ANCHO(?, COALESCE(l.sinonimos, '')) = 1)")
             pc_params.extend([p, p, p])
         pc_clause = " AND (" + " OR ".join(pc_clauses) + ")"
     # v30.2: Generación FTS desacoplada (B2) — sql_con_pc = sql (sin pc_clause en NEAR+AND+OR).
     # El filtrado destructivo de FTS se reemplaza por el Quality Gate de Fallback 2.1 (B3).
-    sql_con_pc = sql
-    pc_params = []
+    sql_con_pc = sql.replace("ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico)", pc_clause + " ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico)")
```

## 4. Siguiente decisión

No hay todavía un diff seguro para proponer. La dirección a estudiar, **sin aplicar nada**, sería validar el término corto que realmente aporta cada coincidencia FTS, sin obligar a que todos los candidatos contengan una palabra corta cuando otro término válido los recupera. Habría que conservar el comportamiento de prefijos, escrituras anchas, sinónimos, `sustantivos_clave`, typos y Quality Gate; también medir el coste. Esta idea no se ha implementado ni validado.

No se ejecutaron las QA oficiales de snapshot/viva ni se midió MCP para este experimento. Al terminar, los 73 archivos `.py` de `core/` coincidieron con la exportación del commit B4a; las huellas de `search.py`, `memory_store.py` y su test se verificaron al inicio y al final: `f4479e7d…`, `b7e7219c…` y `68f89c4c…`.

## Evidencia local

Los archivos siguientes quedaron fuera del repositorio, en `/home/user/MemoryBioRAG_evidencias/e3b4b_20261028/`. **No se publican en la PR**, por lo que el auditor no puede verificar su contenido desde este informe; las huellas se consignan para una eventual comprobación posterior:

- `brazo_baseline.json`: `2814d8ae39f94bb5f4621f4cf6c1db2c592b0cb37e863c1ab48c272e72d3c91a`.
- `brazo_gate_hipotetico.json`: `49188153bcdf07f3b24b39de1240c17c0696b60781f4c2920133049d101df1b7`.
- `brazo_wordnet_off.json`: `88b5ff898980292afd9270a191f557b2b76475cf17633ad3dc42e6ef29374046`.
- `comparacion_brazos_aislados.json`: `391ef7b962a49b35f3d6f8b10e1f3ac6a98347399920090e3e47c7a601243951`.
- `solo_ejemplo_no_aplicar.patch`: diff del experimento descartado, `083de817455a3e491c0e6e83ea1f3d383bef2e400277cd8eba53ca9ad903c4b6`.
- `investigar_b4b.py` y `brazos_aislados.py`: arnés de investigación. La semilla es temporal y no se subió a Git.
