---
name: sdd-validacion
description: >-
  Fase 7 del flujo SDD. Usar cuando todas las tareas están implementadas y
  el usuario quiere verificar que el código cumple la spec. Triggers:
  "validación", "valida la spec", "revisa que todo funciona", "RF por RF",
  "¿se cumple la spec?", "verifica el cumplimiento".
  Recorre la spec RF por RF, verifica qué test cubre cada uno y emite un
  veredicto final.
---

# SDD — Fase 7: Validación

Comprobación sistemática de que el código cumple **todos** los requisitos
de la spec. Se recorre RF por RF, no tarea por tarea.

## Proceso

1. **Lee la spec** (`specs/NNN-nombre/spec.md`) y lista todos los RF.

2. **Ejecuta la suite completa de tests:**
   ```
   <comando de test del proyecto>
   ```
   Muestra el resultado completo.

3. **Para cada RF**, responde:

```markdown
| RF | Descripción resumida | Test que lo cubre | Estado |
|----|---------------------|------------------|--------|
| RF-1 | ... | test_nombre_del_test | ✅ pasa |
| RF-2 | ... | test_otro_test | ✅ pasa |
| RF-3 | ... | (ninguno) | 🚫 sin test |
```

4. **Veredicto final:**

### ✅ Spec cumplida
Todos los RF tienen al menos un test en verde y la demo manual funciona.

```
VEREDICTO: ✅ SPEC CUMPLIDA

RF cubiertos: N/N
Tests: X pasando, 0 fallando
Demo manual: OK

El proyecto está listo para entrega / siguiente iteración.
```

### ⚠️ Cumplimiento parcial
Algunos RF sin cobertura de test o fallando.

```
VEREDICTO: ⚠️ CUMPLIMIENTO PARCIAL

RF sin cobertura:
  - RF-X: <descripción>
RF con tests fallando:
  - RF-Y: <test que falla>

Acción recomendada: <qué hacer>
```

### 🚫 Spec no cumplida
Hay RF críticos sin implementar.

```
VEREDICTO: 🚫 SPEC NO CUMPLIDA

RF no implementados: RF-X, RF-Z
Bloqueadores: <descripción>

Acción recomendada: volver a la implementación con sdd-implementacion.
```

## Reglas

- **Un RF = una fila.** No agrupes ni saltes requisitos.
- Si un RF no tiene test, es `🚫 sin test` — aunque funcione manualmente.
  El comportamiento sin test no es verificable de forma reproducible.
- Los requisitos no funcionales (rendimiento, plataforma) se verifican
  manualmente si no hay test automático — documenta cómo se verificaron.
- No declares "spec cumplida" si hay un solo RF sin cobertura verde.

## Al terminar (spec cumplida)

> "Validación completada. Si vienen cambios al proyecto, usa el skill
> `sdd-cambio` — **nunca toques el código antes de actualizar la spec**."
