---
name: sdd-cambio
description: >-
  Fase 8 del flujo SDD. Usar cuando llega un nuevo requisito o cambio después
  de que la spec está aprobada o el código está implementado. Triggers:
  "nuevo requisito", "cambio", "quiero agregar", "modifica la spec",
  "nuevo feature", "cambia el comportamiento de".
  INVARIANTE: Primero actualiza la spec, luego el plan si aplica, luego el
  código. Nunca al revés. Muestra el diff de la spec antes de tocar código.
---

# SDD — Fase 8: Gestión de Cambios

**La spec manda siempre.** Cuando llega un cambio, el flujo es:
```
Spec primero → Plan si aplica → Tareas nuevas → Código → Validación
```
Nunca al revés.

## Proceso

1. **Recibe el cambio.** Comprende exactamente qué quiere el usuario.
   Si hay ambigüedad, haz **una sola pregunta** para aclarar.

2. **Evalúa el impacto en la spec:**
   - ¿Agrega nuevos RF?
   - ¿Modifica RF existentes?
   - ¿Elimina RF existentes?
   - ¿Entra en conflicto con la constitución?

3. **Actualiza la spec primero.** Edita `specs/NNN-nombre/spec.md`:
   - Agrega los RF nuevos con el siguiente número disponible (RF-N).
   - Modifica los RF afectados.
   - Actualiza "Fuera de alcance" si algo que antes estaba fuera ahora entra.
   - Actualiza "Casos límite" si el cambio genera nuevos.
   - Actualiza "Dudas abiertas" si hay incertidumbre.

4. **Muestra el diff de la spec.** Antes de tocar código:
   ```diff
   - RF-3: SI el archivo no existe, EL SISTEMA devolverá error.
   + RF-3: SI el archivo no existe, EL SISTEMA lo creará vacío y continuará.
   + RF-12: CUANDO el archivo se crea vacío, EL SISTEMA registrará el evento en el log.
   ```
   Y di: *"Este es el cambio en la spec. ¿Lo apruebas?"*

5. **Espera aprobación explícita.**

6. **Evalúa si el plan necesita actualización:**
   - ¿El cambio requiere nuevos módulos o modifica la arquitectura?
   - ¿Cambia el modelo de datos?
   - Si sí: actualiza `specs/NNN-nombre/plan.md` también.

7. **Genera las tareas del cambio.** Agrega al final de `tasks.md` las
   tareas nuevas necesarias para implementar el cambio, con el siguiente
   número disponible (T-N).

8. **Implementa** con el skill `sdd-implementacion`, tarea por tarea.

9. **Valida** que los RF anteriores siguen pasando (no regresión) y que
   los nuevos RF también tienen cobertura.

## Reglas

- **Spec primero, siempre.** Si el usuario dice "agrega X al código",
  la respuesta es: "Primero actualicemos la spec, luego el código."
- **Diff visible antes de implementar.** El usuario debe ver qué cambia
  en la spec antes de que se toque una línea de código.
- **No regresión.** Después del cambio, todos los RF anteriores deben
  seguir pasando. Si alguno falla, es un bug del cambio, no una decisión.
- **Fuera de alcance actualizado.** Si el cambio incorpora algo que antes
  estaba fuera de alcance, actualiza esa sección — explícitamente.
- Si el cambio contradice la constitución, **para y avisa** antes de
  continuar. La constitución solo se cambia con aprobación explícita.

## Al terminar

```
✅ Cambio implementado.

Spec actualizada: specs/NNN-nombre/spec.md
  + RF-N (nuevo), RF-X (modificado)
Plan actualizado: sí / no
Tareas nuevas: T-N, T-N+1
Tests: X pasando (incluyendo regresión), 0 fallando
```
