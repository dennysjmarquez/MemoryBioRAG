---
name: sdd-plan
description: >-
  Fase 4 del flujo SDD. Usar cuando la spec está aprobada y el usuario quiere
  planificar la implementación técnica. Triggers: "plan técnico", "planifica",
  "cómo lo hacemos", "diseña la arquitectura", "plan de implementación".
  Lee constitución y spec. Sin código: genera plan.md con módulos, modelo de
  datos, decisiones justificadas y estrategia de tests. Indica qué RF cubre
  cada parte.
---

# SDD — Fase 4: Plan Técnico

El plan responde al **CÓMO**. La spec dice qué construir (caja negra observable); el plan dice
cómo construirlo por dentro (arquitectura, módulos, algoritmos, tipos). Cero código en esta fase — solo decisiones y estructura.

---

## 🎯 Separación Estricta: Spec vs. Plan

> **Regla de oro:**
> - Lo observable sin mirar el código (mensajes, comandos CLI, exit codes, contrato de datos externo) **ya está en la Spec**.
> - La organización interna (nombres de módulos, clases, funciones, algoritmos internos, modelos internos, patrones de diseño) **se decide y documenta AQUÍ en el Plan**.

---

## Proceso

1. **Lee obligatoriamente:**
   - `docs/constitution.md` — los principios son restricciones duras.
   - La spec activa (`specs/NNN-nombre/spec.md`) — el plan debe cubrir
     **todos** los RF, sin excepción.

2. **Genera `specs/NNN-nombre/plan.md`** con estas secciones:

```markdown
# Plan técnico — Spec NNN

## Estructura de módulos
<Lista de archivos/módulos internos con su responsabilidad y los RF que cubren.>
- modulo/archivo.ext → <qué hace internamente> (RF-X, RF-Y)

## Modelo de datos interno
<Esquema de las estructuras de datos, tipos, clases, dataclasses, tablas.>

## Algoritmos y lógica interna
<Solo los no triviales: cómo se calculan estados/rachas, flujo de datos, pasos internos, RF que cubre.>

## Decisiones técnicas y arquitectura
<Por cada decisión que no sea obvia, formato:>
- **Decisión**: <qué se decidió>
  - **Alternativa descartada**: <qué más se consideró>
  - **Por qué**: <justificación técnica>
  - **Restricción de constitución**: <principio N, si aplica>

## Contrato de interfaces externas
<Alineado 100% con la spec: comandos CLI, exit codes, mensajes exactos, esquemas.>

## Estrategia de tests
<Qué tipos de tests, qué RF cubren, fixtures o datos de prueba necesarios.>
- Unitarios: <funciones / clases internas>
- Integración / CLI: <caja negra probando comandos, mensajes y exit codes>
```

3. **Verifica cobertura total.** Antes de terminar, comprueba que cada RF de
   la spec aparece al menos una vez en el plan (módulo o test). Si alguno
   queda sin cobertura, corrígelo o márcalo como `[SIN COBERTURA — aclarar]`.

4. **Pide aprobación explícita** antes de pasar a tareas.

## Reglas Inmutables

- **Sin código.** Solo estructura, nombres, contratos y decisiones.
- Cada decisión técnica debe incluir la **alternativa descartada** y el **por qué**.
- Si la spec tiene un `[NECESITA ACLARACIÓN]` sin resolver, **no planifiques esa parte**.
- Las decisiones deben respetar la constitución. Si hay conflicto, detente y pregunta.

## Al terminar

> "Plan guardado en `specs/NNN-nombre/plan.md`. Todos los RF tienen cobertura.
> La siguiente fase es **Fase 5: Tareas** — usa el skill `sdd-tareas`."
