# Spec 001 — Sustantivos Clave (Núcleo Temático)

## Contexto y objetivo

BioRAG recupera nodos mediante BM25 sobre concepto (5.0x), contenido (1.0x) y sinónimos (2.0x). Sin embargo, los sinónimos son alternativas de vocabulario (palabras diferentes que significan lo mismo), no indicadores de qué TRATA el nodo. Esto genera una brecha: un nodo sobre "contaminación" que menciona "automóviles" se recupera igual que un nodo sobre "automóviles" que menciona "contaminación", porque ambos comparten las mismas palabras. El campo `sustantivos_clave` resuelve esto definiendo el centro de gravedad semántico del nodo — los 2-4 sustantivos que sostienen la idea principal — y dándoles un peso BM25 de 4.0x (más fuerte que sinónimos, más débil que el nombre del concepto).

## Usuarios / actores

- **Agente bioRAG** (Athena, Hermes, Artemis, Kilo): crean nodos con `biorag_aprender` y buscan con `biorag_recordar`.
- **Humano (Dennys)**: supervisa la calidad de los nodos.

## Historias de usuario

- **H1**: Como agente bioRAG, quiero guardar el núcleo temático de un nodo al crearlo, para que las búsquedas futuras lo recuperen por lo que TRATA, no solo por lo que MENCIONA.
- **H2**: Como agente bioRAG, quiero que el motor BM25 potencie los sustantivos clave con peso 4.0x, para que los nodos con coincidencia temática suban al top de resultados.
- **H3**: Como agente bioRAG, quiero recibir un error claro si omito sustantivos_clave al guardar, para que la calidad sea obligatoria y no opcional.
- **H4**: Como agente bioRAG, quiero que sustantivos_clave se propague de corto_plazo a largo_plazo durante la consolidación (sueño), para que el boost temático persista permanentemente.
- **H5**: Como agente bioRAG, quiero una tool MCP para agregar `sustantivos_clave` a un nodo existente que no lo tenga, para que pueda enriquecer nodos legacy gradualmente sin backfill automático.
- **H6**: Como agente bioRAG, quiero una tool MCP para consultar si un nodo tiene `sustantivos_clave` y devolverlos, para que pueda verificar el estado de cualquier nodo antes de usarlo o mejorarlo.
- **H7**: Como agente bioRAG, quiero pasar `sustantivos_clave` como filtro opcional en `biorag_recordar` para potenciar mis búsquedas con el centro de gravedad temático, recuperando nodos por lo que TRATAN, no solo por lo que MENCIONAN.

## Requisitos funcionales

