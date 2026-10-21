---
name: sdd
description: >-
  Marco de trabajo completo de Spec-Driven Development (SDD). Activar cuando
  el usuario menciona "SDD", "spec-driven", "quiero arrancar bien un proyecto",
  "marco de trabajo", "framework de desarrollo", "cómo trabajamos",
  "explícame el flujo SDD", o cuando pide una guía general del proceso.
  Muestra el flujo completo, los skills disponibles y cómo empezar.
---

# SDD — Marco de Trabajo Completo

**Spec-Driven Development**: construir software partiendo de una especificación
acordada, en lugar de improvisar prompts. La spec es el contrato — si algo no
está en la spec, no se implementa.

---

## El Flujo

```
1. Constitución  →  2. Spec  →  3. Clarificación  →  4. Plan
       ↓                                                  ↓
8. Cambio       ←  7. Validación  ←  6. Implementación  ←  5. Tareas
```

---

## Skills disponibles — invócalos por nombre

| Skill | Cuándo usarlo | Qué produce |
|-------|--------------|-------------|
| `sdd-constitucion` | Al iniciar un proyecto nuevo | `docs/constitution.md` |
| `sdd-spec` | Al especificar una funcionalidad | `specs/NNN-nombre/spec.md` |
| `sdd-clarificacion` | Antes de planificar (revisión QA) | Lista de problemas detectados |
| `sdd-plan` | Después de aprobar la spec | `specs/NNN-nombre/plan.md` |
| `sdd-tareas` | Después de aprobar el plan | `specs/NNN-nombre/tasks.md` |
| `sdd-implementacion` | Para implementar una tarea específica | Código + tests en verde |
| `sdd-validacion` | Al terminar todas las tareas | Tabla RF × test + veredicto |
| `sdd-cambio` | Cuando llega un nuevo requisito | Spec actualizada → diff → código |

### Skills de gobernanza técnica avanzada (de claude-plugin-sdd)

| Skill | Para qué |
|-------|----------|
| `adr` | Registrar una decisión de arquitectura (formato MADR) |
| `check` | Detectar si el código ha divergido de la spec (drift) |
| `audit` | Auditoría completa de alineación código ↔ spec |
| `discover` | Inferir la arquitectura de un proyecto sin spec |
| `plan` | Sprint planning: descomponer spec en issues de tracker |
| `work` | Implementar issues en paralelo con git worktrees |
| `review` | Review de PRs con conciencia de spec |

---

## Principios del marco

### 1. La spec manda
Ningún comportamiento se implementa si no está en la spec activa.
Si falta una decisión, se detiene y se pregunta.

### 2. Spec antes que código
Ante cualquier cambio: **spec primero, código después**. Siempre.
El diff de la spec se muestra y se aprueba antes de tocar el código.

### 3. Una tarea cada vez, tests primero
Cada tarea termina con sus tests en verde antes de pasar a la siguiente.
Prohibido avanzar con tests en rojo.

### 4. Los huecos son visibles
Lo que no se sabe se marca `[NECESITA ACLARACIÓN]`.
Una suposición silenciosa es deuda técnica invisible.

### 5. Cambios con trazabilidad
Todo cambio deja rastro en la spec. El código refleja la spec, no al revés.

---

## Estructura de carpetas

```
proyecto/
├── docs/
│   └── constitution.md        ← Principios innegociables
├── specs/
│   └── NNN-nombre/
│       ├── spec.md            ← Qué se construye (RF en EARS)
│       ├── plan.md            ← Cómo se construye
│       └── tasks.md           ← Tareas con checkboxes
├── AGENTS.md                  ← Contexto del agente para este proyecto
└── CLAUDE.md                  ← Puede ser solo: @AGENTS.md
```

---

## Para empezar ahora mismo

**Proyecto nuevo:**
> "Quiero arrancar con SDD. Tengo un proyecto de [descripción]."
→ Activo `sdd-constitucion`

**Funcionalidad nueva en proyecto existente:**
> "Quiero la spec de [funcionalidad]."
→ Activo `sdd-spec`

**Proyecto sin spec (brownfield):**
> "Tengo código sin spec. Quiero inferir la arquitectura."
→ Activo `discover`

**Cambio en funcionalidad existente:**
> "Nuevo requisito: [descripción]."
→ Activo `sdd-cambio`
