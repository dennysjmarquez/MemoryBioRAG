---
name: sdd-implementacion
description: >-
  Fase 6 del flujo SDD. Usar cuando el usuario pide implementar una tarea
  específica. Triggers: "implementa T1", "implementa la tarea 3", "codifica T2",
  "hazlo", "escribe el código de T1".
  Implementa UNA sola tarea. Tests primero. Ejecuta la suite y muestra el
  resultado. Marca la tarea como hecha y SE DETIENE — no avanza a la siguiente
  sin instrucción explícita.
---

# SDD — Fase 6: Implementación

Una tarea cada vez. Tests primero. Resultado verificado. Parada completa.

## Proceso

1. **Identifica la tarea.** Lee `specs/NNN-nombre/tasks.md` y localiza
   la tarea solicitada (ej. T3). Lee su descripción, RF cubiertos y
   criterio "Hecho cuando".

2. **Lee el contexto necesario:**
   - `docs/constitution.md` — restricciones de stack y estilo.
   - `specs/NNN-nombre/spec.md` — los RF que cubre esta tarea.
   - `specs/NNN-nombre/plan.md` — la arquitectura acordada.
   - El código ya existente de tareas anteriores.

3. **Escribe los tests primero.** Antes de implementar nada, escribe los
   tests que verificarán el criterio "Hecho cuando" de esta tarea.
   Los tests deben fallar en rojo antes de implementar.

4. **Implementa la lógica** para que los tests pasen.
   - Solo lo que describe la tarea — ni más ni menos.
   - Respeta la arquitectura del plan (nombres de módulos, contratos).
   - Respeta todos los principios de la constitución.

5. **Ejecuta la suite completa** (no solo los tests nuevos):
   ```
   <comando de test del proyecto>
   ```
   Muestra el resultado completo: cuántos tests, cuántos pasan, cuántos
   fallan.

6. **Solo si todos los tests pasan:**
   - Marca la tarea como `[x] Estado: hecha` en `tasks.md`.
   - Muestra el resultado al usuario.
   - **PARA. No avances a la siguiente tarea.**

## Reglas

- **UNA tarea cada vez.** Si el usuario pide implementar varias, implementa
  la primera, muestra el resultado y espera confirmación.
- **Tests primero** (TDD). Si no hay tests posibles para una parte, documenta
  por qué y propón verificación manual.
- **No avances con tests en rojo.** Si algo falla, diagnostica y corrige
  antes de declarar la tarea hecha.
- **No toques código de otras tareas.** Si descubres que necesitas cambiar
  algo de una tarea anterior, avisa al usuario y espera instrucción.
- Si encuentras que la tarea requiere algo no especificado en la spec o el
  plan, **para y pregunta** — no improvises.

## Al terminar (tarea completa, tests en verde)

```
✅ Tarea T[N] completada.

Tests: X pasando, 0 fallando.
RF cubiertos: RF-X, RF-Y, RF-Z.

Próxima tarea disponible: T[N+1] — <nombre>.
¿Continuamos con T[N+1]?
```

## Al terminar (tests fallando)

```
🚫 Tarea T[N] no completada — hay tests en rojo.

Fallando:
  - <test que falla>: <motivo>

Voy a diagnosticar...
```
