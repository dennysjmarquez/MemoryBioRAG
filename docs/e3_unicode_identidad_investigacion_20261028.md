# E3 — identidad Unicode: investigación y comparación

**Estado: investigación en copias; no hay cambio de motor ni decisión de implementación.** Cualquier propuesta futura requiere diff y OK de Dennys antes de aplicarse. Los dos métodos aquí comparados son transformaciones experimentales de entradas, no parches de producción.

El auditor aclaró que igualar ancho completo/medio ancho con la forma normal es el **arreglo deseado**, aunque cambie resultados de validaciones B3/B4a. Esos cambios no se presentan aquí como daños. Se separan de otras equivalencias de NFKC que todavía deben vigilarse.

## 1. A) Cambios deseados: ancho y marcas

| Prueba | Actual | NFKC completo | NFC + ancho selectivo |
|---|---|---|---|
| `ｇｏ ｔｏ` frente a `go to` | Distintos | Iguales | Iguales |
| `ｶﾞﾗｽ` frente a `ガラス` | Distintos | Iguales | Iguales |
| `カ` + marca combinante U+3099 frente a `ガ` | Distintos en bytes | Iguales | Iguales |
| `ガラス` frente a `カラス` | Distintos en bytes | **Distintos** | **Distintos** |

En sondas de validación, `ｇｏ ｔｏ` pasa de aceptarse a rechazarse como `go to`, y el caso `ＢＣ` en `ＡＢＣ` pasa de 1 a 0 como `BC` en `ABC`. Ambos son consecuencias deseadas de igualar anchos, no una regresión por sí mismos. También `１２３４` pasa a evaluarse como `1234`: en la prueba de puentes actual eso cambia aceptado → rechazado. La prueba B3 existente que esperaba aceptar `１２３４` tendría que revisarse explícitamente si se aprueba un diff con ese alcance.

**Importante:** actualmente `normalizar_sustantivos_clave` usa NFKD y elimina marcas; por eso `ガラス,カラス` termina como `カラス`. Las dos transformaciones de la tabla distinguen los términos por sí solas, pero **el motor existente aún los confunde después**. En sondas FastMCP, `aprender` y `agregar_sustantivos` con ambos términos rechazaron una cantidad resultante de 1; `aprender` con `ガラス,容器` guardó `カラス,容器`. Esta investigación no ha corregido esa etapa.

La marca *combinante* U+3099 se compone con `カ` en ambos métodos. La grafía visual `゛` también puede ser la marca *espaciada* U+309B: `カ` + U+309B no se convierte a `ガ` por ninguno de los dos métodos probados; NFKC produce `カ` + espacio + U+3099. Si también se desea equivalencia para U+309B, requiere una decisión y prueba aparte.

## 2. Alternativas comparadas

1. **NFKC completo:** `unicodedata.normalize("NFKC", texto)`.
2. **NFC + ancho selectivo:** NFC; después, solo para caracteres U+FF00–U+FFEF, usar su descomposición directa `<wide>` o `<narrow>`; finalmente NFC. No aplicar otras descomposiciones de compatibilidad fuera de ese bloque. Se comprobaron los 240 puntos del bloque para idempotencia individual, además de sondas dirigidas.

Esta es una forma concreta de probar la alternativa del auditor; **no es un diff aprobado**. El alcance literal del bloque deja fuera, por ejemplo, el espacio ideográfico U+3000, que NFKC convierte en espacio normal. Además, el jamo de medio ancho `ﾡ` U+FFA1 se convierte en `ᄀ` U+1100 con NFKC, pero en `ㄱ` U+3131 con el plegado directo selectivo. Esa diferencia necesita decisión si importa para la identidad coreana.

## 3. B) Cambios a vigilar

