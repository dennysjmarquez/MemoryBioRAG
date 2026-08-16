# Decisión de α — el cálculo con el ratio real

**Fecha:** 2026-08-16
**Contexto:** medido el ratio de producción (563 queries únicas, 10.7% sin respuesta).
**Recomendación: opción 1 (α=0.10) + la 4 con guarda.**

---

## 1. Corrección a mi propia auditoría anterior

En la auditoría dije que el balance neto "empeora" con la calibración. **Ese cálculo
usaba el ratio del benchmark (22:1), que ahora sabemos que no es el de producción.**
Con el ratio real medido (8.3:1) la conclusión se invierte. Lo corrijo aquí.

## 2. El punto de equilibrio exacto

Con 563 queries reales → ~503 positivas, ~60 negativas:

| escenario | respuestas correctas perdidas (FN) | respuestas inventadas (FP) |
|---|---|---|
| A) sin abstención (hoy) | 18.3 | **60.0** |
| B) α=0.10 (umbral ~0.60) | 78.6 | **4.8** |

B es mejor que A cuando:

```
C_fp / C_fn  >  (78.6 − 18.3) / (60.0 − 4.8)  =  1.09
```

> **Basta con que una alucinación sea un 9% peor que un silencio para que α=0.10
> sea la opción correcta.**

En una memoria de agente, un FP no es un error cualquiera: es **contaminar la
memoria con algo que no existe**, y el agente lo va a usar como si fuera cierto en
decisiones posteriores. Un silencio solo obliga a preguntar de otra forma.

La relación real no es 1.09 — es mucho mayor. **α=0.10 es defendible con margen
amplio.**

## 3. El "37% de abstención" mezcla tres cosas

El desglose del agente:

| | |
|---|---|
| 10.7% | sin respuesta → **abstenerse es correcto**, no es pérdida |
| 26.6% | con resultados pero score < 0.60 |
| **37.3%** | total |

El 26.6% **no son respuestas buenas perdidas**. `resultados_count > 0` solo dice que
devolvió *algo*, no que fuera correcto — y el log no tiene ground truth (la columna
`util` está vacía, coherente con P4: el bucle de feedback casi nunca se cierra).

La pérdida real medida con ground truth (el eval) es **12% de las positivas** ≈ 60
consultas ≈ **10.7% del total**, no 26.6%.

Y con los **3 niveles**, lo que cae bajo el umbral no desaparece: se marca
`relacionado_confianza_media`. El usuario lo sigue viendo, con la etiqueta puesta.

**La pérdida efectiva es sustancialmente menor que la que sugiere el 37%.**

## 4. Sobre el razonamiento del agente

Llegó a la recomendación correcta, pero el camino tiene un error que conviene
corregir para que no se propague:

> *"cada FP cuesta relativamente más [porque los negativos son raros]"*

Eso está al revés. Que los negativos sean **raros** no hace que cada FP cueste más:
hace que haya **menos FP en total**, lo que debilita el argumento a favor de
abstenerse. El coste unitario de un FP es una propiedad del daño que causa, no de su
frecuencia.

La forma correcta es la del punto 2: comparar el **total** de cada tipo de error
bajo cada política y despejar la razón de costes que iguala ambas.

## 5. Recomendación

**Opción 1 (α=0.10) como default, combinada con la 4 pero con una guarda.**

La 4 sola es peligrosa. Con n=32 negativos:

| α pedido | cuantil exigido | α real garantizado |
|---|---|---|
| 0.05 | **32 de 32 (el máximo)** | 0.030 |
| 0.10 | 30 de 32 | 0.091 |
| 0.20 | 27 de 32 | 0.182 |
| 0.30 | 24 de 32 | 0.273 |

Con 32 muestras, el α mínimo honesto es `1/(n+1) = 0.030`. Pedir α=0.01 no da esa
garantía: solo pone el umbral en el máximo observado y crea una falsa sensación de
rigor.

**Implementación sugerida:**

```python
# BIORAG_ALPHA_CONFORME permite ajustar por entorno (QA / producción / agente).
# GUARDA: con n negativos, el alpha mínimo alcanzable es 1/(n+1). Pedir menos no
# da esa garantía — solo coloca el umbral en el máximo de la muestra, que es el
# estadístico más inestable. Se avisa en vez de fingir precisión.
alpha_min = 1.0 / (n_negativos + 1)
if alpha < alpha_min:
    logger.warning(
        f"alpha={alpha} pedido, pero con {n_negativos} negativos el mínimo "
        f"alcanzable es {alpha_min:.3f}. Se usa {alpha_min:.3f}. "
        f"Para un alpha menor, amplía el corpus de negativos."
    )
    alpha = alpha_min
```

## 6. Lo que sigue importando más que α

**Los negativos son sintéticos.** Se escribieron a mano para ser claramente ajenos
al corpus. Los negativos reales son sutiles (temas vecinos, matices ausentes) y
puntúan más alto.

Ahora hay **60 negativos reales identificados** en `log_busquedas` (las consultas
con `resultados_count = 0`). Recalibrar con esos, en vez de con los 40 sintéticos,
mejora la garantía más que cualquier ajuste de α — porque corrige el sesgo de la
muestra, que es la hipótesis central del método conforme.

**Prioridad:** recalibrar con negativos reales > afinar α.

## 7. Resumen

| Pregunta | Respuesta |
|---|---|
| ¿α=0.10 es correcto? | **Sí**, con margen. El equilibrio está en C_fp/C_fn > 1.09 |
| ¿El 37% de abstención es alarmante? | **No**. La pérdida real es ~10.7%, y los 3 niveles la reducen más |
| ¿Configurable? | **Sí, con guarda** de α ≥ 1/(n+1) |
| ¿Qué falta de verdad? | **Recalibrar con los 60 negativos reales del log** |
