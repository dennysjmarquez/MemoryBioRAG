import os
import sys
import json
import time
import sqlite3
from collections import deque
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
DB_PATH = os.path.join(PROJECT_ROOT, "MemoryBioRAG_Data", "memory_biorag.db")

# Dashboard ports from env (with defaults)
DASHBOARD_BACKEND_PORT = int(os.environ.get('BIORAG_DASHBOARD_BACKEND_PORT', '8001'))
DASHBOARD_FRONTEND_PORT = int(os.environ.get('BIORAG_DASHBOARD_FRONTEND_PORT', '3000'))

# Add project root to path FIRST so config module can be imported
sys.path.insert(0, PROJECT_ROOT)

# Load .env.local before reading env vars
from config import _load_env_local
_load_env_local()

cerebro = None  # Use raw SQLite directly

app = FastAPI(title="BioRAG Neuro-Visor v2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ts_now():
    return time.time()


def ts_to_str(ts):
    if not ts:
        return "nunca"
    diff = ts_now() - ts
    if diff < 60:
        return f"hace {int(diff)}s"
    elif diff < 3600:
        return f"hace {int(diff/60)}min"
    elif diff < 86400:
        return f"hace {int(diff/3600)}h {int((diff%3600)/60)}min"
    else:
        return f"hace {int(diff/86400)}d"


# ============================================================
# VISTA 1: ESTADO DE LA CORTEZA
# ============================================================

@app.get("/api/corteza/estado")
def corteza_estado():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'")
    activos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='dormido'")
    dormidos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sinapsis")
    directas = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sinapsis_latentes")
    latentes = c.fetchone()[0]

    c.execute("SELECT energia_sinaptica FROM metricas_rendimiento ORDER BY rowid DESC LIMIT 1")
    row = c.fetchone()
    energia = round(row[0], 2) if row else 0
    energia_max = max(energia * 1.5, 500)
    energia_pct = round((energia / energia_max) * 100, 1) if energia_max > 0 else 0

    c.execute("SELECT timestamp FROM metricas_rendimiento ORDER BY rowid DESC LIMIT 1")
    row = c.fetchone()
    ultimo_sueno = ts_to_str(row[0]) if row else "desconocido"

    c.execute("SELECT latencia_busqueda_ms FROM metricas_rendimiento ORDER BY rowid DESC LIMIT 1")
    row = c.fetchone()
    latencia = round(row[0], 2) if row else 0

    c.execute("""
        SELECT cat.name,
               SUM(CASE WHEN l.estado = 'activo' THEN 1 ELSE 0 END) as activos,
               SUM(CASE WHEN l.estado = 'dormido' THEN 1 ELSE 0 END) as dormidos
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
        GROUP BY cat.name
        ORDER BY (activos + dormidos) DESC
    """)
    categorias = [{"nombre": r[0], "activos": r[1], "dormidos": r[2], "total": r[1] + r[2]} for r in c.fetchall()]

    c.execute("""
        SELECT td.nombre as eje, ds.name as valor, COUNT(*) as cnt
        FROM largo_plazo_dimensiones lp
        JOIN dimensiones_semanticas ds ON lp.dimension_id = ds.id
        JOIN tipos_dimension td ON ds.tipo_id = td.id
        GROUP BY td.nombre, ds.name
        ORDER BY cnt DESC
        LIMIT 10
    """)
    dimensiones_top = [{"eje": r[0], "valor": r[1], "count": r[2]} for r in c.fetchall()]

    c.execute("SELECT COUNT(*) FROM largo_plazo_dimensiones")
    total_dim_mappings = c.fetchone()[0]

    conn.close()

    return {
        "activos": activos,
        "dormidos": dormidos,
        "directas": directas,
        "latentes": latentes,
        "energia": energia,
        "energia_max": round(energia_max, 2),
        "energia_pct": energia_pct,
        "ultimo_sueno": ultimo_sueno,
        "latencia_ms": latencia,
        "categorias": categorias,
        "dimensiones_top": dimensiones_top,
        "total_dim_mappings": total_dim_mappings,
        "version": "v18.1"
    }


@app.get("/api/corteza/actividad")
def corteza_actividad(dias: int = 7):
    conn = get_db()
    c = conn.cursor()

    cutoff = ts_now() - (dias * 86400)

    c.execute("""
        SELECT mc.timestamp, mc.nodos_consolidados, mc.nodos_dormidos_ciclo,
               mc.sinapsis_creadas, mc.sinapsis_podadas, cat.name, mc.ratio_consolidacion
        FROM metricas_cognitivas mc
        LEFT JOIN categories cat ON mc.categoria_dominante_id = cat.id
        WHERE mc.timestamp >= ?
        ORDER BY mc.timestamp ASC
    """, (cutoff,))
    ciclos = []
    for r in c.fetchall():
        ciclos.append({
            "timestamp": r[0],
            "fecha": ts_to_str(r[0]),
            "consolidados": r[1],
            "dormidos": r[2],
            "sinapsis_creadas": r[3],
            "sinapsis_podadas": r[4],
            "categoria_dominante": r[5],
            "ratio": r[6]
        })

    c.execute("""
        SELECT timestamp, energia_sinaptica, total_nodos, total_dormidos, nodos_activos, latencia_busqueda_ms
        FROM metricas_rendimiento
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
    """, (cutoff,))
    # Build sorted list of ciclo timestamps for binary search
    ciclo_timestamps = sorted([ciclo["timestamp"] for ciclo in ciclos])
    ciclo_by_ts = {ciclo["timestamp"]: ciclo for ciclo in ciclos}

    energia_hist = []
    for r in c.fetchall():
        ts = r[0]

        # Find the most recent ciclo that is <= ts (or closest within 60s)
        ciclo_match = None
        for ct in reversed(ciclo_timestamps):
            if ct <= ts + 1:  # Allow 1 second tolerance
                ciclo_match = ciclo_by_ts[ct]
                break

        # Get concepts from bridge table (metricas_cognitivas_nodos)
        conceptos = []
        categoria_dominante = None
        metrica_id = None
        if ciclo_match:
            # Find metrica_id for this ciclo
            c.execute("""
                SELECT id FROM metricas_cognitivas
                WHERE ABS(timestamp - ?) < 2
                LIMIT 1
            """, (ciclo_match["timestamp"],))
            mc_row = c.fetchone()
            if mc_row:
                metrica_id = mc_row[0]
                c.execute("""
                    SELECT l.concepto, l.contenido
                    FROM metricas_cognitivas_nodos mn
                    JOIN largo_plazo l ON mn.largo_plazo_id = l.id
                    WHERE mn.metrica_id = ? AND mn.accion IN ('nuevo', 'actualizado')
                    ORDER BY mn.peso_nuevo DESC
                    LIMIT 3
                """, (metrica_id,))
                conceptos = [{"concepto": row[0], "contenido": (row[1] or "")[:120]} for row in c.fetchall()]

            # Use precalculated categoria_dominante from metricas_cognitivas
            categoria_dominante = ciclo_match.get("categoria_dominante")

        energia_hist.append({
            "timestamp": ts,
            "energia": round(r[1], 2),
            "total_nodos": r[2],
            "dormidos": r[3],
            "activos": r[4],
            "latencia_ms": r[5],
            "conceptos": conceptos,
            "categoria_dominante": categoria_dominante,
            "metrica_id": metrica_id
        })

    conn.close()
    return {"ciclos": ciclos, "energia_historial": energia_hist}


# ============================================================
# VISTA 2: EXPLORAR CONCEPTO
# ============================================================

@app.get("/api/nodo/{concepto}")
def nodo_detalle(concepto: str):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT l.id, l.concepto, l.contenido, l.peso_sinaptico, l.estado,
               l.sinonimos, l.ultimo_acceso, l.creado_en,
               cat.name as categoria
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE l.concepto = ?
    """, (concepto,))
    r = c.fetchone()
    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Nodo '{concepto}' no encontrado")

    c.execute("SELECT COUNT(*) FROM sinapsis WHERE origen=? OR destino=?", (concepto, concepto))
    num_conexiones = c.fetchone()[0]

    c.execute("""
        SELECT ds.name, td.nombre
        FROM largo_plazo_dimensiones lp
        JOIN dimensiones_semanticas ds ON lp.dimension_id = ds.id
        JOIN tipos_dimension td ON ds.tipo_id = td.id
        WHERE lp.concepto = ?
    """, (concepto,))
    dimensiones = {}
    for row in c.fetchall():
        eje, valor = row[1], row[0]
        if eje not in dimensiones:
            dimensiones[eje] = []
        dimensiones[eje].append(valor)

    c.execute("""
        SELECT gs.nombre, gs.fuente
        FROM nodo_grupos_semanticos ng
        JOIN grupos_semanticos gs ON ng.grupo_id = gs.id
        WHERE ng.concepto = ?
    """, (concepto,))
    grupos = [{"nombre": r[0], "fuente": r[1]} for r in c.fetchall()]

    conn.close()

    return {
        "id": r[0],
        "concepto": r[1],
        "contenido": r[2] or "",
        "peso": round(r[3], 3) if r[3] else 1.0,
        "estado": r[4] or "activo",
        "sinonimos": r[5] or "",
        "ultimo_acceso": r[6],
        "creado_en": r[7],
        "categoria": r[8] or "General",
        "num_conexiones": num_conexiones,
        "dimensiones": dimensiones,
        "grupos": grupos
    }


@app.get("/api/nodo/{concepto}/ego")
def nodo_ego_graph(concepto: str, limit: int = 50):
    """Retorna nodo central + sus conexiones directas con metadata enriquecida."""
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT l.id, l.concepto, l.contenido, l.peso_sinaptico, l.estado,
               l.sinonimos, l.ultimo_acceso, l.creado_en,
               cat.name as categoria
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE l.concepto = ?
    """, (concepto,))
    r = c.fetchone()
    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Nodo '{concepto}' no encontrado")

    center = {
        "id": r[0],
        "concepto": r[1],
        "contenido": r[2] or "",
        "peso": round(r[3], 3) if r[3] else 1.0,
        "estado": r[4] or "activo",
        "sinonimos": r[5] or "",
        "ultimo_acceso": r[6],
        "creado_en": r[7],
        "categoria": r[8] or "General"
    }

    c.execute("""
        SELECT ds.name, td.nombre
        FROM largo_plazo_dimensiones lp
        JOIN dimensiones_semanticas ds ON lp.dimension_id = ds.id
        JOIN tipos_dimension td ON ds.tipo_id = td.id
        WHERE lp.concepto = ?
    """, (concepto,))
    dimensiones = {}
    for row in c.fetchall():
        eje, valor = row[1], row[0]
        if eje not in dimensiones:
            dimensiones[eje] = []
        dimensiones[eje].append(valor)
    center["dimensiones"] = dimensiones

    c.execute("""
        SELECT gs.nombre, gs.fuente
        FROM nodo_grupos_semanticos ng
        JOIN grupos_semanticos gs ON ng.grupo_id = gs.id
        WHERE ng.concepto = ?
    """, (concepto,))
    center["grupos"] = [{"nombre": row[0], "fuente": row[1]} for row in c.fetchall()]

    # Sinapsis directas: salientes
    c.execute("""
        SELECT s.origen, s.destino, s.peso, s.tipo, s.creado_en, s.ultimo_uso,
               l.peso_sinaptico, l.estado, cat.name as categoria, l.contenido
        FROM sinapsis s
        LEFT JOIN largo_plazo l ON s.destino = l.concepto
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE s.origen = ?
    """, (concepto,))
    salientes = []
    for row in c.fetchall():
        preview = (row[9] or "")[:100]
        salientes.append({
            "direccion": "saliente",
            "destino_concepto": row[1],
            "peso": round(row[2], 3) if row[2] else 0.5,
            "tipo": row[3] or "co_ocurrencia",
            "creado_en": row[4],
            "ultimo_uso": row[5],
            "destino_categoria": row[8] or "General",
            "destino_peso": round(row[6], 3) if row[6] else 1.0,
            "destino_estado": row[7] or "activo",
            "destino_preview": preview
        })

    # Sinapsis directas: entrantes
    c.execute("""
        SELECT s.origen, s.destino, s.peso, s.tipo, s.creado_en, s.ultimo_uso,
               l.peso_sinaptico, l.estado, cat.name as categoria, l.contenido
        FROM sinapsis s
        LEFT JOIN largo_plazo l ON s.origen = l.concepto
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE s.destino = ?
    """, (concepto,))
    entrantes = []
    for row in c.fetchall():
        preview = (row[9] or "")[:100]
        entrantes.append({
            "direccion": "entrante",
            "destino_concepto": row[0],
            "peso": round(row[2], 3) if row[2] else 0.5,
            "tipo": row[3] or "co_ocurrencia",
            "creado_en": row[4],
            "ultimo_uso": row[5],
            "destino_categoria": row[8] or "General",
            "destino_peso": round(row[6], 3) if row[6] else 1.0,
            "destino_estado": row[7] or "activo",
            "destino_preview": preview
        })

    # Combinar y deduplicar (si A→B y B→A existen, mostrar como bidireccional)
    all_conns = {}
    for s in salientes:
        key = s["destino_concepto"]
        if key in all_conns:
            all_conns[key]["direccion"] = "bidireccional"
        else:
            all_conns[key] = s
    for e in entrantes:
        key = e["destino_concepto"]
        if key in all_conns:
            all_conns[key]["direccion"] = "bidireccional"
        else:
            all_conns[key] = e

    connections = sorted(all_conns.values(), key=lambda x: x["peso"], reverse=True)[:limit]

    # Sinapsis latentes
    c.execute("""
        SELECT sl.origen, sl.destino, sl.peso_atenuado, sl.saltos,
               l.peso_sinaptico, l.estado, cat.name as categoria, l.contenido
        FROM sinapsis_latentes sl
        LEFT JOIN largo_plazo l ON
            CASE WHEN sl.origen = ? THEN sl.destino ELSE sl.origen END = l.concepto
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE sl.origen = ? OR sl.destino = ?
        ORDER BY sl.peso_atenuado DESC
        LIMIT 30
    """, (concepto, concepto, concepto))
    latentes = []
    for row in c.fetchall():
        destino = row[1] if row[0] == concepto else row[0]
        preview = (row[7] or "")[:80]
        latentes.append({
            "destino_concepto": destino,
            "peso": round(row[2], 3) if row[2] else 0.5,
            "saltos": row[3],
            "destino_categoria": row[6] or "General",
            "destino_preview": preview
        })

    conn.close()
    return {
        "center": center,
        "connections": connections,
        "latentes": latentes,
        "stats": {
            "total_conexiones": len(connections),
            "salientes": len(salientes),
            "entrantes": len(entrantes),
            "latentes": len(latentes)
        }
    }