| Entrada | NFKC completo | NFC + ancho selectivo | Observación |
|---|---|---|---|
| `ㅋ` U+314B | `ᄏ` U+110F | `ㅋ` | En el entorno medido el ancho es W → W; **este caso concreto no cambia de ancho**. |
| `ㅏ` U+314F | `ᅡ` U+1161 | `ㅏ` | Ancho W → N con NFKC. |
| `ㄳ` U+3133 | `ᆪ` U+11AA | `ㄳ` | Ancho W → N con NFKC. |
| `①` | `1` | `①` | Posible equivalencia no deseada según el contexto. |
| `²` | `2` | `²` | Posible pérdida de distinción matemática. |
| `™` | `TM` | `™` | Añade letras al texto normalizado. |
| `ﬁ` | `fi` | `ﬁ` | Una ligadura pasa a dos letras. |

En sondas aisladas de la función real de puentes B3, aplicando primero la transformación a la entrada:

| Entrada de prueba | Actual | NFKC | Selectivo |
|---|---:|---:|---:|
| `ㅏㅏㅏㅏ` | Aceptada | Rechazada | Aceptada |
| `ㄳㄳㄳㄳ` | Aceptada | Rechazada | Aceptada |
| `ㅋㅏㅋㅏ` | Aceptada | Rechazada (`카카`) | Aceptada |
| `™™ ™™` | Rechazada | Aceptada (`TMTM TMTM`) | Rechazada |
| `ﬁﬁ ﬁﬁ` | Rechazada | Aceptada (`fifi fifi`) | Rechazada |
| `①①① ①①①` y `²²² ²²²` | Aceptadas | Aceptadas, transformadas a dígitos | Aceptadas, sin transformación |

Son ejemplos artificiales para detectar diferencias de conteo; no deciden por sí solos si un puente real tiene significado. No se modificó la función B3.

## 4. Multilingüe existente: 132 consultas

Tres brazos sobre el **mismo corpus B4a sin transformar**: consulta original, consulta NFKC y consulta con plegado selectivo. Una copia de base y estado por búsqueda; `profundidad=activos`, límite 5, peso sináptico ignorado, WordNet habilitado y neurona desactivada (`BIORAG_NEURONA=0`) desde el arranque, `PYTHONHASHSEED=0` y reloj fijo. El orden de los brazos se alternó. La base quedó intacta y el brazo original reprodujo las 132 listas y puntuaciones de la investigación B4b anterior. Esta medición es directa y no equivale a la ruta MCP.

R@5/R@1 son aciertos sobre 20 positivos y FP sobre 2 negativos por idioma:

| Idioma | Actual | NFKC en consulta | Selectivo en consulta |
|---|---:|---:|---:|
| Chino | 12/12/0 | 12/12/0 | 12/12/0 |
| Japonés | 12/12/0 | 12/12/0 | 12/12/0 |
| Coreano | 19/18/0 | 19/18/0 | 19/18/0 |
| Ruso | 20/19/0 | 20/19/0 | 20/19/0 |
| Inglés | 20/20/2 | 20/20/2 | 20/20/2 |
| Español | 20/20/0 | 20/20/0 | 20/20/0 |
| **Total** | **103/101/2** | **103/101/2** | **103/101/2** |

No cambiaron posiciones, FP, listas ni puntuaciones en esos 132 casos. Ambas transformaciones cambiaron 18 consultas, únicamente por `？` → `?`. **Los casos B concretos de la tabla anterior no están representados en estas preguntas**, por lo que esta igualdad no prueba su seguridad. Tampoco mide una implementación que cambie el corpus o elimine la pérdida actual de marcas en el motor.

Además, se pasaron las 80 entradas nativas de guardado —400 textos de puentes— por `validar_bridges`, transformando sus textos y la clave de entrada. En los tres brazos los 80 casos conservaron sus cinco puentes válidos: 20/20 por idioma zh, ja, ko y ru. **Esto es solo validación de puentes, no 80 guardados ni 80 búsquedas MCP.**

## 5. B) Prueba multilingüe con símbolos añadidos

Para cubrir las clases B ausentes en las 132 consultas, se añadieron a cada pregunta los mismos términos sintéticos: `ㅏㅏㅏㅏ ①①① ²²² ™™ ﬁﬁ`. Se asumió, solo para esta prueba adversarial, que ese añadido no cambia el recuerdo esperado. El corpus permaneció en B4a; solo se transformó la pregunta. **No es la QA oficial ni sustituye el gold original.**

