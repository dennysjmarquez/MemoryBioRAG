# Capa V del Paso 3: primera medición (escritor mecánico) — 27-11

[V] = verificado con datos o código; [D] = deducción o propuesta.
Protocolo: `../PROTOCOLO_PASO3.md` §4, §5 y §10 (reglas fijadas antes de medir). Tablas completas:
`resultados/tablas_mecanico.md`. Datos por idioma: `resultados/v_mecanico_{es,en,zh,ja}.json`.

## 1. Qué se midió

- **Pregunta:** ¿alguna de las 12 agujas limpias de la capa L ordena el canal 2 del motor mejor que el orden a mano
  (prioridad de tipo, luego peso)? Es el criterio C3.5.
- **Corpus públicos reales**, 1690 recuerdos por idioma: es (AnCora), en (EWT), zh (Lu Xun) y ja (Aozora). Las
  licencias están en `resultados/manifiesto_corpus.json`.
- **Verdad:** dos recuerdos son vecinos verdaderos si vienen del mismo documento.
- **Partición por documento:** Estudio 60 %, Validación 20 % y Guardia 20 %. La Guardia se ingirió, pero nadie la
  leyó.
- **Escritor:** el **mecánico**. Es el control sin conocimiento: palabras más repetidas del propio texto, sin
  dimensiones, sin categoría y sin syn. **No es el escritor que decide** (§10). El escritor ciego (sesión aislada)
  todavía no existe.
- **Motor real** sin tocar, reloj simulado también en SQLite y medición con Neurona 1, PPMI y síntesis DMN apagados.
  Tiempo: 2 h 24 min para los 4 idiomas. La base original quedó intacta tras medir (huella de tablas igual) en los
  4 idiomas.
- **Bridges rechazados por el motor** (regla mecánica): es 247, en 1, zh 89 y ja 17, de 1690. Esos recuerdos se
  guardan sin hub, como en el uso real.

## 2. Resultado principal [V]: el diseño no tiene potencia con este escritor

| idioma | aristas del canal 2 en V | positivos con arista en V | nodos evaluables (documentos) | MRR del piso |
|---|---|---|---|---|
| es | 626 | 28 | 22 (10) | 0,623 |
| en | 1168 | 18 | 17 (9) | 0,404 |
| zh | 152 | 4 | **4 (1)** | 0,794 |
| ja | 212 | 8 | **6 (3)** | 0,872 |

- **zh y ja no se pueden medir.** En zh los 4 nodos son de un solo documento, y por eso los IC95 salen degenerados
  ([0,062; 0,062]). Las ✓ de zh en `tablas_mecanico.md` son un **artefacto**, no un resultado.
- **es y en (C3.5 primario):**
  - pasan S_sk y X_sk en en, y B_angulos en en;
  - en es no pasa ninguna;
  - S+X y las 12 juntas no pasan en ninguno de los dos (IC inferior < 0).
- **Secundario «lista ampliada»** (A en V, vecinos en E ∪ V; declarado antes de ver resultados): S+X y las 12 juntas
  pasan en es y en (es: +0,267 [0,029; 0,523]; en: +0,386 [0,047; 0,717]), igual que X_min, X_max, X_contenido y
  B_angulos en es. Son los **mismos 22 y 17 nodos**, con listas más largas: no gana potencia, solo cambia la
  dificultad.
- **Regla de parada:** ninguna de las 12 cumple C3.5 en los 4 idiomas. Según §10, el escritor mecánico por sí solo no
  la dispara, porque decide el ciego. Aun así **me detengo aquí**: no invento agujas ni cambio criterios, y reporto.

## 3. Por qué hay tan pocos positivos [V]: el canal 2 casi no une recuerdos del mismo documento

Aristas entre recuerdos de E ∪ V, por tipo, y qué fracción une recuerdos del mismo documento:

| idioma | azar (pares del mismo documento) | `pmi_hebbiano` | `co_ocurrencia` | `co_nombre` |
|---|---|---|---|---|
| es | 0,35 % | 16 799 · **0,4 %** | 2534 · 2,2 % | 1276 · 8,2 % (75 % con peso < 0,5) |
| en | 0,24 % | 16 087 · **0,5 %** | 14 730 · 0,4 % | 740 · 15 % (79 % con peso < 0,5) |
| zh | 0,45 % | no nace | 4578 · 0,9 % | no nace |
| ja | 0,49 % | no nace | 4150 · 1,1 % | no nace |

