# Plan técnico — Spec 001: Sustantivos Clave

## Estructura de módulos

| Archivo | Responsabilidad | RFs cubiertos |
|---|---|---|
| `core/memory_store.py` | Schema DB, migración, FTS5, triggers, percibir_corto_plazo, consolidación, bm25 queries | RF-4, RF-5, RF-6, RF-7, RF-10, RF-11, RF-12, RF-15, RF-16, RF-17, RF-18, RF-19, RF-22 |
| `mcp_server.py` | Validación de entrada, tools MCP `aprender`/`guardar`/`agregar_sustantivos`/`sustantivos`/`recordar` | RF-1, RF-2, RF-3, RF-8, RF-9, RF-14, RF-16, RF-17, RF-19, RF-20, RF-21 |
| `specs/001-sustantivos-clave/bateria_extraccion.md` | Set fijo de casos de extracción multi-modelo (guardar + buscar) | RF-23 |
| `core/sinapsis.py` | BM25 query en `auto_vincular` (1 location) | RF-5 |
| `core/stemmer_es.py` | Función central `_quitar_acentos` (ya existe, reutilizar) | RF-10, RF-18 |

## Modelo de datos interno

### Columna nueva en tablas existentes

```sql
-- Ambas tablas reciben la misma columna:
sustantivos_clave TEXT DEFAULT ''
```

**corto_plazo** (agregar después de `valencia_somatica`):
```sql
ALTER TABLE corto_plazo ADD COLUMN sustantivos_clave TEXT DEFAULT ''
```

**largo_plazo** (agregar después de `valencia_somatica`):
```sql
ALTER TABLE largo_plazo ADD COLUMN sustantivos_clave TEXT DEFAULT ''
```

### FTS5 trigram — columna nueva

```sql
-- ANTES (3 columnas):
CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
    concepto, contenido, sinonimos,
    tokenize='trigram'
)

-- DESPUÉS (4 columnas):
CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
    concepto, contenido, sinonimos, sustantivos_clave,
    tokenize='trigram'
)
```

### Triggers — incluir sustantivos_clave

Los 3 triggers de `largo_plazo_fts` (`_ai`, `_ad`, `_au`) deben incluir `sustantivos_clave` en los INSERT/DELETE. El trigger `_au` (AFTER UPDATE) es el que sincroniza FTS5 cuando `biorag_agregar_sustantivos` actualiza el campo.

**NO se modifica** `largo_plazo_fts_unicode` (unicode61) — fuera de alcance según spec.

### BM25 weights

```sql
-- ANTES (3 pesos):
bm25(largo_plazo_fts, 5.0, 1.0, 2.0)

-- DESPUÉS (4 pesos):
bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0)
-- concepto=5.0x, contenido=1.0x, sinonimos=2.0x, sustantivos_clave=4.0x
```

Para nodos sin `sustantivos_clave` (pre-migración, `""`), la columna aporta peso 0.0. El scores relativos se preservan por la normalización min-max del motor.

## Algoritmos y lógica interna

### A. Validación de sustantivos_clave (en `_aprender_impl`)

**Ubicación:** Después de la validación de bridges (~línea 1936 en mcp_server.py).

**Algoritmo:**

```
1. Si sustantivos_clave es None o vacío → error SUSTANTIVOS_CLAVE_AUSENTES (RF-1)
2. Normalizar:
   a. Lowercase (str.lower())
   b. Quitar tildes via _quitar_acentos() de stemmer_es.py (RF-10, RF-18)
   c. Strip espacios alrededor de comas
   d. Colapsar comas múltiples (,, → ,)
   e. Split por "," → lista
3. Auto-deduplicar preservando orden (RF-14):
   seen = set()
   sk_unique = []
   for t in sk:
       if t not in seen: seen.add(t); sk_unique.append(t)
4. Validar cantidad: 2 ≤ len(sk_unique) ≤ 4 → si no, error SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA (RF-2, RF-9)
5. Validar formato por término (RF-3):
   - 2 ≤ len(t) ≤ 15 (inclusivos)
   - Sin espacios
   - Solo alfanuméricos + guion bajo (_)
   - Si falla → error SUSTANTIVOS_CLAVE_FORMATO_INVALIDO
6. Retornar ",".join(sk_unique) como string normalizado
```

