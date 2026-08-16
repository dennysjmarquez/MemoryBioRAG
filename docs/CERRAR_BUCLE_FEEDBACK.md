# Cerrar el bucle de feedback: el diagnóstico era incompleto

**Fecha:** 2026-08-16
**Hallazgo:** `util` no está vacía porque nadie dé feedback. Está vacía porque
**el feedback que sí se da nunca llega hasta ahí.**

---

## 1. Corrección al diagnóstico compartido

Los tres veníamos diciendo: *"la columna `util` está vacía porque nadie cierra el
bucle de feedback"*. Revisando el código, eso es **impreciso** y la diferencia
importa, porque cambia la solución.

**Lo que hay:**

- La tool MCP `feedback` **existe** (`mcp_server.py:2079`), con una descripción que
  la marca como *"HÁBITO OBLIGATORIO"*.
- Llama a `aplicar_refuerzo_dopaminergico(concepto, exito=util)`.
- Eso actualiza `largo_plazo.exitos_dopamina` / `fallos_dopamina` y, desde v28.1,
  la tabla `eventos_refuerzo`.

**Lo que falta:**

- **Nada de eso toca `log_busquedas.util`.** No existe ningún camino de código que
  la escriba, salvo `scripts/marcar_resultado.py`, que es manual y nadie ejecuta.

## 2. La desconexión de fondo: dos granos distintos

| | grano | pregunta que responde |
|---|---|---|
| `feedback` (MCP) | **concepto** | ¿sirvió este nodo? |
| calibración conforme | **consulta** | ¿esta query tenía respuesta? |

Son dos cosas distintas y nadie las une. Por eso puede haber feedback dopaminérgico
ocurriendo y `util` seguir en 0/2157: **el dato existe, pero no en la forma que la
calibración necesita.**

Esto también reencuadra P4. La conclusión *"el olvido está gobernado por el
silencio"* sigue en pie (154 dormidos con `exitos_dopamina = 0` es un hecho), pero
la causa no es solo "nadie usa la tool": es que **el sistema no tiene ningún
mecanismo automático que conecte una búsqueda con su resultado útil.** Depende
enteramente de que un agente externo se acuerde de llamar a una herramienta.

## 3. El puente ya está medio construido

En `core/memory_store.py:4860`, justo después de insertar en `log_busquedas`:

```python
self.last_log_id = self.cursor.lastrowid
```

**Ese `last_log_id` es el eslabón que falta.** Ya identifica la última búsqueda
registrada. Solo hay que usarlo cuando llega el feedback.

## 4. Fix propuesto (una función, ~15 líneas)

En `core/memory_store.py`, dentro de `aplicar_refuerzo_dopaminergico`, junto al
registro en `eventos_refuerzo`:

```python
# Cerrar el bucle hacia log_busquedas.
# POR QUÉ: el feedback llega por CONCEPTO ("¿sirvió este nodo?") pero la
# calibración conforme necesita el grano de CONSULTA ("¿esta query tenía
# respuesta?"). Sin este puente, `util` queda NULL para siempre (0/2157 filas
# al 2026-08-16) y no hay negativos reales con los que calibrar.
# Se marca la última búsqueda de la sesión: es la que motivó el feedback.
try:
    if getattr(self, "last_log_id", None):
        self.cursor.execute(
            "UPDATE log_busquedas SET util = ? WHERE id = ? AND util IS NULL",
            (1 if exito else 0, self.last_log_id),
        )
except Exception as e:
    print(f"[BioRAG] aviso: no se pudo propagar feedback a log_busquedas: {e}")
```

El `AND util IS NULL` evita sobrescribir un feedback anterior. El `try/except` sigue
la misma política que el resto de la telemetría: perder una fila es aceptable,
romper el bucle de feedback no.

### Limitación honesta de este fix

`last_log_id` es la **última** búsqueda, no necesariamente la que originó el
feedback. Si el agente busca A, busca B y luego da feedback sobre un concepto de A,
se marcará B. Es una heurística, no una atribución exacta.

Para atribución real haría falta que la tool `feedback` acepte un `query_id`
opcional, devuelto por `recordar`. Eso es más limpio pero toca el contrato del MCP.

**Recomendación:** empezar por la heurística (ruido bajo, coste casi nulo) y medir
cuántas filas se pueblan. Si el volumen justifica la precisión, añadir el `query_id`
después.

## 5. Por qué esto desbloquea todo

Con `util` poblándose, en unas semanas de uso normal:

| bloqueo actual | se resuelve con |
|---|---|
| 0 negativos reales para calibrar | filas con `util = 0` |
| No se puede verificar intercambiabilidad | distribución real vs sintética |
| El "6% FP" es sobre un simulacro | recalibrar con negativos reales |
| No se sabe el ratio real de la carga | conteo directo `util=1` vs `util=0` |

Y todo con la maquinaria que **ya está construida y verificada**. No hace falta
matemática nueva: hace falta que los datos lleguen.

## 6. Estimación de tiempo hasta tener datos suficientes

Con 2.157 búsquedas registradas históricamente, si el ritmo se mantiene y una
fracción razonable recibe feedback, llegar a 200-300 consultas etiquetadas es
cuestión de semanas de uso normal, no de meses.

Vale la pena instrumentar un contador: cuando `COUNT(*) WHERE util IS NOT NULL`
supere 200, recalibrar automáticamente y comparar el umbral nuevo con el actual. Esa
comparación es la validación empírica que hoy falta.

---

## 7. Resumen

**No es que nadie dé feedback. Es que el feedback no llega a `log_busquedas`.**

La tool existe, el refuerzo funciona, la telemetría nueva (`eventos_refuerzo`) ya
registra los deltas. Lo único que falta es una línea que propague ese mismo evento
al registro de búsquedas — y el `last_log_id` que hace falta ya está ahí.

Es el fix más barato de toda esta sesión y el que desbloquea la validación real de
la calibración.