- **RF-1**: CUANDO un agente llama a `biorag_aprender` sin `sustantivos_clave` o con `sustantivos_clave` vacío, EL SISTEMA retorna error JSON con código `SUSTANTIVOS_CLAVE_AUSENTES` y mensaje accionable con el protocolo de extracción.
- **RF-2**: CUANDO el agente envía menos de 2 o más de 4 términos, EL SISTEMA retorna error `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA`.
- **RF-3**: CUANDO algún término tiene <2 o >15 caracteres (límites inclusivos: 2 y 15 son válidos), contiene espacios, o caracteres especiales (excepto guion bajo), EL SISTEMA retorna error `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`.
- **RF-4**: CUANDO `sustantivos_clave` es válido, EL SISTEMA almacena en `corto_plazo` y indexa en FTS5.
- **RF-5**: EL SISTEMA indexa `sustantivos_clave` en FTS5 trigram. Los queries BM25 usan `bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0)` — concepto=5.0x, contenido=1.0x, sinonimos=2.0x, sustantivos_clave=4.0x. Para nodos sin campo (pre-migración), la columna aporta peso 0.0.
- **RF-6**: MIENTRAS el nodo está en `corto_plazo`, EL SISTEMA propaga el campo a `largo_plazo` durante consolidación.
- **RF-7**: CUANDO un nodo consolidado tiene `sustantivos_clave`, EL SISTEMA lo incluye en FTS5 de `largo_plazo`.
- **RF-8**: `biorag_guardar` (alias legado) acepta `sustantivos_clave` como obligatorio con las mismas validaciones.
- **RF-9**: CUANDO el agente envía >4 términos, EL SISTEMA retorna error (rechazo estricto, sin truncamiento silencioso).
- **RF-10**: EL SISTEMA normaliza a minúsculas, elimina espacios alrededor de comas, y quitas tildes (á→a, é→e, í→i, ó→o, ú→u) preservando la ñ.
- **RF-14**: CUANDO el agente envía términos duplicados en `sustantivos_clave`, EL SISTEMA auto-deduplica preservando el orden original, y luego evalúa la cantidad (2-4 términos únicos). Si tras deduplicar quedan <2 o >4, retorna error `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA`.
- **RF-15**: EL SISTEMA NO ejecuta backfill automático de `sustantivos_clave` sobre nodos existentes. Los nodos pre-migración se quedan con `sustantivos_clave=""` hasta que un agente decida enriquecerlos manualmente usando la tool `biorag_agregar_sustantivos`.
- **RF-16**: EL SISTEMA expone una tool MCP `biorag_agregar_sustantivos(concepto, sustantivos_clave)` que actualiza el campo de un nodo existente en `largo_plazo` (con fallback a `corto_plazo` si no está en largo) con las mismas validaciones que `biorag_aprender` (2-4 términos, formato, normalización). La actualización dispara el trigger `largo_plazo_au` (AFTER UPDATE) sincronizando `largo_plazo_fts` inmediatamente. Retorna error `NODO_NO_ENCONTRADO` si el nodo no existe en ninguna tabla. Si el nodo ya tiene `sustantivos_clave`, sobrescribe mostrando `"sustantivos_anteriores"` vs `"sustantivos_nuevos"` en la respuesta.
- **RF-17**: EL SISTEMA expone una tool MCP `biorag_sustantivos(concepto)` que consulta un nodo por nombre y devuelve sus `sustantivos_clave`. Si el nodo no existe → error `NODO_NO_ENCONTRADO`. Si existe pero no tiene campo → `{"status": "ok", "sustantivos_clave": "", "items": []}`.
- **RF-18**: EL SISTEMA aplica la misma normalización de acentos (`_quitar_acentos()`) a las queries de `biorag_recordar` antes de enviarlas a FTS5, asegurando simetría con lo almacenado en `sustantivos_clave`.
- **RF-19**: `biorag_recordar` acepta un parámetro opcional `sustantivos_clave` (string, separados por coma). Cuando se provee, el sistema lo agrega como condición de boost en la query FTS5 — nodos cuyo `sustantivos_clave` coincida con los términos recibidos suben en el ranking. NO es obligatorio: si se omite, la búsqueda funciona normalmente. Incluir nota en la descripción del parámetro: *"Usar para potenciar la precisión de búsqueda. Los nodos con estos sustantivos en su centro de gravedad temático suben al top."*
- **RF-20**: CUANDO el agente envía `sustantivos_clave` en `biorag_recordar`, EL SISTEMA valida el formato (2-15 chars, sin espacios, solo alfanuméricos + guion bajo, sin tildes) y retorna error accionable si falla. La búsqueda NO se ejecuta si la validación falla.
- **RF-21**: EN `biorag_aprender`, la validación de `sustantivos_clave` (cantidad, formato, normalización) ocurre ANTES de escribir en `corto_plazo`. Si falla, el nodo NO se guarda y el agente recibe el error con el protocolo de extracción para que reformule y vuelva a intentar.
- **RF-22**: CUANDO se crea una base de datos nueva desde cero (primera instalación), EL SISTEMA crea `corto_plazo` y `largo_plazo` con la columna `sustantivos_clave TEXT DEFAULT ''` incluida en el `CREATE TABLE`, y levanta `largo_plazo_fts` con las 4 columnas (concepto, contenido, sinonimos, sustantivos_clave). CUANDO se migra una base de datos existente (sin la columna), EL SISTEMA la agrega con `ALTER TABLE ADD COLUMN` en ambas tablas y reconstruye la FTS5 en 4 columnas, sin afectar los nodos previos.
- **RF-23**: EL SISTEMA provee una batería de casos de extracción (`specs/001-sustantivos-clave/bateria_extraccion.md`) — set fijo de textos de prueba con núcleos temáticos esperados y términos prohibidos, basado en el Ejemplo Maestro — para verificar que cualquier modelo/agente extraiga el centro de gravedad semántico correctamente, tanto al guardar (`biorag_aprender`) como al buscar (`biorag_recordar`). La batería debe poder ejecutarse con el modelo principal y, si la configuración lo permite, con al menos un modelo/agente adicional para comparar.
- **RF-11**: **OBLIGATORIO ANTES DE IMPLEMENTAR:** Medir métricas baseline (pytest + evaluar_qa.py + test_abismo_lexico.py) y registrar resultado.
- **RF-12**: **OBLIGATORIO DESPUÉS DE IMPLEMENTAR:** Repetir las mismas métricas y comparar con baseline. Si hay regresión en CUALQUIER métrica → revertir inmediatamente.
- **RF-13**: **OBLIGATORIO PARA CUALQUIER CAMBIOS FUTUROS:** Toda modificación de código debe ir acompañada de evidencia de métricas Antes vs Después.

