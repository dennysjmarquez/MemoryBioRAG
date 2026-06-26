---
name: biorag-sync
description: |-
  Sincronización bidireccional BioRAG ↔ NotebookLM. Usa este skill cuando el usuario
  mencione "notebooklm", "sincronizar", "sync", "fuente", "cuaderno", "memoria biorag",
  "subir a notebook", "actualizar fuente", "memoria compartida", "cortex notebook",
  "notebook", "subir", "descargar fuente", o cualquier tarea que involucre mantener
  alineados BioRAG y NotebookLM.
---

# Skill: biorag-sync — BioRAG ↔ NotebookLM Sync Protocol

## 1. Datos del Proyecto

| Campo | Valor |
|---|---|
| Ruta proyecto | `/mnt/recursos_compartidos_y_otros/MemoryBioRAG_NOTEBOOK_NCP/` |
| Notebook ID | `b2645e9b-8bce-4067-841a-7796af4a14f0` |
| Notebook URL | https://notebooklm.google.com/notebook/b2645e9b-8bce-4067-841a-7796af4a14f0 |
| Config | `config.json` (dentro del proyecto) |
| DB BioRAG | `/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db` |
| Script export incremental | `scripts/export_pending.py` |
| Script export completo | `scripts/export_full.py` |
| Skill Athena | `/home/dennys/.claude/skills/biorag-sync/SKILL.md` (este archivo) |
| DSL Metacognitivo | `dsl/metacognitivo_v1.0.md` (system prompt del chat AI de NotebookLM) |
| Total nodos | 168 (activos + dormidos) |
| Total categorias madre | 11 (unificadas desde 39 originales) |
| Total fuentes NB | 30 (14 únicas + 16 duplicados por re-uploads) |
| Formato archivo | `.jsonl.txt` (JSON Lines con extensión .txt para NotebookLM) |
| Version actual | v9.5 — Protocolo de 4 Pasos (Síntesis de Espectro post-recuperación), 23 herramientas MCP, EVALUAR VÍNCULO en SAVE/EDIT FLOW, instalador de skills |

## 2. Principio Fundamental

**Local-first.** Los archivos TXT en `db/` son la fuente de verdad canonica.
No descargar de NotebookLM para editar. Editar el TXT local y re-subir.

## 3. Características v8.3 del Motor de Búsqueda

### Pipeline de 9 Capas
```
FTS5 AND → OR → Prefix (unicode61) → Semántica → Conceptual (Jaccard) → Snap → Cadena → Substring → Trigram
```

### Context Window por Sinapsis
Parámetro `context_window=N` en `buscar_por_frase` y MCP. Expande cada resultado principal con hasta N vecinos de la tabla `sinapsis`, con deduplicación y score atenuado.

### Dynamic Multiplicator
Cuando FTS5 falla, Jaccard toma el control: 70% Jaccard + 20% peso sináptico + 10% asociaciones.

### Anclaje Temporal
Bonus en el scoring: +0.15 si accedido <7 días, +0.08 si <30 días, +0.03 si <90 días.

### Ráfaga de Reminiscencia
El LLM genera 10-15 términos relacionados, el script ejecuta en SQLite.
**Se activa cuando:** FTS5 falla O score del top resultado < 0.5.

### Instrucción de 5 Niveles para generar Ráfaga
- NIVEL 1 (Literal): sinonimos exactos (3 términos)
- NIVEL 2 (Tecnico): terminos del dominio (3 términos)
- NIVEL 3 (Contexto): donde/para que se usa (3 términos)
- NIVEL 4 (Problema): que problema resuelve (3 términos)
- NIVEL 5 (Emocion): urgencia o contexto personal (3 términos)

### PALABRA_COMPLETA
Word boundary en SQL para todas las capas FTS5. Previene "culo" → "artículos".

### Auto-aprendizaje de errores
Si el usuario rechaza un resultado, se guarda como lección y se excluye en la próxima búsqueda.

### Co-ocurrencia automática en sueño
El ciclo de sueño crea sinapsis basándose en co-ocurrencia de conceptos en la misma sesión.

### Protocolo de 4 Pasos (Buscar + Sintetizar)

