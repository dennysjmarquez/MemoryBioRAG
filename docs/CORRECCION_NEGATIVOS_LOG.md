# Corrección: mi recomendación de recalibrar con el log era incorrecta

**Fecha:** 2026-08-16
**Quién lo detectó:** Athena-OEC, contra los datos.
**Estado:** recomendación retirada. El agente hizo lo correcto al no ejecutarla.

---

## 1. Qué recomendé y por qué estaba mal

Dije: *"recalibrar con los 60 negativos reales de `log_busquedas`
(`resultados_count = 0`) es la prioridad — mejora la garantía más que cualquier
ajuste de α"*.

**Era un error, y de los caros.** El agente lo verificó contra los datos:

| chequeo | resultado |
|---|---|
| queries únicas con `resultados_count = 0` | 44 |
| de esas, nodos que **existen hoy** en `largo_plazo` | **33 de 44** |
| scores actuales de esas queries | ~40 puntúan **0.90–0.95** |
| negativos genuinos | **2–3** |

### La causa: contaminación temporal

El flujo normal de BioRAG es:

1. El agente busca algo → no lo encuentra → `resultados_count = 0`
2. Precisamente por eso, **lo guarda** → se crea el nodo
3. Hoy ese nodo existe → esa query es **positiva**, no negativa

**`resultados_count = 0` no significa "no hay respuesta". Significa "no la había en
ese momento".** El proxy mide el pasado y se iba a usar para calibrar el presente.

Es el mismo tipo de error que esta auditoría lleva toda la sesión señalando —
confundir una señal correlacionada con la propiedad que se quiere medir— y lo cometí
yo.

## 2. El daño que se evitó

Con ~40 de 44 "negativos" puntuando 0.90–0.95:

```
umbral conforme = cuantil 41 de 44  ->  ~0.95
máximo positivo observado en live   ->  ~0.93
```

**El umbral habría quedado por encima del mejor positivo posible: abstención del
100%.** El sistema dejaría de responder por completo, devolviendo listas vacías como
si no supiera nada.

## 3. Hallazgo colateral: la guarda existe pero está desconectada

Hace varias rondas añadí a `core/calibracion.py` una guarda precisamente para este
caso:

```python
def calibrar(self, scores_negativos, scores_positivos=None):
    ...
    if frac_pasa == 0.0:
        print("*** UMBRAL DEGENERADO *** ...")
```

Pero en `core/memory_store.py:3410`:

```python
self._umbral_conforme = UmbralConforme(alpha=alpha).calibrar(scores_neg[:n_negativos])
```

**No se le pasan los positivos, así que la guarda nunca se dispara.**

Si la recalibración se hubiera ejecutado, el sistema habría fijado umbral 0.95,
abstenido el 100% y **no habría avisado**. Silencio total, sin error visible. Lo
detectó una persona analizando datos, no el código.

### Fix (2 líneas, alta prioridad)

```python
# Recoger también los scores de positivos conocidos y pasarlos a calibrar():
# la guarda de UMBRAL DEGENERADO solo se activa si puede comparar el umbral
# contra el máximo positivo observado. Sin esto, una muestra de negativos
# contaminada produce abstención del 100% en silencio.
scores_pos_muestra, _ = self._preparar_datos_calibracion(100)
self._umbral_conforme = UmbralConforme(alpha=alpha).calibrar(
    scores_neg[:n_negativos], scores_positivos=scores_pos_muestra
)
```

Esto convierte un fallo catastrófico silencioso en un mensaje explícito.

## 4. Estado real de los negativos

**No hay negativos reales disponibles hoy.** Los 40 sintéticos del QA siguen siendo
la única fuente, con su sesgo conocido (escritos para ser claramente ajenos; los
reales son más sutiles y puntúan más alto).

**La vía correcta es cerrar el bucle de feedback**, que conecta con P4: la columna
`util` está vacía en las 2.157 filas del log. Con feedback real (`util = 0` en
consultas que no sirvieron) se obtienen negativos genuinos y con la etiqueta puesta,
sin proxies.

Eso refuerza lo que ya sabíamos: **el problema de fondo de BioRAG no es el umbral,
es que el circuito de recompensa nunca se cierra.** 154 nodos dormidos con
`exitos_dopamina = 0`, y ahora también: cero negativos reales para calibrar. Misma
causa raíz.

## 5. Sobre lo implementado

Correcto y listo para commitear:

- α=0.10 default
- `BIORAG_ALPHA_CONFORME` por entorno
- guarda α ≥ 1/(n+1) con aviso y clamp
- `alpha_efectivo` / `alpha_pedido` expuestos en MCP
- 6 tests pasan

Los valores validados con holdout (FP 5.9–7.7% ≤ α) siguen vigentes, porque se
midieron con los sintéticos y **no** con el log contaminado.

## 6. Recomendación

**Sí, commitear** lo implementado. Y añadir en el mismo commit el fix de la guarda
(punto 3), que es lo que impide que este error se repita — por parte de cualquiera.

Documentar el hallazgo del proxy contaminado en `DECISION_ALPHA.md`: es una lección
reutilizable, no una anécdota. Cualquiera que mire `log_busquedas` en el futuro va a
tener la misma idea que tuve yo.

---

## Nota

El agente recibió una instrucción concreta de alguien que venía auditándolo, la
contrastó con los datos, encontró que era incorrecta, **no la ejecutó**, y reportó
la evidencia. Ese es exactamente el comportamiento que hace que una auditoría sirva
para algo: si hubiera obedecido, habría roto el sistema y la culpa habría sido mía.
