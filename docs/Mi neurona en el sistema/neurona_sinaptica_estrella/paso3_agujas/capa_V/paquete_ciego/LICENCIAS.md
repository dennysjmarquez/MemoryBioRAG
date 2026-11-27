# Licencias y atribución del paquete del escritor ciego

Los archivos `recuerdos_es.jsonl` y `recuerdos_zh.jsonl` son **fragmentos de textos públicos**, preparados para la
capa V del Paso 3 de BioRAG (`../corpus_v.py`, `../laboratorio_capa_V.py exportar`).

- **Cambios hechos a los originales:**
  - el texto se partió en fragmentos de párrafos consecutivos (como mucho 8 por documento);
  - se barajó el orden;
  - se sustituyeron los identificadores por hashes opacos;
  - en zh se quitaron las llamadas a notas editoriales 〔n〕 y las notas.
- La huella de cada corpus está en `../resultados/manifiesto_corpus.json`.

## recuerdos_es.jsonl — UD Spanish AnCora

- Fuente: Universal Dependencies, `UD_Spanish-AnCora`, https://github.com/UniversalDependencies/UD_Spanish-AnCora
  (commit `3ea1f747220979d91787a6d04b85734a42bf22a4`).
- Origen: el corpus AnCora (Taulé, Martí y Recasens, 2008, *AnCora: Multilevel Annotated Corpora for Catalan and
  Spanish*, LREC), en su conversión a UD.
- **Licencia: CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/). Se permite redistribuir y adaptar citando
  la fuente e indicando los cambios, como se hace en este archivo.

## recuerdos_zh.jsonl — Obras de Lu Xun (鲁迅全集)

- Fuente: https://github.com/Ac-heron/luxun (commit `b859e5043211b9ead7417ba3f5776e81eaf9213c`), carpeta `全集`.
- **Dominio público:** Lu Xun murió en 1936. El repositorio de origen no declara licencia propia. Se usa solo el texto
  del autor, sin las notas editoriales de las ediciones modernas.