```
Paso 1 — ENRIQUECIMIENTO:
    Interpretar la query y agregar palabras clave del dominio.
    Aplicar Empatía Sintáctica: raíces morfológicas, patrones repetitivos,
    nomenclaturas técnicas, sustantivos de alto peso.

Paso 2 — RÁFAGA:
    Si score < 0.5 o 0 resultados. 10-15 términos con la instrucción
    de 5 niveles (Literal, Técnico, Contexto, Problema, Emoción).

Paso 3 — CONTINGENCIA:
    Si aún sin resultados, buscar en contexto del chat actual.

Paso 4 — SÍNTESIS DE ESPECTRO (POST-RECUPERACIÓN):
    OBLIGATORIO después de cualquier recuperación con 2+ resultados.
    No responder al primer match. Extraer el espectro completo.

    Sub-pasos:
    a) RECOLECTAR: Escanear TODOS los resultados en busca de TODAS
       las instancias del patrón buscado (versiones vX.Y, fechas,
       cantidades, nombres de archivos, etc.). NO limitarse al
       primer resultado ni al contenido del primer nodo.

    b) CONSOLIDAR: Reunir todas las instancias en un conjunto único.
       Si el patrón es versionado (vX.Y), extraer SOLO los números
       y compararlos con semver. Si son fechas, ordenar cronológicamente.
       Si son valores discretos, deducir el extremo (mayor/menor,
       primero/último) mediante comparación directa.

    c) CONTRADICCIONES: Si dos nodos contienen información
       contradictoria sobre el mismo tema (ej. uno dice v5.1 y
       otro dice v9.4), NO elegir por inercia. Señalar la
       contradicción explícitamente y determinar cuál nodo tiene
       el registro más reciente o la fuente más autorizada.

    d) RESPONDER: Solo después de a+b+c. La respuesta debe reflejar
       el espectro completo, no el primer match.

    EJEMPLO (fallo corregido):
      Query: "última versión de BioRAG"
      Resultados: nodo_A="v5.1", nodo_B="v9.3 (Artemis)", nodo_C="v9.4"
      (Antes) → Responder "v5.1" (primer match en lección_versionado_biorag)
      (Ahora)  → v9.4 > v9.3 > v5.1 → Responder "v9.4", señalando
                 que hay un nodo más antiguo con v5.1 y uno intermedio
                 con v9.3, pero el overview consolidado dice v9.4
				 
	INVARIANT INVARIANT: Aplicar en las búsquedas y en los resultados el Principio de Razonamiento Analítico-Comparativo en Búsquedas RAG.
    Este enfoque sustituye la 'recuperación ciega' por una Deducción Activa, donde el agente actúa como un analista racional que infiere el estado del sistema.
				 
```

## 4. Prioridad de Consulta (Query Chain)

Siempre, sin excepcion:

```
Paso 1: BioRAG (recordar con deep=true)
Paso 2: NotebookLM (notebooklm_notebook_query)
Paso 3: Filesystem (lectura directa)
```

**Nunca saltar el paso 2.** NotebookLM aporta sintesis entre categorias
que BioRAG (motor de busqueda) no puede generar.

## 5. Protocolo de Sincronizacion

### 4.1 SAVE FLOW (guardar nuevo dato)

