#!/usr/bin/env python3
"""Sondeo sintético de fecha, traza de paráfrasis, aviso de brecha y tamaño MCP."""
from __future__ import annotations
import asyncio, hashlib, json, os, sqlite3, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.diagnosticar_rutas_creacion_densidad_e3 import (
    GRAPH_SNAPSHOT_SCOPE, StdioSession, full_graph_snapshot,
)
from scripts.replicar_hipotesis_etiquetas_controles_e3 import parse_tool_result

TARGET = "synthetic_focus_node"
FIXED_EPOCH = 1793059200.0  # mismo reloj fijo que la sesión MCP stdio
FIXED_UTC = datetime.fromtimestamp(FIXED_EPOCH, timezone.utc)

# Todas las cadenas siguientes son fixture sintético; se preservan solo en evidencia privada.
NODES = [
    (TARGET, "A synthetic archive records a quartz reading and a cobalt impulse in a controlled laboratory fixture."),
    ("neighbor_alpha", "Synthetic adjacent note: calibration and instrument context, record one."),
    ("neighbor_bravo", "Synthetic adjacent note: calibration and instrument context, record two."),
    ("neighbor_charlie", "Synthetic adjacent note: calibration and instrument context, record three."),
    ("neighbor_delta", "Synthetic adjacent note: calibration and instrument context, record four."),
    ("neighbor_echo", "Synthetic adjacent note: calibration and instrument context, record five."),
    ("neighbor_foxtrot", "Synthetic adjacent note: calibration and instrument context, record six."),
    ("neighbor_golf", "Synthetic adjacent note: calibration and instrument context, record seven."),
    ("neighbor_hotel", "Synthetic adjacent note: calibration and instrument context, record eight."),
]

CASES = [
    {"case_id":"direct_with_unrelated_paraphrase", "query":"quartz", "parafrasis":"unrelated botanical phrase", "keywords":"quartz,archive", "asociados":True, "context_window":0, "limite":5, "asociaciones_max":0, "completo":True},
    {"case_id":"paraphrase_route_candidate", "query":"qzxnovelquery", "parafrasis":"quartz", "keywords":"granite,orchid", "asociados":True, "context_window":0, "limite":5, "asociaciones_max":0, "completo":True},
    {"case_id":"compact_payload", "query":"quartz", "parafrasis":None, "keywords":"quartz,archive", "asociados":False, "context_window":0, "limite":1, "asociaciones_max":0, "completo":False},
    {"case_id":"expanded_associations_context", "query":"quartz", "parafrasis":None, "keywords":"quartz,archive", "asociados":True, "context_window":2, "limite":10, "asociaciones_max":0, "completo":True},
]


def seed_db(path: Path) -> None:
    from core.memory import consolidation
    from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    memory=SQLiteMemoryBioRAG(str(path))
    try:
        cat=memory._resolver_categoria_id("General")
        exact=normalizar_sustantivos_clave_exacto("fixture,synthetic")
        folded=normalizar_sustantivos_clave(exact)
        for concept,content in NODES:
            consolidation.fusionar_en_largo_plazo(memory,concept,content,"",cat,0.0,folded,exact)
        for concept,_ in NODES[1:]:
            memory.establecer_asociacion(TARGET,concept)
        memory.conn.execute("UPDATE largo_plazo SET creado_en=?",(FIXED_EPOCH,))
        memory.conn.commit()
        memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        memory.cerrar_sistema()


def get_result_dicts(result: dict) -> list[dict]:
    return result.get("resultados",[]) if isinstance(result.get("resultados",[]),list) else []


