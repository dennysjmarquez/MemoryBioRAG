# Indexación Dimensional Explícita — Diseño

> Sistema de ejes ortogonales al texto para recuperar lo que FTS5, sinónimos,
> ráfaga y paráfrasis no pueden conseguir.
> Diseñado por Dennys J. Márquez. Junio 2026.

---

## Problema

Hay búsquedas que no se resuelven con coincidencia léxica:

- "¿Cuántas veces he mostrado afecto hacia los agentes?"
- "Esa vez que me dio la arrechera con la laptop que se dañó"
- "Qué decisiones técnicas tomé con frustración"
- "Momentos neutros vs emocionales en mi aprendizaje"

La palabra "laptop" sola da mil resultados. **Laptop + emoción=frustración** acota
al momento exacto. La información no está en el texto — está en la **cualidad de
la experiencia al guardar**.

---

## Principio

> Indexar lo que el texto no dice.

Los ejes dimensionales son **ortogonales al contenido textual**. Permiten
filtrar por cualidad de la experiencia, no por coincidencia léxica. Esto abre
búsquedas literalmente imposibles con FTS5, sinónimos o paráfrasis.

---

## Decisión arquitectónica — Fase 1: Columna simple

**Opción elegida: columna `emocion` en `largo_plazo`.**

### Por qué

| Criterio | Columna (A) | Tablas (B) | JSON (C) |
|----------|-------------|------------|----------|
| Esfuerzo inicial | Mínimo | Alto | Bajo |
| Consultable vía SQL | Sí | Sí | No |
| N dimensiones | 1 fija | Ilimitadas | Ilimitadas |
| Migración futura a B | Directa | N/A | Media |
| Tests existentes (#72) | Cubre | Parcial | Parcial |

La columna simple es **la ruta más corta a producción**. Si la necesidad de
dimensionalidad crece, la migración a tablas dedicadas es directa:

```
largo_plazo.emocion → concepto_dimension(valor="frustracion", dimension_id=1)
```

Sin romper queries existentes.

---

## Implementación

### Schema

```sql
ALTER TABLE largo_plazo ADD COLUMN emocion TEXT DEFAULT '';
```

Sin tablas nuevas. Sin migración de datos. El valor se escribe al percibir y
se consulta con `WHERE emocion = ?`.

### Cómo se guarda

```python
percibir_corto_plazo(
    concepto="error_laptop_danada",
    contenido="La laptop se dañó y perdí todo...",
    emocion="frustracion"
)
```

Si no se pasa emoción, el middleware de auto_guardado intenta inferirla del
contenido y la sugiere.

### Cómo se busca

`buscar_por_frase()` acepta `filtro_emocion` como parámetro opcional — filtra
DESPUÉS de FTS5/trigram/híbrido, ANTES de devolver resultados:

```python
buscar_por_frase("laptop", filtro_emocion="frustracion")
```

Además, `buscar_por_emocion(emocion, sujeto="")` salta FTS5 por completo y
hace SQL directo a `largo_plazo WHERE emocion = ?`, ideal para análisis
cognitivo ("dame todos los momentos de afecto").

### Exposición MCP

Dos cambios mínimos en `mcp_server.py`:

1. Parámetro `emocion` opcional en `recordar`/`buscar`
2. Nueva tool `buscar_por_emocion` para consulta directa

No se necesitan tools de administración (no hay tablas nuevas que gestionar).

### Tests

El test #72 (`test_memory.py`) ya prueba persistencia de emoción en sinónimos.
Se agrega:

- Test de `percibir_corto_plazo` con `emocion=` y verificar columna
- Test de `buscar_por_frase` con `filtro_emocion` y verificar filtrado
- Test de `buscar_por_emocion` directa

---

## Post-implementación — Fase 2 (si escala)

### Cuándo migrar a tablas dimensionales

- Aparece una segunda dimensión (ej: `confianza`)
- Se necesita `sujeto` por registro (ej: frustración con "la laptop" vs
  frustración con "el proyecto")
- Se necesita `intensidad` (ej: frustración 0.3 vs 0.9)
- Las queries de análisis cognitivo cruzan 2+ dimensiones

### Migración desde columna

```sql
-- Crear tablas dimensionales (Fase 2)
CREATE TABLE dimensiones (...);
CREATE TABLE valores_dimension (...);
CREATE TABLE concepto_dimension (...);

-- Migrar datos existentes
INSERT INTO concepto_dimension (concepto, dimension_id, valor_id)
SELECT concepto, 1, (SELECT id FROM valores_dimension WHERE valor = emocion)
FROM largo_plazo WHERE emocion != '';
```

La columna `emocion` se deja como redundancia transitoria y se elimina tras
verificar la migración.

### Arquitectura Fase 2 (referencia)

```
dimensiones
├── id
├── nombre (UNIQUE)
└── descripcion

valores_dimension
├── id
├── dimension_id → dimensiones(id)
├── valor
├── descripcion
└── UNIQUE(dimension_id, valor)

concepto_dimension
├── concepto → largo_plazo(concepto) ON DELETE CASCADE
├── dimension_id → dimensiones(id)
├── valor_id → valores_dimension(id)
├── sujeto TEXT
├── intensidad REAL DEFAULT 0.5 CHECK(0-1)
└── PRIMARY KEY (concepto, dimension_id)
```

---

## Valor diferencial

1. **Recuperación de lo no-textual**: lo que no está en el contenido ni en
   sinónimos se vuelve consultable
2. **Precisión quirúrgica**: reducir miles de resultados a los 3-5 relevantes
3. **Analítica cognitiva**: correlacionar emociones con categorías, sujetos,
   líneas de tiempo
4. **Cero dependencias**: SQLite puro, misma filosofía que BioRAG
5. **Fase 1 en ~30 líneas**: la ruta más corta a producción posible

---

## Nodos relacionados en BioRAG

- `indexacion_dimensional_explicita` (Architecture)
- `principio_busqueda_por_dimension` (Principle)
- `diseno_tablas_dimensiones_biorag` (Architecture)
