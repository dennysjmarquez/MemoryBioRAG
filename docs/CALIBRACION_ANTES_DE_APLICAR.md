# Antes de aplicar el umbral 0.804: dos números del reporte no significan lo que parecen

**Fecha:** 2026-08-15
**Estado:** H-corpus confirmó escenario A — eso es sólido y bien hecho.
**Pero:** el `FP=6.2%` es tautológico y el `Recall=82%` esconde una pérdida de ~127 casos.
**Recomendación:** no aplicar el umbral 0.804 todavía.

---

## 1. Lo que sí quedó establecido, y es importante

`AUC = 0.914` es un resultado real y valioso. Significa que **las distribuciones de
positivos y negativos están bien separadas**: hay señal de sobra en el score
híbrido. El problema no es la fusión ni las señales — es dónde está puesto el corte.

Eso confirma escenario A y **descarta RRF como solución al FP**. La conclusión del
reporte en ese punto es correcta y bien razonada.

## 2. El `FP = 6.2%` es tautológico (y la culpa es de mi script)

Mi `test_h_corpus_umbral.py` calculaba el umbral y medía el FP **sobre los mismos
32 negativos**. Reconstruido:

```
k = ceil((32+1) * 0.90) = 30
umbral = s_ord[29]           # el 30º de 32
quedan por encima: 32 - 30 = 2
FP = 2/32 = 6.25%
```

**Ese 6.2% es la definición del cuantil 90, no una medición.** Habría salido
prácticamente igual con datos aleatorios. No dice nada sobre si el umbral
funcionará con negativos nuevos.

Es un defecto de diseño de mi script y ya está corregido: ahora parte los negativos
en mitad calibración / mitad validación, y reporta el FP sobre la mitad held-out
que el umbral nunca vio. Verificado: con datos simulados el FP held-out sale 12.5%
en vez del 10% teórico — es decir, ya informa algo.

**Consecuencia práctica:** con 32-40 negativos, partir a la mitad deja ~16-20 para
calibrar, que es muy poco. Es otra razón para ampliar el corpus de negativos antes
de tomar decisiones.

## 3. El `Recall = 82%` es el número que debería frenar la decisión

El reporte lo presenta como dato neutro junto al FP. No lo es.

| | Valor |
|---|---|
| R@5 actual en live (sin abstención) | **96.37%** |
| Positivos que superan el umbral 0.804 | **82.00%** |
| **Pérdida** | **14.37 pp** |

Sobre los 881 casos de retrieval del benchmark:

- hoy responde bien: **849 casos**
- con umbral 0.804: **~722 casos**
- **se perderían ~127 casos que hoy responde correctamente**

A cambio de evitar ~30 falsos positivos de 40 negativos.

> **Ratio 4:1 en contra.** Se sacrifican ~127 respuestas correctas para evitar ~30
> incorrectas.

Y si se cuenta el balance con los tamaños del propio benchmark (881 positivos, 40
negativos, asumiendo que un FP y un FN cuestan lo mismo):

```
aciertos_totales = 881·recall + 40·(1 − FP)

sin abstención (hoy)      : 881·0.9637 + 40·0.00  = 849
con umbral 0.804          : 881·0.8200 + 40·0.94  = 760
```

**Con el ratio del benchmark, abstenerse sale peor que no hacerlo.** El umbral 0.804
destruye más valor del que protege.

## 4. La pregunta que falta: ¿cuál es el ratio real de producción?

El cálculo de arriba usa 881:40 porque es lo que tiene el benchmark. **Pero ese
ratio es un artefacto del diseño del benchmark, no una medida de la carga real.**

Si en producción la mayoría de las consultas del agente sí tienen respuesta en la
memoria, abstenerse agresivamente es un error caro. Si buena parte son consultas
exploratorias sin respuesta, el cálculo se invierte y el umbral alto se justifica.

**Nadie ha medido ese ratio.** Y es medible: la tabla `log_busquedas` que el propio
agente mencionó tiene el histórico de consultas reales.

Sin ese dato, elegir α es adivinar. Y α=0.10 fue **una sugerencia por defecto mía**,
no una decisión informada por el coste real de cada tipo de error.

## 5. Qué hacer en su lugar

### a) Reportar la curva completa, no un punto

En vez de fijar α y aceptar lo que salga, barrer el umbral y ver el frente de
trade-off:

| umbral | FP | recall | aciertos netos (881:40) |
|---|---|---|---|
| 0.25 (hoy) | 100% | 96.4% | 849 |
| ... | ... | ... | ... |
| 0.804 | 6.2%* | 82.0% | 760 |

Con AUC=0.914 hay mucho espacio entre esos extremos. Es muy probable que exista un
umbral intermedio que baje el FP sustancialmente perdiendo poco recall — pero hay
que **verlo**, no asumirlo.

*(el 6.2% hay que recalcularlo held-out)*

### b) Medir el ratio real en `log_busquedas`

Cuántas consultas de producción tienen respuesta útil vs cuántas no. Eso convierte
la elección de α de arbitraria en fundamentada.

### c) Ampliar los negativos a 200-300

Con 40, partir en calibración/validación deja ~20 por lado. Con α=0.10 sobre 20
muestras, el umbral lo determinan 2 valores extremos. Generar negativos es barato:
son consultas que no deben devolver nada.

### d) Considerar abstención parcial en vez de binaria

Con AUC=0.914 el sistema tiene información de sobra para graduar: responder con
confianza alta, responder marcando incertidumbre, o abstenerse. Un único corte
binario desperdicia esa señal — y encaja peor con el "filtro de honestidad
epistémica" que el proyecto ya declara tener.

## 6. Sobre Test B

Sigue pendiente y sigue siendo barato. Pero con la matriz ya cerrada, sólo aclara
si la mejora snapshot 25%→17.5% (3 casos, p=0.25) fue real o artefacto de escala.
No cambia ninguna decisión técnica. Correrlo para cerrar el changelog, sin que
bloquee nada.

---

## Resumen para el agente

| Afirmación del reporte | Estado |
|---|---|
| AUC=0.914, separación excelente | ✅ correcto y valioso |
| Escenario A confirmado, no es la fusión | ✅ correcto |
| RRF no resuelve el FP | ✅ correcto |
| Umbral fijo 0.25 no escala con el corpus | ✅ correcto |
| "FP → 6.2%" | ⚠️ tautológico: calibrado y medido en los mismos datos |
| "Recall=82%" como dato neutro | ❌ es una pérdida de ~127 casos que hoy acierta |
| "Resuelve FP 80% → 6.2%" como decisión lista | ❌ prematuro: el balance neto sale negativo |

El diagnóstico es bueno. La solución va en la dirección correcta. Lo que falta es
elegir el punto de operación con el coste real delante, en vez de aceptar el primer
α que se probó.