| Idioma | Actual con añadido R@5/R@1/FP | NFKC | Selectivo |
|---|---:|---:|---:|
| Chino | 10/10/0 | 10/10/0 | 10/10/0 |
| Japonés | 12/12/0 | 12/12/0 | 12/12/0 |
| Coreano | 17/17/0 | 17/17/0 | 17/17/0 |
| Ruso | 20/19/0 | 20/19/0 | 20/19/0 |
| Inglés | 20/19/2 | 20/19/2 | 20/19/2 |
| Español | 20/20/0 | 20/20/0 | 20/20/0 |
| **Total** | **99/97/2** | **99/97/2** | **99/97/2** |

El añadido artificial ya cambia el baseline respecto de la tabla anterior; no debe atribuirse a NFKC. Frente a ese baseline con añadido, ninguna posición esperada bajó ni hubo nuevos FP en los 12 negativos. El selectivo conservó exactamente las listas; NFKC cambió 100 listas: 95 solo en puntuación y 5 con un candidato adicional en una consulta positiva. Esos candidatos adicionales no se califican automáticamente como FP: los negativos del gold son la medida de FP de esta prueba.

### Sonda adicional de identidad: cinco parejas

Se crearon diez recuerdos sintéticos: cinco parejas que, **por hipótesis de la sonda**, son recuerdos distintos y difieren en jamo, círculos, superíndices, `™`/`TM` o ligaduras. Al normalizar contenido y consulta con NFKC, 4 de las 5 parejas quedaron con contenido idéntico byte a byte; la quinta también coincide tras minúsculas. Con el selectivo no ocurrió ninguna de esas igualdades. No hay negativos en esta sonda.

| Alcance: contenido y consulta sintéticos | Actual R@5/R@1 | NFKC | Selectivo |
|---|---:|---:|---:|
| 10 positivos | 10/1 | 10/5 | 10/1 |

El agregado R@1 mejora en NFKC en esta sonda, pero una posición individual, `marca-a`, baja de **1 a 2**; se reprodujo **3/3** veces. El selectivo conservó la posición 1 en esas repeticiones. El resultado depende de la hipótesis artificial de que las dos formas señalan recuerdos distintos: **no decide la semántica real de `™`, `TM` ni de los jamos**, ni valida un parche final.

## 6. Mapa actual de normalización

| Zona | Tratamiento actual y riesgo |
|---|---|
| `core/mcp_server/_shared.py:92-98` | Valida sustantivos tras NFC, 2–15 caracteres y categorías L/M/N o `_`; recibe términos ya normalizados por las herramientas MCP. |
| `core/memory/constants.py:285-307`, `core/stemmer_es.py:43-46` | Sustantivos: minúsculas, NFKD, eliminación de marcas y deduplicación; protege `ñ` compuesta, pero no la forma `n` + tilde combinante. |
| `core/mcp_server/search.py:203-249`; `write.py:212-247, 876-906` | `recordar`, `aprender`, `guardar` y `agregar_sustantivos` normalizan antes de validar. Sonda FastMCP: consulta `ガラス` con sustantivo `ガラス` llega al motor con boost `カラス`. |
| `core/mcp_server/write.py:83, 251, 862`; `core/memory/ingest.py:31, 131` | Los nombres de concepto usan minúsculas y espacios a `_` en MCP, sin NFKC compartido. En una base sintética se pudieron guardar tanto `go_to` como `ｇｏ_ｔｏ`. |
| `core/concept_hub.py:127-159` | Conteo de puentes con NFC y anchos W/F; duplicados mediante `lower()`. No usa una identidad común de ancho. |
| `core/memory/search.py:142-158` | Limpieza de consulta basada en `\w`; una marca japonesa separada y algunas marcas hindi pueden convertirse en espacios. Componer algunas marcas no resuelve todas las etapas posteriores. |
| `core/fallback_simbolico.py:25-47`, `core/concept_hub.py:431-475` | NFKD/NFD y eliminación de marcas en coincidencia aproximada: `ガラス` y `カラス` pueden colapsar en esas capas. |
| `core/memory/schema.py:60-73, 1000-1008, 1076-1082` | La clave `concepto` es `TEXT UNIQUE` con comparación binaria; hay índices FTS trigram y unicode61 con tratamientos distintos. Normalizar solo consultas no transforma recuerdos ya indexados. |
| `core/memory_store.py:122-138` | `PALABRA_INICIO_ANCHO` usa un inicio normal o carácter previo W/F. La igualdad de anchos deseada cambia el resultado si se transforma la entrada. |

