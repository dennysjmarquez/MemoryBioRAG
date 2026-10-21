---
name: sdd-spec
description: >-
  Fase 2 del flujo SDD. Usar cuando el usuario pide crear, redactar o revisar
  una especificación. Triggers: "spec", "especificación", "requisitos",
  "qué debe hacer", "escribe la spec de", "necesito una spec para".
  Guía una entrevista de requisitos (máx. 6 preguntas, una a la vez) y produce
  un spec.md numerado en notación EARS. Solo el QUÉ y el POR QUÉ — nunca el CÓMO.
  Siempre espera aprobación antes de continuar al plan.
---

# SDD — Fase 2: Especificación (Spec)

La spec es el **contrato**. Si algo no está aquí, no se implementa.
Describe el QUÉ y el POR QUÉ. El CÓMO va en el plan.

---

## 🎯 Regla práctica para decidir qué va en el Spec

> **Pregúntate:**
> **¿Esto lo puede ver, usar o testear alguien sin mirar el código interno?**
> - **SÍ** → Puede y debe ir en el **Spec**.
> - **NO** → Va en el **Plan**, **Tasks** o **Implementación**.

### ✅ Qué SÍ va en un Spec (Negocio / Comportamiento Observable)
- **Contexto y objetivo:** Qué problema resuelve y por qué.
- **Usuarios / Actores:** Quién lo usa y cómo interactúa.
- **Historias de usuario:** H1, H2...
- **Requisitos funcionales (RF):** Qué debe pasar exactamente en notación EARS.
- **Requisitos no funcionales observables:** Idioma, determinismo, sin red, sin dependencias externas, tiempos de respuesta perceptibles.
- **Casos límite:** Vacíos, duplicados, límites, concurrencia, datos corruptos.
- **Fuera de alcance:** Lo que explícitamente NO se hace en esta iteración.
- **Criterios de aceptación y finalización:** Cómo se da por buena la funcionalidad.
- **Mensajes exactos al usuario:** Texto exacto de salida, errores o prompts visibles.
- **Códigos de salida:** Exit codes observables (`0`, `1`, `2`).
- **Comandos CLI y su sintaxis:** Flags, argumentos, subcomandos.
- **Formato del almacén como contrato externo:** Ej. `./habits.json`, esquema público.
- **Restricciones duras del sistema:** Ej. “sin dependencias fuera de la stdlib”.

### ❌ Qué NO va en un Spec (Código / Diseño Interno)
- **Nombres de módulos, clases, funciones o métodos.**
- **Estructura de carpetas interna.**
- **Algoritmos concretos o estructuras de datos internas.**
- **Cómo se calcula un estado internamente (ej. cálculo interno de rachas).**
- **Cómo se organiza internamente el código.**
- **Librerías internas** (salvo que sea una restricción dura del contrato).
- **Decisiones de arquitectura, refactors, patrones de diseño.**
*(Todo esto pertenece a la Fase 4: Plan Técnico o Fase 5: Tareas).*

---

## Proceso de Elaboración

1. **Lee el contexto.** `docs/constitution.md` si existe, y specs previas en
   `specs/` para respetar convenciones y no contradecir lo ya acordado.

2. **Entrevista al usuario.** Preguntas de **UNA en UNA**, máximo 6, esperando
   respuesta antes de la siguiente. Céntrate en:
   - Casos límite y errores
   - Qué queda fuera del alcance
   - Comportamientos ambiguos
   No propongas soluciones técnicas: si el usuario pregunta "¿cómo lo harías?",
   redirige al QUÉ. Solo pregunta lo que cambia lo que hay que construir.

3. **Elige el número.** Mira `specs/` y usa el siguiente libre con tres
   dígitos: `specs/NNN-<nombre-en-kebab-case>/spec.md`.

4. **Redacta** la spec completa con estas secciones (sin saltarte ninguna):

```markdown
# Spec NNN — <Nombre de la funcionalidad>

## Contexto y objetivo
<Qué problema resuelve y por qué merece la pena. Un párrafo.>

## Usuarios / actores
<Quién lo usa.>

## Historias de usuario
- H1: Como <rol> quiero <acción> para <beneficio>.

## Requisitos funcionales (criterios de aceptación en EARS)
- RF-1: CUANDO <evento>, EL SISTEMA <respuesta>.
- RF-2: SI <condición no deseada>, ENTONCES EL SISTEMA <respuesta>.
- RF-3: MIENTRAS <estado>, EL SISTEMA <respuesta>.
- RF-4: EL SISTEMA <comportamiento permanente>.

## Requisitos no funcionales
<Solo observables: rendimiento, determinismo, sin red, plataformas, idioma...>

## Casos límite
<Vacíos, duplicados, datos corruptos, límites, concurrencia...>

## Fuera de alcance
<Lo que explícitamente NO se hace en esta iteración.>

## Criterios de finalización
<Ej.: todos los RF con test en verde + demo manual del flujo principal.>

## Dudas abiertas
- [NECESITA ACLARACIÓN] <duda>
```

5. **Marca los huecos** como `[NECESITA ACLARACIÓN: pregunta concreta]`.
   Nunca rellenes un hueco inventando — un hueco visible es información,
   una suposición silenciosa es deuda técnica.

6. **Pide aprobación explícita** antes de pasar al plan o escribir código.

## Notación EARS — los 5 patrones

| Patrón | Forma | Cuándo usarlo |
|---|---|---|
| **Ubicuo** | EL SISTEMA \<hará\> | Comportamiento permanente |
| **Dirigido por evento** | CUANDO \<disparador\>, EL SISTEMA \<hará\> | Respuesta a una acción o evento |
| **Estado** | MIENTRAS \<estado\>, EL SISTEMA \<hará\> | Durante una condición activa |
| **Opcional** | DONDE \<característica\>, EL SISTEMA \<hará\> | Solo si la característica está presente |
| **No deseado** | SI \<condición\>, ENTONCES EL SISTEMA \<hará\> | Errores y casos límite |

## Reglas Inmutables

- Un requisito, una frase. Si necesitas "y" para unir dos comportamientos, son dos requisitos separados.
- Sin adjetivos no medibles: "rápido", "intuitivo", "robusto" no son requisitos. Escribe el umbral o no lo escribas.
- La sección "Fuera de alcance" es **obligatoria** — es la que evita el scope creep.
- Cada RF debe ser verificable de forma observable (caja negra).

## Si el usuario pide REVISAR una spec existente

No reescribas. Detecta y lista, numerado, en cuatro bloques:
1. Ambigüedades
2. Contradicciones entre requisitos
3. Casos límite no cubiertos
4. Conflictos con la constitución

## Al terminar

> "Spec guardada en `specs/NNN-nombre/spec.md`. La siguiente fase es
> **Clarificación** (revisión QA de la spec) o directamente **Plan técnico**.
> ¿Continuamos?"
