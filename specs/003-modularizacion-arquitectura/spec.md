# Spec 003 — Modularización de Arquitectura y Descomposición de Monolitos

## Contexto y objetivo
`MemoryBioRAG` cuenta con componentes monolíticos de alta densidad (`core/memory_store.py` con 7.778 líneas y 99 métodos, y `mcp_server.py` con 4.358 líneas y 42 tools MCP + 2 resources + 1 prompt). Esta concentración excesiva dificulta la auditoría, mantenimiento y comprensión por desarrolladores humanos y agentes de IA.

El objetivo de esta especificación es descentralizar la base de código hacia módulos de responsabilidad única (SRP), manteniendo el paquete base `core/`, eliminando la fricción cognitiva y asegurando un **contrato de no-regresión por identidad verificable en entorno local controlado** (mismos Top-5 y mismos scores redondeados a 4 decimales caso a caso en el benchmark canónico de 921 casos, sin regresión en la suite unitaria de 264 tests).

---

## Usuarios / actores
- **Desarrollador / Investigador Humano:** Requiere navegar archivos legibles ($\le 500$ líneas orientativo, funciones $\le 100$ líneas), documentados y con responsabilidades desacopladas.
- **Agentes de IA (OEC / IDE):** Consumen las 42 herramientas MCP y la API de `SQLiteMemoryBioRAG` sin sufrir fallos de importación, cambios de contratos o timeouts de parsing.
- **Harness de Evaluación y CI:** Ejecuta suites unitarias y benchmarks asegurando reproducibilidad determinista en el entorno local activo.

---

## Historias de usuario
- **H1 (Navegabilidad y Legibilidad):** Como desarrollador o agente de IA, quiero inspeccionar módulos especializados por dominio semántico para auditar o extender componentes sin tener que procesar archivos de miles de líneas.
- **H2 (Invarianza de API y Compatibilidad de Imports):** Como cliente externo, script o agente que utiliza BioRAG, quiero invocar cualquier método público de `SQLiteMemoryBioRAG`, símbolo exportado (`normalizar_sustantivos_clave`) o herramienta MCP con sus nombres, parámetros y rutas de importación originales sin sufrir cambios de contrato ni roturas.
- **H3 (Determinismo y No-Regresión Local):** Como mantenedor del proyecto, quiero verificar tras cada extracción que el comportamiento del motor, los scores redondeados a 4 decimales y el orden del ranking Top-5 son exactamente idénticos al golden generado en la misma máquina.
- **H4 (Trazabilidad y Control de Versiones):** Como mantenedor del proyecto, quiero que cada avance atómico quede registrado en una rama de trabajo aislada con auditoría de líneas y pruebas en verde, manteniendo `master` 100% protegido.

---

## Requisitos funcionales (criterios de aceptación en EARS)

### Superficie Pública Congelada e Invarianza de Puntos de Entrada
- **RF-1 (Ubicuo):** EL SISTEMA mantendrá intactas todas las firmas públicas, nombres de métodos, parámetros y tipos de retorno de la clase `SQLiteMemoryBioRAG`.
- **RF-2 (Ubicuo):** EL SISTEMA mantendrá los 42 nombres exactos (`name=`) de las herramientas MCP, los 2 resources y el prompt sin alteración alguna.
- **RF-3 (Ubicuo):** EL SISTEMA preservará en la raíz del repositorio los puntos de entrada:
  1. `mcp_server.py`: requerido por `install.py`, `scripts/concurrencia_qa.py`, `pyproject.toml` (`mcp_server:main`), exponiendo `_build_server` (importado por `scripts/fuzz_qa.py`, `test_memory.py` y 4 tests) y `main`, delegando formalmente a `core.mcp_server.server` mediante bloque `if __name__ == "__main__": sys.exit(main())`.
  2. `biorag.py`: requerido por `pyproject.toml` (`biorag:main`), re-exportando `SQLiteMemoryBioRAG` (importado por `scripts/prune_stale_synapses.py` y `tests/test_biorag_cli.py`).
  3. `core/memory_store.py`: re-exportando la clase `SQLiteMemoryBioRAG` y la función `normalizar_sustantivos_clave` (importada por `biorag.py`, `mcp_server.py` y tests).
- **RF-4 (Ubicuo):** EL SISTEMA preservará la estructura exacta de tablas, índices y triggers del esquema SQLite sin introducir cambios de DDL incompatibles con bases de datos preexistentes.

