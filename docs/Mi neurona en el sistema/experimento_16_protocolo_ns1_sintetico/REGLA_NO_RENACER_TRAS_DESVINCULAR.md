# Regla aparte, sin implementar: una pareja no renace después de una desvinculación explícita

**Estado:** solo documentada (decisión 5 de Dennys, 2026-11-25). **No se implementa** y **no forma
parte** de la neurona ni del ordenamiento del canal 2.

## Por qué va aparte
- El Pilar 12 habla de **recordar**: las neuronas ordenan y nunca ocultan, borran ni filtran
  asociaciones al recordar.
- Esta regla actúa en otro momento: **al nacer**. Además, solo se aplica a un par que un humano o el
  agente quitó **a propósito**.
- No es un filtro por calidad: es respetar una decisión explícita. Mezclarla con la neurona haría
  imposible auditar cuál de las dos produjo un cambio.

## Qué diría la regla (borrador para discutir)
1. `desvincular(a, b)` deja una marca **del par** (no de la consulta ni del agente): `(a, b, cuándo)`.
2. Ningún camino **automático** de nacimiento vuelve a crear `a↔b` mientras exista la marca. Los
   caminos son las 4 pasadas de `auto_vincular`, `vincular_por_sinonimos`, la co-ocurrencia, el DMN, la
   ráfaga y el léxico.
3. Un `vincular(a, b)` explícito **sí** puede volver a crearlo y borra la marca.
4. La marca no afecta la búsqueda ni el ranking. No oculta recuerdos: solo impide que se cree esa
   sinapsis automática.

## Preguntas abiertas (para Dennys)
- ¿La marca es para siempre o vence?
- ¿Aplica a `desvincular` del agente, del humano o de los dos? Hoy no se distingue la procedencia.
- ¿Guardar la marca cuenta como «registro de actividad por enlace»? Por la decisión 2, eso sería una
  decisión de privacidad aparte. La marca guarda una **decisión**, no un uso, pero conviene confirmarlo.
- ¿Qué pasa con lo que la hormiguita mandó a cuarentena? Por la decisión 4, **no** se trata como
  rechazo explícito.

## Cómo se mediría (cuando se autorice)
- En el mundo sintético del experimento 16, la métrica Q6 (renacimiento) da la línea base de hoy.
- Con la regla, Q6 debería ser 0, y Q1–Q5 e I1–I5 no deberían empeorar.
