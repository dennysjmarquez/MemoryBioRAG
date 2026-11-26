# Paso 2: examen de rescate en el laboratorio — resultados (2026-11-25)

Protocolo y puertas, fijados antes de medir: `PROTOCOLO_EXAMEN_RESCATE.md`. Script: `examen_rescate.py`.
Datos completos: `resultados/examen.json` (dos corridas completas, idénticas). [V] = medido, [D] = deducido.

## 1. Veredicto en una línea
**El examen está bien construido y limpio, pero el mundo de E1 (24 recuerdos por idioma) no puede alojarlo:** la
búsqueda ciega casi nunca falla, así que casi no hay preguntas, y las pocas que hay son basura que la puerta de
validez detectó. **Pasa 1 de 7 puertas (P6).** No se cambió ningún umbral.

## 2. Puertas [V]
| puerta | es | en | zh | ja | ¿pasa? |
|---|---|---|---|---|---|
| P1 casos ≥ 30, B ≥ 8, guardia ≥ 2 | 4 · 3 · 1 | 3 · 3 · 1 | 0 | 0 | ❌ |
| P2 top-5 ciego idéntico D vs DI ≥ 98 % | 283/343 (82,5 %) | 287/347 (82,7 %) | 315/344 (91,6 %) | 301/352 (85,5 %) | ❌ |
| P2b misma respuesta en casos comunes | sin casos suficientes | | | | ❌ |
| P3 hubs (A máx ≤ 25 %, top-3 ≤ 50 %) | con 3–4 casos no puede cumplirse | | | | ❌ |
| P4 margen (piso no acierta ≥ 20 %) | R@1 = 1,00 | 0,67 | — | — | ❌ |
| P5 validez | 0 % relación real en casos frente a 12 % en aristas | 0 % frente a 13,5 % | — | — | ❌ |
| P6 limpieza y reproducibilidad | ✅ | ✅ | ✅ | ✅ | ✅ |

P6 en detalle: dos repasos idénticos; sha256 de todas las bases igual antes y después; la copia ciega termina con
0 sinapsis, 0 asociaciones y 0 dimensiones emergentes; pedir los vecinos al motor no cambia el número de sinapsis.

## 3. Por qué no hay preguntas [V]
- B quedó fuera del top-5 ciego en solo **21/343** pistas (es), **19/347** (en), **0/344** (zh) y **2/352** (ja).
- Con 24 recuerdos, casi cualquier pieza del texto de B (incluso un bigrama chino suelto, que desde el Paso 1 el motor
  sí ve) es casi única en el mundo: no hay competencia. El examen necesita que muchas memorias compitan por la pista.
- El grafo ruidoso tiene 50–52 aristas, y 12 de los 32 recuerdos están dormidos (el canal 2 no los muestra).

## 4. Lo que sí enseña: las pocas preguntas eran basura y la validación lo atrapó [V]
Los 7 casos (es + en) salen de pistas de **una palabra vacía**: «la», «de», «el», «un», «and», «a», «the in».
En **los 7**, el A encontrado está unido a B por una de las **sinapsis falsas** (temas distintos). Es decir: en un
mundo pequeño, el examen premiaría justo las sinapsis malas. P5 lo detectó (0 % de relación real en los casos
frente a 12–13,5 % en el grafo). **Diseño que hay que añadir [D]:** un filtro de pistas sin contenido que **no use
listas de palabras**. Candidatos para el siguiente ciclo, a medir:
1. exigir que la pista ciega encuentre a A con un margen claro sobre el resto (contraste dentro de la misma
   respuesta, sin estadísticas del corpus);
2. un control al azar: la misma pista contra un B elegido al azar; el caso cuenta solo si B gana al azar;
3. pistas de 2–3 unidades como mínimo en un mundo grande (la de 1 unidad queda solo como nivel extremo).

## 5. Invariancia: la mayor parte del fallo de P2 es legítima [V]
| | es | en | zh | ja |
|---|---|---|---|---|
| pistas con top-5 distinto | 60 | 60 | 29 | 51 |
| … porque entra un recuerdo «irrelevante» que **contiene la pieza** | 51 | 46 | 28 | 51 |
| … con reorden entre los recuerdos D de siempre | 21 | 25 | 2 | 0 |

Un recuerdo que contiene la pieza buscada no es irrelevante para esa pista: ahí cambiar es correcto. El reorden real
(6–7 % en es/en; ~0 en zh/ja) es la misma causa conocida de E1 C1.1: el BM25 del canal 1 depende del corpus. La
puerta P2 se queda como estaba (falla); para el siguiente ciclo la propuesta [D] es medir la invariancia solo sobre
recuerdos I que **no** contienen ninguna pieza de la pista (la definición exacta de la NORMA MÁXIMA).

## 6. Qué se necesita (y cómo encaja con el plan)
El examen y el paso 3 piden lo mismo: **un mundo grande, real y escrito a ciegas**. Fuente encontrada y verificada
desde este entorno [V]: **Universal Dependencies PUD** (GitHub, CC BY-SA 3.0): las **mismas 1000 frases reales**
(noticias y Wikipedia) en **es, en, zh y ja**, agrupadas en **397 documentos**. Ventajas:
- nadie del proyecto las escribió (el mayor riesgo del plan desaparece);
- la agrupación por documento da una relación real que no depende de mí;
- es paralelo, como los mundos espejo: lo único que cambia entre idiomas es el idioma.
Propuesta: no se sube el corpus al repo; se descarga al correr (atribución CC BY-SA en el informe).

## 7. Reproducir
```
python "docs/Mi neurona en el sistema/neurona_sinaptica_estrella/paso2_examen_rescate/examen_rescate.py"
```
Unos 75 s con 2 CPU. Todo en `/tmp/exp18_rescate` y `/tmp/exp18_e1`.