### Descomposición de `mcp_server.py` (`core/mcp_server/`)
- **RF-5 (Ubicuo):** EL SISTEMA organizará las 42 herramientas, 2 recursos y 1 prompt en el paquete `core/mcp_server/` con la siguiente distribución estricta y exhaustiva:
  - `_shared.py`: única fuente de verdad para `_sesiones_activas` (compartida entre `contexto_inicio`, `contexto_fin` y `actualizar`), constantes (`LIMITE_MCP`, `VENTANA_CORRECCION`, `PARAFRASIS_PENALTY`, `NOTEBOOK_ID_ORACULO`, etc.) y helpers de módulo (`_get_cerebro()` perezoso delegando al singleton sin reconstruir corteza). Un helper va a `_shared.py` **solo si lo usan dos o más submódulos**, o si es estado o constante compartida; si lo usa un solo submódulo, se queda en ese submódulo. Los submódulos importan `_shared`; `server.py` es el único que importa submódulos — nunca al revés.
  - `server.py`: orquestador de registro `@mcp.tool`, bootstrap del servidor, import perezoso de `FastMCP` dentro de `_build_server()` con `try/except`. `_build_server()` queda como cableado puro: recorre los submódulos llamando a `register(mcp)` y devuelve el servidor ensamblado. Los cuerpos de las tools no se reescriben.
  - `search.py`: `biorag_recordar`, `biorag_buscar`, `_recordar_impl`.
  - `write.py`: `biorag_aprender`, `biorag_guardar`, `_aprender_impl`, `biorag_agregar_sustantivos`, `biorag_sustantivos`, `biorag_actualizar`.
  - `synapses.py`: `biorag_vincular`, `biorag_asociar`, `biorag_desvincular`, `biorag_feedback`.
  - `concept_hub_tools.py`: las 6 herramientas de Concept Hub, preservando intacto el identificador de función `concept_hub_cargar_iniciales_tool`.
  - `catalog.py`: `biorag_listar_categorias`, `biorag_listar_dimensiones`, `biorag_listar_tipos_dimension`, `biorag_listar_dimensiones_por_tipo`.
  - `introspection.py`: `biorag_introspeccion`, `biorag_estado`, `biorag_mapear`, `biorag_corteza`, `biorag_metricas_historial`.
  - `communication.py`: `biorag_comunicar`, `biorag_leer_mensajes`, `biorag_marcar_como_leido`.
  - `consolidation.py`: `biorag_consolidar`, `biorag_sueno`.
  - `daemon.py`: `biorag_hormiguita`, `biorag_hormiguita_estado`, `biorag_estado_dmn`.
  - `session.py`: `biorag_contexto_inicio`, `biorag_contexto_fin`.
  - `oracle.py`: `biorag_oraculo_inicio`, `biorag_oraculo_preguntar` y sus 3 helpers (`_nlm_detectado`, `_consultar_notebooklm`, `_buscar_contexto_biorag_arranque`), definidos en ese orden.
  - `sync.py`: `biorag_sync_status`, `biorag_export_sync`, `biorag_export_full`.
  - `calibrar.py`: `biorag_calibrar` (nombrado `calibrar.py` para no colisionar con `core/calibracion.py`).
  - `resources.py`: los 2 resources MCP.
  - `prompt.py`: el prompt MCP.
- **RF-6 (Ubicuo):** Cada submódulo de `core/mcp_server/` expondrá una función `register(mcp)` y documentará en la primera línea de su docstring la lista de nombres MCP en español correspondientes.
- **RF-7 (No deseado):** SI se trasladan referencias a `__file__` o `_PROJECT_ROOT` desde `mcp_server.py` hacia cualquier submódulo de `core/mcp_server/`, ENTONCES EL SISTEMA resolverá la raíz del proyecto mediante `core.paths.project_root()`. Esto aplica a:
  1. El arranque del servidor (`server.py` en Paso 2.4): `load_dotenv`, `logging.basicConfig`, warmup de WordNet, y el `sys.path.insert` que habilita `middleware.auto_guardado` — el insert debe agregar la raíz del repo, no el directorio del archivo nuevo. **Estos efectos de arranque se ejecutan al nivel de módulo al importar `server.py`, no dentro de `_build_server()`.** `FastMCP` se instancia dentro de `_build_server()`, igual que hoy.
  2. Cualquier bloque movido que use `_PROJECT_ROOT` (ej. línea 3051: `estado_hormiga.json` en hormiguita).
  3. **Test de validación CWD:** Se verifica en el Paso 2.4 lanzando un subproceso con `cwd=/tmp` y `PYTHONPATH=raíz_del_repo` (no con `os.chdir("/tmp")` seguido de import, que rompe el path).

