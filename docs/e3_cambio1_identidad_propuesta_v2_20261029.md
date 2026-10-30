# E3 · Cambio 1: propuesta v2 de identidad Unicode

**DOCUMENTO Y DIFF PARA REVISIÓN. NO APLICADO AL MOTOR.** Esta v2 incorpora los dos cambios pedidos por la [auditoría](https://github.com/dennysjmarquez/MemoryBioRAG/blob/a4109657cf13621fe3f574fd06b1271d9540e40e/docs/auditoria_ci/auditoria_e3_cambio1_identidad_20261029.md) y corrige la lectura de la base mixta. No es autorización para aplicar el cambio ni para hacer merge.

- [Diff v2 — NO APLICAR](e3_cambio1_identidad_diff_v2_NO_APLICAR_20261029.patch).
- SHA-256 del diff v2: `68439804583a727fadb6cea597542e11b4e6b77339fb99cee9262ee423e54cc4`.
- Base del diff v2: `3f71f7434e95d6f6e61f71c00b64a3e7a49c2e49`, que contiene los dos documentos v1 pero no aplica el motor propuesto.
- Aplicación comprobada únicamente en una copia desechable; los 13 archivos obtenidos coinciden con los probados. El checkout de trabajo no recibió el patch.
- La v1 queda intacta: [informe](e3_cambio1_identidad_propuesta_20261029.md) y [diff](e3_cambio1_identidad_diff_NO_APLICAR_20261029.patch). Sus huellas siguen siendo, respectivamente, `3ee4d90c344795c8c4ca5e96dee47556fa8223705dcc0da078d1ec474860d2cc` y `98254a8611aa6d744c2433c83d2ba02601aa199531c444d65565dc6460f0747c`.

## 1. Los dos ajustes de v2

### Contenido y sinónimos: conservar signos

Para consultas, sustantivos, puentes y nombres se mantiene la identidad completa de v1: NFC, mapeo directo `<wide>`/`<narrow>` de U+FF00–FFEF y U+3000 → espacio. No se usa NFKC general. La validación de puentes sigue devolviendo su texto original; al guardar un puente nuevo sí se aplica la identidad completa.

En **contenido y sinónimos que entran por el flujo de aprendizaje** se emplea la misma función en modo limitado: solo se pliegan caracteres de categorías Unicode L* o N* del bloque U+FF00–FFEF. Se conservan los signos de puntuación, símbolos y U+3000. NFC sigue operando en tramos de letras, marcas y números, pero no sobre signos, símbolos ni separadores: esto también protege los caracteres de esas categorías que NFC global podría cambiar. Después del plegado se recompone, por ejemplo, `ｶﾞ` → `ガ`.

```text
Entrada:  你好，世界！（测试）：ＡＢＣ１２３
Guardado: 你好，世界！（测试）：ABC123
```

El mismo criterio se prueba para sinónimos, incluso con espacios U+3000. Las fusiones ya existentes de sinónimos usaban `strip()`, que también podía borrar U+3000 en los extremos: el diff preserva ese espacio al fusionar tanto en corto como en largo plazo. No cambia la regla de omitir términos vacíos ni la comparación histórica de duplicados. El separador de sinónimos sigue siendo la coma ASCII; una coma china `，` conservada no se convierte en ese separador.

**Alcance:** este comportamiento se conecta a `percibir_corto_plazo` y a MCP `aprender`/`guardar`. MCP `actualizar` sigue sobrescribiendo sus campos con lo recibido, como antes; no se le añadió normalización. Las pruebas MCP están preparadas, pero no se han ejecutado para v2.

### Clave antigua: conservar la original

Si la clave original exacta ya existe en corto o largo plazo, se selecciona esa clave; si no existe, se usa la normalizada. La elección se transmite a ingreso, servicio y consolidación, y se propone también para el flujo MCP. Ya no se lanza el `ValueError` de v1. Si coexisten original y normalizada, una escritura dirigida a la original modifica solo la original; no crea otra clave plegada ni actualiza la fila normalizada por accidente.

En una prueba directa se parte de `ｇｏ_ｔｏ` en largo plazo y se llama `aprender(c, "ｇｏ_ｔｏ", ...)`: se actualiza esa misma fila, conservando su id, y no se crea `go_to`. Se probaron también colisiones en corto y largo y consolidación que no debe desviarse. Cuando una consolidación actualiza una fila existente, se conserva la regla **preexistente** de fusión, incluido el aumento de peso `+0,20` con tope `1,0`; el diff no cambia esa fórmula ni añade un ajuste de peso.

**Límites:** se comprueba la clave original exacta tras el tratamiento habitual de minúsculas y bordes; no se buscan todas las variantes antiguas equivalentes ni se migran datos. La comprobación y la escritura no se convierten en una operación atómica frente a escrituras concurrentes. Una referencia a la forma normalizada no identifica por sí sola una fila antigua de otra forma.

## 2. Qué forma original se pierde

La normalización ocurre antes de guardar las letras y números anchos de contenido/sinónimos nuevos: por ejemplo, `Marcador ｚｑｘｈｎ` se guarda como `Marcador zqxhn`. NFC también puede recomponer letras y marcas. El diff no guarda una copia recuperable de esa representación original. La puntuación, los símbolos y U+3000 no se pliegan en ese modo; las reglas de fusión indicadas arriba siguen aplicando.

Los nombres de recuerdos nuevos y puentes nuevos usan identidad completa, por lo que tampoco conservan necesariamente el ancho original. Las filas antiguas no se reescriben por instalar el cambio. Esta propuesta no demuestra que transformar el texto guardado sea la única solución posible.

**Cambio 2 no adelantado:** el normalizador histórico de sustantivos conserva su etapa posterior NFKD y puede seguir colapsando marcas o compatibilidades; la ingestión directa sigue esperando sustantivos ya normalizados. U+309B y B4b son asuntos independientes, fuera de este diff.

## 3. Base mixta: identidad funcionando

Esta es la **medición anterior de v1**, no una prueba nueva de v2. La sonda reproducible y sus condiciones completas están en la sección 7 del [informe v1](e3_cambio1_identidad_propuesta_20261029.md). Se creó una base sintética con `recuerdo_antiguo` y `recuerdo_nuevo`; ambos contienen el mismo marcador y **no hay gold** que privilegie uno.

| Consulta | Base anterior | Propuesta v1 |
|---|---|---|
| `ｚｑｘｈｎ` | nuevo 1 (`0.1786`), antiguo 2 (`0.0488`) | antiguo 1 (`0.1781`), nuevo 2 (`0.0454`) |
| `zqxhn` | antiguo 1 (`0.1781`), nuevo 2 (`0.0454`) | antiguo 1 (`0.1781`), nuevo 2 (`0.0454`) |

Con v1, las consultas de ambos anchos devuelven **exactamente la misma lista**: es la identidad funcionando. El cambio 1↔2 frente a la base anterior no es una regresión demostrada: ambos recuerdos comparten el marcador y no hay gold. La consulta ancha se repitió 3/3 con el mismo resultado por brazo. Los índices FTS literales distinguen anchos, pero esa observación por sí sola no es la búsqueda completa. Fuente sintética SHA-256: `5d02f4821f8856970dba1dbe20bb30c143e96a2aae68c6595526876ee40ad782`.

Para esa medición se usaron la misma base fuente por brazo, `profundidad="activos"`, `limite=5`, `ignore_peso_sinaptico=True`, WordNet encendido, neurona apagada, reloj y hash fijados. En v2 no se repitió la búsqueda mixta; la identidad completa de v1 y v2 se contrastó en el bloque entero U+FF00–FFEF y nueve ejemplos, con resultados iguales en esas 249 entradas.

## 4. Llamadas en los archivos propuestos

Estas son las **21 llamadas directas de producción** a `normalizar_identidad`, obtenidas del AST. Las líneas corresponden a v2, no al motor sin aplicar.

| Archivo y línea | Función / entrada |
|---|---|
| `core/concept_hub.py:112` | `validar_bridges`: nombre. |
| `core/concept_hub.py:131` | `validar_bridges`: texto para contar y comparar. |
| `core/concept_hub.py:346` | `agregar_bridges`: texto del puente nuevo. |
| `core/mcp_server/_shared.py:95` | `_sustantivo_valido`: término. |
| `core/mcp_server/search.py:154` | `_recordar_impl`: entrada sanitizada. |
| `core/mcp_server/search.py:169` | `_recordar_impl`: paráfrasis. |
| `core/mcp_server/search.py:179` | `_recordar_impl`: ráfaga. |
| `core/mcp_server/write.py:43` | `_buscar_registro_sustantivos`: alternativa normalizada. |
| `core/mcp_server/write.py:105` | `_aprender_impl`: nombre. |
| `core/mcp_server/write.py:132` | `_aprender_impl`: contenido, modo limitado. |
| `core/mcp_server/write.py:134` | `_aprender_impl`: sinónimos, modo limitado. |
| `core/mcp_server/write.py:891` | `biorag_agregar_sustantivos`: nombre. |
| `core/memory/constants.py:301` | `normalizar_sustantivos_clave`: entrada. |
| `core/memory/ingest.py:47` | `percibir_corto_plazo`: nombre. |
| `core/memory/ingest.py:49` | `percibir_corto_plazo`: contenido, modo limitado. |
| `core/memory/ingest.py:50` | `percibir_corto_plazo`: sinónimos, modo limitado. |
| `core/memory/ingest.py:155` | `consolidar_concepto`: nombre alternativo. |
| `core/memory/search.py:78` | `buscar_por_frase`: consulta. |
| `core/memory/search.py:80` | `buscar_por_frase`: cada paráfrasis. |
| `core/memory/search.py:82` | `buscar_por_frase`: impulso por sustantivos. |
| `core/memory_service.py:86` | `aprender`: nombre alternativo. |

La elección de clave `_comprobar_clave_legacy` se llama en `core/memory/ingest.py:48,156`, `core/memory_service.py:91` y `core/mcp_server/write.py:280`. El recorte que conserva U+3000 se llama en `core/memory/ingest.py:67,72` y `core/memory/consolidation.py:261,266`. Esta última es la **decimotercera ruta** respecto de v1 y se incluye para conservar U+3000 también al fusionar sinónimos en largo plazo.

En `tests/test_identidad_unicode_cambio1.py` hay 18 llamadas directas a `normalizar_identidad`: líneas 31, 32, 36 (dos), 37 (dos), 38, 39, 44, 45, 46, 52, 53, 56, 57, 63, 65 y 68. La prueba MCP del límite también conserva una referencia en la línea 264 y la llama indirectamente en la 268; esa prueba no se ejecutó en v2.

## 5. SHA-256 de los archivos del diff

`Antes` corresponde a `3f71f74`; `Propuesto` es el contenido al aplicar el diff en copia. `NUEVO` indica que no existe en la base.

| Archivo | SHA-256 antes | SHA-256 propuesto |
|---|---|---|
| `core/README.md` | `0f5d12b01cf00b9f4f6579e850117379398c09eb842d33c57f841badfbff0992` | `4c2291a14d4af686180bd7a04bd5ec5035c4d015dcb4889d951c1e9f45a2a351` |
| `core/concept_hub.py` | `50cdced5342eb255abcd1ea9ab0781ab677ec518b173bc3855a32c0be9b618cf` | `c02ca5191f61d5d578a66bad6a2a21eefc49151cf1925c02477a32091c8243c7` |
| `core/identidad_unicode.py` | `NUEVO` | `05f6a3284ede311b7f7c9f59f4f43e046342275f1f403643fb0a70ecf53c0b8a` |
| `core/mcp_server/_shared.py` | `eaf26c15feafe47c574a381ad6e7f1118439c825e893a95db6cbce94d2ef7e36` | `31f9f6ec5befdc98ca492b55646763b7eac0503d328c7ea27364d2b3f543589c` |
| `core/mcp_server/search.py` | `797d2b254d7b9b215537ab6c3fe40d8e0c492f7e64bbc0a55d5a773f185663fc` | `432ee33c499bd9326010a6172e6208b8879e25a767343d7e78bc70a0db7fb32a` |
| `core/mcp_server/write.py` | `b188d7430e8e37dcbcde1dcb949cc5255c7d205c1b7c1cc9de3ef726e4545218` | `3fe72510034498f07fd7c28b1dbc5d10c5159d2b72365f71f65e526d8ccd8ec1` |
| `core/memory/constants.py` | `de8397eefa632d18eb06d61a3907286b17ba9c022b2e3924389d082041439c35` | `8f748fe21e4aa524ca84df71cb021a2c9e81ca2ba2cdc33f3d23e1f135ca13e8` |
| `core/memory/consolidation.py` | `5f882a19cdac96b38574ea5295892095fa40d8ed1eb0ba3dec1ed2f93112ce3c` | `e33f2c40f033a193b128501589c4c10f393766e1eb54e5e1556975df49b47f06` |
| `core/memory/ingest.py` | `25f72f24e60723008cece6792583f39c64927ad4dcae73e90118357ef87c7951` | `2b3c7c520f40506ce23687865eb18110b9ca6ceddd140a8f23babd4a52ede459` |
| `core/memory/search.py` | `f4479e7db7673c264176a48d467ab7c32411ea67a8cb39ad8daf4a4089677286` | `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6` |
| `core/memory_service.py` | `51ec9b5181c5e92410c31cf80e8bc68e86b82908ed0b1542639827c72e137f7b` | `5692b6a8dc7d8302356a476603bfa39840867f983896d9f3168c831421e8ff07` |
| `tests/test_identidad_unicode_cambio1.py` | `NUEVO` | `f884e2f830c566c3943515265fe5b790dafe5d6157a68009d493c723def04b57` |
| `tests/test_validacion_bridges_unicode_b3.py` | `9b4d70a224b974d28441628b0e3acb37951dd1920140542bfb962157bfae0c88` | `fc6ad1d4a0a75009f11af6e6ee6f4f5ebdd89a50daf156834e298232f0192bc1` |

El patch contiene 13 archivos, 552 líneas agregadas y 58 eliminadas. `git diff --check` sobre el código propuesto pasó; al revisar el `.patch` como documento nuevo pueden aparecer espacios de las líneas de contexto propias del formato diff, que no deben alterarse.

## 6. Comprobaciones realizadas y pendientes

Solo en una copia aislada, con Python 3.11.2, Unicode 14.0.0, `PYTHONHASHSEED=0`, WordNet habilitado y sin forzar la neurona apagada, se ejecutaron pruebas unitarias de identidad, ingreso, claves antiguas, fusión de sinónimos, puentes y consolidación. Se excluyeron las pruebas MCP, la búsqueda directa, sustantivos MCP y preflight MCP:

```text
....................................................                     [100%]
52 passed, 8 deselected in 3.79s
```

Comprobaciones puramente locales adicionales: los 8.560 signos y símbolos Unicode individuales de esa versión se conservaron en el modo de texto; en el bloque U+FF00–FFEF se verificaron 172 caracteres L/N y 68 de otras categorías. Se comprobaron 841 recortes sin U+3000 frente a `strip()` y 5.000 pares sintéticos de fusión sin U+3000 frente a la regla previa. No son QA oficiales ni pruebas de calidad de búsqueda.

El diff se aplicó con `git apply --check` y `git apply` en una **segunda copia** de `3f71f74`. Los 13 archivos coincidieron con la copia probada; también se compararon los 1.800 archivos de ambas copias, excluidos cachés de pytest y Python, sin diferencias. El snapshot original mantuvo SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`.

**Pendiente del OK de Dennys:** las cuatro QA oficiales, la batería multilingüe, las pruebas MCP y el circuito de 80 guardados MCP. No se ejecutaron para v2. Los 746 tests y las 132 búsquedas sintéticas del informe v1 corresponden a **v1**, no acreditan v2. La regresión de búsqueda se evaluará por rangos, R@5/R@1 y falsos positivos por categoría, no solo por score.

El commit documental lleva `[skip ci]` para no disparar automáticamente la suite que incluye pruebas MCP antes de ese OK. No se modificó el workflow; la CI exitosa del commit v1 corresponde al árbol sin aplicar el motor propuesto y no certifica v2.

### Reproducir las pruebas unitarias en copia

Con un entorno Python que tenga las dependencias del proyecto y pytest, desde la raíz del repositorio:

```bash
PATCH="$PWD/docs/e3_cambio1_identidad_diff_v2_NO_APLICAR_20261029.patch"
D=$(mktemp -d)
git archive 3f71f7434e95d6f6e61f71c00b64a3e7a49c2e49 | tar -x -C "$D"
(cd "$D" && git apply --check "$PATCH" && git apply "$PATCH")
cd "$D"                              # solo la copia desechable
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 BIORAG_WORDNET_ENABLED=1
export BIORAG_DMN_ESTADO_PATH="$D/estado-test.json"
unset BIORAG_NEURONA BIORAG_PATH
python -m pytest -q \
  tests/test_identidad_unicode_cambio1.py \
  tests/test_validacion_bridges_unicode_b3.py \
  tests/test_consolidar_concepto_fusion.py \
  -k 'not mcp and not sustantivos and not busqueda and not preflight'
```

No copiar una base con WAL/SHM pendientes ni abrir el snapshot original en escritura. Estas pruebas usan bases temporales y la fixture de pytest copia el snapshot de la copia.