**Error codes y mensajes (exactos):**

| Code | Mensaje |
|---|---|
| `SUSTANTIVOS_CLAVE_AUSENTES` | `"SUSTANTIVOS_CLAVE_AUSENTES: el nodo '{concepto}' NO fue guardado. Los parámetros concepto, contenido, dimensiones, syn y bridges ya llegaron correctamente. Solo falta el parámetro obligatorio 'sustantivos_clave'. ACCIÓN REQUERIDA: repetí la llamada con TODOS los mismos parámetros más el campo sustantivos_clave. Protocolo: ¿De QUÉ TRATA este nodo? Identificá 2-4 sustantivos centrales. Formato: 'servidor,backend,timeout,conexion'"` |
| `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA` | `"SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA: se requieren entre 2 y 4 términos únicos; se recibió {n} tras deduplicar. Formato: 'servidor,backend,timeout,conexion'"` |
| `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO` | `"SUSTANTIVOS_CLAVE_FORMATO_INVALIDO: el término '{term}' no cumple formato (2-15 chars, sin espacios, solo alfanuméricos y guion bajo)."` |
| `NODO_NO_ENCONTRADO` | `"NODO_NO_ENCONTRADO: el concepto '{concepto}' no existe en la base de datos."` |

### B. Propagación en consolidación (ciclo_sueno)

**Ubicación:** `ciclo_sueno_consolidacion` en memory_store.py, fase de transferencia (~línea 2283).

**Nodo nuevo (Branch B, ~línea 2327):**
```sql
INSERT INTO largo_plazo (..., sustantivos_clave)
VALUES (..., ?)
-- Se copia directo desde corto_plazo
```

**Nodo existente (Branch A, ~línea 2299):**
```python
# Sobrescribe: sustantivos_clave de corto_plazo reemplaza el de largo_plazo (RF-6, CL-6)
# Si corto_plazo.sustantivos_clave es "" → NO sobrescribe (preserva el de largo_plazo)
sk_nuevo = corto_row['sustantivos_clave']
if sk_nuevo:  # solo sobrescribe si tiene valor
    largo_row['sustantivos_clave'] = sk_nuevo
```

**Razón de la sobrescritura (no merge):** A diferencia de `sinonimos` (que se unen), `sustantivos_clave` representa el centro de gravedad temático — no se "mezclan", se reemplazan. Si el agente actualiza el nodo con nuevos sustantivos, es porque el tema cambió.

### C. Función de normalización central

**Decisión:** Reusar `_quitar_acentos` de `core/stemmer_es.py` (línea 43-46). No crear nueva implementación.

```python
from core.stemmer_es import _quitar_acentos

def normalizar_sustantivos_clave(raw: str) -> str:
    """Normaliza sustantivos_clave: lowercase, quitar tildes, trim, dedup, colapsar comas."""
    sk = [t.strip().lower() for t in raw.split(",") if t.strip()]
    sk = [_quitar_acentos(t) for t in sk]  # RF-10, RF-18
    seen = set()
    unique = []
    for t in sk:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return ",".join(unique)
```

**Ubicación:** Definir en `memory_store.py` (cerca de `percibir_corto_plazo`) y exportar para uso en `mcp_server.py`.

### D. Normalización en queries (RF-18)

**Ubicación:** `buscar_por_frase` en memory_store.py, antes de construir la query FTS5.

**Algoritmo:** Aplicar `_quitar_acentos(query)` antes de pasar el string a FTS5. Esto asegura que "conexión" (con tilde) matchee "conexion" (sin tilde) almacenado.

**Nota:** FTS5 trigram ya es accent-insensitive internamente, pero la normalización explícita garantiza simetría perfecta con lo almacenado.

## Decisiones técnicas y arquitectura

### Decisión 1: FTS5 trigram vs crear tabla separada
- **Decisión:** Agregar columna `sustantivos_clave` a `largo_plazo_fts` existente
- **Alternativa descartada:** Crear una tabla FTS5 separada `largo_plazo_sustantivos_fts`
- **Por qué:** Una sola tabla FTS5 simplifica las queries (un solo JOIN), los triggers, y el maintenance. El peso BM25 se controla con el 4° parámetro.

