# v35.3 (PROPUESTA, no aplicada): palabras de función en el concept hub

## El fallo (base viva de Dennys, 1087 hubs, tras v35.2)
`tests/test_concept_hub_generalizacion.py::paraf_1`: "qué hacía antes de ser programador"
→ el hub no decidía y el recuerdo esperado salía del top 5. En copias sintéticas pasaba.

`scripts/diagnostico_hub.py` sobre la base viva mostró la causa: v35.2 quitaba las palabras
de la lista `STOPWORDS_ES` (186), que incluye "antes", "hacia" (= "hacía" sin tilde) y "que".
La pregunta quedaba en {ser, programador}; "ser" es común, así que un puente con solo
"programador" cubría ~94 % de la pregunta (parecido 0.754 contra 0.813 del correcto).

## La corrección propuesta (V2)
- El hub ya no tira palabras: todas cuentan.
- Las palabras de función aportan **como mucho 1 bit**: ln 2, el peso de una palabra que
  parte la memoria en dos mitades (menos si en esa base son aún más comunes). El tope hace
  falta porque los puentes son frases cortas: ahí "dónde" parece rara y sin tope pesaría
  como una palabra de contenido.
- No abren candidatos: compartir solo palabras de función no es coincidencia.

Diff: `propuesta.diff` (solo `core/concept_hub.py`). Tests: `tests_propuestos.py`
(se agregan a `tests/test_hub_escala.py`; el primero reproduce el caso vivo con datos
genéricos y falla con v35.2).

## Medición (QA oficial 921 casos, BIORAG_NEURONA=0, PYTHONHASHSEED=1, copias)
R@1 / R@5 / MRR

| Base | v35.2 (hoy) | V1 (sin lista, sin tope) | **V2 (tope 1 bit)** |
|---|---|---|---|
| Snapshot oficial | 93.14 / 100 / .9573 | 93.14 / 100 / .9573 | **93.14 / 100 / .9573** |
| H_mitad (436 hubs) | 93.03 / 100 / .9569 | 93.26 / 100 / .9580 | **93.03 / 100 / .9569** |
| H_todos (866 hubs) | 93.83 / 99.89 / .9613 | 93.71 / 99.89 / .9607 | **93.83 / 99.89 / .9613** |

FP 0/40 en todas. V1 pierde 0564 en H_todos ("¿Dónde encuentro la info de…?": "dónde"
pesaba como contenido), por eso se descartó.

H_vivo = H_todos + hubs curados + los 55 hubs rivales reales del diagnóstico vivo:
`test_concept_hub_generalizacion` 2 fallos con v35.2 → 10/10 con V2 (paraf_1 confianza 0.43;
con V1 0.64). Abismo léxico 5/5 en las 4 bases. Suite: 502 passed.

## Ideas medidas y descartadas
- Que compitan solo los 3 rivales más fuertes: más aciertos del hub pero más errores.
- Que solo compitan rivales con parecido ≥ 0.40 (umbral de recuperación): errores del hub
  en H_mitad 71 → 227, y el caso vivo seguía fallando. La "multitud" de rivales débiles
  avisa con razón de que la zona es ambigua.
