# Experimento 18 — Resultados de E0: las agujas del par en cuatro idiomas

**Fecha:** 2026-11-25.

Trazabilidad:
- Protocolo fijado en `5bfe989`.
- Corpus y script subidos **antes** de correr, en `b33ed60`.
- Comando: `python medir_e0.py` desde esta carpeta.
- Salida completa: `resultados/e0.json`.

Este es un resultado **nuevo y sintético**. No se compara número a número con los experimentos históricos.
No se tocó el motor, ninguna base de datos ni ningún test.

## Resultado

| Aguja | AUC es | AUC en | AUC zh | AUC ja | Dispersión | Spearman vs es (en / zh / ja) | Invariancia | Reproducible | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| **N1** n-gramas de caracteres | 0,575 | 0,541 | 0,636 | 0,703 | 0,162 | 0,17 / 0,18 / 0,10 | 276/276 en los 4 | ✅ | **NO PASA** (C0.1, C0.2, C0.3) |
| **N2** compresión (NCD, zlib) | 0,615 | 0,568 | 0,702 | 0,678 | 0,134 | 0,32 / 0,07 / 0,28 | 276/276 en los 4 | ✅ | **NO PASA** (C0.1, C0.2, C0.3) |
| ref. `\w{4,}` (motor hoy, B6/B7) | 0,548 | 0,551 | **0,500** | **0,500** | — | 0,33 / 0,00 / 0,00 | 276/276 | ✅ | referencia |

- Positivos: 24 pares del mismo tema por idioma. Negativos: 249. Puentes «rojo»: 3.
- Una AUC de 0,5 equivale al azar.

**Según la lectura fijada antes de medir, N1 y N2 no se usan como entradas de la neurona.** No se ajustan
para que pasen.

## Qué significa

1. **La invariancia por construcción se cumple:** 276/276 en los cuatro idiomas, en las tres agujas. Una
   medida que solo lee los dos textos del par no cambia al agregar recuerdos irrelevantes. Eso era lo fácil.

2. **Pero la forma del texto casi no dice si dos recuerdos están relacionados.**
   - En este corpus, los recuerdos de un mismo tema hablan de **facetas distintas** con palabras distintas. Por
     ejemplo, en el tema de los bomberos: el camión, el rescate en el cuarto piso y el peritaje del cortocircuito.
   - Así, ninguna medida de superficie supera un AUC de 0,72 en ningún idioma, y su orden de los pares no se
     parece de un idioma a otro (Spearman ≤ 0,32).
   - Lo que une esos recuerdos es **conocimiento del mundo**, y no está en las letras.
   - [D] El AUC de 1,000 del exp. 16 venía de lo contrario: su generador escribe la relación en el vocabulario
     (`INFORME_VERIFICACION.md` §3).

3. **El motor de hoy está ciego en chino y japonés en las vías por tokens.** `\w{4,}` da exactamente 0,500 en
   chino y japonés porque toma cláusulas enteras como una sola «palabra» y nunca coinciden. Eso confirma con
   medición lo que en el ciclo anterior era solo análisis (P7).

4. **Los puentes por un solo carácter se pierden con bigramas y trigramas.** En chino y japonés, «红» y «赤» son
   un solo carácter, así que el puente «rojo» no aparece en N1: 0,003 y 0,002, al nivel de los negativos. En
   español e inglés sí aparece algo: 0,191 y 0,217 frente a 0,169 y 0,160. No se ajustó, porque agregar
   unigramas traería el ruido de los caracteres más comunes.

## Mi predicción frente a lo medido (escrita en el protocolo antes de correr)

| Predicción | Resultado |
|---|---|
| N1 pasa en español e inglés y es dudosa en chino y japonés | ❌ **Al revés:** en español e inglés es casi azar (0,54–0,58); en chino y japonés, algo mejor (0,64–0,70) |
| N2 queda por debajo de N1 | ❌ Mixto: N2 supera a N1 en español, inglés y chino |
| `\w{4,}` se hunde en chino y japonés | ✅ Exactamente 0,500 |

## Límites (honestos)

- 24 positivos por idioma: el error de la AUC ronda ±0,05. Es una **prueba de humo**.
- El corpus está escrito para que los temas compartan pocas palabras. Es un caso **difícil a propósito**. En
  memorias reales del mismo proyecto se repiten nombres propios, y ahí N1 daría más señal. Pero entonces la
  señal es la misma que ya dan B1/B2, y no un valor nuevo.
- Textos cortos, medidos en caracteres: español 86–130, inglés 69–120, chino 22–39 y japonés 31–53. En UTF-8, el chino ocupa unos 66–117 bytes. La NCD se resiente con textos así, como advierte la literatura.

## Consecuencia para el diseño (deducción [D], para discutir)

Lo que relaciona dos facetas de un tema **no está en la superficie del texto**. En el cerebro tampoco: dos
recuerdos se asocian porque se vivieron **en el mismo contexto** (contigüidad temporal y episódica) o porque se
**reactivan juntos**, no porque se parezcan letra por letra.

Sin embeddings ni API, las señales que sí pueden llevar esa información, sin depender del idioma, son:
1. **la estructura que escribe el propio agente al aprender:** dimensiones, sustantivos clave, categoría y
   sinónimos, comparados por igualdad exacta normalizada, como en el cambio 2a;
2. **la reactivación conjunta en el repaso interno (R):** hereda lo anterior, porque la búsqueda real usa esos
   campos;
3. **la contigüidad episódica:** se aprendieron en la misma sesión. Hoy B6 la usa, pero la mezcla con `\w{4,}`;
4. **la competencia dentro del nodo (K).**

Esto **no** reabre F1–F6 ni toca el motor. Es lo que habría que medir en E1 y E2 si Dennys los autoriza
(`PROTOCOLO.md` §7).