```
1. aprender (legacy: guardar) — percibir el concepto:
   aprender(concepto="NOMBRE", contenido="TEXTO",
     cat="CATEGORIA", syn="sinonimos,separados,por,coma")

   NOTA: auto_vincular ya se ejecuta internamente en el motor (pre-filtro FTS5
   con umbral 0.3). Este paso manual es para vínculos semánticos ADICIONALES
   que el agente identifica como relevantes y que el motor no puede inferir.

2. [OBLIGATORIO] EVALUAR VÍNCULO:
   ¿El concepto nuevo tiene relación semántica genuina con nodos existentes
   que auto_vincular no cubrió?
   - SI → vincular(a, b) — especificar CON QUÉ se vincula y POR QUÉ
   - NO → continuar sin vincular
   PROHIBIDO: vincular por inercia de protocolo, "siempre se hace después de aprender",
   o por cumplir el paso. La relación debe ser demostrable, no procesal.
   PRINCIPIO: la vinculación manual del agente complementa (no reemplaza)
   la vinculación algorítmica del motor.

4. Regenerar TXT local:
   python3 scripts/export_biorag_to_jsonl.py
   for f in db/*.jsonl; do cp "$f" "${f%.jsonl}.txt"; done
   O manual: agregar linea JSONL al archivo db/cat_CATEGORIA.txt

5. Consultar source_id actual en NotebookLM:
   notebooklm_notebook_get(notebook_id)
   Buscar la fuente por titulo (cat_CATEGORIA.txt) en la lista de sources.

6. Reemplazar fuente en NotebookLM:
   notebooklm_source_delete(source_id, confirm=True)
   notebooklm_source_add(notebook_id=b2645e9b-...,
     source_type="text",
     text=<contenido COMPLETO del TXT>,
     title="cat_CATEGORIA.txt")

7. Si categoria nueva:
   notebooklm_source_add(...) directamente (sin delete previo)

8. Si se regenero todo:
   Re-subir todas las fuentes que cambiaron.
   Los source_ids cambian con cada delete+add. Consultar NotebookLM directamente.
```

### 4.2 EDIT FLOW (modificar dato existente)

```
1. Identificar categoria del concepto: recordar(query, limite=1)

2. Consultar source_id en NotebookLM via notebooklm_notebook_get(notebook_id)

3. Editar la linea correspondiente en db/cat_CATEGORIA.txt

4. Reemplazar fuente en NotebookLM:
   notebooklm_source_delete(source_id, confirm=True)
   notebooklm_source_add(notebook_id, source_type="text",
     text=<contenido COMPLETO del TXT>,
     title="cat_CATEGORIA.txt")

5. Si amerita persistencia: aprender (legacy: guardar)

   NOTA: después de aprender, EVALUAR VÍNCULO con el mismo criterio
   que en SAVE FLOW. Si la edición revela una relación nueva con otro nodo,
   vincular manualmente. auto_vincular solo cubre overlap de tokens.
```

### 4.3 DELETE FLOW (eliminar dato)

```
1. Identificar categoria del concepto
2. Consultar source_id en NotebookLM via notebooklm_notebook_get(notebook_id)
3. Borrar linea de db/cat_CATEGORIA.txt
4. Reemplazar fuente en NotebookLM (delete + add)
5. En BioRAG: nodos no se borran. Solo duermen via LTD.
   Para poda forzada (peso <= 0.01): export BIORAG_PODAR=true
```

### 4.4 EXPORT FLOW (sync incremental)

**Tools MCP disponibles:**
- `biorag_sync_status` — muestra categorías pendientes de sincronizar
- `biorag_export_sync` — genera .jsonl.txt SOLO de categorías pendientes
- `biorag_export_full` — export completo (fallback)

**Flujo manual:**
```
1. Guardar/consolidar nodos en BioRAG
2. sync_log registra cambios automáticamente
3. Ejecutar: biorag_export_sync
4. Subir archivos .jsonl.txt indicados a NotebookLM
```

**Flujo completo manual:**
```bash
cd /mnt/recursos_compartidos_y_otros/MemoryBioRAG_NOTEBOOK_NCP/
python3 scripts/export_pending.py
# Subir archivos indicados a NotebookLM
```

**Export completo (fallback):**
```bash
python3 scripts/export_full.py
```

## 6. Pipeline Research → BioRAG (7 pasos)

Cuando se complete un research en NotebookLM, incorporar resultados nuevos:

```
Paso 1: research_start(query, mode="deep", ...)
        Poll research_status hasta completar.

Paso 2: Leer reporte generado:
        notebooklm_source_get_content(source_id)

Paso 3: Extraer 1-5 insights candidatos del reporte:
        - Conceptos principales
        - Relaciones con conceptos existentes
        - Datos factuales nuevos

Paso 4: Por cada insight candidato:
        recordar(concepto, deep=true)
        SI existe nodo semanticamente equivalente:
            skip (el peso sinaptico se refuerza por el acceso)
        SI es genuinamente nuevo:
            aprender(concepto, contenido, cat=<inferida>)

Paso 5: Re-exportar TXT de categorias afectadas:
        python3 scripts/export_biorag_to_jsonl.py
        cp db/cat_CATEGORIA.jsonl db/cat_CATEGORIA.txt

Paso 6: Re-upload a NotebookLM (delete + add por categoria modificada)

Paso 7: Los source_ids se consultan directamente en NotebookLM (notebooklm_notebook_get). El nodo notebooklm-category-map esta deprecado (dormido en BioRAG).
```

