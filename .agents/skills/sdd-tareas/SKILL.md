---
name: sdd-tareas
description: >-
  Fase 5 del flujo SDD. Usar cuando el plan está aprobado y hay que dividirlo
  en tareas implementables. Triggers: "tareas", "divide el plan", "crea las
  tareas", "dame los tickets", "desglosa en pasos", "tasks".
  Divide el plan en tareas de menos de 30 minutos, ordenadas por dependencia,
  con checkboxes y una línea "Hecho cuando:" verificable para cada una.
---

# SDD — Fase 5: Tareas

Convierte el plan en pasos implementables, ordenados y verificables.
Cada tarea debe poder hacerse en **menos de 30 minutos** y terminar con
sus tests en verde antes de pasar a la siguiente.

## Proceso

1. **Lee el plan** (`specs/NNN-nombre/plan.md`) y la spec
   (`specs/NNN-nombre/spec.md`).

2. **Divide en tareas** siguiendo estas reglas:
   - Ordena por **dependencias**: las tareas fundacionales (tipos, modelos,
     utilidades compartidas) van primero.
   - Cada tarea cubre **uno o más RF relacionados** — nunca mezcla áreas
     no relacionadas.
   - Tamaño objetivo: lo que se puede implementar y testear en ≤30 minutos.
     Si una tarea es más grande, divídela.

3. **Genera `specs/NNN-nombre/tasks.md`** con este formato:

```markdown
# Tareas — Spec NNN

## T1: <Nombre corto y descriptivo>
- **RF cubiertos**: RF-X, RF-Y
- **Descripción**: <qué implementar, en 2-3 líneas máximo>
- **Hecho cuando**: <criterio verificable y concreto>
  - [ ] <check específico 1>
  - [ ] <check específico 2>
- [ ] **Estado**: pendiente

---

## T2: <Nombre>
...
```

4. **Al final del archivo**, agrega un índice de cobertura:

```markdown
## Cobertura de requisitos
| RF | Cubierto por |
|----|-------------|
| RF-1 | T1 |
| RF-2 | T1, T3 |
| RF-3 | T2 |
```

Si algún RF no tiene tarea asignada, márcalo como `⚠️ SIN TAREA` y
avisa al usuario.

5. **Pide aprobación** antes de implementar.

## Reglas

- **"Hecho cuando"** es obligatorio y debe ser **verificable sin ambigüedad**.
  Ejemplos correctos:
  - ✅ "pytest -q muestra 5 tests en verde, 0 fallidos"
  - ✅ "La función devuelve [] cuando la entrada está vacía"
  - ❌ "La tarea funciona bien"
  - ❌ "El código está limpio"
- Tests primero: el "Hecho cuando" debe incluir siempre al menos un test
  automático.
- No saltes tareas ni las marques como hechas si sus tests no pasan.
- El orden importa: si T3 depende de T2, T3 va después de T2.

## Al terminar

> "Tareas guardadas en `specs/NNN-nombre/tasks.md`. Todos los RF tienen
> cobertura. Para implementar, usa el skill `sdd-implementacion` indicando
> el número de tarea: 'Implementa T1'."