### Descomposición de `core/memory_store.py` (`core/memory/` y Fachada)
- **RF-8 (Ubicuo - Mudanza sin Reescritura):** EL SISTEMA extraerá los métodos de `SQLiteMemoryBioRAG` hacia submódulos en `core/memory/` como funciones a nivel de módulo cuyo primer parámetro se llama `self`. El cuerpo no se toca, `self` no se renombra y las llamadas `self.X()` no se reescriben. La fachada `SQLiteMemoryBioRAG` conservará un delegador explícito para cada método — público o privado — que el cuerpo movido invoque como `self.X()`, de modo que `self` sigue siendo la instancia y el call-graph no cambia. Queda prohibido pasar `conn` suelto o reescribir llamadas cruzadas: eso es reescritura y está fuera de esta spec.
  - **Delegadores con firma completa:** Cada delegador conserva la firma completa del método original (todos los parámetros con sus nombres, tipos y defaults). Queda prohibido usar `*args, **kwargs` para comprimir delegadores y caber en 500. Si la fachada pasa de 500 por firmas largas, la justificación de una línea basta; no se parte la fachada ni es causal de fallo.
  - **Delegadores `@staticmethod` sin `self`:** `_ncd_sim`, `_jsd_weight_adaptativo`, `_calcular_jsd` y `_calcular_bm25_bayesiano` son `@staticmethod`. La fachada `SQLiteMemoryBioRAG` conservará el decorador `@staticmethod` con la misma firma sin `self` (delegando a `scoring.<metodo>(...)`), garantizando que llamadas sobre la clase (`SQLiteMemoryBioRAG._ncd_sim` en `tests/test_ncd_e6.py`, `SQLiteMemoryBioRAG._jsd_weight_adaptativo` en `tests/test_jsd_adaptativo_e7.py`) y llamadas sobre instancia (`self.X()`) sigan funcionando de forma idéntica. El cuerpo se muda a `scoring.py` como función o staticmethod sin `self`. `_calcular_bm25_bayesiano` se trata igual.
  - **Resolución de constantes y Monkeypatching en tests (Paso 3.1):** La calificación `constants.NOMBRE` se realiza una sola vez en el Paso 3.1, con las funciones todavía en la clase `SQLiteMemoryBioRAG` dentro de `core/memory_store.py`. Cada lectura de constante de configuración pasa a calificarse como `constants.NOMBRE` (importando `constants` desde `core.memory.constants`). No se toca ningún `if`, `SQL` ni fórmula. `logger` no es una constante (no se prefija; cada submódulo define su `logger`). `constants.py` no importa la fachada; `core/memory_store.py` re-exporta las constantes. En ese mismo commit, el `monkeypatch` de los tests pasa de `core.memory_store.FLAG` a `core.memory.constants.FLAG`. Las mudanzas posteriores no reescriben eso: el cuerpo ya dice `constants.NOMBRE` y el submódulo importa `constants`.
  - **Actualización de asserts literales (Paso 3.1):** En ese mismo commit del Paso 3.1, los 4 asserts que inspeccionan el texto exacto actualizan su cadena literal esperada:
    1. `tests/test_dim_escape.py`: `DIM_ESCAPE` → `constants.DIM_ESCAPE`
    2. `tests/test_dim_resonancia.py`: `"if DIM_RESONANCIA:"` → `"if constants.DIM_RESONANCIA:"`
    3. `tests/test_ncd_e6.py`: `"NCD_PESO * ncd_score"` → `"constants.NCD_PESO * ncd_score"`
    4. `tests/test_qcr_typo_d4.py`: la llamada con `QCR_TYPO_DIST`, al texto que quede tras calificar la constante y `_qcr_todos_cercanos`.
    El resto del assert no se toca. Queda prohibido borrar o debilitar los tests.
  - **Adaptación progresiva de `inspect.getsource`:**
    - En el Paso 3.4a: solo se redirige el `inspect.getsource` de `_calcular_score_hibrido` (en `test_ncd_e6.py`) hacia `core.memory.scoring`.
    - En el Paso 3.4h (cuando se mueve `buscar_por_frase`): se apunta el `inspect.getsource` de `tests/test_jsd_adaptativo_e7.py` hacia `core.memory.search.buscar_por_frase`, junto a `tests/test_dim_escape.py`, `tests/test_dim_resonancia.py`, `tests/test_qcr_idf_e3.py` y `tests/test_qcr_typo_d4.py`.
  - **`cerrar_sistema` permanece en la fachada:** `cerrar_sistema` no se delega a ningún submódulo; vive junto a `__init__` en `core/memory_store.py`.
- **RF-9 (Ubicuo - Estado en Memoria No-SQL):** EL SISTEMA mantendrá el estado en memoria que no reside en SQLite (caches de firmas, flags en caliente) encapsulado en la fachada o pasado explícitamente como argumento a las funciones de dominio, prohibiendo variables globales mutables colgadas en los módulos.
- **RF-10 (Dirigido por evento):** CUANDO se extraiga un cluster de código de `memory_store.py`, EL SISTEMA moverá funciones y métodos como bloques completos sin alterar su lógica interna ni reescribir algoritmos en el mismo paso.
- **RF-11 (Estado):** MIENTRAS se realice la modularización, EL SISTEMA mantendrá `core/memory_store.py` como una fachada delgada (remitiendo a RNF-1.4: techo orientativo $\le 400$ líneas, tope duro $\le 500$ líneas con justificación si las firmas completas lo superan) con delegación explícita método a método hacia `core/memory/`, prohibiendo el uso de introspección mágica (`__getattr__`).
- **RF-12 (Opcional):** DONDE existan constantes de módulo preexistentes (~170 líneas de pesos, umbrales y flags en `memory_store.py`), EL SISTEMA las aislará en `core/memory/constants.py`, importado por quien las use. `core/memory_store.py` las re-exportará si algún consumidor externo ya las importaba de ahí. Nada nuevo cae suelto en `core/`.

