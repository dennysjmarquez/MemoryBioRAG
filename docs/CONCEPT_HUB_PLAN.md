# Concept Hub — Plan de Implementación

**Fecha:** 2026-08-21
**Autor:** Athena-OEC
**Estado:** Implementado (fase inicial)

---

## Problema que resuelve

BioRAG es un motor **léxico** (FTS5/BM25) que falla el 100% de las búsquedas semánticas puras — cuando la query y el nodo no comparten palabras pero comparten significado.

**Evidencia (FASE 1+2):**
- Búsqueda exacta: 80% éxito ✅
- Sinónimos: 80% éxito ✅
- Dimensiones solas: 0% éxito ❌
- Semántica pura: 0% éxito ❌

**Causa raíz:** BM25 necesita coincidencia textual. Las capas semánticas existentes (PPMI/SVD, SDM, WordNet, dimensiones) pesan ~30% del scoring pero no tienen entrada cuando BM25 devuelve 0.

---

## Solución: 4 técnicas combinadas

### 1. Concept Hub (implementado)
- **Qué:** Grafo de significado con bridges explícitos
- **Cómo:** Tablas SQLite que mapean frases a nodos canónicos
- **Integración:** Expansión de query ANTES de FTS5 + señal #14 en scoring

### 2. WordNet expandido (futuro)
- **Qué:** Usar sinónimos + hiperonimia en vez de solo lexnames
- **Estado:** Código existe en `fallback_simbolico.py`, pendiente integración

### 3. Expansión vía grafo sináptico (futuro)
- **Qué:** Usar spreading activation para expandir queries
- **Estado:** Código existe en `similitud_conceptual.py`, pendiente mejora

### 4. Diccionario de dominio (futuro)
- **Qué:** Mapeo explícito de términos técnicos
- **Estado:** Pendiente

---

## Archivos modificados/creados

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `core/concept_hub.py` | **NUEVO** | Motor del Concept Hub (CRUD + expansión) |
| `core/memory_store.py` | MODIFICADO | Integración expansión en `buscar_por_frase()` + señal #14 en scoring |
| `mcp_server.py` | MODIFICADO | 5 tools MCP nuevos |
| `scripts/test_concept_hub.py` | **NUEVO** | Script de evaluación FASE 2 |
| `docs/CONCEPT_HUB_PLAN.md` | **NUEVO** | Este documento |

---

## Estructura de datos

```sql
-- Nodos canónicos agrupados por significado
concept_hubs (hub_id, canonical_node, description, created_at)

-- Nodos vinculados a cada hub
concept_hub_nodes (hub_id, node_concepto, role)

-- Bridges: frases que mapean al hub (la capa semántica real)
concept_hub_bridges (hub_id, bridge_text, weight)
```

---

## Tools MCP

| Tool | Función |
|------|---------|
| `concept_hub_crear` | Crear hub con bridges |
| `concept_hub_agregar_bridges` | Agregar bridges a hub existente |
| `concept_hub_listar` | Listar todos los hubs |
| `concept_hub_buscar` | Buscar qué hub matchea una query |
| `concept_hub_cargar_iniciales` | Cargar 10 hubs predefinidos |

---

## Scoring

**Fórmula anterior (13 señales):**
```
55% BM25 + 14% dim + 8% concepto + 8% sinonimos + 10% peso + 
10% jaccard + 10% grupo + 8% tematico + 4% temporal + 2% asoc + 
20% pred + 15% PPMI
```

**Fórmula nueva (14 señales):**
```
25% BM25 + 14% dim + 8% concepto + 8% sinonimos + 10% peso + 
10% jaccard + 10% grupo + 8% tematico + 4% temporal + 2% asoc + 
20% pred + 15% PPMI + 12% hub
```

El peso del hub (12%) se redistribuye de los pesos existentes (renormalización automática).

---

## Evaluación

### FASE 2: Queries semánticas puras

| Query | Nodo esperado | Sin hub | Con hub |
|-------|---------------|---------|---------|
| "trabajos que tuve antes de programar" | historia_tasajera | ? | ? |
| "romper algo que funcionaba" | leccion_control_flujo | ? | ? |
| "aprender sin que nadie enseñe" | biorag_v20_rpe_dopamina | ? | ? |
| "trabajos ingeniero sobrevivir antes programar" | historia_tasajera | ? | ? |
| "IAs que se contradigan para encontrar la verdad" | impugn_consenso | ? | ? |

**Métrica objetivo:** Recall@5 semántico puro > 60% (vs 0% actual)

---

## Seguridad

- DB de tests separada: `memory_biorag_test.db`
- Migración automática de tablas (CREATE TABLE IF NOT EXISTS)
- Fallback silencioso si Concept Hub no está disponible
- No se modifica el pipeline existente — solo se agrega una capa

---

## Próximos pasos

1. ✅ Implementar Concept Hub core
2. ✅ Integrar con buscar_por_frase()
3. ✅ Agregar señal #14 al scoring
4. ✅ Registrar tools MCP
5. ✅ Crear 10 hubs iniciales
6. ⏳ Ejecutar evaluación FASE 2
7. ⏳ Integrar WordNet expandido
8. ⏳ Integrar expansión vía grafo sináptico
9. ⏳ Crear diccionario de dominio
10. ⏳ Evaluación final completa
