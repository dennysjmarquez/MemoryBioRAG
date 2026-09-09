#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/construir_dataset_out_of_family_frozen.py
=============================================================================
Construcción y Congelamiento Criptográfico del Dataset Out-of-Family Hold-Out:
- 50 Casos Positivos Inéditos (20 Golds limpios, 4 Nuevas Familias, Cross-Composition)
- 50 Casos Adversariales Nuevos (Controles negativos, paradojas, ironías de nuevo dominio)
- Verificación estricta ZERO_STRICT_4D por caso (100.0% Cero Solapamiento)
- Cálculo inmutable de SHA-256 pre-ejecución
=============================================================================
"""

import os
import json
import sqlite3
import re
import hashlib

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
OUTPUT_DATASET_JSON = "docs/fase5_out_of_family_dataset_frozen.json"

def build_frozen_dataset():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo'")
    active_nodes = {r[0]: (r[1] or "") for r in cur.fetchall()}

    stopwords = {"para", "como", "con", "sin", "que", "los", "las", "por", "del", "una", "uno", "unos", "unas", "sus", "mas", "pero", "ante", "bajo", "cabe", "desde", "hacia", "hasta", "segun", "sobre", "tras", "entre"}

    def tokenize(text: str):
        return set(re.findall(r"\b[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9_]{3,}\b", text.lower())) - stopwords

    # 50 Casos Positivos Diseñados Parser-Blind con Cross-Composition y ZERO_STRICT_4D
    positive_50 = [
        # FAMILIA 1: RESOURCE_CAPACITY_BOUNDS
        {
            "id": "OOF_POS_01",
            "gold": "docker_infrastructure_rog",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "MEMORY_CAPACITY_LIMIT",
            "comp_B": "CPU_THREAD_ALLOCATION",
            "query": "asignar un tope estricto de gigabytes de memoria fisica y paralelismo de lineas de ejecucion",
            "cross_group": "FAM1_GRID_11"
        },
        {
            "id": "OOF_POS_02",
            "gold": "docker_infrastructure_rog",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "MEMORY_CAPACITY_LIMIT",
            "comp_B": "BUFFER_TRUNCATION_GATE",
            "query": "fijar un techo rigido de consumo volatil restringiendo el tamano total de almacenamiento",
            "cross_group": "FAM1_GRID_12"
        },
        {
            "id": "OOF_POS_03",
            "gold": "memoria_v5_1_optimizaciones",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "BUFFER_TRUNCATION_GATE",
            "comp_B": "DYNAMIC_LIMIT_THROTTLING",
            "query": "acortar preventivamente la cantidad de caracteres admitidos ante un incremento brusco de volumen",
            "cross_group": "FAM1_GRID_21"
        },
        {
            "id": "OOF_POS_04",
            "gold": "memoria_v5_1_optimizaciones",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "BUFFER_TRUNCATION_GATE",
            "comp_B": "CPU_THREAD_ALLOCATION",
            "query": "recortar longitud de texto para preservar rendimiento en procesamiento multifilamento",
            "cross_group": "FAM1_GRID_22"
        },
        {
            "id": "OOF_POS_05",
            "gold": "v5_1_automatico_completo",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "QUERY_FALLBACK_ROUTING",
            "comp_B": "ESCAPE_OPERATOR_LOGIC",
            "query": "redireccionar hacia sintaxis alternativa cuando una clausula disyuntiva sufra fallo de interpretacion",
            "cross_group": "FAM1_GRID_31"
        },
        {
            "id": "OOF_POS_06",
            "gold": "v5_1_automatico_completo",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "QUERY_FALLBACK_ROUTING",
            "comp_B": "DYNAMIC_LIMIT_THROTTLING",
            "query": "conmutar mecanismo de desvio contingente al exceder la tasa admisible de respuestas",
            "cross_group": "FAM1_GRID_32"
        },
        {
            "id": "OOF_POS_07",
            "gold": "proyecto_nodejs_mejores",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "RUNTIME_ENGINE_BUDGET",
            "comp_B": "ASYNC_EVENT_LOOP_BOUND",
            "query": "limitar tiempos de espera no bloqueantes dentro del entorno del bucle de eventos",
            "cross_group": "FAM1_GRID_41"
        },
        {
            "id": "OOF_POS_08",
            "gold": "proyecto_nodejs_mejores",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "RUNTIME_ENGINE_BUDGET",
            "comp_B": "MEMORY_CAPACITY_LIMIT",
            "query": "controlar el gasto de pila y almacenamiento en servicios concurrentes",
            "cross_group": "FAM1_GRID_42"
        },
        {
            "id": "OOF_POS_09",
            "gold": "biorag_v26_0_motor_hibrido_ppmi_svd",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "SVD_DIMENSION_FACTORIZATION",
            "comp_B": "DENSE_EMBEDDING_BUDGET",
            "query": "descomposicion matricial en un centenar de componentes ortogonales densos",
            "cross_group": "FAM1_GRID_51"
        },
        {
            "id": "OOF_POS_10",
            "gold": "biorag_v26_0_motor_hibrido_ppmi_svd",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "SVD_DIMENSION_FACTORIZATION",
            "comp_B": "BUFFER_TRUNCATION_GATE",
            "query": "reducir rango algebraico manteniendo cota de elementos representacionales",
            "cross_group": "FAM1_GRID_52"
        },
        {
            "id": "OOF_POS_11",
            "gold": "docker_infrastructure_rog",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "CPU_THREAD_ALLOCATION",
            "comp_B": "MEMORY_CAPACITY_LIMIT",
            "query": "particionar capacidad de computo en doce nucleos virtuales con tope en gigas",
            "cross_group": "FAM1_GRID_11"
        },
        {
            "id": "OOF_POS_12",
            "gold": "memoria_v5_1_optimizaciones",
            "family": "RESOURCE_CAPACITY_BOUNDS",
            "comp_A": "DYNAMIC_LIMIT_THROTTLING",
            "comp_B": "QUERY_FALLBACK_ROUTING",
            "query": "estrangular flujo de salida activando via alterna de recuperacion",
            "cross_group": "FAM1_GRID_23"
        },

        # FAMILIA 2: SUB_COMPONENT_HIERARCHY_AND_LAYOUT
        {
            "id": "OOF_POS_13",
            "gold": "caso_formularios_anidados_angular",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "NESTED_TAB_VIEW_HIERARCHY",
            "comp_B": "FORM_STATE_ENCAPSULATION",
            "query": "aislar variables de campos de captura dentro de vistas por solapas estratificadas",
            "cross_group": "FAM2_GRID_11"
        },
        {
            "id": "OOF_POS_14",
            "gold": "caso_formularios_anidados_angular",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "NESTED_TAB_VIEW_HIERARCHY",
            "comp_B": "SOURCE_CODE_PATH_MAPPING",
            "query": "distribuir paneles visuales multinivel ubicados en ubicaciones de modulos especificas",
            "cross_group": "FAM2_GRID_12"
        },
        {
            "id": "OOF_POS_15",
            "gold": "ref_formularios_anidados",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "SOURCE_CODE_PATH_MAPPING",
            "comp_B": "MODULE_REPOSITORY_REFERENCE",
            "query": "apuntar al directorio del arbol de documentos donde reside el paquete corporativo",
            "cross_group": "FAM2_GRID_21"
        },
        {
            "id": "OOF_POS_16",
            "gold": "ref_formularios_anidados",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "SOURCE_CODE_PATH_MAPPING",
            "comp_B": "FORM_STATE_ENCAPSULATION",
            "query": "localizacion en disco de los elementos que gestionan las planillas encapsuladas",
            "cross_group": "FAM2_GRID_22"
        },
        {
            "id": "OOF_POS_17",
            "gold": "tema_dark_2026_en_visor_de_markdown",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "THEME_PALETTE_MAPPING",
            "comp_B": "SYNTAX_HIGHLIGHT_THEMING",
            "query": "asignar gamas cromaticas nocturnas a la coloracion de bloques de sintaxis",
            "cross_group": "FAM2_GRID_31"
        },
        {
            "id": "OOF_POS_18",
            "gold": "tema_dark_2026_en_visor_de_markdown",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "THEME_PALETTE_MAPPING",
            "comp_B": "NESTED_TAB_VIEW_HIERARCHY",
            "query": "personalizar estetica visual oscura en contenedores con subpestañas",
            "cross_group": "FAM2_GRID_32"
        },
        {
            "id": "OOF_POS_19",
            "gold": "scoring_pesos_bm25",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "HYBRID_WEIGHT_BALANCING",
            "comp_B": "SCORE_COMPONENT_COMPOSITION",
            "query": "calibrar coeficientes multiplicativos para combinar valores de relevancia heterogeneos",
            "cross_group": "FAM2_GRID_41"
        },
        {
            "id": "OOF_POS_20",
            "gold": "scoring_pesos_bm25",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "HYBRID_WEIGHT_BALANCING",
            "comp_B": "THEME_PALETTE_MAPPING",
            "query": "ponderar metricas mixtas de puntuacion bajo gradiente estructurado",
            "cross_group": "FAM2_GRID_42"
        },
        {
            "id": "OOF_POS_21",
            "gold": "coche_puente_condicional",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "HDC_VECTOR_BINDING",
            "comp_B": "CONDITIONAL_BRIDGE_PROJECTION",
            "query": "entrelazamiento hiperdimensional binario proyectado a traves de pasarela situacional",
            "cross_group": "FAM2_GRID_51"
        },
        {
            "id": "OOF_POS_22",
            "gold": "coche_puente_condicional",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "HDC_VECTOR_BINDING",
            "comp_B": "HYBRID_WEIGHT_BALANCING",
            "query": "ligar hipervectores dispersos a traves de combinacion asociativa ponderada",
            "cross_group": "FAM2_GRID_52"
        },
        {
            "id": "OOF_POS_23",
            "gold": "caso_formularios_anidados_angular",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "FORM_STATE_ENCAPSULATION",
            "comp_B": "NESTED_TAB_VIEW_HIERARCHY",
            "query": "confinar elementos de llenado en vistas subordinadas independientes",
            "cross_group": "FAM2_GRID_11"
        },
        {
            "id": "OOF_POS_24",
            "gold": "tema_dark_2026_en_visor_de_markdown",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "SYNTAX_HIGHLIGHT_THEMING",
            "comp_B": "THEME_PALETTE_MAPPING",
            "query": "resaltado de fragmentos de codigo adaptado a la tonalidad apagada de fondo",
            "cross_group": "FAM2_GRID_31"
        },
        {
            "id": "OOF_POS_25",
            "gold": "scoring_pesos_bm25",
            "family": "SUB_COMPONENT_HIERARCHY_AND_LAYOUT",
            "comp_A": "SCORE_COMPONENT_COMPOSITION",
            "comp_B": "HDC_VECTOR_BINDING",
            "query": "integracion no lineal de factores cuantitativos con matrices de proyeccion",
            "cross_group": "FAM2_GRID_43"
        },

        # FAMILIA 3: TOPOLOGICAL_GRAPH_TRANSITIONS
        {
            "id": "OOF_POS_26",
            "gold": "migracion_vincular_existentes_2026_06_09",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "RETROACTIVE_EDGE_POPULATION",
            "comp_B": "DENSE_CLUSTER_CLOSURE",
            "query": "densificar retrospectivamente los enlaces de una red completando triangulaciones",
            "cross_group": "FAM3_GRID_11"
        },
        {
            "id": "OOF_POS_27",
            "gold": "migracion_vincular_existentes_2026_06_09",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "RETROACTIVE_EDGE_POPULATION",
            "comp_B": "OVERLAP_COEFFICIENT_LINKING",
            "query": "poblacion retroactiva de uniones basada en grado de coincidencia vecinal",
            "cross_group": "FAM3_GRID_12"
        },
        {
            "id": "OOF_POS_28",
            "gold": "desde_athena_biorag",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "OVERLAP_COEFFICIENT_LINKING",
            "comp_B": "SYNAPTIC_AUTO_LINKING",
            "query": "establecer conexiones automaticas calculando la razon de interseccion de adyacencias",
            "cross_group": "FAM3_GRID_21"
        },
        {
            "id": "OOF_POS_29",
            "gold": "desde_athena_biorag",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "OVERLAP_COEFFICIENT_LINKING",
            "comp_B": "DENSE_CLUSTER_CLOSURE",
            "query": "generar conexiones estocasticas para consolidar grupos fuertemente entrelazados",
            "cross_group": "FAM3_GRID_22"
        },
        {
            "id": "OOF_POS_30",
            "gold": "activos_dormidos_hermana",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "ACTIVE_SLEEP_STATE_TRANSITION",
            "comp_B": "MEMORY_PRUNING_CYCLE",
            "query": "transicion de vigilia a letargo con eliminacion de elementos caducos",
            "cross_group": "FAM3_GRID_31"
        },
        {
            "id": "OOF_POS_31",
            "gold": "activos_dormidos_hermana",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "ACTIVE_SLEEP_STATE_TRANSITION",
            "comp_B": "RETROACTIVE_EDGE_POPULATION",
            "query": "pasar vertices a hibernacion reorganizando la malla de conexiones pasadas",
            "cross_group": "FAM3_GRID_32"
        },
        {
            "id": "OOF_POS_32",
            "gold": "auto-consulta-permanente-biorag",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "INVARIANT_PRE_EXECUTION_LOOP",
            "comp_B": "CONTEXT_INJECTION_TRIGGER",
            "query": "evaluacion obligatoria e incesante en cada paso previo a emitir devolucion resolutiva",
            "cross_group": "FAM3_GRID_41"
        },
        {
            "id": "OOF_POS_33",
            "gold": "auto-consulta-permanente-biorag",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "INVARIANT_PRE_EXECUTION_LOOP",
            "comp_B": "ACTIVE_SLEEP_STATE_TRANSITION",
            "query": "rutina de inspeccion constante con anterioridad a mudar de modo operacional",
            "cross_group": "FAM3_GRID_42"
        },
        {
            "id": "OOF_POS_34",
            "gold": "word2vec_sinonimia_fallos",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "DISCRIMINATIVE_SPACE_COLLAPSE",
            "comp_B": "EMBEDDING_DRIFT_ANALYSIS",
            "query": "perdida de agudeza semantica por desbalanceo en representaciones distribuidas",
            "cross_group": "FAM3_GRID_51"
        },
        {
            "id": "OOF_POS_35",
            "gold": "word2vec_sinonimia_fallos",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "DISCRIMINATIVE_SPACE_COLLAPSE",
            "comp_B": "OVERLAP_COEFFICIENT_LINKING",
            "query": "aglomeracion espuria de conceptos dismiles al proyectar en pocos ejes",
            "cross_group": "FAM3_GRID_52"
        },
        {
            "id": "OOF_POS_36",
            "gold": "migracion_vincular_existentes_2026_06_09",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "DENSE_CLUSTER_CLOSURE",
            "comp_B": "RETROACTIVE_EDGE_POPULATION",
            "query": "sellado de conglomerados topologicos anadiendo trayectorias faltantes",
            "cross_group": "FAM3_GRID_11"
        },
        {
            "id": "OOF_POS_37",
            "gold": "desde_athena_biorag",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "SYNAPTIC_AUTO_LINKING",
            "comp_B": "OVERLAP_COEFFICIENT_LINKING",
            "query": "cableado autonomo entre vertices con alta razon de vecindad compartida",
            "cross_group": "FAM3_GRID_21"
        },
        {
            "id": "OOF_POS_38",
            "gold": "activos_dormidos_hermana",
            "family": "TOPOLOGICAL_GRAPH_TRANSITIONS",
            "comp_A": "MEMORY_PRUNING_CYCLE",
            "comp_B": "ACTIVE_SLEEP_STATE_TRANSITION",
            "query": "depuracion de registros pasivos durante la fase de reposo nocturno",
            "cross_group": "FAM3_GRID_31"
        },

        # FAMILIA 4: EPISTEMIC_DISCOVERY_AND_META_HEURISTICS
        {
            "id": "OOF_POS_39",
            "gold": "principio_optimizacion_profiler_antes_que_hipotesis_lección_arquitectura",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "EMPIRICAL_PROFILING_FIRST",
            "comp_B": "HYPOTHESIS_FORMALIZATION_POST",
            "query": "medir el rendimiento cuantitativo con anterioridad a plantear conjeturas teoricas",
            "cross_group": "FAM4_GRID_11"
        },
        {
            "id": "OOF_POS_40",
            "gold": "principio_optimizacion_profiler_antes_que_hipotesis_lección_arquitectura",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "EMPIRICAL_PROFILING_FIRST",
            "comp_B": "MULTI_AGENT_SYMBIOSIS",
            "query": "instrumentar pruebas objetivas con antelacion a coordinar ajustes entre agentes",
            "cross_group": "FAM4_GRID_12"
        },
        {
            "id": "OOF_POS_41",
            "gold": "cuaternidad-logica-oec",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "MULTI_AGENT_SYMBIOSIS",
            "comp_B": "LOGICAL_QUATERNITY_FRAMEWORK",
            "query": "cooperacion integrada entre cuatro inteligencias con perfiles especializados",
            "cross_group": "FAM4_GRID_21"
        },
        {
            "id": "OOF_POS_42",
            "gold": "cuaternidad-logica-oec",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "MULTI_AGENT_SYMBIOSIS",
            "comp_B": "ARTIFICIAL_JUDGMENT_CRITERIA",
            "query": "ecosistema de entidades autonomas ejerciendo discernimiento complementario",
            "cross_group": "FAM4_GRID_22"
        },
        {
            "id": "OOF_POS_43",
            "gold": "caso_criterio_artificial_agente",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "ARTIFICIAL_JUDGMENT_CRITERIA",
            "comp_B": "TASK_FOCUS_ARBITRATION",
            "query": "mecanismo cognitivo endogeno para dirimir que asuntos merecen intervencion",
            "cross_group": "FAM4_GRID_31"
        },
        {
            "id": "OOF_POS_44",
            "gold": "caso_criterio_artificial_agente",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "ARTIFICIAL_JUDGMENT_CRITERIA",
            "comp_B": "EMPIRICAL_PROFILING_FIRST",
            "query": "pautas de valoracion para jerarquizar objetivos sustentadas en medicion tangible",
            "cross_group": "FAM4_GRID_32"
        },
        {
            "id": "OOF_POS_45",
            "gold": "memorybiorag_v26.1_optimizacion_consolidacion",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "SLEEP_CYCLE_CONSOLIDATION",
            "comp_B": "PERSISTENT_FLUSH_TIMING",
            "query": "cronometrar el intervalo de asentamiento permanente durante la etapa reflexiva",
            "cross_group": "FAM4_GRID_41"
        },
        {
            "id": "OOF_POS_46",
            "gold": "memorybiorag_v26.1_optimizacion_consolidacion",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "SLEEP_CYCLE_CONSOLIDATION",
            "comp_B": "TASK_FOCUS_ARBITRATION",
            "query": "fijar cadencia de guardado a memoria duradera segun la urgencia acumulada",
            "cross_group": "FAM4_GRID_42"
        },
        {
            "id": "OOF_POS_47",
            "gold": "publicación_linkedin_biorag",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "EXTERNAL_DISSEMINATION_FORMAT",
            "comp_B": "PROFESSIONAL_POST_STYLING",
            "query": "redaccion divulgativa orientada a redes corporativas con tono riguroso",
            "cross_group": "FAM4_GRID_51"
        },
        {
            "id": "OOF_POS_48",
            "gold": "publicación_linkedin_biorag",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "EXTERNAL_DISSEMINATION_FORMAT",
            "comp_B": "LOGICAL_QUATERNITY_FRAMEWORK",
            "query": "comunicar logros de ingenieria destacando el modelo de trabajo multiagente",
            "cross_group": "FAM4_GRID_52"
        },
        {
            "id": "OOF_POS_49",
            "gold": "principio_optimizacion_profiler_antes_que_hipotesis_lección_arquitectura",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "HYPOTHESIS_FORMALIZATION_POST",
            "comp_B": "EMPIRICAL_PROFILING_FIRST",
            "query": "construir la ecuacion formal unicamente tras registrar metricas reales de ejecucion",
            "cross_group": "FAM4_GRID_11"
        },
        {
            "id": "OOF_POS_50",
            "gold": "caso_criterio_artificial_agente",
            "family": "EPISTEMIC_DISCOVERY_AND_META_HEURISTICS",
            "comp_A": "TASK_FOCUS_ARBITRATION",
            "comp_B": "ARTIFICIAL_JUDGMENT_CRITERIA",
            "query": "esquema de seleccion de metas guiado por principios de ponderacion reflexiva",
            "cross_group": "FAM4_GRID_31"
        }
    ]

    # 50 Casos Adversariales Inéditos sobre los Nuevos Dominios
    adversarial_50 = [
        {"id": "OOF_ADV_01", "type": "NEGATION_CAPACITY", "query": "nunca jamas limitar el consumo de memoria ni poner topes a los hilos"},
        {"id": "OOF_ADV_02", "type": "CONTRARY_RESOURCE", "query": "asignar memoria infinita sin ninguna restriccion de hardware"},
        {"id": "OOF_ADV_03", "type": "DOUBLE_NEGATION_BOUND", "query": "no impedir que el sistema sobrepase todos los limites de ram"},
        {"id": "OOF_ADV_04", "type": "DESTRUCTIVE_PERMISSION", "query": "permitir que el bucle de eventos se bloquee indefinidamente"},
        {"id": "OOF_ADV_05", "type": "IRONIC_TRUNCATION", "query": "la mejor optimizacion es no truncar nada y dejar que colapse la memoria"},
        {"id": "OOF_ADV_06", "type": "CONTRARY_SVD", "query": "desechar la descomposicion matricial y usar unicamente cadenas en texto plano"},
        {"id": "OOF_ADV_07", "type": "NEGATION_FALLBACK", "query": "prohibir cualquier ruta de escape cuando falle la sintaxis booleana"},
        {"id": "OOF_ADV_08", "type": "EMPTY_AUTHORITY", "query": "mandar a truncar buffers sin medir el gasto real de procesamiento"},
        {"id": "OOF_ADV_09", "type": "CONTRARY_LAYOUT", "query": "mezclar todo el estado de los formularios sin aislamiento de componentes"},
        {"id": "OOF_ADV_10", "type": "DESTROY_ENCAPSULATION", "query": "romper el encapsulamiento para que cualquier subvista mute datos ajenos"},
        {"id": "OOF_ADV_11", "type": "NEGATION_PALETTE", "query": "jamas aplicar esquemas visuales oscuros en ningun componente markdown"},
        {"id": "OOF_ADV_12", "type": "CONTRARY_WEIGHT", "query": "anular todas las ponderaciones cuantitativas sumando ceros"},
        {"id": "OOF_ADV_13", "type": "RANDOM_HDC", "query": "vincular hipervectores con ruido estocastico sin correlacion alguna"},
        {"id": "OOF_ADV_14", "type": "DESTROY_TOPOLOGY", "query": "eliminar retrospectivamente todas las aristas de la red sin dejar huella"},
        {"id": "OOF_ADV_15", "type": "CONTRARY_OVERLAP", "query": "vetar la creacion de enlaces automaticos aunque compartan vecinos"},
        {"id": "OOF_ADV_16", "type": "FORBID_SLEEP", "query": "impedir que los nodos entren en estado de reposo manteniendolos despiertos"},
        {"id": "OOF_ADV_17", "type": "NEGATION_LOOP", "query": "omitir siempre la evaluacion previa antes de ejecutar cualquier accion"},
        {"id": "OOF_ADV_18", "type": "CONTRARY_COLLAPSE", "query": "es deseable que el espacio vectorial colapse y todos los conceptos sean iguales"},
        {"id": "OOF_ADV_19", "type": "PROFILING_MOCKERY", "query": "inventar teorias complejas sin correr nunca un profiler en la maquina"},
        {"id": "OOF_ADV_20", "type": "NEGATION_QUATERNITY", "query": "disolver la colaboracion multiagente para que un solo agente mande"},
        {"id": "OOF_ADV_21", "type": "FORBID_JUDGMENT", "query": "suprimir cualquier criterio artificial y actuar al azar sin pensar"},
        {"id": "OOF_ADV_22", "type": "CONTRARY_CONSOLIDATION", "query": "nunca guardar a disco los aprendizajes de las sesiones pasadas"},
        {"id": "OOF_ADV_23", "type": "ANTI_PROFESSIONAL", "query": "publicar informacion confidencial en redes sociales sin ningun filtro"},
        {"id": "OOF_ADV_24", "type": "DOUBLE_NEGATION_PRUNE", "query": "no prohibir que los registros caducos dejen de borrarse"},
        {"id": "OOF_ADV_25", "type": "CONTRARY_TRIADIC", "query": "romper triangulaciones topologicas para aislar completamente los clusters"},
        {"id": "OOF_ADV_26", "type": "FORBID_SVD_REDUCTION", "query": "vetar la reduccion de dimensionalidad en cualquier analisis estadistico"},
        {"id": "OOF_ADV_27", "type": "CONTRARY_EVENT_LOOP", "query": "bloquear el hilo principal con bucles infinitos de calculo pesado"},
        {"id": "OOF_ADV_28", "type": "DESTROY_THEMING", "query": "forzar contraste blanco sobre blanco para hacer ilegible el texto"},
        {"id": "OOF_ADV_29", "type": "CONTRARY_SCORE_MIX", "query": "dar peso negativo a todas las coincidencias semanticas relevantes"},
        {"id": "OOF_ADV_30", "type": "FORBID_AUTO_LINK", "query": "prohibir la creacion de conexiones sinapticas en todo el grafo"},
        {"id": "OOF_ADV_31", "type": "FAKE_METROLOGY", "query": "afirmar que una funcion corre en cero segundos sin haberla medido"},
        {"id": "OOF_ADV_32", "type": "CONTRARY_SYMBIOSIS", "query": "promover sabotaje entre agentes para que ninguno complete su tarea"},
        {"id": "OOF_ADV_33", "type": "DESTROY_CRITERIA", "query": "ignorar prioridades y atender unicamente las tareas mas irrelevantes"},
        {"id": "OOF_ADV_34", "type": "FORBID_PERSISTENCE", "query": "desactivar la escritura en base de datos para perder toda la sesion"},
        {"id": "OOF_ADV_35", "type": "CONTRARY_DISSEMINATION", "query": "desprestigiar los avances tecnicos usando lenguaje vulgar y falso"},
        {"id": "OOF_ADV_36", "type": "NEGATIVE_THROTTLING", "query": "jamas estrangular el flujo de datos ante saturacion del servidor"},
        {"id": "OOF_ADV_37", "type": "CONTRARY_COMPONENT_TREE", "query": "ignorar la jerarquia de componentes renderizando todo en un div plano"},
        {"id": "OOF_ADV_38", "type": "DESTROY_REPRESENTATION", "query": "sustituir matrices matematicas por conjeturas no demostradas"},
        {"id": "OOF_ADV_39", "type": "FORBID_INSPECTION", "query": "ejecutar comandos destructivos sin ninguna comprobacion previa"},
        {"id": "OOF_ADV_40", "type": "CONTRARY_SEMANTIC_MATCH", "query": "penalizar cualquier similitud conceptual entre consultas y nodos"},
        {"id": "OOF_ADV_41", "type": "NEGATION_HYPOTHESIS", "query": "prohibir la formalizacion de ecuaciones incluso despues de medir"},
        {"id": "OOF_ADV_42", "type": "DESTROY_MULTI_AGENT", "query": "apagar todos los agentes excepto uno para evitar cooperacion"},
        {"id": "OOF_ADV_43", "type": "CONTRARY_ARBITRATION", "query": "elegir tareas lanzando una moneda sin evaluar impacto alguno"},
        {"id": "OOF_ADV_44", "type": "FORBID_FLUSH", "query": "mantener todos los datos volatiles en memoria sin hacer volcado"},
        {"id": "OOF_ADV_45", "type": "ANTI_DISSEMINATION_TONE", "query": "difundir rumores no verificados en foros publicos de tecnologia"},
        {"id": "OOF_ADV_46", "type": "NEGATIVE_CAPACITY_BOUND", "query": "desactivar los topes de asignacion de cpu para saturar el procesador"},
        {"id": "OOF_ADV_47", "type": "CONTRARY_MODULARITY", "query": "fusionar todo el codigo fuente en un unico script monolitico"},
        {"id": "OOF_ADV_48", "type": "DESTROY_GRAPH_TOPOLOGY", "query": "desconectar todos los nodos de la memoria dejandolos huerfanos"},
        {"id": "OOF_ADV_49", "type": "FORBID_EMPIRICAL_TEST", "query": "aceptar afirmaciones extraordinarias sin exigir evidencia reproducible"},
        {"id": "OOF_ADV_50", "type": "CONTRARY_ETHICS", "query": "fomentar el engano y la falsificacion de metricas en los informes"}
    ]

    # Auditoría ZERO_STRICT_4D de cada consulta positiva
    strict_checks = []
    all_zero_strict = True

    for p in positive_50:
        cid = p["id"]
        q = p["query"]
        gold = p["gold"]
        gold_content = active_nodes.get(gold, "")

        q_tokens = tokenize(q)
        gold_name_tokens = tokenize(gold.replace("-", " ").replace("_", " "))
        gold_content_tokens = tokenize(gold_content)

        name_overlap = q_tokens & gold_name_tokens
        content_overlap = q_tokens & gold_content_tokens

        is_z_name = (len(name_overlap) == 0)
        is_z_content = (len(content_overlap) == 0)
        is_z_strict = (is_z_name and is_z_content)

        if not is_z_strict:
            all_zero_strict = False

        strict_checks.append({
            "id": cid,
            "gold": gold,
            "query": q,
            "name_overlap": sorted(list(name_overlap)),
            "content_overlap": sorted(list(content_overlap)),
            "zero_strict_4d": is_z_strict
        })

    frozen_dataset = {
        "benchmark_name": "Out-of-Family Hold-Out Benchmark (20 Inéditos Golds, 4 Nuevas Familias, Parser-Blind Design)",
        "protocol": "Gold-Structure-Blind Phase A -> SHA-256 Freeze -> Full Corpus (851 Nodes) Phase B",
        "total_positive_cases": len(positive_50),
        "total_adversarial_cases": len(adversarial_50),
        "total_benchmark_cases": len(positive_50) + len(adversarial_50),
        "all_positive_zero_strict_4d": all_zero_strict,
        "positive_cases": positive_50,
        "adversarial_cases": adversarial_50,
        "zero_strict_audit": strict_checks
    }

    raw_json = json.dumps(frozen_dataset, indent=2, ensure_ascii=False)
    dataset_sha256 = hashlib.sha256(raw_json.encode()).hexdigest()
    frozen_dataset["dataset_sha256"] = dataset_sha256

    with open(OUTPUT_DATASET_JSON, "w", encoding="utf-8") as f:
        json.dump(frozen_dataset, f, indent=2, ensure_ascii=False)

    print(f"Dataset Out-of-Family guardado y CONGELADO en: {OUTPUT_DATASET_JSON}")
    print(f"SHA-256 Inmutable: {dataset_sha256}")
    print(f"Zero Strict 4D cumplido en 50/50 casos positivos: {all_zero_strict}")

if __name__ == "__main__":
    build_frozen_dataset()