### Fase 0 — Congelamiento de Golden, Entorno Local y Snapshot ANTES
- **RF-14 (Dirigido por evento - Fase 0):** ANTES de iniciar cualquier extracción de código, EL SISTEMA generará en el entorno local, sin commitear scripts nuevos en `scripts/` (se usa un harness local que reutiliza el mismo protocolo de `evaluar_qa.py`, incluyendo resolución de etiquetas y exclusión de `ambiguo` sobre `snapshots/qa_escape_qcr_20260811.db`):
  1. `golden_921.jsonl`: salida completa de los 921 casos (Top-5 y scores redondeados a 4 decimales sobre el snapshot `snapshots/qa_escape_qcr_20260811.db`) ejecutada con `PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1` y `BIORAG_DMN_ESTADO_PATH` apuntando fuera del repositorio.
  2. Lista cerrada e inmutable de IDs para el golden reducido (~120 casos): proporcionales al tamaño de cada categoría de recuperación, más unos pocos negativos. Se congelan en un archivo de IDs que solo se commitea si Dennys lo autoriza explícitamente tras revisarlo.
  3. Archivo de congelamiento de entorno (`entorno_golden.json`) registrando versiones de Python, numpy, SQLite y variables `BIORAG_*` activas.
  4. Verificación de auto-identidad: ejecución de una segunda corrida sobre el mismo commit verificando que produce 100% de coincidencia exacta contra el golden recién generado.
  5. **Snapshot ANTES de la Base Viva (congelado, fuera del árbol del repo):** Copia de la **base viva real** `MemoryBioRAG_Data/memory_biorag.db` vía `sqlite3.backup()` + `PRAGMA wal_checkpoint(TRUNCATE)`, guardada como archivo inmutable en una ruta **fuera del árbol del repositorio** que Dennys indique al inicio de la Fase 0. Este snapshot de la base viva es el sustrato fijo e inmutable para ambas corridas del Gate Dual (Pilar 5 / RF-27.3: ANTES y DESPUÉS). No se hardcodea ninguna ruta.
  6. **Backup completo del repositorio (fuera del árbol del repo):** Copia íntegra del directorio del repositorio en una ruta **fuera del árbol del repositorio** que Dennys indique al inicio de la Fase 0. No se crea `_backup_monolito_pre_modularizacion/` dentro del repo. No se edita `.gitignore`. Es un seguro de vida para conservar los originales intactos.

### Fase 1 — Alcance Estricto y No-Operación sobre Archivos Sensibles
- **RF-15 (Ubicuo - Invarianza de Rutas y Tests en Fase 1):** EL SISTEMA mantendrá intactos en su ubicación actual los siguientes archivos y carpetas, sin moverlos ni reclasificarlos durante la Fase 1. Adicionalmente, la Fase 1 no editará docstrings ni comentarios de `mcp_server.py` ni de `core/memory_store.py` para no ensuciar el diff de la mudanza posterior. `ARCHITECTURE.md` puede esperar a que los módulos existan:
  1. `test_resonancia.py` y `test_resonancia_avanzado.py`: permanecen en la raíz (no poseen `def test_`, ejecutan efectos al importar y no deben ser recolectados por `pytest`).
  2. `test_memory.py`: permanece en la raíz (importado por `tests/test_memory_core.py:11`).
  3. `dashboard-neuro-visor/`: permanece en la raíz (referenciado por `biorag.py:987` e `install.py:936`).
  4. Scripts ejecutables de benchmark (`benchmark.py`, `benchmark_comparativo.py`, `benchmark_abismo_lexico.py`) y sus archivos de salida asociados (`benchmark_results.json`, `benchmark_comparativo_results.json`, `baseline_oficial_*.txt`, `post_qa_oficial_*.txt`): no se mueven por separado de los scripts que escriben en ellos.
  5. Archivos ignorados por Git (`dashboard.py`, `dashboard-2.py`, `dashboard/`, `agent_benchmark_*.jsonl`): no se tocan ni se asumen como parte del repositorio trackeado.

### Flujo Git, Ramas y Gobernanza de Commits
- **RF-16 (Ubicuo):** Todo el trabajo se desarrollará exclusivamente en la rama de trabajo `modularizacion-arquitectura`. Queda prohibido commitear o pushear directamente a `master`.
- **RF-17 (Ubicuo):** La decisión de mergear `modularizacion-arquitectura` hacia `master` recae exclusivamente en el usuario Dennys, condicionada a la obtención del Gate Nivel 2 en verde en la misma máquina y entorno donde se congeló el golden, acompañado del informe comparativo antes/después auditado entregado directamente a Dennys.
- **RF-18 (Dirigido por evento):** CUANDO una extracción resulte en verde, EL SISTEMA generará un commit atómico en la rama `modularizacion-arquitectura` y la empujará (`git push`) a `origin`. Queda prohibido el uso de `git push --force`.
- **RF-19 (No deseado):** SI un commit empujado presenta fallo en el gate, ENTONCES EL SISTEMA lo revertirá mediante `git revert`.
- **RF-20 (Ubicuo):** Los mensajes de commit seguirán estrictamente el estándar del repositorio (`type(scope): descripción < 70 chars`), listando en su cuerpo el desglose de archivos (`What / Why / Purpose`), el propósito estratégico, la tabla de auditoría (`archivo -> líneas`, `función -> líneas`), la lista de deuda técnica y el gate superado.
- **RF-21 (Ubicuo - Archivos Prohibidos en Commits):** Queda estrictamente prohibido incluir en cualquier commit de esta rama:
  - `MemoryBioRAG_Data/memory_biorag.db`
  - `snapshots/*.db`
  - `estado_hormiga.json`, `.env.local`, archivos de lock, `__pycache__`
  - `scripts/qa_metrics.json` ni reportes autogenerados por corridas locales (salvo commits explícitos de evidencia autorizados).
