# El fix del bucle de feedback es correcto pero inalcanzable desde el MCP

**Fecha:** 2026-08-16
**Commit revisado:** `8794768`
**Estado:** el código es correcto. **En el flujo real nunca se ejecuta.**

---

## 1. El código está bien

`core/memory_store.py:2568-2576`:

```python
try:
    if getattr(self, "last_log_id", None):
        self.cursor.execute(
            "UPDATE log_busquedas SET util = ? WHERE id = ? AND util IS NULL",
            (1 if exito else 0, self.last_log_id),
        )
except Exception as e:
    print(f"[BioRAG] aviso: no se pudo propagar feedback a log_busquedas: {e}")
```

Correcto: idempotente, con `try/except`, y la lógica es la propuesta.

## 2. Por qué no se ejecuta nunca

`mcp_server.py:172`:

```python
def _get_cerebro() -> SQLiteMemoryBioRAG:
    return SQLiteMemoryBioRAG(db_path=os.environ.get("BIORAG_PATH") or _DEFAULT_DB)
```

**Crea una instancia nueva en cada llamada a herramienta.** Y cada tool cierra la
suya al terminar (`finally: cerebro.cerrar_sistema()`).

Flujo real de un agente:

```
1. tool `recordar`  -> cerebro_A = _get_cerebro()
                       cerebro_A.last_log_id = 42
                       cerebro_A.cerrar_sistema()      <- se destruye

2. tool `feedback`  -> cerebro_B = _get_cerebro()      <- OTRA instancia
                       cerebro_B.last_log_id           <- no existe
                       getattr(..., None) -> None
                       el UPDATE nunca corre
```

`last_log_id` es **estado de instancia en memoria**. No sobrevive entre llamadas
MCP, que es exactamente donde ocurre el feedback real.

### Verificado por simulación

```
CASO A: misma instancia (como en los tests)  -> util = 1     ✔
CASO B: dos instancias (flujo MCP real)      -> util = None  ✘
```

Los tests pasan porque prueban el caso A. El caso B es el que ocurre en producción.

**Y falla en silencio:** el `getattr(..., None)` hace que no salte ninguna
excepción. `util` sigue en NULL y nadie se entera — el mismo patrón que esta
auditoría lleva toda la sesión persiguiendo.

## 3. El fix que sí funciona: persistir el vínculo en la DB

El estado no puede vivir en memoria si el proceso no sobrevive. Tiene que estar en
SQLite, que es lo único compartido entre llamadas.

### Opción A (recomendada): resolver por concepto recuperado

El problema de fondo es que `log_busquedas` **no guarda qué conceptos devolvió**.
Si lo guardara, el feedback por concepto se podría atribuir a su consulta sin
depender de estado en memoria.

```sql
-- Nueva columna: qué conceptos devolvió esta búsqueda (CSV, top-5).
-- POR QUÉ: permite atribuir un feedback por concepto a la consulta que lo
-- recuperó, sin depender de estado en memoria (que no sobrevive entre
-- llamadas MCP, ver docs/FIX_FEEDBACK_NO_ALCANZABLE.md).
ALTER TABLE log_busquedas ADD COLUMN conceptos_top TEXT;
```

Al registrar la búsqueda (`memory_store.py:4857`), guardar los conceptos del top-5.
Y en `aplicar_refuerzo_dopaminergico`:

```python
# Atribuir el feedback a la búsqueda más reciente que devolvió este concepto.
# No usa last_log_id (estado en memoria) porque el MCP crea una instancia
# nueva por llamada: ver docs/FIX_FEEDBACK_NO_ALCANZABLE.md
try:
    self.cursor.execute(
        "UPDATE log_busquedas SET util = ? "
        "WHERE id = (SELECT id FROM log_busquedas "
        "            WHERE util IS NULL "
        "              AND (',' || conceptos_top || ',') LIKE ? "
        "            ORDER BY creado_en DESC LIMIT 1)",
        (1 if exito else 0, f"%,{key},%"),
    )
    if self.cursor.rowcount == 0:
        print(f"[BioRAG] aviso: feedback sobre '{key}' sin búsqueda asociada "
              f"pendiente; no se propagó a log_busquedas.")
except Exception as e:
    print(f"[BioRAG] aviso: no se pudo propagar feedback: {e}")
```

**Ventajas:** atribución correcta (no "la última búsqueda cualquiera", sino la que
realmente devolvió ese concepto), funciona entre procesos, y el `rowcount == 0`
avisa en vez de fallar en silencio.

### Opción B (más simple, menos precisa): tabla de última búsqueda

Persistir `last_log_id` en la tabla `data`, que ya existe:

```python
# al registrar la búsqueda
self.cursor.execute(
    "INSERT INTO data (clave, valor) VALUES ('ultima_busqueda_id', ?) "
    "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
    (str(self.last_log_id),))
```

y leerlo en el feedback. Es menos código, pero mantiene la imprecisión de "la última
búsqueda", y además se pisa si hay varios agentes concurrentes.

**Recomendación: opción A.** El coste extra es una columna y una consulta; a cambio
la atribución es correcta y el fallo es visible.

## 4. Lo que hay que corregir en los tests

Los tests actuales validan el caso A (misma instancia). Hace falta uno que replique
el caso B:

```python
def test_feedback_propaga_util_entre_instancias(self):
    """El MCP crea una instancia nueva por llamada. El feedback debe propagarse
    igual: si esto falla, `util` queda NULL para siempre en producción aunque
    los tests de una sola instancia pasen."""
    c1 = SQLiteMemoryBioRAG(self.db)
    c1.buscar_por_frase("consulta de prueba")
    c1.cerrar_sistema()

    c2 = SQLiteMemoryBioRAG(self.db)          # instancia distinta, como el MCP
    c2.aplicar_refuerzo_dopaminergico("concepto_devuelto", exito=True)
    c2.cerrar_sistema()

    con = sqlite3.connect(self.db)
    util = con.execute(
        "SELECT util FROM log_busquedas ORDER BY id DESC LIMIT 1").fetchone()[0]
    self.assertIsNotNone(util, "util quedó NULL: el feedback no cruzó instancias")
```

Ese test es el que distingue "funciona en el banco" de "funciona en producción".

## 5. Por qué esto importa más de lo que parece

El bucle de feedback es el cuello de botella de **tres** líneas de trabajo a la vez
(negativos reales para calibrar, validación empírica de la garantía conforme, y el
olvido gobernado por silencio). Darlo por cerrado cuando no lo está significa que
dentro de dos semanas `util` seguirá en 0 y nadie sabrá por qué.

Es literalmente el mismo patrón del hallazgo H5 (`categoria IS NULL` que nunca
recibe LTD) y del de la guarda desconectada: **una pieza correcta que no está
enchufada, fallando sin ruido.**