@app.get("/api/nodo/{concepto}/vecinos")
def nodo_vecinos(concepto: str, limit: int = 50):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT s.destino, s.peso, s.tipo, l.peso_sinaptico, l.estado, cat.name
        FROM sinapsis s
        LEFT JOIN largo_plazo l ON s.destino = l.concepto
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE s.origen = ?
        ORDER BY s.peso DESC
        LIMIT ?
    """, (concepto, limit))
    salientes = []
    for r in c.fetchall():
        salientes.append({
            "concepto": r[0], "peso": round(r[1], 3) if r[1] else 0.5,
            "tipo": r[2] or "co_ocurrencia",
            "peso_nodo": round(r[3], 3) if r[3] else 1.0,
            "estado": r[4] or "activo",
            "categoria": r[5] or "General"
        })

    c.execute("""
        SELECT s.origen, s.peso, s.tipo, l.peso_sinaptico, l.estado, cat.name
        FROM sinapsis s
        LEFT JOIN largo_plazo l ON s.origen = l.concepto
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE s.destino = ?
        ORDER BY s.peso DESC
        LIMIT ?
    """, (concepto, limit))
    entrantes = []
    for r in c.fetchall():
        entrantes.append({
            "concepto": r[0], "peso": round(r[1], 3) if r[1] else 0.5,
            "tipo": r[2] or "co_ocurrencia",
            "peso_nodo": round(r[3], 3) if r[3] else 1.0,
            "estado": r[4] or "activo",
            "categoria": r[5] or "General"
        })

    conn.close()
    return {"concepto": concepto, "salientes": salientes, "entrantes": entrantes}


# ============================================================
# BÚSQUEDA
# ============================================================

@app.get("/api/buscar")
def buscar_conceptos(q: str = "", limit: int = 20):
    if not q or len(q.strip()) < 2:
        return {"resultados": []}

    conn = get_db()
    c = conn.cursor()

    if cerebro is not None:
        try:
            resultados, total = cerebro.buscar_por_frase(q, profundidad="profundo", limite=limit)
            mapped = []
            for r in resultados:
                mapped.append({
                    "concepto": r[0],
                    "contenido": (r[1] or "")[:200],
                    "score": round(float(r[4]), 4) if r[4] is not None else 1.0,
                    "estado": r[3] or "activo"
                })
            conn.close()
            return {"resultados": mapped, "total": total}
        except Exception:
            pass

    c.execute("""
        SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, cat.name
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE l.concepto LIKE ? OR l.contenido LIKE ?
        ORDER BY l.peso_sinaptico DESC
        LIMIT ?
    """, (f"%{q}%", f"%{q}%", limit))
    mapped = []
    for r in c.fetchall():
        mapped.append({
            "concepto": r[0],
            "contenido": (r[1] or "")[:200],
            "score": 1.0,
            "estado": r[3] or "activo",
            "categoria": r[4] or "General"
        })
    conn.close()
    return {"resultados": mapped, "total": len(mapped)}


# ============================================================
# VISTA 3: SINAPSIS LATENTES
# ============================================================

@app.get("/api/latentes")
def listar_latentes(
    min_peso: float = 0.0,
    max_saltos: int = 10,
    tipo_puente: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    conn = get_db()
    c = conn.cursor()

    query = """
        SELECT sl.origen, sl.destino, sl.peso_atenuado, sl.saltos, sl.calculado_en,
               l1.peso_sinaptico as peso_origen, l2.peso_sinaptico as peso_destino,
               cat1.name as cat_origen, cat2.name as cat_destino
        FROM sinapsis_latentes sl
        LEFT JOIN largo_plazo l1 ON sl.origen = l1.concepto
        LEFT JOIN largo_plazo l2 ON sl.destino = l2.concepto
        LEFT JOIN categories cat1 ON l1.categoria = cat1.id
        LEFT JOIN categories cat2 ON l2.categoria = cat2.id
        WHERE sl.peso_atenuado >= ?
        AND sl.saltos <= ?
        ORDER BY sl.peso_atenuado DESC
        LIMIT ? OFFSET ?
    """
    c.execute(query, (min_peso, max_saltos, limit, offset))
    latentes = []
    for r in c.fetchall():
        latentes.append({
            "origen": r[0],
            "destino": r[1],
            "peso": round(r[2], 4) if r[2] else 0,
            "saltos": r[3],
            "calculado_en": ts_to_str(r[4]),
            "peso_origen": round(r[5], 3) if r[5] else 1.0,
            "peso_destino": round(r[6], 3) if r[6] else 1.0,
            "cat_origen": r[7] or "General",
            "cat_destino": r[8] or "General"
        })

    c.execute("SELECT COUNT(*) FROM sinapsis_latentes WHERE peso_atenuado >= ? AND saltos <= ?", (min_peso, max_saltos))
    total = c.fetchone()[0]

    conn.close()
    return {"latentes": latentes, "total": total, "offset": offset, "limit": limit}


@app.post("/api/latentes/confirmar")
def confirmar_latente(data: dict):
    origen = data.get("origen")
    destino = data.get("destino")
    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Faltan origen y destino")

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT peso_atenuado FROM sinapsis_latentes WHERE origen=? AND destino=?", (origen, destino))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Sinapsis latente no encontrada")

    peso = row[0]

    c.execute("SELECT 1 FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
              (origen, destino, destino, origen))
    if c.fetchone():
        conn.close()
        return {"status": "ya_existe", "mensaje": "La sinapsis directa ya existe"}

    c.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, 'latente_confirmada', ?)",
              (origen, destino, peso, ts_now()))

    c.execute("DELETE FROM sinapsis_latentes WHERE origen=? AND destino=?", (origen, destino))

    conn.commit()
    conn.close()
    return {"status": "ok", "mensaje": f"Sinapsis directa creada: {origen} → {destino}"}


@app.post("/api/latentes/rechazar")
def rechazar_latente(data: dict):
    origen = data.get("origen")
    destino = data.get("destino")
    razon = data.get("razon", "")
    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Faltan origen y destino")

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS sinapsis_bloqueadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            razon TEXT,
            bloqueado_en REAL NOT NULL,
            UNIQUE(origen, destino)
        )
    """)

    try:
        c.execute("INSERT INTO sinapsis_bloqueadas (origen, destino, razon, bloqueado_en) VALUES (?, ?, ?, ?)",
                  (origen, destino, razon, ts_now()))
    except sqlite3.IntegrityError:
        conn.close()
        return {"status": "ya_bloqueado", "mensaje": "Esta ruta ya estaba bloqueada"}

    c.execute("DELETE FROM sinapsis_latentes WHERE origen=? AND destino=?", (origen, destino))

    conn.commit()
    conn.close()
    return {"status": "ok", "mensaje": f"Ruta bloqueada: {origen} → {destino}"}


