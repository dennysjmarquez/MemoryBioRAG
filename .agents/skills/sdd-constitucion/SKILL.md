---
name: sdd-constitucion
description: >-
  Fase 1 del flujo SDD. Usar cuando el usuario quiere iniciar un nuevo proyecto
  o cuando dice "constitución", "principios del proyecto", "arrancar con SDD",
  "empezar proyecto nuevo", "quiero arrancar bien este proyecto".
  Genera los principios innegociables del proyecto (stack, calidad, tests, límites).
  Siempre espera aprobación explícita antes de continuar a la siguiente fase.
---

# SDD — Fase 1: Constitución del Proyecto

La constitución son los **principios innegociables** del proyecto. Todo spec,
plan y tarea debe cumplirlos. Es la ley máxima: si algo contradice la
constitución, se detiene y se pregunta.

## Proceso

1. **Analiza el contexto.** Lee cualquier README, código o descripción que
   exista. Si no hay nada, pregunta al usuario en **una sola pregunta**:
   "¿Qué vas a construir y con qué stack quieres trabajar?"

2. **Propón la constitución.** Entre 5 y 8 principios, cortos y verificables.
   Cubre obligatoriamente:
   - **Stack y dependencias**: qué está permitido y qué no.
   - **Calidad**: cobertura mínima de tests, estilo de código.
   - **Separación de responsabilidades**: qué capa hace qué.
   - **Datos**: dónde y cómo se persiste.
   - **Idioma**: del código, de los mensajes al usuario, de la documentación.
   - **Límites**: qué NO se hace sin aprobación explícita.

3. **Escribe un principio por renglón.** Formato:
   ```
   N. **Nombre corto**: descripción verificable en una frase.
   ```

4. **Pide aprobación explícita.** Di: *"Esta es la constitución propuesta.
   ¿La apruebas tal como está, o quieres cambiar algo antes de continuar?"*
   No avances hasta tener "sí" o una corrección clara.

5. **Guarda el archivo.** Una vez aprobada, escríbela en `docs/constitution.md`.

## Reglas

- Máximo 15 líneas en total. La constitución larga no se lee.
- Cada principio debe ser **verificable**: si no puedes comprobar si se
  cumple, no es un principio, es un deseo. Reformúlalo o elimínalo.
- Sin adjetivos vacíos: "robusto", "limpio", "profesional" no dicen nada.
  Escribe el umbral concreto.
- La constitución puede evolucionar, pero **solo con aprobación explícita**
  del usuario. Nunca la modifiques silenciosamente.

## Al terminar

Informa al usuario que puede continuar con la siguiente fase:
> "Constitución guardada en `docs/constitution.md`. Cuando quieras,
> continuamos con la **Fase 2: Spec** — dime la funcionalidad a especificar
> o usa el skill `sdd-spec`."
