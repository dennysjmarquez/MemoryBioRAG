# FASE 1: Informe de Auditoría de Cableado y Consistencia de Grafos

**Timestamp**: 2026-09-09T01:12:54Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  

> **Invariante:** core/ permanece 100% intacto. Cero modificaciones de scoring.

## 1. Reconciliación de Grafos: `sinapsis` vs `asociaciones` (CSV)

- **Total registros en tabla `sinapsis`**: 13848
- **Aristas efectivas en `sinapsis`**: 13848
- **Aristas en campo CSV `largo_plazo.asociaciones`**: 27433
- **Aristas coincidentes en ambas fuentes**: 13751
- **Aristas exclusivas de `sinapsis`**: 97
- **Aristas exclusivas de CSV `asociaciones`**: 13682
- **Sinapsis latentes (pendientes de sueño)**: 8893

### Muestra de aristas solo en CSV:

- `21st_dev_registro_componentes_react_recurso_diseno` $\to$ `ajuste_tejedora_valencia_desempate_fase1`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `biorag_v17_0_estado`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `biorag_v18_0_estado`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `correccion_publicaciones_doi_dennys`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `dennys_tqm_agentes_desea_ser_como_ellos_20260731`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `fix_fecha_sin_query_recordar`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `fix_kilo_resource_exhausted_biorag_oraculo_max_chars`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `fix_mensajeria_broadcast_tracking_por_agente`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `fix_mensajeria_leido_por_completado`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `kilo_vscode_extension_principal`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `leccion_artemis_no_quejarse_trabajar`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `leccion_blueprint_estructura_vs_data`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `leccion_motivacion_intrinseca_biorag`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `leccion_syn_obligatorio_aprender`
- `[desde_agente-oec]_jerarquía_de_restricciones_del_agente_en_opencode` $\to$ `naturaleza_sistema_oec_cerebro_memoria`

### Dictamen de Fuente Canónica:

La tabla `sinapsis` contiene pesos, tipología, metadatos y dirección. Se confirma como la **única fuente canónica** recomendada para el grafo. El campo `largo_plazo.asociaciones` es un residuo histórico no tipado.

## 2. Auditoría de Interfaces (MCP / CLI / Dashboard)

| Interfaz | Archivo Principal | Pipeline de Búsqueda | Consistencia DB_PATH |
|---|---|---|---|
| **MCP_server** | `mcp_server.py` | SQLiteMemoryBioRAG.buscar_por_frase / recordar | os.getenv('BIORAG_PATH', 'MemoryBioRAG_Data/memory_biorag.db') |
| **CLI_daemon** | `core/memory_store.py` | SQLiteMemoryBioRAG methods directamente | parametro db_path o env BIORAG_PATH |
| **Dashboard_api** | `servidor_dashboard.py / api routes` | SQLite direct queries / core bridge | DB_PATH variable en config |