@app.post("/api/latentes/batch")
def batch_latentes(data: dict):
    accion = data.get("accion")
    filtro_peso = data.get("min_peso", 0.6)
    filtro_saltos = data.get("max_saltos", 3)
    limite = data.get("limite", 100)

    if accion not in ("confirmar", "rechazar"):
        raise HTTPException(status_code=400, detail="accion debe ser 'confirmar' o 'rechazar'")

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT origen, destino, peso_atenuado
        FROM sinapsis_latentes
        WHERE peso_atenuado >= ? AND saltos <= ?
        ORDER BY peso_atenuado DESC
        LIMIT ?
    """, (filtro_peso, filtro_saltos, limite))
    latentes = c.fetchall()

    procesados = 0
    errores = 0

    for origen, destino, peso in latentes:
        try:
            if accion == "confirmar":
                c.execute("SELECT 1 FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
                          (origen, destino, destino, origen))
                if not c.fetchone():
                    c.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, 'latente_confirmada', ?)",
                              (origen, destino, peso, ts_now()))
                    c.execute("DELETE FROM sinapsis_latentes WHERE origen=? AND destino=?", (origen, destino))
                    procesados += 1
            elif accion == "rechazar":
                c.execute("""
                    CREATE TABLE IF NOT EXISTS sinapsis_bloqueadas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        origen TEXT NOT NULL,
                        destino TEXT NOT NULL,
                        razon TEXT,
                        bloqueado_en REAL NOT NULL,
                        UNIQUE(origen, destino)
                    )
                """)
                try:
                    c.execute("INSERT INTO sinapsis_bloqueadas (origen, destino, razon, bloqueado_en) VALUES (?, ?, ?, ?)",
                              (origen, destino, f"batch_{accion}", ts_now()))
                    c.execute("DELETE FROM sinapsis_latentes WHERE origen=? AND destino=?", (origen, destino))
                    procesados += 1
                except sqlite3.IntegrityError:
                    pass
        except Exception:
            errores += 1

    conn.commit()
    conn.close()
    return {"status": "ok", "procesados": procesados, "errores": errores}


# ============================================================
# CRUD DE SINAPSIS
# ============================================================

@app.post("/api/sinapsis")
def crear_sinapsis(data: dict):
    origen = data.get("origen")
    destino = data.get("destino")
    peso = data.get("peso", 0.5)
    tipo = data.get("tipo", "manual")

    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Faltan origen y destino")

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT 1 FROM largo_plazo WHERE concepto=?", (origen,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Nodo '{origen}' no encontrado")
    c.execute("SELECT 1 FROM largo_plazo WHERE concepto=?", (destino,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Nodo '{destino}' no encontrado")

    c.execute("SELECT 1 FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
              (origen, destino, destino, origen))
    if c.fetchone():
        conn.close()
        return {"status": "ya_existe", "mensaje": "La sinapsis ya existe"}

    c.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, ?, ?)",
              (origen, destino, peso, tipo, ts_now()))
    conn.commit()
    conn.close()
    return {"status": "ok", "mensaje": f"Sinapsis creada: {origen} ↔ {destino}"}


@app.delete("/api/sinapsis")
def eliminar_sinapsis(data: dict):
    origen = data.get("origen")
    destino = data.get("destino")
    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Faltan origen y destino")

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
              (origen, destino, destino, origen))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return {"status": "ok", "eliminados": deleted}


# ============================================================
# CREAR / EDITAR NODOS
# ============================================================

@app.post("/api/aprender")
def aprender_nodo(data: dict):
    concepto = data.get("concepto", "").strip().lower().replace(" ", "_")
    contenido = data.get("contenido", "")
    cat = data.get("categoria", "General")
    syn = data.get("sinonimos", "")

    if not concepto or not contenido:
        raise HTTPException(status_code=400, detail="Faltan concepto y contenido")

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT 1 FROM largo_plazo WHERE concepto=?", (concepto,))
    if c.fetchone():
        conn.close()
        return {"status": "ya_existe", "mensaje": f"El nodo '{concepto}' ya existe"}

    c.execute("SELECT id FROM categories WHERE name=?", (cat,))
    row = c.fetchone()
    cat_id = row[0] if row else 1

    c.execute("""
        INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, sinonimos, creado_en, ultimo_acceso)
        VALUES (?, ?, ?, 1.0, 'activo', ?, ?, ?)
    """, (concepto, cat_id, contenido, syn, ts_now(), ts_now()))

    conn.commit()
    conn.close()
    return {"status": "ok", "mensaje": f"Nodo '{concepto}' creado", "concepto": concepto}


@app.put("/api/nodo/{concepto}")
def actualizar_nodo(concepto: str, data: dict):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT 1 FROM largo_plazo WHERE concepto=?", (concepto,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Nodo '{concepto}' no encontrado")

    updates = []
    params = []
    for field in ["contenido", "peso_sinaptico", "estado", "sinonimos"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        conn.close()
        return {"status": "sin_cambios"}

    params.append(concepto)
    c.execute(f"UPDATE largo_plazo SET {', '.join(updates)} WHERE concepto=?", params)
    conn.commit()
    conn.close()
    return {"status": "ok", "mensaje": f"Nodo '{concepto}' actualizado"}


# ============================================================
# VISTA 4: COMUNIDADES
# ============================================================

@app.get("/api/comunidades")
def listar_comunidades():
    conn = get_db()
    c = conn.cursor()

    c.execute("PRAGMA table_info(largo_plazo)")
    cols = [r[1] for r in c.fetchall()]

    if "community_id" not in cols:
        conn.close()
        return {"comunidades": [], "mensaje": "Comunidades no calculadas aún. Ejecutar 'Consolidar Cerebro'."}

    c.execute("""
        SELECT l.community_id, COUNT(*) as tamano,
               GROUP_CONCAT(l.concepto, '|') as nodos,
               cat.name as cat_principal
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE l.community_id IS NOT NULL
        GROUP BY l.community_id
        ORDER BY tamano DESC
    """)
    comunidades = []
    for r in c.fetchall():
        nodos_lista = r[2].split("|") if r[2] else []
        comunidades.append({
            "id": r[0],
            "tamano": r[1],
            "nodos": nodos_lista[:20],
            "cat_principal": r[3] or "General"
        })

    conn.close()
    return {"comunidades": comunidades}


@app.get("/api/comunidades/{community_id}/nodos")
def comunidad_nodos(community_id: int):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT l.concepto, l.peso_sinaptico, l.estado, cat.name
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
        WHERE l.community_id = ?
        ORDER BY l.peso_sinaptico DESC
    """, (community_id,))
    nodos = []
    for r in c.fetchall():
        nodos.append({
            "concepto": r[0],
            "peso": round(r[1], 3) if r[1] else 1.0,
            "estado": r[2] or "activo",
            "categoria": r[3] or "General"
        })

    conn.close()
    return {"community_id": community_id, "nodos": nodos}


