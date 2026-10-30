# `core/mcp_server/` — la puerta del agente (MCP)

> **Para quién es esto:** cualquier persona o IA que necesite saber **cómo habla el agente con el cerebro**.
> Regla de oro (Constitución, Pilares 9 y 10): cada pieza dice **qué es, por qué existe, qué aporta y con qué se conecta**. Si agregas, quitas o apagas una herramienta, **actualiza esta tabla en el mismo cambio**.
> Las conexiones salen del código: `python3 scripts/mapa_dependencias_core.py mcp_server`.
> Última revisión: 2026-10-28 (auditor). Solo documenta; no cambia ningún comportamiento.

## Qué es esta carpeta

El **MCP** (Model Context Protocol) es el idioma con el que un agente (OpenCode, Claude, Cursor, VS Code…) usa BioRAG **sin ejecutar comandos**. Esta carpeta convierte cada función del cerebro en una **herramienta** (`biorag_recordar`, `biorag_aprender`…).

En arquitectura hexagonal, esta carpeta es un **adaptador**: traduce lo que pide el agente a llamadas al motor (`core/memory_store.py` → `core/memory/`). **El motor no sabe que el MCP existe.** Por eso aquí solo se valida y se traduce; la inteligencia de búsqueda vive en el motor.

```
mcp_server.py (raíz)  →  server.py  →  register(mcp) de cada archivo  →  _shared._get_cerebro()  →  motor
```

Principio que manda aquí: **"BioRAG no piensa, el agente piensa"** (Constitución §2). Las instrucciones que el agente recibe al conectarse están en `prompt.py`.

## Los archivos

