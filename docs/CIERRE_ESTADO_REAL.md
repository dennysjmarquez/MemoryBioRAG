# Cierre: qué quedó demostrado, qué no, y qué hacer el lunes

**Fecha:** 2026-08-15
**Sobre:** el resumen final de Athena-OEC.
**Veredicto:** el trabajo de investigación fue bueno y llegó a un diagnóstico
correcto. El resumen, en cambio, contiene una contradicción interna y arrastra tres
afirmaciones ya refutadas en esta misma sesión. **No proceder con el plan tal como
está escrito.**

---

## 1. La contradicción interna

El resumen afirma dos cosas incompatibles:

| Sección | Afirmación |
|---|---|
| H-Corpus | *"Umbral óptimo (881:32) = **0.25 (actual)** — Net=849"* |
| Próximos pasos | *"Paso 1 **AHORA**: Calibración → FP 80% → **<10%**"* |

Para llevar el FP del 80% a menos del 10% hay que **subir** el umbral muy por
encima de 0.25. Y eso reduce el net:

| umbral | FP | Recall | net (881:32) |
|---|---|---|---|
| **0.25** | 100% | 100% | **849** ← el propio resumen lo llama óptimo |
| 0.70 | 34% | 88% | 764 |
| 0.78 | 0% | 78% | 687 |

**Si 0.25 es el óptimo, entonces "bajar el FP a <10%" no es una mejora**: cuesta
~162 aciertos para evitar ~29 falsos positivos.

El resumen adoptó mi cálculo del óptimo y a la vez conservó el plan que ese cálculo
contradice. Una de las dos cosas tiene que caer, y hay que decidir cuál **antes** de
tocar nada.

Mi lectura: el óptimo "0.25" sale de aplicar `TP − FP` con el ratio 881:32 del
benchmark. Pero ese ratio es un artefacto del diseño del benchmark, no la carga
real. **La decisión correcta no es ni 0.25 ni 0.78: es medir el ratio real primero.**
Mientras tanto, cualquier umbral elegido es una preferencia disfrazada de resultado.

## 2. Afirmaciones refutadas que reaparecen

**a) *"Live DB FP alto por daemon activo"*** (nota al pie de la tabla de métricas)

Refutado dos veces en esta sesión: por su propia Prueba A (daemon OFF → sigue 80%)
y por la matriz (baseline@live = 80% sin los fixes). La misma línea se contradice
sola: dice "daemon activo" y tres palabras después "baseline live = 80%
(preexistente)". No pueden ser ambas la causa.

**b) *"Fix 1.2 = driver principal: +0.11pp R@5, −7.5pp FP"***

- +0.11pp = 847 → 848 casos = **+1 caso**. McNemar p = **1.00**
- −7.5pp = 10 → 7 de 40 = **−3 casos**. McNemar p = **0.25**

Señalado tres veces en esta sesión; sigue en la tabla. Redacción correcta:

> Los 5 fixes son correctos y neutros en calidad medible. Su valor es de
> correctitud (1.1, 1.4), latencia (1.5) y coherencia de escala (1.2, 1.3).

**c) *"UmbralConforme: ⚠️ Roto"***

El diagnóstico de la causa es correcto (escala de score vs probabilidad), pero el
módulo no está roto: estaba **mal usado**. Y ya tiene la guarda que detecta
exactamente ese caso y emite `*** UMBRAL DEGENERADO ***`. Etiquetarlo como roto en
el estado del proyecto va a confundir a quien lo lea en tres meses.

## 3. Lo que no se hizo y quedó pendiente

El resumen **no menciona** haber rehecho el barrido con el script corregido (sin
`limite_casos`, con held-out). Por tanto:

- **la fila imposible sigue sin explicar**: en la tabla anterior, al pasar de 0.78
  a 0.80 subían *a la vez* el FP (0% → 9.4%) y el recall (78% → 82%). Eso viola la
  monotonía: subir el umbral solo puede bajar ambos. Es un error de medición sin
  diagnosticar, y contamina cualquier "óptimo" derivado de esa curva.
- el `net` de la tabla vieja se calculó sobre ~51 positivos en vez de 881.

**Rehacer el barrido y verificar que la curva sale monótona es el prerrequisito de
todo lo demás.** Si no sale monótona, el problema está en la medición, no en el
umbral.

## 4. Riesgo que introduce el estado actual del código

El resumen lista: *"core/memory_store.py — Bugs 1.2, 1.3, **calibración**, logging"*.

Es decir, hay **código de calibración dentro del motor de producción**, y en la
misma página se declara que el `UmbralConforme` está roto. Aunque esté inactivo,
eso es deuda peligrosa: un flag mal puesto y el sistema se abstiene del 100% de las
consultas en silencio.

Recomendación concreta: que la calibración viva **fuera** de `memory_store.py`
hasta que haya un umbral validado — igual que se hizo bien con `eventos_refuerzo`
(tabla propia, sin tocar el historial forense). Ese parche fue el patrón correcto;
conviene repetirlo aquí.

## 5. Lo que sí quedó sólidamente demostrado

Esto es real y hay que conservarlo:

| Hallazgo | Evidencia |
|---|---|
| El 80% de FP en live es **preexistente** | matriz 2×2 completa, baseline@live medido |
| El daemon **no** es la causa | Prueba A: daemon OFF → 80% |
| Los 5 fixes **no** lo causaron | baseline sin fixes ya daba 80% |
| **AUC = 0.914**: hay separación de sobra | H-corpus |
| El problema es **el corte**, no las señales | escenario A confirmado |
| **RRF no resuelve el FP** | invariante a magnitud; y R@5 en live es 96.37% |
| El umbral 0.25 no escala con el corpus | negativos en [0.3, 0.5] |

Ese conjunto es un buen trabajo de investigación. Cinco hipótesis levantadas y
descartadas con evidencia, en una sesión. Merece entrar en `EXPERIMENTS.md`, que es
justo el registro que el proyecto mantiene para esto.

## 6. Plan recomendado (reemplaza al del resumen)

| # | Acción | Coste | Bloquea a |
|---|---|---|---|
| 1 | Rehacer barrido con script corregido; **verificar monotonía** | 1 corrida | todo |
| 2 | Medir ratio real positivos:negativos en `log_busquedas` | 1 consulta | la elección de umbral |
| 3 | Ampliar negativos a 200-300 | 1 tarde | la calibración |
| 4 | Elegir umbral con el coste relativo **explícito y escrito** | — | aplicar |
| 5 | Aplicar, con benchmark antes/después | 2 corridas | — |
| 6 | Sacar la calibración de `memory_store.py` mientras tanto | 1 h | reduce riesgo ya |
| — | RRF | **aplazado** | no ataca el FP; hacerlo cuando el objetivo sea ranking |

Los pasos 1 y 2 son una corrida y una consulta SQL. Ninguno modifica producción.

## 7. Nota sobre mis propios errores en esta línea

Para que quede en el registro: de los problemas encontrados en las dos últimas
rondas, **dos los causé yo**, y ambos por el mismo patrón — un default cómodo que
se vuelve sesgo silencioso:

- `FP = 6.2%` tautológico: mi script calibraba y medía sobre los mismos negativos.
  Corregido con partición calibración/validación.
- `net = 40` sesgado: `limite_casos = 120` truncaba los positivos pero no los
  negativos, distorsionando el ratio de 22:1 a 1.6:1. Corregido a sin límite, con
  aviso si se usa.

Es exactamente lo que la regla 21 del manual describe: un resultado que parece
válido y no lo es. Vale la pena que ambos casos queden documentados como ejemplo.