## Requisitos no funcionales

- **RNF-1**: Validación fail-fast ANTES de escribir en DB.
- **RNF-2**: Compatible con FTS5 trigram existente.
- **RNF-3**: Sin degradación de rendimiento en búsquedas existentes.

## Casos límite

- **CL-1**: String vacío `""` → error `SUSTANTIVOS_CLAVE_AUSENTES`.
- **CL-2**: Comas múltiples `"servidor,,backend"` → normalizar a `"servidor,backend"`.
- **CL-3**: Espacios alrededor de comas `"servidor , backend"` → trim.
- **CL-4**: 5 términos → error `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA`.
- **CL-5**: Nodo pre-migración sin campo → queda `""`, peso BM25 = 0.0 en esa columna.
- **CL-6**: Fusión en consolidación → `sustantivos_clave` de `corto_plazo` sobrescribe el de `largo_plazo`.
- **CL-7**: Guion bajo `_` permitido, guiones `-` no permitidos, mayúsculas → minúsculas.
- **CL-8**: Duplicados `"servidor,servidor,backend"` → auto-dedup a `"servidor,backend"` (2 únicos → válido).
- **CL-9**: Acentos `"conexión,timeout"` → normalizar a `"conexion,timeout"` (sin tildes, preservando ñ).
- **CL-10**: `sustantivos_clave` en `recordar` con formato inválido → error accionable, búsqueda NO se ejecuta.
- **CL-11**: `sustantivos_clave` en `recordar` con nodo pre-migración (campo vacío) → el nodo no recibe boost pero aparece en resultados normales.
- **CL-12**: Instalación (DB nueva desde cero) → las tablas nacen con `sustantivos_clave` y la FTS5 con 4 columnas sin ejecutar ningún `ALTER`.
- **CL-13**: Instalación (DB existente) → el arranque agrega la columna vía `ALTER` y reconstruye la FTS5 en 4 columnas preservando los nodos ya consolidados.
- **CL-14**: Batería de extracción: texto con núcleo implícito ("Los automóviles botan humo") → el extraído DEBE ser `contaminacion`, NUNCA `automovil` (ejemplo secundario). Un agente que extraiga `automovil` falla la batería.

## Protocolo de extracción (para agentes)

El agente DEBE extraer los sustantivos clave del contenido. No los inventa. Pregunta: **¿Qué TRATA este nodo?**

### El Ejemplo Maestro

**La distinción clave:** `sustantivos_clave` ≠ `sinonimos`. Los sinónimos son palabras diferentes que significan lo mismo (variedad de vocabulario). Los sustantivos clave son el **centro de gravedad semántico** — los objetos/conceptos sobre los cuales TRATA el nodo.

**La prueba del automóvil:**

| Texto | ✅ Sustantivo Clave | ❌ No es el núcleo | ¿Por qué? |
|---|---|---|---|
| "Historia del automóvil desde 1886" | `automóvil` | ~~`historia`~~ | Todo gira en torno al automóvil |
| "Los automóviles botan humo que contamina" | `contaminación` | ~~`automóvil`~~ | Automóvil es solo ejemplo secundario; el texto TRATA sobre contaminación |
| "El servidor backend cae por timeout" | `servidor, backend, timeout` | ~~`caída`~~ | "Caída" es consecuencia, no el tema central |
| "CSS flexbox arregla el layout" | `css, flexbox, layout` | ~~`arreglo`~~ | "Arreglo" es la acción, no el tema |

**Regla mental:** El mismo nodo puede contener "automóvil" como palabra, pero si el texto TRATA sobre contaminación, el sustantivo clave es `contaminación`, no `automóvil`. El sustantivo clave se forma por la **intención del autor** (qué TRATA), no por qué palabras aparecen.

### Protocolo

1. Leé el contenido completo.
2. Preguntá: ¿De QUÉ TRATA este nodo? No qué menciona — qué TRATA.
3. Identificá los 2-4 sustantivos centrales (objetos/conceptos/personas/lugares).
4. Filtrá: ejemplos secundarios y consecuencias NO van. El centro de gravedad SÍ va.
5. Validá: 2-4 términos, 2-15 chars, sin espacios, sin especiales.

### Ejemplo de guardado

```
concepto: "leccion_http_500_timeout"
contenido: "Se corrigió el error 500 en el servidor backend por timeout de conexión..."
sustantivos_clave: "servidor, backend, timeout, conexion"
syn: "error five hundred, server error, backend, caída del servidor"
```

## Métricas de referencia (baseline v31.3)