### Decisión 2: Sobrescribir vs merge en consolidación
- **Decisión:** Sobrescribir `sustantivos_clave` de largo_plazo con el de corto_plazo (si corto tiene valor)
- **Alternativa descartada:** Merge/union como se hace con `sinonimos`
- **Por qué:** `sustantivos_clave` es el centro de gravedad temático — no se "acumulan", se reemplazan. Un nodo sobre "contaminación" que se actualiza con "automóvil" significa que el tema cambió.

### Decisión 3: Reusar `_quitar_acentos` existente
- **Decisión:** Importar de `core.stemmer_es.py` (línea 43-46)
- **Alternativa descartada:** Crear nueva función o reusar las 6 implementaciones duplicadas existentes
- **Por qué:** Ya existe, está probada, es la implementación canónica. Las otras 5 copias son deuda técnica preexistente.

### Decisión 4: `biorag_agregar_sustantivos` busca en ambas tablas
- **Decisión:** Buscar primero en `largo_plazo`, fallback a `corto_plazo`
- **Alternativa descartada:** Buscar solo en `largo_plazo` (RF-16 original)
- **Por qué:** Un nodo recién creado puede no haberse consolidado aún. Sin fallback, la tool fallaría silenciosamente para nodos válidos.

### Decisión 5: BM25 unicode61 sin cambios
- **Decisión:** No agregar `sustantivos_clave` a `largo_plazo_fts_unicode`
- **Alternativa descartada:** Agregar columna a ambas tablas FTS5
- **Por qué:** Fuera de alcance (spec: "Indexación unicode — solo trigram"). Unicode61 se usa como fallback y no necesita el boost temático.

## Contrato de interfaces externas

### Tool: `biorag_aprender` (modificada)

```python
# Parámetro NUEVO (después de bridges):
sustantivos_clave: Annotated[Optional[str], Field(
    description=(
        "OBLIGATORIO — centro de gravedad semántico: 2-4 sustantivos "
        "que definen de QUÉ TRATA el nodo (no qué menciona).\n"
        "Formato: separados por coma, minúsculas, sin tildes.\n"
        "Ejemplo: 'servidor,backend,timeout,conexion'\n"
        "Mínimo 2, máximo 4 términos únicos (2-15 chars cada uno)."
    )
)] = None
```

### Tool: `biorag_guardar` (modificada)

Mismo parámetro `sustantivos_clave` que `biorag_aprender`. Ambas delegan a `_aprender_impl`.

### Tool: `biorag_recordar` (modificada — RF-19, RF-20)

```python
# Parámetro NUEVO (opcional):
sustantivos_clave: Annotated[Optional[str], Field(
    description=(
        "Opcional — sustantivos clave para boost de precisión en la búsqueda.\n"
        "Cuando se provee, nodos cuyo sustantivos_clave coincida con estos términos "
        "suben en el ranking (peso BM25 4.0x).\n"
        "Formato: separados por coma, minúsculas, sin tildes.\n"
        "Ejemplo: 'servidor,backend,timeout'\n\n"
        "NOTA: Este parámetro es OPCIONAL. Si se omite, la búsqueda funciona normalmente. "
        "Úsalo cuando quieras recuperar nodos por lo que TRATAN, no solo por lo que MENCIONAN."
    )
)] = None
```

**Flujo interno en `_recordar_impl`:**

1. Si `sustantivos_clave` es None o vacío (`""`) → no hacer nada (búsqueda normal). String vacío = omitido.
2. Si se provee → normalizar (lowercase, quitar tildes, trim, dedup) con la misma función de `aprender`
3. Validar formato (2-15 chars, sin espacios, alfanuméricos + _). Si falla → error accionable, búsqueda NO se ejecuta
4. **NO validar cantidad en recordar** — es solo boost, no guardado. El agente puede pasar 1 o 10 términos; el motor BM25 los procesa igual.
5. Inyectar los sustantivos normalizados como condición adicional en la query FTS5 de `buscar_por_frase`

**Mecanismo de boost:** Los sustantivos se pasan como parámetro a `buscar_por_frase`, que los agrega como filtro `MATCH` adicional en la columna `sustantivos_clave` de `largo_plazo_fts`. El peso BM25 4.0x ya está configurado en los 8 locations de bm25(). No se necesita cambiar los weights — solo pasar el filtro.