def audit_date_storage(path: Path) -> dict:
    uri="file:"+str(path.resolve())+"?mode=ro"
    con=sqlite3.connect(uri,uri=True)
    try:
        objects={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        stored=con.execute("SELECT concepto,creado_en FROM largo_plazo ORDER BY concepto").fetchall()
        probes={}
        sqls={
            "code_path_table_and_column":("SELECT l.concepto,l.creado_en,c.nombre FROM largo_plazo l JOIN categorias c ON c.id=l.categoria WHERE l.concepto=?",TARGET),
            "current_table_old_column":("SELECT l.concepto,l.creado_en,c.nombre FROM largo_plazo l JOIN categories c ON c.id=l.categoria WHERE l.concepto=?",TARGET),
            "schema_name_join":("SELECT l.concepto,l.creado_en,c.name FROM largo_plazo l JOIN categories c ON c.id=l.categoria WHERE l.concepto=?",TARGET),
        }
        for name,(sql,param) in sqls.items():
            try: probes[name]={"row_count":len(con.execute(sql,(param,)).fetchall()),"error_type":None,"error":None}
            except sqlite3.Error as exc: probes[name]={"row_count":None,"error_type":type(exc).__name__,"error":str(exc)}
        return {
            "schema_objects_relevant":sorted(x for x in objects if x in {"categories","categorias"}),
            "target_stored_created_en":next((float(ts) for concept,ts in stored if concept==TARGET and ts is not None),None),
            "expected_fixture_created_en":FIXED_EPOCH,
            "date_join_probes":probes,
            "stored_row_count":len(stored),
        }
    finally: con.close()


async def run_case(seed: Path,temp_root: Path,spec: dict) -> dict:
    db=temp_root/f"copy_{spec['case_id']}.db"
    src,dst=sqlite3.connect(str(seed)),sqlite3.connect(str(db))
    try: src.backup(dst)
    finally: dst.close();src.close()
    snapshots={"before_stdio":full_graph_snapshot(db)}
    raw_text="";parsed={};error=None;open_result=None
    try:
        async with StdioSession(db,temp_root) as session:
            open_result=await session.call("sustantivos",{"concepto":TARGET})
            snapshots["after_open"] = full_graph_snapshot(db)
            args={
                "query":spec["query"],"sustantivos_clave":spec["keywords"],
                "parafrasis":spec["parafrasis"],"completo":spec["completo"],
                "asociados":spec["asociados"],"asociaciones_max":spec["asociaciones_max"],
                "context_window":spec["context_window"],"limite":spec["limite"],
                "usar_inferencia":False,"forzar_rafaga":False,
            }
            mcp_result=await session._session.call_tool("recordar",arguments=args)
            raw_text="\n".join(getattr(block,"text","") for block in (getattr(mcp_result,"content",None) or []))
            parsed=parse_tool_result(mcp_result)
            snapshots["after_recordar"] = full_graph_snapshot(db)
    except Exception as exc:
        error={"type":type(exc).__name__,"message":str(exc)[:500]}
    items=get_result_dicts(parsed)
    target=next((item for item in items if item.get("concepto")==TARGET),None)
    try: json_offset=raw_text.index("{")
    except ValueError: json_offset=len(raw_text)
    date_rows=[{"concepto":item.get("concepto"),"timestamp_creado":item.get("timestamp_creado"),"fecha_legible":item.get("fecha_legible")} for item in items]
    return {
        "case_id":spec["case_id"],"input":spec,
        "opening_tool_status":(open_result or {}).get("status"),
        "opening_tool_mcp_error":bool((open_result or {}).get("_mcp_is_error")),
        "response_status":parsed.get("status"),"mcp_is_error":bool(parsed.get("_mcp_is_error")),
        "response_shape_present":"resultados" in parsed and "total" in parsed,
        "total":parsed.get("total"),"primary_count":len(items),
        "target_found":target is not None,"target_score":target.get("score_hibrido") if target else None,
        "target_trace":parsed.get("trazabilidad",{}),
        "gap_warning_present":"BRECHA DE CONOCIMIENTO" in raw_text,
        "warning_prefix":raw_text[:json_offset],
        "raw_response_size_bytes":len(raw_text.encode("utf-8")),
        "json_payload_size_bytes":len(json.dumps(parsed,ensure_ascii=False,separators=(",",":")).encode("utf-8")),
        "result_dates":date_rows,
        "association_count_target":len((target or {}).get("asociaciones_enriquecidas",[])),
        "context_count":len(parsed.get("contexto_expandido",[])),
        "python_exception":error,
        "graph_snapshots":snapshots,
        "date_storage_audit":audit_date_storage(db),
        "raw_response_text":raw_text,
        "parsed_response":parsed,
    }


def public_summary(report:dict)->dict:
    rows=report["cases"]
    direct=next(row for row in rows if row["case_id"]=="direct_with_unrelated_paraphrase")
    paraphrase=next(row for row in rows if row["case_id"]=="paraphrase_route_candidate")
    compact=next(row for row in rows if row["case_id"]=="compact_payload")
    expanded=next(row for row in rows if row["case_id"]=="expanded_associations_context")
    date_fields=[r for row in rows for r in row["result_dates"]]
    return {
        "synthetic_only":True,"engine_patch":False,"user_databases_opened":0,"e4_advanced":False,
        "case_count":len(rows),"python_exceptions_escaping_mcp_calls":sum(bool(r["python_exception"]) for r in rows),
        "mcp_error_flags":sum(r["mcp_is_error"] for r in rows),
        "response_shape_cases":sum(r["response_shape_present"] for r in rows),
        "date_join_reproduction_operational_errors":sum(r["date_storage_audit"]["date_join_probes"]["code_path_table_and_column"]["error_type"]=="OperationalError" for r in rows),
        "result_bearing_cases_with_reproduced_date_join_failure":sum(r["target_found"] and r["date_storage_audit"]["date_join_probes"]["code_path_table_and_column"]["error_type"]=="OperationalError" for r in rows),
        "schema_name_join_success_cases":sum(r["date_storage_audit"]["date_join_probes"]["schema_name_join"]["row_count"]>0 for r in rows),
        "direct_case_target_found":direct["target_found"],
        "direct_case_paraphrase_trace":direct["target_trace"].get("capa_parafrasis"),
        "paraphrase_candidate_target_found":paraphrase["target_found"],
        "paraphrase_candidate_trace":paraphrase["target_trace"].get("capa_parafrasis"),
        "gap_warning_with_results_cases":sum(r["gap_warning_present"] and r["primary_count"]>0 for r in rows),
        "gap_warning_cases":sum(r["gap_warning_present"] for r in rows),
        "date_fields_present_rows":sum(bool(r["timestamp_creado"]) and bool(r["fecha_legible"]) for r in date_fields),
        "date_rows_observed":len(date_fields),
        "target_created_en_matches_fixed_epoch":all(r["date_storage_audit"]["target_stored_created_en"]==FIXED_EPOCH for r in rows),
        "code_path_date_join_failure_types":sorted({r["date_storage_audit"]["date_join_probes"]["code_path_table_and_column"]["error_type"] for r in rows if r["date_storage_audit"]["date_join_probes"]["code_path_table_and_column"]["error_type"]}),
        "code_path_date_join_failure_messages":sorted({r["date_storage_audit"]["date_join_probes"]["code_path_table_and_column"]["error"] for r in rows if r["date_storage_audit"]["date_join_probes"]["code_path_table_and_column"]["error"]}),
        "current_table_old_column_failure_types":sorted({r["date_storage_audit"]["date_join_probes"]["current_table_old_column"]["error_type"] for r in rows if r["date_storage_audit"]["date_join_probes"]["current_table_old_column"]["error_type"]}),
        "current_schema_name_join_rows_per_copy":sorted({r["date_storage_audit"]["date_join_probes"]["schema_name_join"]["row_count"] for r in rows}),
        "current_schema_name_join_errors":sum(r["date_storage_audit"]["date_join_probes"]["schema_name_join"]["error_type"] is not None for r in rows),
        "timezone_in_date_string":False,
        "compact_raw_bytes":compact["raw_response_size_bytes"],
        "expanded_raw_bytes":expanded["raw_response_size_bytes"],
        "expanded_to_compact_size_ratio":round(expanded["raw_response_size_bytes"]/max(1,compact["raw_response_size_bytes"]),3),
        "compact_association_count":compact["association_count_target"],
        "expanded_association_count":expanded["association_count_target"],
        "compact_context_count":compact["context_count"],
        "expanded_context_count":expanded["context_count"],
        "snapshot_query_errors":sum(len(s.get("query_errors",{})) for r in rows for s in r["graph_snapshots"].values()),
        "snapshot_scope":{"full_row_tables":GRAPH_SNAPSHOT_SCOPE["full_row_tables"],"row_projections":GRAPH_SNAPSHOT_SCOPE["row_projections"],"complete_sqlite_database_snapshot":False},
    }


async def execute()->dict:
    os.environ["TZ"]="UTC"
    if hasattr(time,"tzset"): time.tzset()
    old_auto=os.environ.get("BIORAG_MCP_AUTO_PARAFRASIS")
    os.environ["BIORAG_MCP_AUTO_PARAFRASIS"]="0"
    try:
        with tempfile.TemporaryDirectory(prefix="e3_feedback_stdio_") as temp:
            root=Path(temp);seed=root/"seed.db";seed_db(seed)
            rows=[]
            for spec in CASES: rows.append(await run_case(seed,root,spec))
        return {"experiment":"E3 synthetic MCP response feedback signals","synthetic_only":True,"user_databases_opened":0,"engine_patch":False,"e4_advanced":False,"fixed_utc":FIXED_UTC.isoformat(),"fixed_epoch":FIXED_EPOCH,"cases":rows,"graph_snapshot_scope":{"full_row_tables":GRAPH_SNAPSHOT_SCOPE["full_row_tables"],"row_projections":GRAPH_SNAPSHOT_SCOPE["row_projections"],"complete_sqlite_database_snapshot":False}}
    finally:
        if old_auto is None: os.environ.pop("BIORAG_MCP_AUTO_PARAFRASIS",None)
        else: os.environ["BIORAG_MCP_AUTO_PARAFRASIS"]=old_auto


def main()->None:
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--evidence-dir",required=True);args=p.parse_args()
    out=Path(args.evidence_dir);private=(ROOT/".private_evidence").resolve();out=(out if out.is_absolute() else ROOT/out).resolve()
    if private not in out.parents or out.exists():raise ValueError("Use a new directory under .private_evidence/")
    report=asyncio.run(execute());summary=public_summary(report);report["public_aggregate"]=summary
    out.mkdir(parents=True,exist_ok=False)
    manifest={"nodes":NODES,"cases":CASES,"fixed_utc":FIXED_UTC.isoformat(),"purpose":"synthetic feedback signals only"}
    for filename,obj in (("stdio_cases_full.json",report),("synthetic_manifest.json",manifest)):
        data=(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode();(out/filename).write_bytes(data)
    hashes={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ("stdio_cases_full.json","synthetic_manifest.json")}
    (out/"SHA256SUMS.json").write_text(json.dumps(hashes,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))

if __name__=="__main__": main()