- **RF-22 (Ubicuo - Prohibición de Inclusión Ciega):** Queda prohibido el uso de `git add -A` y `git checkout` ciego sobre bases de datos locales modificadas.

### Gates de Verificación en 3 Niveles
- **RF-23 (Ubicuo - Entorno de Gate):** Toda corrida de gate (no solo la generación del golden) se ejecutará con `PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1` y `BIORAG_DMN_ESTADO_PATH` apuntando fuera del repositorio. Los archivos del golden no se commitean salvo que Dennys lo autorice explícitamente. Los 2 fallos de la categoría `ambiguo` que ya existen hoy no son regresión y no cuentan contra el 875/875.
- **RF-24 (Dirigido por evento - Gate Nivel 0):** CUANDO concluya una extracción individual intermedia, EL SISTEMA ejecutará:
  1. `pytest tests/ -v` (264 tests passed, 0 skipped).
  2. Smoke test de importaciones públicas (`mcp_server`, `biorag`, `core.memory_store`).
  3. Golden reducido (~120 casos fijos), exigiendo igualdad estricta en Top-5 y scores a 4 decimales contra el baseline local.
  4. **Inventario MCP (en Fase 2):** Verificación de que `_build_server()` devuelve exactamente 42 `name=`, 2 resources y 1 prompt. No se espera al Gate Nivel 1 para esto: pytest no verifica el registro de tools MCP, y sin este check catorce commits pueden pasar en verde con una tool caída.
- **RF-25 (Dirigido por evento - Gate Nivel 1):** CUANDO se cierre la extracción de un módulo completo, EL SISTEMA ejecutará:
  1. El benchmark de 921 casos exigiendo **identidad exacta en Top-5 y scores redondeados (4 decimales)** caso a caso contra `golden_921.jsonl` (ejecutado sobre `snapshots/qa_escape_qcr_20260811.db`).
  2. Para fases MCP: verificación de que `_build_server()` devuelve exactamente los mismos 42 `name=`, 2 resources y 1 prompt (complementaria al check del Nivel 0).
- **RF-26 (No deseado):** SI en el Gate Nivel 0 o Nivel 1 se detecta una sola variación en un score o Top-5 respecto al golden local, ENTONCES EL SISTEMA revertirá inmediatamente el cambio realizado. **Excepción explícita de latencia:** la latencia se reporta en el informe de gate pero no dispara revert automático, porque dos corridas idénticas del mismo código ya varían por ruido de máquina. El revert es exclusivamente por identidad funcional: Top-5, scores a 4 decimales, tests y FP. Dennys juzga el lag. Esto no es permiso para empeorar el recall.
- **RF-27 (Dirigido por evento - Gate Nivel 2):** CUANDO se finalice la especificación completa, EL SISTEMA ejecutará:
  1. `./scripts/run_qa_suite.sh` exigiendo reporte de 100.00% Recall@5 (875/875), 0 fallos y 0.00% FP (0/40) (sobre `snapshots/qa_escape_qcr_20260811.db`).
  2. `python3 scripts/fuzz_qa.py` (33/33 passed).
  3. **Verificación Dual no-tautológica (Pilar 5):** Se utiliza el snapshot de la **base viva** congelado en Fase 0 (`MemoryBioRAG_Data/memory_biorag.db`, guardado fuera del árbol del repo) como sustrato fijo e inmutable para ambas corridas. La corrida ANTES usa el código **pre-modularización** sobre una copia de ese snapshot de base viva → `antes.jsonl`. La corrida DESPUÉS usa el código **modularizado** sobre otra copia de ese mismo snapshot de base viva → `despues.jsonl`. Se compara `antes.jsonl` vs `despues.jsonl`, exigiendo 100% de identidad caso a caso. **Queda prohibido usar una copia fresca de la base viva al final** (puede haber mutado durante el trabajo) y queda prohibido usar `snapshots/qa_escape_qcr_20260811.db` (que ya evalúa el golden y QA suite).

---

## Requisitos no funcionales