| Métrica | Valor | Gate |
|---|---|---|
| Recall@5 Global | 98.06% | ≥ 97.0% |
| Recall@1 (Top-1) | 90.74% | ≥ 88.0% |
| MRR | 0.9355 | ≥ 0.90 |
| Tasa de FP | 0.0% (0/40) | = 0.0% |
| Tests Unitarios | 168/168 PASSED | 100% |

### Comandos de verificación obligatorios

```bash
# ANTES de implementar:
python3 -m pytest tests/ -v --tb=short | tee /tmp/baseline_tests_$(date +%Y%m%d_%H%M).txt
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py 2>&1 | tee /tmp/baseline_qa_$(date +%Y%m%d_%H%M).txt
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py 2>&1 | tee /tmp/baseline_abismo_$(date +%Y%m%d_%H%M).txt

# DESPUÉS de implementar:
python3 -m pytest tests/ -v --tb=short | tee /tmp/post_tests_$(date +%Y%m%d_%H%M).txt
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py 2>&1 | tee /tmp/post_qa_$(date +%Y%m%d_%H%M).txt
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py 2>&1 | tee /tmp/post_abismo_$(date +%Y%m%d_%H%M).txt

# COMPARAR:
diff /tmp/baseline_tests_*.txt /tmp/post_tests_*.txt
diff /tmp/baseline_qa_*.txt /tmp/post_qa_*.txt
```

## Fuera de alcance

- Extracción automática (TF-IDF) — fase 2 futura.
- Backfill automático de nodos existentes — **NUNCA**. Los agentes enriquecen nodos gradualmente usando `biorag_agregar_sustantivos`.
- Ajuste dinámico de pesos BM25.
- Indexación unicode (solo trigram).

## Criterios de finalización

- [x] RF-1: error `SUSTANTIVOS_CLAVE_AUSENTES` con mensaje + protocolo.
- [x] RF-2: error `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA` con 1 término.
- [x] RF-3: error `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO` con término inválido.
- [x] RF-4: guardado exitoso con `sustantivos_clave='servidor,backend,timeout'`.
- [x] RF-5: BM25 prioriza nodos con match en `sustantivos_clave`.
- [x] RF-6: consolidación propaga campo a `largo_plazo`.
- [x] RF-7: nodo consolidado aparece en `largo_plazo_fts`.
- [x] RF-8: `biorag_guardar` sin campo retorna error.
- [x] RF-9: 5 términos → error (sin truncamiento).
- [x] RF-10: normalización a minúsculas funciona.
- [x] RF-14: deduplicación silenciosa funciona (duplicados → únicos).
- [x] RF-10: normalización de acentos funciona (conexión → conexion, preservando ñ).
- [x] RF-11: baseline medido y registrado ANTES de implementar.
- [x] RF-12: post-change medido y comparado. Cero regresiones.
- [x] Tests existentes pasan sin regresión (221/221 PASSED).
- [x] RF-15: nodo pre-migración se queda con `sustantivos_clave=""` (sin backfill).
- [x] RF-16: `biorag_agregar_sustantivos` actualiza nodo existente con validación completa + FTS5 sincronizado.
- [x] RF-16: `biorag_agregar_sustantivos` retorna `NODO_NO_ENCONTRADO` si el nodo no existe.
- [x] RF-16: `biorag_agregar_sustantivos` muestra `sustantivos_anteriores` vs `sustantivos_nuevos` al sobrescribir.
- [x] RF-17: `biorag_sustantivos` devuelve campo de nodo existente o `"", []`.
- [x] RF-17: `biorag_sustantivos` retorna `NODO_NO_ENCONTRADO` si el nodo no existe.
- [x] RF-18: normalización de acentos en queries de `biorag_recordar` simétrica con storage.
- [x] RF-19: `biorag_recordar` acepta `sustantivos_clave` opcional y boostea resultados.
- [x] RF-20: `biorag_recordar` valida `sustantivos_clave` y retorna error si formato inválido.
- [x] RF-21: `biorag_aprender` valida `sustantivos_clave` ANTES de escribir en DB (fail-fast).
- [x] RF-22: DB nueva desde cero → `.schema` muestra `sustantivos_clave` en ambas tablas, FTS5 con 4 columnas, sin ALTER.
- [x] RF-22: DB existente migrada → columna agregada en ambas tablas, FTS5 reconstruida, nodos previos intactos.
- [x] RF-23: `bateria_extraccion.md` existe con ≥6 casos (esperados + prohibidos).
- [x] RF-23: corrida con modelo principal → casos guardados y buscados coinciden con núcleos esperados (8/8 Top-1).
- [x] RF-23: corrida (si hay 2º modelo configurado) → comparación registrada en matriz.
- [x] Demo manual: guardar → buscar → boost verifica.
