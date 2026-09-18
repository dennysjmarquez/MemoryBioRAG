# Spec 003 — Descubrimiento del Núcleo Temático por parte del Agente

## Contexto y objetivo

Las Specs 001 y 002 dejaron `sustantivos_clave` completamente implementado en las tres
capas del sistema: motor (`core/memory_store.py`: columna, FTS5 de 4 columnas, BM25
`5.0/1.0/2.0/4.0`, propagación en consolidación), servidor MCP (`mcp_server.py`:
validación fail-fast, tools `sustantivos` / `agregar_sustantivos`, boost en
`recordar`) y CLI (`biorag.py`: flags, subcomandos, visibilidad transversal).

Quedaba pendiente una cuarta capa, que es la que determina si la feature se usa o no:
**el descubrimiento por parte del agente**. Los otros dos parámetros cognitivos de
búsqueda —`deep` (búsqueda profunda) y `parafrasis` (parafraseo)— están expuestos en
seis superficies distintas cada uno; `sustantivos_clave` estaba en dos.

El `AGENTS.md` del repositorio lo establece como invariante:

> **Invariant 1: UX-First Universal Design** — If a feature is "default-OFF" and
> invisible to a standard user, it provides zero real-world value.

Un parámetro que el agente no encuentra es un parámetro que no se usa. Y aquí el costo
no es teórico: `sustantivos_clave` es **obligatorio al guardar**, de modo que un agente
que no lo conoce no puede persistir memoria en absoluto.

### Diagnóstico de partida (brecha por superficie)

Auditoría de las superficies donde `deep` y `parafrasis` ya estaban presentes:

| # | Superficie | `parafrasis` | `deep` | `sustantivos_clave` (antes) |
|---|---|---|---|---|
| 1 | `ORACLE_PROMPT` (`instructions=` de FastMCP) | plantilla 5 niveles + reglas + árbol | árbol de decisión | 2 menciones sueltas, sin plantilla |
| 2 | Warning pedagógico en runtime (`_warnings`) | ⚠️ `parafrasis=None` | — | **ausente** |
| 3 | Descripción de la tool `recordar` | guía de modos, PASO 1, PARÁMETROS CLAVE | PARÁMETROS CLAVE | solo en el `Field` del parámetro |
| 4 | Alias legacy `buscar` | sí | sí | **no aceptaba el parámetro** |
| 5 | Prompt MCP `biorag-system-prompt` | — | — | **ausente** |
| 6 | `config/prompts.py` (system prompt que copia el humano) | gobernanza + ejemplos | gobernanza | **ausente**; ejemplos de `aprender` rotos |
| 7 | `AGENTS.md` (tabla de pitfalls) | fila propia | — | **ausente** |
| 8 | `skills/biorag-sync/SKILL.md` | flujo INVARIANT + tabla | tabla | **ausente**; ejemplos de `aprender` rotos |
| 9 | `plugin/opencode-biorag-remember-plugin.ts` | — | — | **ausente** |
| 10 | Visibilidad en resultados de búsqueda | `capa_parafrasis` en trazabilidad | `profundidad` | **ausente** |
| 11 | `log_busquedas` (auditoría de adopción) | registrado | registrado | **no registrado** |

### Hallazgos críticos detectados durante el análisis

Dos defectos que **rompían el uso real**, encontrados al ejecutar la documentación tal
como está escrita:

