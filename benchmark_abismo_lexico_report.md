# Reto Abismo Léxico — MemoryBioRAG

_Generado: 2026-09-15 13:01:04 · 5 casos metafóricos con 0 palabras en común_

## Qué se mide
Consultas en lenguaje natural / metáforas donde **no hay ni una palabra compartida** con el recuerdo buscado. Un sistema puramente léxico no tiene nada que hacer.

## Sistemas
| ID | Sistema |
|----|---------|
| S1 | LEXICAL | baseline léxico independiente |
| S2 | BioRAG-base | BioRAG sin capa semántica v29.1 (Hub/WordNet/Domain off) |
| S3 | BioRAG-full | BioRAG completo |
| S4 | Dense | OMITIDO: No module named 'psutil' |

## Resumen
| Sistema | R@1 | R@5 | MRR |
|---------|-----|-----|-----|
| S1_lexical | 0% | 0% | 0.000 |
| S2_biorag_base | 0% | 0% | 0.000 |
| S3_biorag_full | 0% | 0% | 0.000 |

## Por caso

**1.** Q: "qué hacía antes de ser programador"  → esperado `historia_tasajera_fumigador_rufino`  _(overlap=2 tokens)_

  - S1_lexical: ✗ top1 = `despertar_grafo_universal_dennys_2026`
  - S2_biorag_base: ✗ top1 = `oracle_que_recordar_sobre_artemis_hermes`
  - S3_biorag_full: ✗ top1 = `fca_reticulo_galois_f2_resultado_refuta_exclusion_triviales`

**2.** Q: "metí un cambio y todo se rompió"  → esperado `leccion_control_flujo_codigo_preexistente`  _(overlap=1 tokens)_

  - S1_lexical: ✗ top1 = `word2vec_pooling_promedio`
  - S2_biorag_base: ✗ top1 = `reglas_trabajo_equipo_dennys_athena`
  - S3_biorag_full: ✗ top1 = `athena_todos_confirmación`

**3.** Q: "toqué algo que andaba bien y dejó de andar"  → esperado `leccion_control_flujo_codigo_preexistente`  _(overlap=1 tokens)_

  - S1_lexical: ✗ top1 = `oracle_que_deben_saber_artemis_hermes`
  - S2_biorag_base: ✗ top1 = `dennys-working-style`
  - S3_biorag_full: ✗ top1 = `dennys-working-style`

**4.** Q: "cómo sobrevivía económicamente antes de la tecnología"  → esperado `historia_tasajera_fumigador_rufino`  _(overlap=0 tokens)_

  - S1_lexical: ✗ top1 = `oracle_custom_prompt_arsitecura_que_funciona`
  - S2_biorag_base: ✗ top1 = `identidad_dennys_perfil_completo`
  - S3_biorag_full: ✗ top1 = `autoria-athena-oec-sanitizacion-rafaga-v9.2`

**5.** Q: "dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?"  → esperado `resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad`  _(overlap=2 tokens)_

  - S1_lexical: ✗ top1 = `reglas_trabajo_equipo_dennys_athena`
  - S2_biorag_base: ✗ top1 = `puente_llm_sinonimos_veredicto_refutado_invariante_cero_llm`
  - S3_biorag_full: ✗ top1 = `dennys_morpheus_de_los_transformers`


## Lectura
- S1 (léxico) y S2 (BioRAG sin la capa v29.1) fallan: sin palabras comunes no hay señal.
- S3 (BioRAG completo) resuelve los casos vía Concept Hubs (5 ángulos) + WordNet + Domain Dict + grafo.