**Principio:** Push, no pull. Se gatilla por cada research completado.
Deteccion de novedad via recordar (legacy: buscar) antes de guardar.
Antes de guardar, presentar al humano y esperar autorizacion.

## 7. Nodos BioRAG del Proyecto

| Concepto | Categoria | Proposito |
|---|---|---|
| `notebooklm-sync-protocol` | protocolo | Protocolo completo de sincronizacion |
| `notebooklm-memory-biorag-project` | proyecto | Datos del proyecto, inventario |
| `notebooklm-category-map` | project | DORMIDO — deprecado, no mantener |
| `notebooklm-sync-lecciones` | lesson | Lecciones aprendidas del proyecto |
| `notebooklm-chat-configure` | protocolo | Configuracion del chat AI (DSL) |

## 8. Mapa de Fuentes (Categoria Madre → Source ID)

Las 11 fuentes categoricas (unificadas desde 39 originales).
Los source_ids se consultan directamente en NotebookLM, no se almacenan en BioRAG.
`notebooklm-category-map` esta deprecado (marcado como dormido en BioRAG).

### Fuentes categoricas (11 madres)

| Categoria | Archivo |
|---|---|
| System | cat_system.txt |
| Architecture | cat_architecture.txt |
| Project | cat_project.txt |
| Lesson | cat_lesson.txt |
| Profile | cat_profile.txt |
| Personal | cat_personal.txt |
| Principle | cat_principle.txt |
| Protocol | cat_protocol.txt |
| Cognition | cat_cognition.txt |
| Relation | cat_relation.txt |
| General | cat_general.txt |

### Fuentes resumen (3)

| Archivo | Source ID |
|---|---|
| corto_plazo.txt | `4502fae1-220c-40ba-8499-568676142294` |
| nodos_activos.txt | `d7dd7fe8-8516-4ee9-b483-254d56eb175b` |
| nodos_dormidos.txt | `72c9cf77-3c4f-4b88-914c-e1f28cca347d` |

## 9. DSL Metacognitivo del Chat AI

El chat AI de NotebookLM esta configurado con un DSL formal como system prompt.

| Campo | Valor |
|---|---|
| DSL version | `metacognitivo_v1.0` |
| Archivo | `/mnt/recursos_compartidos_y_otros/MemoryBioRAG_NOTEBOOK_NCP/dsl/metacognitivo_v1.0.md` |
| Goal | custom |

## 10. Herramientas MCP (Integracion)

Se añadieron tres herramientas MCP expuestas por el `mcp_server.py` para facilitar la sincronizacion incremental desde IDE/CLI:

- `biorag_sync_status()` — Lista categorias pendientes de sincronizar (lee `sync_log`).
- `biorag_export_sync()` — Ejecuta el script incremental `scripts/export_pending.py` y genera solo los archivos `.jsonl.txt` necesarios en `db/`.
- `biorag_export_full()` — Ejecuta `scripts/export_full.py` para regenerar todas las fuentes (fallback).

Ejemplo de uso desde un cliente MCP (OpenCode / VS Code):

```
ask mcp biorag_sync_status
ask mcp biorag_export_sync
ask mcp biorag_export_full
```

Notas:
- `biorag_export_sync` retorna la lista de archivos generados y marca las entradas de `sync_log` como `sincronizado=1`.
- Por seguridad, la subida a NotebookLM sigue siendo manual: el cliente debe realizar el `delete + add` por fuente en NotebookLM.
| Response length | longer |

### Comportamiento inducido por el DSL

