# Instrumentar el LTP: por qué el parche obvio falla y cuál funciona

Contexto: P4 confirmado (100% de 154 dormidos con `exitos_dopamina == 0`, 97 puentes
de grado ≥10 muertos). El plan siguiente era:

1. agregar `'reforzado'` al CHECK de `metricas_cognitivas_nodos`
2. loguear el feedback en `aplicar_refuerzo_dopaminergico`

**Ese plan falla por dos razones, ambas verificadas ejecutando SQLite.** No es una
objeción de estilo: rompe en tiempo de ejecución.

---

## Bloqueador 1 — `metrica_id` es `NOT NULL` con FK, y el feedback ocurre fuera del sueño

Esquema real (`memory_store.py:1926-1937`):

```sql
metrica_id INTEGER NOT NULL,
FOREIGN KEY (metrica_id) REFERENCES metricas_cognitivas(id) ON DELETE CASCADE
```

y en `memory_store.py:173`: `PRAGMA foreign_keys = ON`.

`metricas_cognitivas` es la tabla de **ciclos de sueño**: una fila por ciclo. El
único INSERT al historial (`:2338`) ocurre dentro del ciclo, usando el
`lastrowid` del ciclo recién creado.

Pero `aplicar_refuerzo_dopaminergico` se dispara desde `mcp_server.py:2094`, **en
tiempo real, cuando no hay ningún ciclo de sueño en curso**. No existe un
`metrica_id` válido al que apuntar.

Comprobado ejecutando:

```
Intento A: metrica_id = NULL      -> IntegrityError: NOT NULL constraint failed
Intento B: metrica_id = 999       -> IntegrityError: FOREIGN KEY constraint failed
Intento C: metrica_id existente   -> OK
```

Si se añade el logging sin resolver esto, **cada llamada al feedback lanza
`IntegrityError`**. Y como `aplicar_refuerzo_dopaminergico` hace `commit()` al
final sin `try/except`, la excepción sube al servidor MCP: se rompe el feedback en
producción, que es justo lo que se quería arreglar.

## Bloqueador 2 — `CREATE TABLE IF NOT EXISTS` no modifica una tabla existente

Comprobado:

```
CREATE TABLE t (accion TEXT CHECK(accion IN ('nuevo','actualizado')));
CREATE TABLE IF NOT EXISTS t (accion TEXT CHECK(accion IN (...,'reforzado')));
-- el esquema NO cambia
INSERT INTO t VALUES ('reforzado');  -> CHECK constraint failed
```

En la DB de producción la tabla ya existe con el CHECK viejo. Editar el
`CREATE TABLE IF NOT EXISTS` del código **no tiene ningún efecto sobre ella**. Y
SQLite no permite `ALTER TABLE ... ALTER CONSTRAINT`: hay que recrear y migrar.

Peor: en una DB nueva el CHECK sí aceptaría `'reforzado'`, y en producción no. El
mismo código se comportaría distinto según la antigüedad de la base — el tipo de
bug que aparece semanas después.

---

## El parche que sí funciona

La causa raíz es que se está intentando meter un evento **en tiempo real** dentro
de una tabla cuyo grano es **por ciclo de sueño**. Son dos frecuencias distintas;
forzarlas a convivir es lo que genera los dos bloqueadores.

Tabla propia, sin FK a ciclos:

```sql
-- Eventos de refuerzo dopaminérgico en tiempo real.
-- POR QUÉ una tabla aparte: metricas_cognitivas_nodos tiene grano de "ciclo de
-- sueño" (metrica_id NOT NULL con FK). El feedback ocurre entre ciclos, así que
-- no tiene un ciclo padre al que apuntar. Meterlo ahí obliga a inventar un
-- metrica_id o a relajar la FK; ambas cosas corrompen el historial forense.
CREATE TABLE IF NOT EXISTS eventos_refuerzo (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto      TEXT    NOT NULL,
    exito         INTEGER NOT NULL CHECK(exito IN (0,1)),
    peso_anterior REAL    NOT NULL,
    peso_nuevo    REAL    NOT NULL,
    delta         REAL    NOT NULL,
    exitos_previos INTEGER NOT NULL,
    motivo        TEXT,
    created_at    REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_evref_concepto ON eventos_refuerzo(concepto);
CREATE INDEX IF NOT EXISTS ix_evref_fecha    ON eventos_refuerzo(created_at);
```