- **H-A — Ejemplos de guardado inviables.** Los ejemplos de `biorag_aprender` en
  `config/prompts.py` (REGLA #2 CASO A y AUTO-APRENDIZAJE DE ERRORES) y en
  `skills/biorag-sync/SKILL.md` no incluían `sustantivos_clave`. Verificado ejecutando
  el ejemplo verbatim: la tool responde `SUSTANTIVOS_CLAVE_AUSENTES` y **no guarda el
  nodo**. Un agente que siguiera la documentación oficial no podía persistir nada.
- **H-B — Placeholder inválido.** El mismo ejemplo usaba `cat="tipo"`, que no es una
  categoría válida. Respuesta real del motor: `Categoria 'tipo' no existe. Validas:
  Architecture, Cognition, General, Lesson, Personal, Principle, Profile, Project,
  Protocol, Relation, System`.

Ambos se corrigieron y se cubrieron con tests.

---

## Usuarios / actores

- **Agente BioRAG** (Athena, Hermes, Artemis, Kilo): descubre el parámetro sin haber
  leído el spec, por las superficies que ya usa (descripción de tool, warning, prompt).
- **Humano (Dennys)**: copia `config/prompts.py` al system prompt de sus agentes; los
  ejemplos deben funcionar a la primera.
- **Agente de mantenimiento**: ve el núcleo de cada nodo en los resultados y detecta los
  nodos legacy vacíos para enriquecerlos.

---

## Historias de usuario

- **H1**: Como agente, quiero que `recordar` me avise cuando omito `sustantivos_clave`,
  igual que me avisa con `parafrasis`, para descubrir el parámetro usándolo.
- **H2**: Como agente, quiero ver el `sustantivos_clave` de cada nodo en los resultados,
  para comprobar por qué subió al top y detectar nodos legacy sin núcleo.
- **H3**: Como agente, quiero que el alias `buscar` acepte el mismo parámetro que
  `recordar`, para no perder el boost por usar la tool legacy.
- **H4**: Como agente, quiero una plantilla de extracción en mis instrucciones de
  sistema, al mismo nivel que las de paráfrasis y ráfaga, para saber cómo extraer el
  núcleo sin inventarlo.
- **H5**: Como humano, quiero que los ejemplos de guardado de la documentación
  funcionen tal como están escritos, para no debuggear el system prompt.
- **H6**: Como agente de mantenimiento, quiero que las búsquedas queden registradas con
  el núcleo aplicado, para auditar la adopción real del parámetro.

---

## Requisitos funcionales

- **RF-D1**: EL SISTEMA expone `sustantivos_clave` en `ORACLE_PROMPT` (que FastMCP
  inyecta como `instructions=`) con el mismo nivel de detalle que `parafrasis` y
  `rafaga_palabras`: plantilla propia de extracción, entradas en errores comunes, rama
  en el árbol de decisión y paso explícito en el protocolo de guardado.
- **RF-D2**: CUANDO `recordar` o `buscar` devuelven resultados, EL SISTEMA incluye en
  cada item los campos `sustantivos_clave` (string) y `sustantivos_clave_items` (lista),
  con `""` / `[]` para nodos legacy sin núcleo.
- **RF-D3**: CUANDO el agente llama a `recordar`/`buscar` con `query` y sin
  `sustantivos_clave`, EL SISTEMA antepone un ⚠️ pedagógico que explica el efecto
  (boost BM25 4.0x), el formato y un ejemplo. La búsqueda SE EJECUTA igual (RF-19 del
  Spec 001: el parámetro es opcional al buscar).
- **RF-D4**: EL alias legacy `buscar` acepta `sustantivos_clave` y lo aplica con
  paridad exacta respecto de `recordar`, incluida la validación fail-fast de RF-20.
- **RF-D5**: Las descripciones de las tools `recordar`, `buscar`, `aprender` y `guardar`
  documentan el parámetro, y el JSON Schema que publica el servidor lo expone — que es
  lo que el cliente MCP muestra al agente.
- **RF-D6**: El prompt MCP `biorag-system-prompt` incluye la regla del núcleo temático
  (obligatorio al guardar, opcional al buscar, tools hermanas).
- **RF-D7**: EL SISTEMA registra `sustantivos_clave` **normalizado** en
  `log_busquedas.params_json` (`None` cuando se omite), para auditar adopción.
- **RF-D8**: Los ejemplos de `aprender`/`guardar` de toda documentación orientada al
  agente incluyen `sustantivos_clave` y `bridges`, y usan únicamente categorías válidas.
- **RF-D9**: **NO** se modifica el motor de scoring, el esquema, ni los pesos BM25.
  Esta spec es exclusivamente de exposición. Cero riesgo de regresión de ranking.

---

## Requisitos no funcionales

- **RNF-D1**: Sin cambio en el orden de resultados para llamadas que no pasen el
  parámetro (verificado con la suite QA oficial de 921 casos).
- **RNF-D2**: La visibilidad del campo (RF-D2) se resuelve con 1 query batch por tabla,
  reutilizando el patrón ya existente de `dimensiones_semanticas`. Sin N+1.
- **RNF-D3**: Los tests de esta spec no dependen del orden de ejecución ni de la
  higiene de otros módulos (fijan sus propias precondiciones de entorno).

---

## Casos límite

- **CL-D1**: `sustantivos_clave=""` → se trata como omisión: sin boost y con ⚠️.
- **CL-D2**: Nodo legacy (`sustantivos_clave=''`) → aparece en resultados con `""` y
  `[]`; no recibe boost pero tampoco se oculta (RF-15 Spec 001: sin backfill).
- **CL-D3**: Término inválido vía alias `buscar` → error
  `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`, búsqueda NO ejecutada (paridad con `recordar`).
- **CL-D4**: Warning pedagógico nunca bloquea la búsqueda: `total >= 1` igual que sin él.
- **CL-D5**: DB anterior a la migración de la columna → el campo simplemente no se
  adjunta; la búsqueda no se rompe.

---

## Decisiones de diseño

### El warning es pedagógico, no bloqueante

`parafrasis` y `dimensiones` ya usan este mecanismo: la búsqueda se ejecuta y el ⚠️ va
como texto plano antes del JSON. Se replica exactamente ese patrón. Convertirlo en error
contradeciría RF-19 del Spec 001, que definió el parámetro como opcional al buscar.

### Visibilidad del campo en resultados: por qué importa

No es decoración. Cumple tres funciones concretas:

1. **Descubrimiento por observación** — el agente ve el campo en la respuesta y aprende
   que existe, sin leer documentación.
2. **Circuito cerrado** — si buscó con `sustantivos_clave='contaminacion,aire'`, ve el
   núcleo del nodo que subió al top y puede comprobar por qué ganó.
3. **Mantenimiento** — `""` delata un nodo legacy. El agente sabe que puede enriquecerlo
   con `agregar_sustantivos()` en lugar de ignorarlo.

### Lo que deliberadamente NO se cambió

Las rutas de auto-guardado (`middleware/auto_guardado.py`, `auto_save_plugin.py`,
`middleware/interceptor.py`) llaman a `cerebro.percibir_corto_plazo()` directamente, sin
pasar por la validación obligatoria del MCP, y por lo tanto crean nodos con
`sustantivos_clave=""`. Se evaluó derivarles un núcleo automáticamente y se descartó:

- El Spec 001 es explícito: *"El agente DEBE extraer los sustantivos clave del contenido.
  **No los inventa**"*. Un heurístico automático los inventaría.
- RF-15 prohíbe el backfill automático.
- `AGENTS.md` prohíbe hardcodear vocabularios de dominio en el motor.
- Tocar la ruta de escritura cambiaría métricas, violando Invariant 2 (un cambio a la vez).

En su lugar se optó por **hacerlos visibles** (RF-D2): el agente los ve vacíos y decide.
Es consistente con la filosofía del spec y no introduce sesgo de dominio.

---

## Métricas de referencia

| Métrica | Baseline oficial | Gate | Post-Spec-003 |
|---|---|---|---|
| Recall@5 Global | 98.06% | ≥ 97.0% | **98.06%** ✅ |
| Recall@1 (Top-1) | 90.74% | ≥ 88.0% | **90.74%** ✅ |
| MRR | 0.9355 | ≥ 0.90 | **0.9355** ✅ |
| Tasa de FP | 0.0% (0/40) | = 0.0% | **0.00%** ✅ |
| Fallos | 17/875 | ≤ 24 | **17** ✅ |
| Concept Hub (5 ángulos) | 5/5 (100%) | — | **5/5 (100%)** ✅ |
| Abismo léxico | 3/3 (100%) | — | **3/3 (100%)** ✅ |
| Tests unitarios | 263 | 100% | **295** ✅ (+32) |

Cero regresión: la suite oficial `scripts/run_qa_suite.sh` termina con `EXIT=0` y
`[GATE] OK`.

### Nota de entorno (reproducible)

La primera corrida de la suite QA en este entorno dio roja (Recall@5 por categoría hasta
-12.50 pp). La causa **no** fue el cambio de código sino una dependencia faltante:
`nltk` no estaba instalado, y se usa en la ruta caliente de recuperación
(`core/memory_store.py:5010` para WordNet y `core/stemmer_es.py:102` para el stemmer
Snowball), donde su ausencia degrada en silencio. Tras `pip install -r requirements.txt`
(freeze pineado que el propio `requirements.txt` documenta como obligatorio para medir),
las métricas volvieron a la baseline exacta.

> **Lección**: medir siempre con el freeze pineado. Un entorno incompleto produce
> regresiones fantasma que no existen en el código.

---

## Comandos de verificación

```bash
# Suite oficial completa (pytest + scoring + concept hub + abismo léxico + QA 921 casos):
bash scripts/run_qa_suite.sh

# Solo los tests de esta spec:
python3 -m pytest tests/test_sustantivos_clave_descubrimiento.py -v

# Suite completa:
python3 -m pytest tests/ -q
```
