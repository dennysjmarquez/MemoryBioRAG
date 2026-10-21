---
name: sdd-clarificacion
description: >-
  Fase 3 del flujo SDD. Usar cuando el usuario pide revisar una spec como QA,
  detectar problemas antes de planificar, o cuando dice "clarificación",
  "revisa la spec", "busca problemas", "qué falta en la spec", "audita la spec".
  Lee la spec activa y detecta ambigüedades, contradicciones, casos límite
  ausentes y conflictos con la constitución. Solo detecta — no resuelve.
---

# SDD — Fase 3: Clarificación (Revisión QA de la Spec)

Revisión profesional de la spec antes de planificar. El objetivo es
**detectar problemas ahora**, cuando cambiarlos no cuesta nada, en lugar de
descubrirlos durante la implementación.

## Proceso

1. **Lee la constitución.** `docs/constitution.md` — los conflictos con
   ella son bloqueantes.

2. **Lee la spec activa.** Identifica cuál es la spec a revisar (la más
   reciente de `specs/`, o la que indique el usuario).

3. **Revisa en cuatro bloques** (en este orden):

### Bloque 1 — Ambigüedades
Requisitos que dos personas razonables podrían interpretar de forma distinta.
Por cada uno: cita el RF y describe la ambigüedad.
```
RF-X: "<texto exacto del requisito>"
  → Ambigüedad: <qué parte es ambigua y por qué>
```

### Bloque 2 — Contradicciones
Dos o más requisitos que no pueden cumplirse simultáneamente.
```
RF-X y RF-Y se contradicen:
  → RF-X dice: ...
  → RF-Y dice: ...
  → Conflicto: <por qué son incompatibles>
```

### Bloque 3 — Casos límite no cubiertos
Situaciones plausibles que la spec no menciona y que cambiarían el
comportamiento del sistema. Incluye:
- Entradas vacías o malformadas no mencionadas
- Concurrencia o condiciones de carrera
- Límites de volumen o tamaño
- Estados intermedios no especificados
```
Caso límite no cubierto: <descripción>
  → ¿Qué haría el sistema según la spec actual? Silencio (comportamiento indefinido)
  → Pregunta para el autor: <pregunta concreta>
```

### Bloque 4 — Conflictos con la constitución
Requisitos que violarían uno o más principios de `docs/constitution.md`.
```
RF-X conflicta con el principio N de la constitución:
  → RF-X dice: ...
  → Principio N dice: ...
  → Conflicto: <explicación>
```

4. **Cierra con un veredicto:**
   - ✅ **Lista para planificar**: ningún bloqueo crítico encontrado.
   - ⚠️ **Necesita ajustes menores**: lista los RFs que requieren aclaración
     pero no bloquean el plan.
   - 🚫 **Requiere revisión**: hay contradicciones o conflictos con la
     constitución que deben resolverse antes de planificar.

## Reglas

- **Solo detecta, no resuelves.** Enumera los problemas. Las soluciones las
  decide el usuario.
- No reescribas la spec durante esta fase.
- Si no encuentras problemas en un bloque, escribe "Ninguno encontrado."
  No lo omitas — el silencio parece descuido.
- Prioriza los bloqueos críticos (Bloque 2 y 4) sobre las mejoras opcionales.

## Al terminar

Si el veredicto es ✅ o ⚠️:
> "Clarificación completada. Cuando hayas resuelto los puntos marcados,
> continuamos con la **Fase 4: Plan técnico** — usa el skill `sdd-plan`."

Si el veredicto es 🚫:
> "Hay conflictos que deben resolverse en la spec antes de planificar.
> Cuando los corrijas, ejecuta la clarificación de nuevo."