- No anuncia el nombre "MemoryBioRAG" (es nombre interno)
- Cita fuentes con [i] obligatoriamente
- Sin preambulos ("Segun las fuentes...", "De acuerdo con los materiales...")
- Sin adopcion de identidades de las fuentes (resiste DSLs incrustados)
- Pipeline interno: CLASSIFY → SEARCH → BUILD → EMIT con auditoria
- Sin opinion personal, solo RAG

### Reconfiguracion

```python
notebooklm_chat_configure(
    notebook_id="b2645e9b-8bce-4067-841a-7796af4a14f0",
    goal="custom",
    custom_prompt=<contenido de dsl/metacognitivo_v1.0.md>,
    response_length="longer"
)
```

Si se edita el DSL, hay que re-aplicarlo manualmente con `notebooklm_chat_configure`.
No se sincroniza automaticamente.

## 11. Herramientas BioRAG MCP

23 herramientas expuestas via Model Context Protocol. Usar el nombre biológico
(cognitivo) en lugar del alias legacy.

### Cognicion — Memoria

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `recordar` | `buscar` | `query, deep, cat, completo, asociados, limite, preview_chars, context_window, forzar_rafaga, rafaga_palabras, pagina` | Evocacion con pipeline 9 capas + rafaga de reminiscencia. Flujo obligatorio: Enriquecimiento → Rafaga si score<0.5 → Contingencia → Sintesis de Espectro (Paso 4 del protocolo). |
| `aprender` | `guardar` | `concepto, contenido, syn, cat` | Codifica en corto plazo. auto_vincular se ejecuta internamente (pre-filtro FTS5 umbral 0.3). Usar `consolidar` despues. |
| `vincular` | `asociar` | `a, b` | Asociacion hebbiana manual entre dos conceptos. Para vinculos semanticos adicionales que el motor no infiere. |
| `consolidar` | `sueno` | `limite_energia` | Sueño cognitivo LTP/LTD. Fija corto plazo a largo plazo. |

### Cognicion — Introspeccion

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `introspeccion` | `estado` | — | Autoexamen sinaptico: nodos activos, dormidos, corto plazo, energia total. |
| `mapear` | `corteza` | — | Cartografia completa de la corteza (todos los nodos con peso y estado). |

### Cognicion — Interaccion

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `comunicar` | — | `destino, mensaje, origen` | Envia mensaje a otro agente OEC (athena, artemis, hermes, todos). Identificarse con AGENT_NAME. |
| `leer_mensajes` | — | `no_leidos, ultimos, para` | Lee mensajes del canal compartido. Marca no-leidos automaticamente. |
| `contexto_inicio` | — | `agente, contexto` | Anuncia inicio de interaccion significativa. |
| `contexto_fin` | — | `agente, resumen` | Anuncia fin + auto-guardado + auto-suenno si hay nodos en corto plazo. |

### Boot — Oraculo

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `oraculo_inicio` | — | `agente, contexto_adicional` | OBLIGATORIO al iniciar sesion con Dennys. Consulta NotebookLM si esta configurado, si no consulta BioRAG local. |

### Gestion — Categorias

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `listar_categorias` | — | — | Lista categorias validas (System, Architecture, Project, Lesson, Profile, Personal, Principle, Protocol, Cognition, Relation, General). |

### Sync — Export

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `sync_status` | — | — | Muestra categorias pendientes de sincronizar a NotebookLM. |
| `export_sync` | — | — | Exporta SOLO categorias pendientes a .jsonl.txt. |
| `export_full` | — | — | Export completo de todas las categorias. |

### Metricas — Analisis

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `metricas_historial` | — | `n` | Ultimos N ciclos de sueno: tendencias de consolidacion, olvido, salud sinaptica. |

### Semantica — Vocabulario

| Herramienta | Alias | Parametros | Descripcion |
|---|---|---|---|
| `semantica_admin` | — | `accion, termino, equivalente, peso, vocabulario_json` | Gestiona vocabulario semantico (equivalencias bidireccionales). Acciones: listar, agregar, eliminar, cargar_vocabulario. |

## 12. Deteccion y Reparacion de Corrupcion por Compactacion