**Nota de descripción (RF-19):** El texto del parámetro incluye explícitamente: *"Úsalo cuando quieras recuperar nodos por lo que TRATAN, no solo por lo que MENCIONAN"* — para que cualquier agente (incluso con modelo pequeño) entienda cuándo usarlo.

### Tool: `biorag_agregar_sustantivos` (NUEVA)

```python
@mcp.tool(name="agregar_sustantivos")
def biorag_agregar_sustantivos(
    concepto: Annotated[str, Field(description="Nombre del nodo existente.")],
    sustantivos_clave: Annotated[str, Field(
        description="2-4 sustantivos clave separados por coma."
    )],
) -> str:
    # 1. Buscar nodo en largo_plazo, fallback a corto_plazo
    # 2. Si no existe en ninguna → error NODO_NO_ENCONTRADO
    # 3. Normalizar sustantivos_clave (misma función que aprender)
    # 4. Validar (2-4 términos, formato)
    # 5. Guardar sustantivos_anteriores para respuesta
    # 6. UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?
    #    (trigger _au sincroniza FTS5 automáticamente)
    # 7. Retornar {status, concepto, sustantivos_anteriores, sustantivos_nuevos}
```

**Respuesta exitosa:**
```json
{
  "status": "ok",
  "concepto": "leccion_http_500",
  "sustantivos_anteriores": "",
  "sustantivos_nuevos": "servidor,backend,timeout"
}
```

### Tool: `biorag_sustantivos` (NUEVA)

```python
@mcp.tool(name="sustantivos")
def biorag_sustantivos(
    concepto: Annotated[str, Field(description="Nombre del nodo a consultar.")],
) -> str:
    # 1. Buscar en largo_plazo, fallback a corto_plazo
    # 2. Si no existe → error NODO_NO_ENCONTRADO
    # 3. Si existe pero sustantivos_clave = "" → {status: "ok", sustantivos_clave: "", items: []}
    # 4. Si tiene valor → {status: "ok", sustantivos_clave: "a,b,c", items: ["a","b","c"]}
```

### Respuesta de error ( ambas tools nuevas )

```json
{
  "status": "error",
  "codigo": "NODO_NO_ENCONTRADO",
  "mensaje": "El concepto 'xyz' no existe en la base de datos."
}
```

## Estrategia de tests

### Unitarios (nuevos, en `tests/`)

| Test | RF cubierto | Qué verifica |
|---|---|---|
| `test_sustantivos_clave_ausente` | RF-1 | Error cuando no se pasa el parámetro |
| `test_sustantivos_clave_cantidad_invalida` | RF-2, RF-9 | <2 o >4 términos → error |
| `test_sustantivos_clave_formato_invalido` | RF-3 | Término con espacio, especial, <2 o >15 chars |
| `test_sustantivos_clave_valido` | RF-4 | Guardado exitoso en corto_plazo |
| `test_sustantivos_clave_dedup` | RF-14 | Duplicados se eliminan, se valida cantidad post-dedup |
| `test_sustantivos_clave_normalizacion` | RF-10 | Lowercase + quitar tildes + trim |
| `test_sustantivos_clave_bm25_boost` | RF-5 | BM25 prioriza nodos con match en sustantivos_clave |
| `test_sustantivos_clave_consolidacion` | RF-6 | Propagación corto→largo durante sueño |
| `test_sustantivos_clave_fts_index` | RF-7 | Nodo consolidado aparece en FTS5 |
| `test_agregar_sustantivos` | RF-16 | Tool actualiza nodo existente + FTS5 sync |
| `test_agregar_sustantivos_no_existe` | RF-16 | Error NODO_NO_ENCONTRADO |
| `test_agregar_sustantivos_sobrescribe` | RF-16 | Muestra anterior vs nuevo |
| `test_sustantivos_tool` | RF-17 | Devuelve campo de nodo existente |
| `test_sustantivos_tool_no_existe` | RF-17 | Error NODO_NO_ENCONTRADO |
| `test_sustantivos_tool_sin_campo` | RF-17 | Devuelve "" y [] |
| `test_acentos_en_query` | RF-18 | Query "conexión" matchea "conexion" almacenado |
| `test_recordar_sustantivos_clave_boost` | RF-19 | `recordar` con sustantivos_clave boostea resultados |
| `test_recordar_sustantivos_clave_formato_invalido` | RF-20 | `recordar` con formato inválido → error, búsqueda NO se ejecuta |
| `test_aprender_valida_antes_de_escribir` | RF-21 | `aprender` con sustantivos_clave inválido → error, nodo NO se guarda |

