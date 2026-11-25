# Experimento 17 (diseño): sinapsis «puente» y salto según el contexto

**Fecha:** 2026-11-25. **Estado:** diseño. Todavía no se midió nada; el protocolo con umbrales se
escribe y se sube antes de medir, igual que en el experimento 16.

## La idea del usuario (corrección al experimento 16)

> «Hay palabras, por ejemplo *color rojo*, que son claves y están relacionadas porque están en otros
> lados. Son tipos de sinapsis: no tienen que ver una cosa con la otra, pero hacen salto. Cuando
> necesito, se hace el salto.»

Así funciona la memoria humana:
- «rojo» conecta tomate, sangre, semáforo y fuego, que son temas sin relación;
- «papa» conecta comida, el Papa y papá.

Esos enlaces **no son ruido**: son **puentes**. Permanecen callados hasta que el contexto los
necesita. Si pienso en «colores», el salto de tomate a semáforo tiene sentido; si pienso en
«recetas», no.

**Error del experimento 16 que esto corrige:** la verdad sintética marcaba como «no relacionado» a
**todo** par de temas distintos. Así, las métricas castigaban también a los puentes legítimos.
- La cifra de que solo entre el 11 % y el 18 % de las sinapsis une recuerdos relacionados
  **exagera** el ruido, porque una parte de esos enlaces entre temas podrían ser puentes.
- Lo que sí es ruido seguro son las coincidencias en siglas, conectores o palabras genéricas
  («sistema», «de»).

## Tres clases de enlace, en lugar de dos

| Clase | Qué comparte el par | Ejemplo | Qué debe hacer el sistema |
|---|---|---|---|
| **Temática** | Significado cercano | Dos recuerdos sobre el mismo arreglo | Mostrarlo casi siempre |
| **Puente** | Un **rasgo saliente** que aparece en muchos temas | «rojo» entre tomate y semáforo | **Guardarlo** con su rasgo. Mostrarlo solo cuando el contexto activa ese rasgo |
| **Accidental** | Una forma vacía: sigla, conector o palabra genérica | «qa», «sistema» | Dejarlo al fondo del orden. Nunca se borra (Pilar 12) |

Un puente se distingue de un accidente en que su rasgo:
- tiene **contenido**: no es una palabra vacía;
- es **saliente** en los dos recuerdos: está en el nombre, en los sustantivos clave o se repite;
- aparece en **varios** temas **con el mismo sentido**.

La memoria semántica ya mide esto último. Si el sentido cambia según el tema, como en «papa», el
puente es de una sola palabra con dos sentidos, y el contexto decide cuál.

## Lo que aprende la neurona (v3)

Para cada sinapsis, la neurona produce tres cosas:
1. **Probabilidad** de cada clase: temática, puente o accidental.
2. **El rasgo del puente:** qué palabras o conceptos sostienen el enlace. Es el «por qué» del salto.
3. **Fuerza temática**, la que ya calcula hoy.

Todo depende solo del par y de estadísticas congeladas, así que la invariancia se mantiene.

## El salto: re-ranqueo híbrido del canal 2 según el contexto

Hoy el canal 2 ordena siempre igual, por tipo y peso, sin mirar qué se preguntó. La propuesta es que
el orden dependa de la búsqueda:

```
puntaje(vecino | consulta) = p_temática
                           + p_puente × activación(rasgo del puente | consulta)
```

- `activación` mide cuánto toca la consulta, o el recuerdo que la originó, al rasgo del puente. Usa
  coincidencia exacta del rasgo y la memoria semántica.
- **Sin contexto que lo active**, el puente queda detrás de los enlaces temáticos, pero sigue en la
  lista de candidatos.
- **Con contexto**, el puente sube y se produce el salto.
- No se oculta ni se borra nada, y los manuales siguen primero: Pilar 12.
- **El canal 1, el ranking de búsqueda, no se toca.** Esto ordena solo el canal 2.

## Cómo se medirá (mundo sintético v3, sin datos reales)

**Mundo v2 + rasgos transversales.** Se agregan 15 rasgos, del estilo «rojo»: conceptos que aparecen
como palabra saliente en recuerdos de 3 a 6 temas distintos. Así, la verdad tiene tres clases por
construcción.

**Consultas sintéticas de dos tipos:**
- **temáticas**, de un subtema;
- **de rasgo**, que mencionan el rasgo o un sinónimo suyo.

**Métricas previstas** (los umbrales se fijan en el protocolo antes de medir):
- en consultas de rasgo, cuántos **puentes correctos** aparecen en las 5 primeras posiciones;
- en consultas temáticas, que la precisión no caiga respecto de la v2;
- clasificación entre las tres clases, en especial no confundir un puente con un accidente;
- invariancia y costo, como en el experimento 16.

**Además se arregla la debilidad del experimento 16** con las palabras nuevas: el entrenamiento
incluye recuerdos que la memoria semántica no conoce, y se agrega una aguja de cobertura.

## Lo que NO cambia

Se mantienen las decisiones de Dennys:
- solo datos sintéticos;
- U0: sin señal de uso;
- ningún cambio al motor ni a los tests;
- E3 sigue abierto.

Que la neurona decida **qué nace** sigue requiriendo autorización (F2–F4). Este diseño trabaja sobre
lo que ya nace y sobre el **orden según el contexto**.