| Archivo | Herramientas que expone | Por qué existe / qué aporta | Se conecta con | Notas y estado |
|---|---|---|---|---|
| `server.py` | — (arranca todo) | Crea el servidor FastMCP, le pasa las instrucciones de `prompt.py` y registra cada archivo | Todos los de esta carpeta, `daemon_lifecycle`, `clasificador_wordnet` (calentamiento al arrancar), `paths` | Lo lanza `mcp_server.py` en la raíz |
| `_shared.py` | — | Utilidades comunes: abrir el cerebro (`_get_cerebro`), interceptor de sesión, resolver dimensiones, límites y validaciones compartidas | `memory_store`, `memory_service`. Lo usan **14** archivos | Pieza más usada de la carpeta: cambiarla afecta a casi todas las herramientas |
| `prompt.py` | prompt `biorag-system-prompt` | El "manual" que el agente lee: cómo recordar, cómo guardar, qué parámetros usar | `server` | Cambiarlo cambia el **comportamiento del agente**: se trata como cambio importante |
| `search.py` (1.523 líneas) | `biorag_recordar`, `biorag_buscar` | **Recordar**: valida lo que manda el agente (sustantivos clave, dimensiones, profundidad), llama al motor y arma la respuesta (recuerdos, pistas, asociaciones) | `memory_store`, `evidence_convergence`, `pmi_semantico`, `sinapsis`, `stemmer_es` | Activo. `biorag_recordar` **exige** `sustantivos_clave`. Paráfrasis y dimensiones automáticas apagadas (`BIORAG_MCP_AUTO_PARAFRASIS=0`, `BIORAG_MCP_AUTO_DIMS=0`, decisión de Dennys) |
| `write.py` (1.159 líneas) | `biorag_aprender`, `biorag_guardar`, `biorag_actualizar`, `biorag_agregar_sustantivos`, `biorag_sustantivos` | **Guardar**: valida antes de tocar la base (búsqueda previa obligatoria, 5 puentes, 2–10 sustantivos clave, categoría, dimensiones) y no deja nada a medias (Pilar 7) | `memory_store`, `concept_hub`, `sinapsis`, `sdm`, `categorizador` | Activo. Ojo: `biorag_agregar_sustantivos` **reemplaza** los sustantivos en vez de añadir (comportamiento anotado, pendiente de decidir) |
| `concept_hub_tools.py` | `concept_hub_crear`, `…_agregar_bridges_tool`, `…_listar_tool`, `…_buscar_tool`, `…_eliminar_tool`, `…_cargar_iniciales_tool` | Gestionar los **hubs de concepto**: puentes para encontrar un recuerdo aunque la pregunta no comparta palabras con él | `concept_hub` | Activo. Estas herramientas no llevan el prefijo `biorag_` |
| `synapses.py` | `biorag_vincular`, `biorag_desvincular`, `biorag_asociar`, `biorag_feedback` | Enlaces manuales entre recuerdos y refuerzo | `sinapsis` | Activo. Los enlaces `manual` nunca se borran solos |
| `catalog.py` | `biorag_listar_categorias`, `biorag_listar_dimensiones`, `biorag_listar_tipos_dimension`, `biorag_listar_dimensiones_por_tipo` | Que el agente conozca las etiquetas disponibles antes de guardar o filtrar | `_shared` | Activo |
| `introspection.py` | `biorag_introspeccion`, `biorag_estado`, `biorag_mapear`, `biorag_corteza`, `biorag_metricas_historial` | Mirar el estado del cerebro: tamaño, grafo, métricas | `_shared` | Activo |
| `consolidation.py` | `biorag_consolidar`, `biorag_sueno` | Lanzar a mano la consolidación y el ciclo de sueño | `_shared` | Activo |
| `daemon.py` | `biorag_hormiguita`, `biorag_hormiguita_estado`, `biorag_estado_dmn` | Mantenimiento en segundo plano del grafo (la "hormiguita") y estado de la DMN | `dmn_reflexion`, `paths` | **La hormiguita está decidida para quitarse** (apagarla mejoró la QA, experimento 13); su reemplazo propuesto es la neurona asociativa |
| `session.py` | `biorag_contexto_inicio`, `biorag_contexto_fin` | Marcar inicio y fin de una sesión de trabajo | `_shared` | Activo |
| `communication.py` | `biorag_comunicar`, `biorag_leer_mensajes`, `biorag_marcar_como_leido` | Tablón de mensajes entre agentes | `_shared` | Activo |
| `oracle.py` | `biorag_oraculo_inicio`, `biorag_oraculo_preguntar` | Integración opcional con NotebookLM | `_shared` | Opcional (`BIORAG_NOTEBOOK_ID`) |
| `sync.py` | `biorag_sync_status`, `biorag_export_sync`, `biorag_export_full` | Exportar la memoria (NotebookLM u otros) | `_shared`, `paths` | Activo |
| `calibrar.py` | `biorag_calibrar` | Recalibrar la certeza (umbral conforme, Platt) | `_shared` | Activo |
| `resources.py` | recursos `biorag://concepto/{nombre}`, `biorag://mensajes` | Leer un recuerdo o los mensajes como "recurso" MCP | `_shared` | Activo |
| `__init__.py` | — | Marca el paquete | — | Vacío |

## Reglas que aplican a esta carpeta

- **Validar antes de escribir** (Pilar 7): un rechazo nunca deja estado a medias.
- **Errores accionables:** decir al agente qué corregir, con un código (`SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`, `BUSQUEDA_PREVIA_REQUERIDA`…).
- **Sin trabajo extra para el agente** y **sin registrar su uso** (decisiones de Dennys).
- **La E3 (independencia del idioma) toca esta carpeta:** las validaciones de sustantivos y puentes se están haciendo neutrales al idioma (pasos B1–B3 en la rama del operador).

## Lo que falta (Fase 2 de modularización)

- `search.py` y `write.py` son grandes (más de 1.100 líneas cada uno). Candidatos a dividirse: validación / llamada al motor / armado de la respuesta.
- Las validaciones compartidas podrían vivir en un módulo propio (`validacion.py`) en lugar de en `_shared.py`.