# ============================================================
# VISTA 5: BITÁCORA DE SUEÑOS
# ============================================================

@app.get("/api/suenos/historial")
def historial_suenos(limite: int = 20):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT mc.timestamp, mc.nodos_consolidados, mc.nodos_dormidos_ciclo,
               mc.sinapsis_creadas, mc.sinapsis_podadas, cat.name,
               mr.energia_sinaptica, mr.total_nodos, mr.total_dormidos, mr.nodos_activos
        FROM metricas_cognitivas mc
        LEFT JOIN categories cat ON mc.categoria_dominante_id = cat.id
        LEFT JOIN metricas_rendimiento mr ON abs(mc.timestamp - mr.timestamp) < 5
        ORDER BY mc.timestamp DESC
        LIMIT ?
    """, (limite,))
    ciclos = []
    for r in c.fetchall():
        ciclos.append({
            "timestamp": r[0],
            "fecha": ts_to_str(r[0]),
            "consolidados": r[1],
            "dormidos_ciclo": r[2],
            "sinapsis_creadas": r[3],
            "sinapsis_podadas": r[4],
            "categoria_dominante": r[5],
            "energia": round(r[6], 2) if r[6] else None,
            "total_nodos": r[7],
            "total_dormidos": r[8],
            "activos": r[9]
        })

    conn.close()
    return {"ciclos": ciclos}


# ============================================================
# UTILIDADES
# ============================================================

@app.get("/api/categorias")
def listar_categorias():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM categories ORDER BY name")
    cats = [r[0] for r in c.fetchall()]
    conn.close()
    return {"categorias": cats}


@app.get("/api/grafo/global")
def grafo_global(max_edges: int = 2000):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT l.concepto, l.peso_sinaptico, l.estado, cat.name
        FROM largo_plazo l
        LEFT JOIN categories cat ON l.categoria = cat.id
    """)
    nodes = []
    for r in c.fetchall():
        nodes.append({
            "id": r[0],
            "peso": round(r[1], 3) if r[1] else 1.0,
            "estado": r[2] or "activo",
            "categoria": r[3] or "General"
        })

    c.execute("""
        SELECT origen, destino, peso, tipo
        FROM sinapsis
        ORDER BY peso DESC
        LIMIT ?
    """, (max_edges,))
    edges = []
    seen = set()
    for r in c.fetchall():
        key = tuple(sorted([r[0], r[1]]))
        if key not in seen:
            seen.add(key)
            edges.append({
                "source": r[0],
                "target": r[1],
                "peso": round(r[2], 3) if r[2] else 0.5,
                "tipo": r[3] or "co_ocurrencia"
            })

    conn.close()
    return {"nodes": nodes, "edges": edges}


@app.post("/api/consolidar")
def consolidar_cerebro():
    if cerebro is None:
        raise HTTPException(status_code=500, detail="Motor BioRAG no disponible")

    try:
        limite = max(10, int(len(get_db().execute("SELECT COUNT(*) FROM corto_plazo").fetchone()) * 1.6))
    except Exception:
        limite = 50

    try:
        resultado = cerebro.consolidar(limite_energia=limite)
        return {"status": "ok", "mensaje": "Cerebro consolidado", "resultado": str(resultado)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consolidar: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_BACKEND_PORT)