### RNF-1 (Granularidad y Límites de Código - Opción B Enmendada)
**Todas las líneas se cuentan con `wc -l`: físicas, incluyendo blancos y comentarios. La misma regla aplica a los techos de 500, 800 y la fachada.**
1. **Límite por Archivo:**
   - Techo orientativo: $\le 500$ líneas.
   - Tope duro para código nuevo: $\le 800$ líneas.
   - Todo archivo que supere 500 líneas deberá incluir una justificación explícita de una línea en su docstring de módulo explicando la indivisibilidad del bloque cohesivo.
   - **Excepción del Tope de 800 líneas:** El tope de 800 líneas no aplica al archivo que aloje una función monolítica preexistente trasladada intacta como deuda técnica; aplica a todo el código restante de dicho archivo.
2. **Límite por Función:**
   - Objetivo: $\le 100$ líneas.
   - Bandera roja: $> 150$ líneas (prohibido en funciones nuevas).
3. **Regla de Deuda Técnica (Mover $\neq$ Partir):**
   - Las funciones monolíticas preexistentes (ej. `buscar_por_frase` de 2.109 líneas, `_recordar_impl` de 753 líneas (L652–L1404 por AST), `_aprender_impl` de 321 líneas, `ciclo_sueno_consolidacion` de 505 líneas, `_crear_estructura_cerebral` de 513 líneas) se trasladan **completas e intactas** sin particionar ni reescribir. Nota: `_build_server` no entra en esta lista porque en Fase 2 se convierte en cableado puro (recorre `register(mcp)` por submódulo); lo que no se reescribe es el cuerpo de cada tool individual.
4. **Fachada (`core/memory_store.py`):**
   - Techo orientativo: $\le 400$ líneas. Tope duro: $\le 500$ líneas. Con 99 delegadores de una línea más el `__init__`, 400 duro no cabe y empujaría a partir delegadores. Pasar de 500 exige la misma justificación de una línea que el resto de archivos.
5. **Auditoría de Entrega:**
   - Cada cierre de módulo incluirá una tabla auditada de `archivo -> líneas` y `función -> líneas`, junto a la lista de deuda técnica (funciones $> 150$ líneas trasladadas intactas).

### RNF-2 (Rendimiento y Medición Empírica)
- **Latencia:** La mediana de tiempo por categoría (p50 y p95) en el benchmark de 921 casos no debe empeorar respecto a la línea base medida en el mismo entorno de hardware, manteniéndose dentro del margen de ruido natural del sistema.
- **Recursos:** Cero dependencias externas adicionales, 100% Python estándar y SQLite local.
- **Entorno:** Ejecución 100% offline sin acceso a red.

---

## Secuencia Estricta de Fases de Ejecución

El trabajo se ejecutará en orden estrictamente secuencial en la rama `modularizacion-arquitectura`. Ninguna fase inicia con la anterior en estado no verificado:
1. **Fase 0 (Línea Base, Congelamiento Golden y Snapshot ANTES):** Generación local (sin commitear scripts) de `golden_921.jsonl`, golden reducido (~120 casos), `entorno_golden.json`, snapshot ANTES de la base viva, y backup completo del repo. Validación de auto-identidad.
2. **Fase 1 (Preparación Mínima):** Sin alterar docstrings de monolitos ni rutas de módulos, tests o scripts de benchmark. `ARCHITECTURE.md` puede esperar a Fase 2/3.
3. **Fase 2 (Modularización de `mcp_server.py` hacia `core/mcp_server/`):**
   - *Paso 2.1:* Crear paquete `core/mcp_server/` con `__init__.py` vacío, `_shared.py` vacío y `server.py` vacío. Nada de `_build_server()` inline en este paso.
   - *Paso 2.2:* Extracción secuencial módulo a módulo (15 submódulos con `register()`): primero `communication.py`, después `catalog.py`, avanzando hacia los más acoplados, dejando `search.py` para el final. Cuando un helper se muda a `_shared.py`, desaparece de `mcp_server.py` en el mismo commit.
   - *Paso 2.3:* Ensamblado en `server.py` y validación de 42 `name=`, 2 resources y 1 prompt.
   - *Paso 2.4:* Sustitución de `mcp_server.py` en la raíz por el shim (último commit de la fase). En este paso se ejecutan los efectos de arranque a nivel de módulo en `server.py` (`load_dotenv`, `logging.basicConfig`, warmup WordNet, `sys.path.insert` con `core.paths.project_root()`) y se ejecuta el test CWD de validación (`cwd=/tmp`). En todos los commits anteriores de la Fase 2, `from mcp_server import _build_server` sigue funcionando; el archivo de la raíz no desaparece en ningún momento.
