# Paso 2b: examen de rescate v2 en un mundo real (UD PUD) — protocolo fijado ANTES de medir (2026-11-25)

Viene del Paso 2 (`../paso2_examen_rescate/RESULTADOS.md`): el examen era limpio, pero 24 recuerdos no daban
competencia y las pocas preguntas salían de palabras vacías. Aprobado por el usuario y su asesor con dos condiciones:
filtro de pistas sin contenido **sin listas y sin bloquear palabras CJK de 1–2 caracteres**, e invariancia medida
**solo con recuerdos I que no contienen la pista**. **No toca el motor. No entrena ninguna neurona.**

## 1. Mundo
- **Universal Dependencies PUD** (GitHub `UniversalDependencies/UD_{Spanish,English,Chinese,Japanese}-PUD`,
  CC BY-SA 3.0): las mismas 1000 frases reales (noticias y Wikipedia) en es, en, zh (tradicional) y ja, en 397
  documentos, con el mismo identificador de frase en los 4 idiomas. Se descarga al correr; no se sube al repo.
- **Recuerdo** = una frase. Nombre = su identificador (p. ej. `n01001011`): no revela nada del contenido.
  Sin dimensiones ni sustantivos clave (nadie los declaró), categoría «General».
- **Relación real (solo para auditar, nunca entra al examen):** dos frases del mismo documento.
- **D** = documentos con `sha256(doc) % 5 != 0` (~80 %). **I** = el resto (~20 %), para invariancia.
  La misma partición en los 4 idiomas.
- Construcción con el motor real, como E1 y el exp. 16 (`construir.guardar`, sueño cada 50 y al final). DI = D
  igual + I después (sueño cada 50 y al final). **No se añaden sinapsis falsas:** el grafo que crece solo ya es
  ruidoso, como una base real.

## 2. Pistas
- Mismas unidades Unicode que el Paso 2 (`e1_repaso.unidades`: palabras entre espacios; bigramas en escritura sin
  espacios; una corrida CJK de 1 carácter es una unidad). Muestras dispersas por `sha256(B|sueño|nivel)`, niveles
  3/2/1 unidades, **sueños 1–3** (hasta 9 pistas por B).
- **Filtro de pistas sin contenido (nuevo):** una pista cuenta solo si **cada** unidad aparece en **≤ 10
  recuerdos** del mundo examinado (incluido B). Es un conteo de presencia de la unidad, sin listas de palabras.
  Una palabra vacía («la», «the», 的) aparece en cientos de frases y cae sola; una palabra de contenido de cualquier
  idioma, y un bigrama o ideograma CJK, no se bloquean por su longitud. Se mantiene el nivel de 1 unidad.
- Invariancia del filtro: añadir I que **no contienen** las unidades de la pista no cambia su conteo.

## 3. Búsqueda ciega, piso y casos
Igual que el Paso 2: copia limpia A4; `buscar_por_frase(pista, limite=6, profundidad="profundo",
usar_inferencia=False, context_window=0, ignore_peso_sinaptico=True)`; piso = `obtener_asociaciones_enriquecidas`
del motor real (lista completa) sobre una copia del grafo. **Caso:** B fuera del top-5 ciego y un A del top-5 con B
en su lista del canal 2; se toma el primer A. Guardia: `sha256(B) % 5 == 0`.

## 4. Puertas (en D; deben cumplirse en los 4 idiomas)
| id | qué | umbral |
|---|---|---|
| P1 | Casos suficientes | ≥ 100 casos, ≥ 40 B distintos y ≥ 8 B distintos en la guardia |
| P2 | Invariancia de la pregunta, según la NORMA MÁXIMA | en las pistas cuyas unidades **no aparecen en ningún I**: top-5 ciego idéntico en D y DI en ≥ 98 % |
| P2b | Invariancia de la respuesta | en los casos comunes a D y DI (pistas elegibles para P2): mismo A y mismo puesto del piso en ≥ 98 % |
| P3 | Control de hubs | ningún A aporta más del 10 % de los casos; los 3 A más frecuentes, ≤ 25 % |
| P4 | Margen para aprender | el piso NO pone a B primero en ≥ 20 % de los casos |
| P5 | Validez | (a) fracción de casos con A y B del mismo documento > fracción de aristas del grafo entre frases del mismo documento; (b) MRR oráculo (mismo documento primero) > MRR piso > MRR anti-oráculo |
| P6 | Limpieza y reproducibilidad | segundo repaso idéntico (sobre los primeros 150 B, por tiempo); sha256 sin cambio; 0 sinapsis, 0 asociaciones y 0 emergentes en la copia ciega; la consulta de vecinos no cambia las sinapsis |

Referencias sin puerta: pistas antes y después del filtro, pistas con B fuera del top-5, casos por nivel, dormidos,
B sin compañero de documento posible, MRR del azar, piso «visible» (B entre los 5 que el canal 2 muestra).

## 5. Lectura
- **Todas pasan:** el examen de rescate queda validado como verdad gratuita para el paso 3 y siguientes.
- **Falla P5:** el examen premia coincidencias de superficie; no se entrena con él.
- **Falla P1/P3/P4:** el examen no da material suficiente o el piso ya acierta: se informa y se ajusta el diseño en
  un ciclo nuevo, con umbrales fijados otra vez antes de medir.
Ningún umbral se cambia después de ver los datos.