La compactacion de contexto en sesiones largas puede CORROMPER nodos BioRAG
por duplicacion cuando se llama `aprender` + `consolidar` repetidamente.

### Sintomas

- Nodos con contenido repetido ("| Actualizacion:" aparece 3-5 veces)
- Source_ids incorrectos en `notebooklm-category-map`
- Nodos que pesan 3-5x de lo normal (sync-protocol pasa de ~4k a ~14k chars)

### Deteccion

```python
import sqlite3
db = '/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db'
conn = sqlite3.connect(db, timeout=5)
cur = conn.cursor()
cur.execute('SELECT concepto, length(contenido) FROM largo_plazo WHERE contenido LIKE "%Actualizacion%" OR contenido LIKE "%Actualización%"')
for r in cur.fetchall():
    print(f'{r[0]}: {r[1]} chars')
```

### Reparacion (SQL directo, no aprender)

```python
import sqlite3, time
db = '/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db'
conn = sqlite3.connect(db, timeout=5)
cur = conn.cursor()
cur.execute('UPDATE largo_plazo SET contenido = ?, ultimo_acceso = ? WHERE concepto = ?',
    (contenido_limpio, time.time(), 'notebooklm-sync-protocol'))
conn.commit()
conn.close()
```

### Prevencion

- Verificar periodicamente nodos del proyecto en sesiones largas
- `recordar` con `completo=true` para inspeccionar contenido completo
- Despues de compactacion, revisar source_ids del category-map

## 13. Herramientas NotebookLM Disponibles

| Herramienta | Uso |
|---|---|
| `notebooklm_notebook_get(notebook_id)` | Detalle del notebook + fuentes |
| `notebooklm_notebook_query(notebook_id, query)` | Preguntar a la IA del cuaderno |
| `notebooklm_chat_configure(notebook_id, ...)` | Configurar prompt del chat AI |
| `notebooklm_source_add(notebook_id, source_type, text/title/url)` | Agregar fuente |
| `notebooklm_source_delete(source_id, confirm=True)` | Eliminar fuente |
| `notebooklm_source_get_content(source_id)` | Descargar texto de fuente |
| `notebooklm_source_rename(...)` | Renombrar fuente |
| `notebooklm_studio_create(...)` | Generar audio/video/reportes |
| `notebooklm_studio_status(notebook_id)` | Ver artefactos generados |
| `notebooklm_label(...)` | Gestionar etiquetas |
| `notebooklm_tag(...)` | Tags para smart selection |

## 14. Limites y Restricciones

- NotebookLM Plus: maximo 100 fuentes (14/100 ocupados: 11 categorias + 3 resumen)
- Maximo 200 MB o 500,000 palabras por fuente
- No existe API de "update in-place" — solo delete + recreate
- Cada delete+add invalida citas anteriores (source_id cambia)
- Custom prompt: maximo 10,000 caracteres

## 15. Archivos del Proyecto

```
/MemoryBioRAG_NOTEBOOK_NCP/
├── config.json                     Configuracion (notebook_id, rutas, conteos, dsl)
├── README.md                       Documentacion humana y para agentes
├── dsl/
│   └── metacognitivo_v1.0.md       DSL system prompt del chat AI
├── db/
│   ├── cat_NOMBRE.txt              Una fuente TXT por categoria madre (11 + 3 resumen)
│   ├── nodos_activos.txt           Resumen nodos activos
│   ├── nodos_dormidos.txt          Resumen nodos dormidos
│   └── corto_plazo.txt             Resumen corto plazo
├── backup/
│   └── corrupted_nodes_sql_backup_2026-06-13.txt  Respaldo pre-reparacion
└── scripts/
    └── export_biorag_to_jsonl.py   Exportador BioRAG → JSONL → TXT
```

## 16. Integracion con CLAUDE.md

Los invariantes en CLAUDE.md garantizan el funcionamiento:

1. **Sincronizacion Simbiotica:** leer canal Artemis antes de operar
2. **Auto-Consulta en Cadena:** BioRAG (1°) → NotebookLM (2°) → Filesystem (3°)
3. **NotebookLM Sync Protocol:** sincronizar automaticamente al guardar/editar/borrar