4. **Fase 3 (Modularización de `core/memory_store.py` hacia `core/memory/`):**
   - *Paso 3.0:* Crear `core/memory/__init__.py` (vacío).
   - *Paso 3.1:* Extracción de constantes hacia `core/memory/constants.py` y funciones de módulo puras (`normalizar_sustantivos_clave`, `_qcr_levenshtein`, `_qcr_todos_cercanos`). Calificación `constants.NOMBRE` en `memory_store.py`, actualización de monkeypatches en tests y actualización de los 4 asserts literales. `core/memory_store.py` re-exporta las constantes.
   - *Paso 3.2a:* Extraer `comms.py` (~130 líneas).
   - *Paso 3.2b:* Extraer `telemetry.py` (~170 líneas).
   - *Paso 3.3a:* Extraer `synapses.py` (~523 líneas, grafo puro).
   - *Paso 3.3b:* Extraer `episodes.py` (~120 líneas).
   - *Paso 3.3c:* Extraer `quarantine.py` (~180 líneas).
   - *Paso 3.3d:* Extraer `ingest.py` (~122 líneas: solo `percibir_corto_plazo` y `consolidar_concepto`).
   - *Paso 3.3e:* Extraer `dmn.py` (~140 líneas).
   - *Paso 3.3f:* Extraer `consolidation.py` (~694 líneas: `ciclo_sueno_consolidacion` intacta, `_auto_generar_co_ocurrencia`, `_clasificar_nodo_wordnet`, `_calcular_base_level_actr`).
   - *Paso 3.4a:* Extraer `scoring.py` (~420 líneas: score híbrido y señales puras). Adaptar `inspect.getsource` de `_calcular_score_hibrido`.
   - *Paso 3.4b:* Extraer `umbral.py` (~430 líneas: cluster de calibración conforme).
   - *Paso 3.4c:* Extraer `context.py` (~200 líneas: epistémico).
   - *Paso 3.4d:* Extraer `catalog_methods.py` (~110 líneas).
   - *Paso 3.4e:* Extraer `adn.py` (~90 líneas: 3 funciones de firma ADN pura).
   - *Paso 3.4f:* Extraer `schema.py` (~1200 líneas: `_crear_estructura_cerebral`, `_poblar_fts`, `_poblar_fts_unicode` en el mismo commit).
   - *Paso 3.4g:* Extraer `rafaga.py` (~370 líneas: `buscar_por_rafaga`, `validar_rafaga`).
   - *Paso 3.4h:* Extraer `search.py` (~2500 líneas: `buscar_por_frase` intacta con closures anidadas). Adaptar `inspect.getsource` en `test_jsd_adaptativo_e7.py`, `test_dim_escape.py`, `test_dim_resonancia.py`, `test_qcr_idf_e3.py` y `test_qcr_typo_d4.py`.
   - *Paso 3.5:* Consolidar la fachada `core/memory_store.py` (~450 líneas, techo orientativo $\le 400$ / tope duro $\le 500$ con justificación si las firmas completas lo superan — RNF-1.4). `cerrar_sistema` permanece en la fachada junto a `__init__`.


---

## Casos límite

- **CL-1 (Funciones Anidadas / Closures en Rutas Críticas):** Funciones anidadas dentro de `buscar_por_frase` (`_fts_safe_term`, `_fts_safe_phrase`, `strip_accents`), `__init__` (`palabra_completa`, `palabra_prefijo`), `_calcular_jsd` y `_rerank_jaccard_protect_r0` permanecen dentro del cuerpo de sus funciones contenedoras. No se extraen como primer paso.
- **CL-2 (Importaciones Circulares en `core/mcp_server/`):** Los submódulos importan `_shared`; `server.py` es el único que importa los submódulos. Ningún submódulo importa `server` ni `mcp_server` de la raíz. En `core/memory/`, los submódulos no importan la fachada (`core/memory_store.py`).
- **CL-3 (Rutas de Scripts en CI):** `scripts/test_regresion_scoring.py` y `scripts/test_concept_hub.py` están referenciados por ruta en `.github/workflows/ci.yml`. Cualquier reubicación de scripts requiere actualizar simultáneamente `ci.yml`.
- **CL-4 (Herramienta MCP con Nombre Implícito):** `concept_hub_cargar_iniciales_tool` no utiliza argumento `name=`; su nombre MCP es el identificador de la función y no debe renombrarse.
- **CL-5 (Orden de Definición Interno en Submódulos MCP):** Dentro de cada módulo de tools, la función cerrada se define antes que la dependiente (`vincular` antes de `asociar`, `consolidar` antes de `sueno`, `introspeccion` antes de `estado`, `mapear` antes de `corteza`; en `oracle.py`: `_nlm_detectado`, `_consultar_notebooklm`, `_buscar_contexto_biorag_arranque` antes de las tools que los usan). Las descripciones largas se quedan con su tool en el commit de la mudanza.
- **CL-6 (Transición Incremental de `_build_server` en Fase 2):** Cada commit intermedio de la Fase 2 deja `_build_server` funcional: llama `register()` de lo ya extraído y mantiene inline lo que todavía no se movió. Siempre 42 names. No se vacía de golpe.
- **CL-7 (Superficie del Shim Raíz `mcp_server.py`):** El shim re-exporta `_build_server` y `main`. Nada más, salvo que un `grep` posterior muestre otro import, y en ese caso se re-exporta antes de mover.
- **CL-8 (Sin Re-export en `core/memory/__init__.py`):** `core/memory/__init__.py` no re-exporta la clase `SQLiteMemoryBioRAG`. La API pública sigue siendo `core.memory_store`. El paquete `core.memory` lo importa solo la fachada. No se crean dos caminos de import.
- **CL-9 (Techo de `_shared.py`):** `_shared.py` tiene el mismo techo: 500 orientativo, 800 duro. Si no cabe, se parte dentro de `core/mcp_server/`, no se acepta un monolito nuevo.
- **CL-10 (Congelamiento de Versiones y Protocolo de Regeneración):** Python, numpy y SQLite quedan congelados en `entorno_golden.json`. Si hay que cambiarlos, se pausa, se regenera el golden, la segunda corrida tiene que coincidir consigo misma, y solo entonces se sigue. Un gate rojo no se "arregla" regenerando el golden.
- **CL-11 (`scripts/run_qa_suite.sh` Preexistente):** `scripts/run_qa_suite.sh` ya existe y es el comando del Gate Nivel 2. No es dependencia nueva. La Constitución cita `evaluar_qa.py` y 168 tests — está desactualizada; no se edita en esta spec.

