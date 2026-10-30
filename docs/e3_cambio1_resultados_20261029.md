# E3 Cambio 1 — identidad Unicode: aplicación y resultados (2026-10-29)

**Resultado: sin bajadas detectadas** en las cuatro QA oficiales, ni pérdidas de rango dentro del top 5 en las comparaciones sintéticas disponibles. Las QA oficiales no conservan todos los rangos individuales: la igualdad caso por caso de sus 921 consultas no puede certificarse con sus archivos de salida.

- Commit del motor y pruebas: `c695310f84164eb2a8496fb7b9dc38f4733d8285`.
- Diff v2 autorizado, conservado sin cambios: `68439804583a727fadb6cea597542e11b4e6b77339fb99cee9262ee423e54cc4`.
- Resumen agregado legible por máquina: `docs/e3_cambio1_resultados_agregados_20261029.json`, SHA-256 `57c4ec72c8add829293d44fcb4aa707dbba9d2ba7842e34b1cc8a8d4d570c3cf`. No contiene consultas, títulos, fallos individuales ni base de la viva.
- Referencia de comparación: B3/B4a, antes de aplicar Cambio 1. Sin merge; la decisión sobre master corresponde a Dennys.

## 1. Corrección y suite completa

El auditor detectó que el test MCP llamaba a `recordar` sin sustantivos clave. La única diferencia frente al diff v2 es añadir `sustantivos_clave="ejemplo"` a esa llamada. Los otros 12 archivos son idénticos a la propuesta v2.

En una copia aislada con los mismos 13 archivos, Python 3.11.2, sin `BIORAG_PATH` ni `BIORAG_NEURONA` forzados y **sin filtros**:

```text
python -m pytest -q tests/
753 passed in 171.02s (0:02:51)
```

Salida 0. Antes de aplicar y después de las QA se comprobó que los 13 archivos del motor coinciden byte a byte con esa copia y con las huellas de inicio. El antiguo resultado de 52 pruebas usaba `-k 'not mcp and not sustantivos and not busqueda and not preflight'`, excluía la prueba fallida y **no** era una suite completa.

## 2. Cuatro QA oficiales

921 casos por ejecución; sin filtro manual de casos. La métrica honesta mantiene las exclusiones y resolución de etiquetas históricas. `BIORAG_NEURONA=0`, `PYTHONHASHSEED=0`, WordNet habilitado, límite 5 y `ignore_peso_sinaptico=True`. Para comparabilidad con B3, el arnés usa `activos` normalmente y `profundo` en `deep`, `dormido` y `negativo`. En ruido se añadió `zzqx` y se activó el censo temático.

Valores **antes = después**. Cada celda muestra R@5 / R@1 en porcentaje / MRR; FP es falsos positivos / controles negativos.

| Escenario | Snapshot R@5 / R@1 / MRR | Viva R@5 / R@1 / MRR | FP snapshot | FP viva |
|---|---:|---:|---:|---:|
| Normal | 100,00 / 95,31 / 0,9718 | 99,88 / 93,53 / 0,9622 | 0/40 → 0/40 | 0/40 → 0/40 |
| Ruido | 97,34 / 88,63 / 0,9281 | 96,63 / 88,12 / 0,9215 | 0/40 → 0/40 | 0/40 → 0/40 |