La sonda FastMCP de `recordar` se hizo con límite interno 15 y peso por defecto, no con los parámetros de la búsqueda directa de la sección 4; no son métricas equivalentes. Hay otros normalizadores específicos en `core/memory/escala.py`, `core/memory/scoring.py` y `core/lexical_learning.py`; no se concluye que todos deban cambiar en una misma entrega.

## 7. Datos existentes y límites

- Un sustantivo ya guardado como `カラス` puede haber llegado como `ガラス` o como `カラス`; ese campo por sí solo no permite recuperar la forma original. Reconstruir el índice no recupera información ya perdida.
- Normalizar claves almacenadas puede producir colisiones entre recuerdos distintos. No se autorizan fusiones, cambios de pesos ni migraciones automáticas. Cambiar solo la consulta o solo escrituras nuevas puede dejar registros antiguos sin correspondencia. En una base sintética, los dos índices FTS distinguieron `ｶﾞﾗｽ` de `ガラス` y `ｇｏ_ｔｏ` de `go_to`.
- `café`/`cafe`, `ñ`, otras marcas significativas y el troceo zh/ja sin espacios requieren políticas y pruebas propias. NFKC y el plegado selectivo no sustituyen esas decisiones.
- Censo del snapshot público en `mode=ro&immutable=1`, sin WAL/SHM y con SHA comprobado antes/después: 866 nombres en largo y 1 en corto, sin cambios ni colisiones NFKC en esos nombres; 30 puentes sin cambios NFKC. Solo 6 filas de largo tenían sustantivos. **No se inspeccionó la viva ni se extrapola este resultado a ella.**

## 8. Evidencias y siguiente puerta

Python informa Unicode `14.0.0`; SQLite `3.40.1`. Pasaron **122 pruebas existentes** de validación Unicode, puentes B3 y prefijo B4a en la copia anterior; no son las cuatro QA oficiales de un cambio nuevo. Los brazos de esta investigación conservaron el código B4a sin editar. La fuente del gold de 132 consultas tiene SHA `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`.

Evidencias sintéticas locales bajo `/home/user/MemoryBioRAG_evidencias/e3_unicode_identidad_20261028/`:

- `comparacion_anchos_multilingue.json`: ejemplos, 132 consultas, validación de 400 puentes y sonda de diez positivos. SHA `237745a9b11a774a28a51f7e8c1b175b76a7df9343036967ccda3f75054dd210`.
- `stress_b_132_multilingue.json`: 132 variantes con símbolos añadidos. SHA `e5e3293ae5d4679b037ce8701545d03a656862ef1deb595378cd34e190266c4d`.
- `confirmacion_marca_unicode.json`: tres repeticiones del rango individual. SHA `ec63dc8d6c7094ebcaead3bded0d6546de2c7bfc0bcb80bab3a3986047c940e9`.
- `identidad_unicode.json`, `mcp_sondas.json`, `censo_snapshot_completo.json` y `pytest_baseline.log`: sondas y comprobaciones previas. Los scripts y resultados permanecen locales; esta publicación contiene solo el informe.

**Siguiente puerta:** Dennys y el auditor pueden decidir el alcance de equivalencia y cuál alternativa investigar como cambio acotado. Antes de tocar el motor: diff visible, OK de Dennys y mediciones apropiadas, incluidos rangos/R@5/R@1/FP y compatibilidad con datos anteriores.