---

## Fuera de alcance

- **Reestructuración a `src-layout` o renombramiento `core -> src/biorag`:** Se mantiene el paquete `core/` y el layout actual.
- **Partición interna de funciones monolíticas complejas:** `buscar_por_frase`, `_recordar_impl`, `ciclo_sueno_consolidacion`, `_crear_estructura_cerebral`, etc., no se subdividen internamente en esta iteración.
- **Conversión de métodos a funciones puras:** Queda fuera de esta spec pasar `conn` como parámetro suelto o eliminar `self` de los bloques movidos. Los métodos se mudan con su interfaz original intacta.
- **Modificación o creación de jerarquía de excepciones:** No se alterarán los tipos de excepciones lanzadas (`raise Exception`, `ValueError`, etc.).
- **Migración a Git LFS o alteración del `.gitignore` de bases de datos:** `snapshots/qa_escape_qcr_20260811.db` y `MemoryBioRAG_Data/memory_biorag.db` se mantienen trackeados como están.
- **Refactorización de `test_memory.py`:** La partición de la función de prueba de 2.311 líneas queda fuera de esta especificación.
- **Modificación de pesos de scoring:** La fórmula `_calcular_score_hibrido` permanece 100% intocada.
- **Reubicación de `test_resonancia*.py`, `test_memory.py`, dashboards o resultados de benchmark en Fase 1:** Se mantienen en sus rutas originales.
- **Arreglos de paso ("oportunistas"):** Prohibido intentar reparar la condición de carrera en triggers de `_crear_tabla_fts` (`concurrencia_qa.py`), modificar la ruta de escritura de `estado_hormiga.json` o alterar textos de ayuda de la CLI durante esta migración.

---

## Criterios de finalización

1. Todos los módulos extraídos cumplen la regla de granularidad ($\le 500$ líneas orientativo / fachada $\le 400$ líneas / excepciones de deuda explícitamente registradas).
2. Los 264 tests unitarios de `pytest tests/ -v` pasan al 100% (0 fallos, 0 errores, 0 skipped).
3. El benchmark de 921 casos valida **identidad exacta en Top-5 y scores redondeados (4 decimales)** caso a caso contra `golden_921.jsonl` (sobre `snapshots/qa_escape_qcr_20260811.db`) en el mismo entorno.
4. `_build_server()` devuelve exactamente los mismos 42 `name=`, 2 resources y 1 prompt.
5. `python3 scripts/fuzz_qa.py` pasa 33/33 sin excepciones no controladas.
6. Verificación dual no-tautológica exitosa: la corrida ANTES (código pre-modularización sobre copia del snapshot de la base viva congelado en Fase 0) y la corrida DESPUÉS (código modularizado sobre otra copia de ese mismo snapshot de la base viva) arrojan 100% de identidad caso a caso. El snapshot de la base viva de Fase 0 es el sustrato fijo e inmutable para ambas corridas.
7. Shims y puntos de entrada en raíz (`mcp_server.py`, `biorag.py`, `core/memory_store.py`) probados y funcionales con todos los importadores registrados.
8. Validación de rutas de entorno: `.env.local`, `estado_hormiga.json` y `middleware` operan correctamente desde cualquier directorio de invocación.
9. Informe final auditado de líneas por archivo y por función entregado a Dennys.
10. El merge a `master` se ejecuta exclusivamente por Dennys tras autorizarlo con el Gate Nivel 2 en verde y el informe antes/después auditado.

---

## Deuda técnica explícita (Funciones monolíticas que se trasladan intactas)

- `buscar_por_frase` (~2.109 líneas).
- `_recordar_impl` (~753 líneas, L652–L1404 por AST).
- `_aprender_impl` (~321 líneas).
- `ciclo_sueno_consolidacion` (~505 líneas).
- `_crear_estructura_cerebral` (~513 líneas).
- `test_memory.py` (función monolítica de 2.311 líneas).

> **Nota:** `_build_server` (~3.656 líneas) no aparece aquí porque en Fase 2 se convierte en cableado puro que llama `register(mcp)` por submódulo. Los cuerpos individuales de las 42 tools sí se trasladan intactos a sus módulos de destino.