- `pmi_hebbiano` une recuerdos del mismo documento **al ritmo del azar** en texto real.
- `co_ocurrencia` sale de `auto_vincular` (`sinapsis.py` ~L112–186: similitud de tokens ≥ 0,4 sin IDF,
  `idf_map=None`). Sin dimensiones compartidas nunca es `co_semantica`. Une sobre todo por palabras frecuentes: entre
  1,6 y 6 veces el azar, pero con precisión de 0,4–2,2 %.
- En zh y ja solo nace `co_ocurrencia`: ni `pmi_hebbiano` ni `co_nombre`, como ya anticipaba PLAN §9.3.
- **Consecuencia [D]:** casi ningún vecino verdadero llega a estar en el canal 2. Reordenar una lista que no lo contiene
  no puede ayudar mucho. El cuello de botella, con este escritor, es **qué candidatos entran**, no en qué orden
  quedan.

## 4. Las agujas sí llevan señal de documento [V] (C3.3, informativo)

AUC sobre **pares al azar** de Validación (todos los positivos y el mismo número de negativos al azar):

| aguja | es | en | zh | ja |
|---|---|---|---|---|
| X_max = X_contenido | 0,717 | 0,765 | 0,716 | 0,790 |
| X_min | 0,622 | 0,716 | 0,657 | 0,769 |
| B_angulos | 0,763 | 0,739 | 0,615 | 0,743 |
| S_sk | 0,603 | 0,635 | 0,594 | 0,678 |
| R (referencia) | 0,513 | 0,613 | 0,587 | 0,553 |

- Hasta el escritor mecánico deja agujas con señal en los 4 idiomas.
- C3.7 (hubs): ρ con el grado ≤ 0,21 en todas.
- C3.3 **con arista** (el primario) pasa en es y en para S_sk, las X y las B, pero en zh y ja hay 4 y 8 positivos:
  no es medible.
- S_tem, S_tono y Cat quedan «no medibles» (C3.8) con este escritor, como estaba previsto.

## 5. Qué propongo [D] (nada se ejecuta sin OK)

1. **El escritor ciego es el paso decisivo**, y además puede cambiar el canal 2.
   - Con dimensiones, `auto_vincular` crea `co_semantica` (prioridad 2).
   - Con syn, `vincular_por_sinonimos` crea `sinonimo_explicito` (prioridad 1).
   - Las dos deberían unir más recuerdos del mismo documento.
   - El paquete y las instrucciones están listos (`INSTRUCCIONES_ESCRITOR_CIEGO.md`, `laboratorio_capa_V.py
     exportar`): 1690 recuerdos por idioma.
   - Para no gastar 6760 declaraciones a ciegas, propongo **empezar por es y zh** (una escritura latina y una CJK) y
     comprobar la potencia antes de seguir.
2. **Regla de potencia antes del ciego** (enmienda; requiere OK): C3.5 es «no medible por potencia» si hay menos de
   30 nodos evaluables o menos de 10 documentos. Así no se repite el artefacto de zh.
   Dos formas de ganar potencia sin tocar la Guardia:
   - **ajuste cruzado E↔V**: se ajusta con E y se evalúa en V, y al revés. Usa los nodos de las dos particiones y
     duplica los evaluables;
   - **más N** en es, zh y ja. Hay más documentos disponibles (AnCora 1635, Aozora 981, Lu Xun ~2400 recuerdos). En
     inglés el límite es EWT (1697), salvo que se acepte GUM (CC BY-NC-SA) u otra fuente.
3. **Verdad ampliada**, ya prevista en §4: documentos distintos enlazados por una entidad común poco frecuente
   también cuentan como positivos. Añade positivos reales, sin inventar agujas.
4. **Para el Paso 4 y los tickets del motor** (anotado, sin tocar el motor):
   - `pmi_hebbiano` no distingue documentos en texto real;
   - `auto_vincular` sin IDF une por palabras frecuentes;
   - en CJK, el canal 2 es casi solo `co_ocurrencia`.
   - Si con el escritor ciego tampoco entran los vecinos verdaderos, la ganancia de una neurona que solo **ordena** el
     canal 2 tiene un techo bajo. La pregunta pasaría a ser si se le permite **proponer candidatos**, cosa que hoy
     las normas no contemplan (piso, sin borrar, ordena el canal 2). Eso lo decide Dennys.

## 6. Incidentes [V]

- El primer `subir()` del idioma es falló al hacer rebase, porque había cambios sin commit en el árbol. El resultado
  quedó en un commit local y se subió en el siguiente push. Los demás idiomas subieron solos.
- La «lista ampliada» se añadió durante la corrida. Solo cambia el análisis, que se recalculó desde las mediciones
  guardadas (`laboratorio_capa_V.py analizar mecanico`). Las bases no se reconstruyeron.
