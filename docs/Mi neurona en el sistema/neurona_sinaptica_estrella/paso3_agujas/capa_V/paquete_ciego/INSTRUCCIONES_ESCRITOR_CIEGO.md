# Instrucciones para el escritor ciego (capa V del Paso 3)

Este documento se le entrega a una **sesión aislada**: un agente que no participó en el diseño del protocolo, no
conoce el corpus y no ha visto este repositorio. Es lo más parecido a cómo un agente guarda recuerdos en BioRAG en
el uso real.

## Qué hay que hacer

Para cada recuerdo de `recuerdos_{idioma}.jsonl` (cada línea trae `{"id": ..., "contenido": ...}`), escribir las
declaraciones que pondrías al guardarlo con la herramienta `aprender` de BioRAG. **No llames a `aprender`** ni a
ninguna otra herramienta que escriba en la memoria: solo se escribe un archivo.

## Reglas de aislamiento (son lo que hace válida la medición)

1. **Un recuerdo cada vez.** Decláralo mirando solo su `contenido`. No busques, compares ni enlaces con otros
   recuerdos del archivo, ni con recuerdos anteriores del lote.
2. **Lotes cortos en contexto limpio.** Si puedes, abre una conversación nueva cada 20 o 30 recuerdos, para que el
   contexto no acumule los anteriores.
3. **No intentes adivinar de qué texto o autor viene** el recuerdo, ni qué otros recuerdos son «del mismo».
4. No uses `vincular_con` ni busques en BioRAG (`busqueda_previa` no aplica: no hay base).
5. No cambies el orden ni el `id`.

## Qué escribir por recuerdo (una línea JSON por recuerdo)

```json
{"id": "es1a2b3c4d",
 "concepto": "nombre_descriptivo_en_snake_case",
 "categoria": "Lesson",
 "dimensiones": {"emocion": ["preocupacion"], "entidad": ["identidad_organizacional"], "dominio": ["dominio_social"]},
 "syn": "palabra1,palabra2,palabra3,palabra4,palabra5,palabra6,palabra7,palabra8",
 "sustantivos_clave": "nucleo1,nucleo2,nucleo3",
 "bridges": [{"text": "...", "angle": "sinonimo"}, {"text": "...", "angle": "problema"},
             {"text": "...", "angle": "solucion"}, {"text": "...", "angle": "situacion"},
             {"text": "...", "angle": "ingenuo"}]}
```

Sigue el contrato de `aprender` tal como lo describe la herramienta:

- **`concepto`:** nombre único y descriptivo del recuerdo (se le añade el `id` después, para que no choque).
- **`categoria`:** System | Architecture | Project | Lesson | Profile | Personal | Principle | Protocol | Cognition
  | Relation | General.
- **`dimensiones`:** los 13 ejes de la herramienta (emocion, entidad, accion, cualidad, coordenada, intencion,
  dominio, cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad), con los
  **valores curados** del catálogo. Solo los que se sostengan en una frase del texto. No inventes valores salvo como
  último recurso.
- **`syn`:** al menos 8 palabras con las que alguien buscaría este recuerdo y que **no** estén ya en el texto.
- **`sustantivos_clave`:** de 2 a 10 palabras núcleo: de qué **trata** el recuerdo.
- **`bridges`:** exactamente 5, uno por ángulo (sinonimo, problema, solucion, situacion, ingenuo). Cada uno con 2 o
  más palabras de contenido y sin repetir el nombre del concepto.
- **Idioma:** escribe las declaraciones en el idioma del recuerdo (es, en, zh o ja). Los valores de las dimensiones
  son los del catálogo, tal cual.

## Entrega

Un archivo por idioma, `ciego_{idioma}.jsonl`, con una línea por recuerdo y todos los `id` del archivo de entrada.
Se guarda en `paso3_agujas/capa_V/declaraciones_ciegas/` (o se le pasa al auditor). La sesión aislada **no** debe
leer nada más de este repositorio.

## Cómo se genera el paquete (lo hace Dennys o el auditor, no la sesión aislada)

```bash
cd "docs/Mi neurona en el sistema/neurona_sinaptica_estrella/paso3_agujas/capa_V"
python corpus_v.py                    # descarga los corpus públicos fijados por commit y arma los recuerdos
python laboratorio_capa_V.py exportar # → /tmp/capa_V/paquete_ciego/recuerdos_{es,en,zh,ja}.jsonl + estas instrucciones
```

El paquete de **es** y **zh** (los dos primeros idiomas, decisión del 27-11) ya está en el repositorio, en
`paso3_agujas/capa_V/paquete_ciego/`. A la sesión aislada se le entrega **solo esa carpeta**.

Volumen: 1690 recuerdos por idioma (3380 entre es y zh). El análisis de cada idioma necesita **todas** sus
declaraciones, porque el mundo se construye con todos los recuerdos. Antes de medir, el auditor revisa los archivos
con `python laboratorio_capa_V.py validar es zh`.