También son iguales los R@5 y R@1 por categoría y, en ruido, el censo; cero fallos R@5 nuevos o recuperados. Cada fuente, el código de los 13 archivos, los scripts de QA y el archivo de casos conservaron su huella entre el inicio y el final de cada ejecución. No se publicó la huella de la viva; el snapshot conservó SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`.

Las pruebas con ruido completaron todos los casos y exportaron métricas y fallos, pero su proceso salió con código 1 por el **gate histórico**: ya termina en rojo con los valores de referencia ruidosos. Los códigos de las normales fueron 0. Se compararon los resultados reales, no se trató el código 1 como éxito genérico.

Por categoría: valores **antes = después**, expresados como R@5 / R@1; los denominadores están en el JSON agregado. La categoría negativa aporta los 40 controles de FP de cada ejecución.

| Categoría | Snapshot normal | Viva normal | Snapshot ruido | Viva ruido |
|---|---:|---:|---:|---:|
| `cruce_idioma` | 100,00 / 62,50 | 100,00 / 62,50 | 62,50 / 50,00 | 62,50 / 62,50 |
| `dormido` | 100,00 / 100,00 | 100,00 / 100,00 | 98,46 / 95,38 | 98,46 / 98,46 |
| `literal` | 100,00 / 99,59 | 100,00 / 99,38 | 99,38 / 91,38 | 98,56 / 91,38 |
| `por_tema` | 100,00 / 69,23 | 98,46 / 63,08 | 95,38 / 67,69 | 92,31 / 56,92 |
| `pregunta_natural` | 100,00 / 96,92 | 100,00 / 95,38 | 98,46 / 93,85 | 100,00 / 96,92 |
| `sinonimo` | 100,00 / 87,88 | 100,00 / 90,00 | 88,89 / 78,79 | 85,37 / 80,00 |
| `typo` | 100,00 / 92,31 | 100,00 / 87,69 | 93,85 / 90,77 | 96,92 / 90,77 |
| `variante_gramatical` | 100,00 / 93,85 | 100,00 / 83,08 | 95,38 / 84,62 | 92,31 / 80,00 |

**Límite de evidencia:** el arnés guarda agregados por categoría y los fallos R@5, no todos los rangos individuales. Igualdad de agregados y de fallos no demuestra igualdad de todos los puestos individuales. Como control adicional, ninguna de las 921 consultas cambia al aplicar el normalizador, ni normal ni con `zzqx`; esto no reemplaza una medición por rango.

## 3. Baterías sintéticas multilingües y MCP

Sin filtros de idioma o de casos: 132 casos directos y 132 MCP, cada batería con 20 positivos y 2 negativos por idioma. Comparados por ID contra B4a: cero rangos del top 5 perdidos o mejorados, cero FP nuevos y cero rechazos nuevos. Las posiciones fuera del top 5 no se distinguen entre sí. La ejecución en orden inverso no cambió los resultados. Directa: `activos`, límite 5, peso ignorado. MCP: `activos`, límite público 5, pool interno 15; `recordar` no expone ignorar peso y usa el valor predeterminado del motor. `BIORAG_NEURONA=0`, semilla 0 y reloj fijo en ambos brazos.

Valores **antes = después**: aciertos R@5 / aciertos R@1 / FP.

| Idioma | Directa | MCP |
|---|---:|---:|
| zh | 12 / 12 / 0 | 12 / 12 / 0 |
| ja | 12 / 12 / 0 | 8 / 8 / 0 |
| ko | 19 / 18 / 0 | 16 / 16 / 0 |
| ru | 20 / 19 / 0 | 20 / 19 / 0 |
| en | 20 / 20 / 2 | 20 / 20 / 2 |
| es | 20 / 20 / 0 | 20 / 20 / 0 |

Los 2 FP en inglés ya estaban en B4a. Las 14 consultas MCP del hueco de un carácter siguen pendientes (14 → 14), sin rechazos nuevos.

En 80 intentos de guardado MCP por versión, sin filtro de idioma: 69 guardados en cada una (zh 18, ja 15, ko 16, ru 20); los otros 11 tampoco se guardaban en la referencia. No se perdió ningún guardado ni hubo errores operativos. Cada semilla sintética terminó con 69 hubs y 345 puentes. En 414 búsquedas por brazo, con hubs ON/OFF y comparadas por ID, no bajó ningún rango dentro del top 5: tanto usando la misma semilla para ambos motores como comparando las semillas creadas por cada versión. Las semillas tienen SHA distintos y no se presentan como idénticas.

## 4. Base mixta sintética

Con v2, las consultas ancha y estrecha devuelven la misma lista. Ambos recuerdos comparten el mismo marcador y no existe gold para decidir cuál debe ir primero: **la identidad funciona; no es una regresión**. Esta prueba usa una base sintética, no la viva; `activos`, límite 5 y peso ignorado. SHA-256 de la base sintética: `5d02f4821f8856970dba1dbe20bb30c143e96a2aae68c6595526876ee40ad782`.

## 5. Alcance y huellas SHA-256

En contenido y sinónimos nuevos solo se pliegan letras y números de ancho completo/medio y se conserva la puntuación, símbolos y U+3000; en nombres, consultas, puentes y sustantivos clave se mantiene la identidad completa. En las rutas probadas se prioriza la clave legacy original exacta y se actualiza sin error ni crear un duplicado plegado; no garantiza unificar todas las variantes heredadas ni operaciones concurrentes. Esto no afirma que todas las rutas de escritura plieguen ancho: `actualizar` MCP queda fuera. Cambio 2, U+309B y B4b siguen independientes.

Las siguientes huellas son las de los archivos del commit del motor y las medidas en QA. Coinciden con el diff v2 salvo el test MCP indicado:

| Archivo | SHA-256 del commit/QA | Comparación con v2 |
|---|---|---|
| `core/README.md` | `4c2291a14d4af686180bd7a04bd5ec5035c4d015dcb4889d951c1e9f45a2a351` | Igual |
| `core/concept_hub.py` | `c02ca5191f61d5d578a66bad6a2a21eefc49151cf1925c02477a32091c8243c7` | Igual |
| `core/identidad_unicode.py` | `05f6a3284ede311b7f7c9f59f4f43e046342275f1f403643fb0a70ecf53c0b8a` | Igual |
| `core/mcp_server/_shared.py` | `31f9f6ec5befdc98ca492b55646763b7eac0503d328c7ea27364d2b3f543589c` | Igual |
| `core/mcp_server/search.py` | `432ee33c499bd9326010a6172e6208b8879e25a767343d7e78bc70a0db7fb32a` | Igual |
| `core/mcp_server/write.py` | `3fe72510034498f07fd7c28b1dbc5d10c5159d2b72365f71f65e526d8ccd8ec1` | Igual |
| `core/memory/constants.py` | `8f748fe21e4aa524ca84df71cb021a2c9e81ca2ba2cdc33f3d23e1f135ca13e8` | Igual |
| `core/memory/consolidation.py` | `e33f2c40f033a193b128501589c4c10f393766e1eb54e5e1556975df49b47f06` | Igual |
| `core/memory/ingest.py` | `2b3c7c520f40506ce23687865eb18110b9ca6ceddd140a8f23babd4a52ede459` | Igual |
| `core/memory/search.py` | `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6` | Igual |
| `core/memory_service.py` | `5692b6a8dc7d8302356a476603bfa39840867f983896d9f3168c831421e8ff07` | Igual |
| `tests/test_identidad_unicode_cambio1.py` | `3a81c9150cb64915eaeacc386b29f64f40a034abf297b6ff454d62fe58778bbd` | Línea MCP corregida |
| `tests/test_validacion_bridges_unicode_b3.py` | `fc6ad1d4a0a75009f11af6e6ee6f4f5ebdd89a50daf156834e298232f0192bc1` | Igual |

Test antes de corregir en el diff v2: `f884e2f830c566c3943515265fe5b790dafe5d6157a68009d493c723def04b57`. Test corregido: `3a81c9150cb64915eaeacc386b29f64f40a034abf297b6ff454d62fe58778bbd`.