Ventajas concretas:

- No toca `metricas_cognitivas_nodos`: cero riesgo de regresión en el historial
  forense que ya funciona y que el benchmark usa.
- No hay CHECK que migrar, ni comportamiento distinto entre DB vieja y nueva.
- Guarda `peso_anterior`, `peso_nuevo` y `delta`, que es **exactamente lo que P3
  necesitaba y no pudo medir**. Con esta tabla, validar Δw = 0.15(1−0.3w) pasa de
  inferencia a medición directa.
- Guarda `exitos_previos`, que permite validar también la inercia del fallo
  (−0.10/(1+ln(1+éxitos))), hoy no verificable de ninguna forma.

En `aplicar_refuerzo_dopaminergico`, justo antes del `commit()` final, y **dentro
de un try/except que no pueda tumbar el feedback**:

```python
# Registrar el evento de refuerzo. POR QUÉ: el LTP dopaminérgico era la única
# regla de actualización de peso sin rastro persistente (P3, 2026-08-15), lo que
# la hacía imposible de validar contra la teoría. El try/except es deliberado:
# perder una fila de telemetría es aceptable; romper el bucle de feedback no.
try:
    self.cursor.execute(
        "INSERT INTO eventos_refuerzo "
        "(concepto, exito, peso_anterior, peso_nuevo, delta, exitos_previos, motivo, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (key, 1 if exito else 0, peso_actual, nuevo_peso,
         round(nuevo_peso - peso_actual, 4), exitos, motivo, time.time())
    )
except Exception as e:
    print(f"[BioRAG] aviso: no se pudo registrar evento_refuerzo para '{key}': {e}")
```

El `except` imprime en vez de callar: un fallo de telemetría debe ser visible,
pero no debe propagarse al camino crítico.

---

## Antes de aplicarlo: la pregunta que P4.b dejó abierta

**P4.b se reportó como "refutada" pero es el resultado más importante de los tres,
y apunta a un agujero en mi modelo.**

La mediana de `exitos_dopamina` es 0 **también en los activos**. O sea: el feedback
no es raro en los dormidos, es raro en todo el sistema. Entonces el LTP
dopaminérgico tampoco es lo que mantiene vivos a los activos.

Y ahí falla mi teoría: si el LTD resta `0.05·d·m` por ciclo y nada compensa,
**todo** debería estar muriendo. Algo los sostiene y no está en
`termodinamica_cortical.py`.

Cuatro explicaciones posibles, excluyentes:

| | Hipótesis | Qué predice |
|---|---|---|
| H1 | Colapso en curso: aún no han muerto | pesos de activos concentrados cerca de 0.05 |
| H2 | Sostén por fusión (+0.20 al re-guardar) | peso alto + marcas `\| Actualización:` |
| H3 | Inmunidad (valencia ≥0.8, Principle/Protocol, prio 0/1) | alta fracción inmune |
| H4 | El LTD apenas corrió (pocos ciclos de sueño) | pocas filas en `metricas_cognitivas` |

`scripts/test_p5_que_sostiene_activos.py` las mide todas y dice cuál sostiene.

**Por qué importa el orden:** si resulta ser **H3**, entonces los 154 dormidos no
son víctimas de falta de feedback — son los nodos *no protegidos*, y el sistema
está funcionando como fue diseñado. Instrumentar el feedback sería correcto pero
no resolvería nada. Si es **H1**, hay una hemorragia activa y la urgencia es otra.

El logging es útil en los cuatro casos, así que puede aplicarse ya. Lo que **no**
debe hacerse todavía es cambiar constantes de decaimiento o automatizar refuerzos
para "arreglar" el olvido, porque aún no se sabe qué lo está causando.

---

## Orden recomendado

1. **Correr P5.** Es una lectura, no modifica nada. Minutos.
2. **Aplicar el parche de `eventos_refuerzo`** (tabla nueva + logging). Es aditivo
   y de bajo riesgo. Correr `test_memory.py` antes y después y comparar el conteo
   de tests que pasan.
3. **Esperar a tener datos** en `eventos_refuerzo` y recién entonces correr P3-ter
   (validar Δw = 0.15(1−0.3w) por medición directa).
4. **Solo después**, con P5 respondida y P3-ter medida, decidir si hay que tocar
   la dinámica.

Un cambio a la vez, cada uno con su medición propia.