### Garantía de instalación (RF-22)

Dos caminos verificados por tests, ambos cubriendo la existencia de `sustantivos_clave` en las 4 capas (tabla corto_plazo, tabla largo_plazo, FTS5, triggers):

| Camino | Test | Qué verifica |
|---|---|---|
| DB nueva desde cero | `test_schema_*` (create_table) | Columnas en `CREATE TABLE` + FTS5 4 columnas, sin `ALTER` |
| DB existente migrada | `test_migracion_db_vieja_agrega_columnas` | `ALTER TABLE ADD COLUMN` en ambas tablas + rebuild FTS5, nodos previos intactos |

### Batería de extracción multi-modelo (RF-23)

| Elemento | Detalle |
|---|---|
| Artefacto | `specs/001-sustantivos-clave/bateria_extraccion.md` (≥6 casos con `Esperado` y `Prohibido`) |
| Ejecución | Manual/agente por modelo; guardar con `biorag_aprender` + buscar con `biorag_recordar` |
| Criterio de pase | Extraído == `Esperado` y != `Prohibido`; nodo recuperado en top al buscar |
| Registro | Matriz de corridas en la batería (modelo, guardado OK, búsqueda OK, fallos) |

### Integración (existentes, ejecutar post-cambio)

| Comando | Gate |
|---|---|
| `python3 -m pytest tests/ -v` | 168/168 PASSED |
| `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py` | Recall@5 ≥ 97.0%, FP = 0.0% |
| `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py` | Cero regresión |

### Cobertura RF

| RF | Módulo | Test |
|---|---|---|
| RF-1 | mcp_server.py (_aprender_impl) | test_sustantivos_clave_ausente |
| RF-2 | mcp_server.py (_aprender_impl) | test_sustantivos_clave_cantidad_invalida |
| RF-3 | mcp_server.py (_aprender_impl) | test_sustantivos_clave_formato_invalido |
| RF-4 | memory_store.py (percibir_corto_plazo) | test_sustantivos_clave_valido |
| RF-5 | memory_store.py (bm25 queries) + sinapsis.py | test_sustantivos_clave_bm25_boost |
| RF-6 | memory_store.py (ciclo_sueno) | test_sustantivos_clave_consolidacion |
| RF-7 | memory_store.py (FTS5 triggers) | test_sustantivos_clave_fts_index |
| RF-8 | mcp_server.py (biorag_guardar) | test_sustantivos_clave_valido (mismo impl) |
| RF-9 | mcp_server.py (_aprender_impl) | test_sustantivos_clave_cantidad_invalida |
| RF-10 | memory_store.py (normalizar) | test_sustantivos_clave_normalizacion |
| RF-11 | Pre-implementación | Benchmark baseline |
| RF-12 | Post-implementación | Benchmark post-change |
| RF-13 | Post-implementación | diff baseline vs post |
| RF-14 | mcp_server.py (_aprender_impl) | test_sustantivos_clave_dedup |
| RF-15 | memory_store.py (schema) | test_nodo_pre_migracion (campo vacío) |
| RF-16 | mcp_server.py (nueva tool) | test_agregar_sustantivos + test_agregar_sustantivos_no_existe + test_agregar_sustantivos_sobrescribe |
| RF-17 | mcp_server.py (nueva tool) | test_sustantivos_tool + test_sustantivos_tool_no_existe + test_sustantivos_tool_sin_campo |
| RF-18 | memory_store.py (buscar_por_frase) | test_acentos_en_query |
| RF-19 | mcp_server.py (_recordar_impl) + memory_store.py (buscar_por_frase) | test_recordar_sustantivos_clave_boost |
| RF-20 | mcp_server.py (_recordar_impl) | test_recordar_sustantivos_clave_formato_invalido |
| RF-21 | mcp_server.py (_aprender_impl) | test_aprender_valida_antes_de_escribir |
| RF-22 | memory_store.py (create_table + migración) | test_schema_* + test_migracion_db_vieja_agrega_columnas |
| RF-23 | bateria_extraccion.md | corrida manual por modelo (guardar + buscar) |
