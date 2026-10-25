"""scripts/qa_neurona.py: la neurona de ranking dentro de la QA oficial.

Cada prueba es una falla concreta que debe estar cubierta:
  A. Leer el estado guardado SIN tocar la base (no existe, no es SQLite, sin tabla, con campeón,
     de otra versión del motor).
  B. El espía ve el orden antes y después de la neurona sin cambiar nada, y se quita al terminar.
  C. Las dos columnas y el control de daño (R@5 idéntico, total en 1er lugar, tolerancia por categoría).
  D. El aviso dice la verdad en cada situación (y nombra el parámetro para ver la neurona).
  E. Argumentos de evaluar_qa.py compatibles con el uso de siempre.
"""
import hashlib
import importlib.util
import os
import sqlite3

import numpy as np
import pytest

from core import memory_service
from core.memory import neurona as N
from core.memory_store import SQLiteMemoryBioRAG

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("qa_neurona", os.path.join(RAIZ, "scripts", "qa_neurona.py"))
QN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(QN)

NODOS = [
    ("receta_pan_casero", "Amasar harina, agua, sal y levadura. Dejar levar dos horas y hornear a 220 grados."),
    ("configuracion_servidor_nginx", "El servidor nginx escucha en el puerto 80 y redirige a la aplicacion en el 8000."),
    ("leccion_backup_base_datos", "Hacer copia de la base de datos cada noche; restaurar probando en otra maquina."),
    ("error_timeout_api_pagos", "La API de pagos corta a los 30 segundos; reintentar con espera exponencial."),
    ("cumpleanos_hermana_marzo", "Mi hermana cumple el 14 de marzo; le gustan las orquideas y el chocolate amargo."),
    ("plan_entrenamiento_correr", "Correr tres veces por semana: series cortas el martes y fondo largo el domingo."),
    ("fix_cache_redis_expira", "La cache en redis expiraba antes de tiempo por un TTL en segundos y no en minutos."),
]


@pytest.fixture
def chica(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    c = SQLiteMemoryBioRAG(str(tmp_path / "chica.db"))
    for k, v in NODOS:
        memory_service.aprender(c, k, v)
    c.conn.commit()
    monkeypatch.setenv("BIORAG_NEURONA", "1")
    yield c
    c.cerrar_sistema()


def _campeon_que_invierte():
    """Campeón a mano que da vuelta el orden: sube a quien tenga BAJO el rasgo 0 (bm25)."""
    W = np.zeros((N.OCULTAS, len(N.F_SIG)))
    W[0, 0] = -5.0
    return {"W": W, "b": np.zeros(N.OCULTAS), "v": np.array([3.0] + [0.0] * (N.OCULTAS - 1))}


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ───────────────────────── A. leer sin tocar ─────────────────────────

def test_leer_guardada_no_existe_o_no_es_sqlite(tmp_path):
    assert QN.leer_guardada(str(tmp_path / "no_existe.db")) is None
    puntero = tmp_path / "memory_biorag.db"   # como queda un archivo de Git LFS sin descargar
    puntero.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n")
    assert QN.leer_guardada(str(puntero)) is None
    assert QN.leer_guardada("") is None and QN.leer_guardada(None) is None


def test_leer_guardada_base_sin_neurona(tmp_path):
    p = str(tmp_path / "vacia.db")
    sqlite3.connect(p).execute("CREATE TABLE x (a)").connection.close()
    info = QN.leer_guardada(p)
    assert info is not None and info["campeon"] is False and info["stats"] == {}


def test_leer_guardada_con_campeon_no_escribe_y_reconoce_el_motor(chica):
    est = N.estado(chica)
    est.campeon = _campeon_que_invierte()
    est.stats.update(ciclos=436, ascensos=8, retiros=0)
    assert N._guardar(chica, est) is True
    chica.conn.commit()
    antes = _sha(chica.db_path)
    info = QN.leer_guardada(chica.db_path)
    assert _sha(chica.db_path) == antes                                    # solo lectura de verdad
    assert info["campeon"] is True and info["stats"]["ciclos"] == 436
    assert QN.vale_para_este_motor(info, N.VERSION, N.huella_motor(chica))
    assert not QN.vale_para_este_motor(info, N.VERSION + 1, N.huella_motor(chica))   # otra versión
    assert not QN.vale_para_este_motor(info, N.VERSION, "otra_huella")               # otra fórmula
    assert not QN.vale_para_este_motor(None, N.VERSION, "x")


def test_rutas(tmp_path):
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "snapshots"))
    snap = os.path.join(base, "snapshots", "s.db")
    assert QN.es_snapshot(snap, base)
    assert not QN.es_snapshot(os.path.join(base, "snapshots_falsos", "s.db"), base)
    assert not QN.es_snapshot(os.path.join(base, "MemoryBioRAG_Data", "m.db"), base)
    assert not QN.es_snapshot("", base)
    assert QN.misma_db(snap, os.path.join(base, "snapshots", ".", "s.db"))
    assert not QN.misma_db(snap, "") and not QN.misma_db(None, snap)
    assert QN.mostrar_ruta(snap, base) == os.path.join("snapshots", "s.db")


# ───────────────────────── B. el espía ─────────────────────────

def test_espia_sin_campeon_no_es_llamado_y_las_columnas_son_iguales(chica):
    original = N.reordenar
    with QN.Espia(N) as espia:
        espia.nueva_busqueda()
        r, _ = chica.buscar_por_frase("servidor puerto", limite=5, ignore_peso_sinaptico=True)
        servido = [x[0] for x in r]
        formula, neu, ok = espia.ordenes(servido)
    assert espia.llamadas == 0 and formula == neu == servido and ok
    assert N.reordenar is original


def test_espia_con_campeon_ve_antes_y_despues_sin_cambiar_nada(chica, monkeypatch):
    est = N.estado(chica)
    est.campeon = _campeon_que_invierte()
    q = "base de datos copia servidor cache"
    # Lo que sirve el motor SIN espía (la referencia)
    sin_espia = [x[0] for x in chica.buscar_por_frase(q, limite=5, ignore_peso_sinaptico=True)[0]]
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    solo_formula = [x[0] for x in chica.buscar_por_frase(q, limite=5, ignore_peso_sinaptico=True)[0]]
    monkeypatch.setenv("BIORAG_NEURONA", "1")
    original = N.reordenar
    with QN.Espia(N) as espia:
        espia.nueva_busqueda()
        servido = [x[0] for x in chica.buscar_por_frase(q, limite=5, ignore_peso_sinaptico=True)[0]]
        formula, neu, ok = espia.ordenes(servido)
    assert N.reordenar is original                       # se quita al salir
    assert espia.llamadas >= 1 and ok and len(espia.ms) == espia.llamadas
    assert servido == sin_espia                          # el espía no cambia lo servido
    assert formula == solo_formula                       # "antes" = la fórmula a mano sola
    assert sorted(formula) == sorted(servido)            # mismos nodos: solo cambia el orden


def test_espia_ve_el_reorden_real_de_la_neurona(chica):
    """Página sintética (como test_neurona): el campeón sube a n3; el espía ve los dos órdenes."""
    est = N.estado(chica)
    W = np.zeros((N.OCULTAS, len(N.F_SIG)))
    W[0, 0] = 5.0
    est.campeon = {"W": W, "b": np.zeros(N.OCULTAS), "v": np.array([3.0] + [0.0] * (N.OCULTAS - 1))}
    nombres = [f"n{i}" for i in range(5)]
    scores = [.95, .9, .85, .8, .75]
    rasgos = {n: ([0.0] * len(N.F_FORMULA), s) for n, s in zip(nombres, scores)}
    rasgos["n3"] = ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .8)
    pag = [(n, "contenido", 1.0, "activo", s, "") for n, s in zip(nombres, scores)]
    v = N.vista(pag, rasgos, {}, {}, {}, con_peso=False, con_agente=False)
    with QN.Espia(N) as espia:
        espia.nueva_busqueda()
        nuevo = N.reordenar(chica, "consulta cualquiera", pag, v)
        formula, servido, ok = espia.ordenes([r[0] for r in nuevo])
    assert ok and formula == nombres and servido[0] == "n3" and sorted(servido) == nombres
    c = QN.Comparacion()
    c.anotar("x", QN.puesto(formula, "n3"), QN.puesto(servido, "n3"), formula != servido, ok)
    res = c.resumen()
    assert res["cambios"]["subio_al_1"] == 1 and res["categorias"]["x"]["hits1_neurona"] == 1


def test_espia_se_quita_aunque_haya_error():
    class M:
        @staticmethod
        def reordenar(motor, frase, pagina, v):
            return pagina
    original = M.reordenar
    with pytest.raises(RuntimeError):
        with QN.Espia(M):
            raise RuntimeError("falla en medio de la QA")
    assert M.reordenar is original


def test_espia_detecta_medicion_incoherente():
    class M:
        @staticmethod
        def reordenar(motor, frase, pagina, v):
            return list(reversed(pagina))
    with QN.Espia(M) as espia:
        espia.nueva_busqueda()
        M.reordenar(None, "q", [("a",), ("b",), ("c",)], None)
        assert espia.ordenes(["c", "b", "a"]) == (["a", "b", "c"], ["c", "b", "a"], True)
        assert espia.ordenes(["a", "c", "b"])[2] is False   # lo servido no es lo que devolvió


def test_puesto():
    assert QN.puesto(["a", "b", "c"], "a") == 1 and QN.puesto(["a", "b", "c"], "c") == 3
    assert QN.puesto(["a", "b"], "z") == 0 and QN.puesto([], "a") == 0


# ───────────────────────── C. columnas y control de daño ─────────────────────────

def _comparacion(casos):
    c = QN.Comparacion()
    for cat, pf, pn in casos:
        c.anotar(cat, pf, pn, pf != pn)
    return c.resumen()


def test_columnas_y_cambios():
    res = _comparacion([("a", 2, 1), ("a", 1, 1), ("a", 1, 2), ("a", 3, 2), ("b", 0, 0), ("b", 1, 1)])
    a, g, k = res["categorias"]["a"], res["global_"], res["cambios"]
    assert (a["hits1_formula"], a["hits1_neurona"]) == (2, 2)
    assert a["hits5_formula"] == a["hits5_neurona"] == 4
    assert a["mrr_formula"] == round((0.5 + 1 + 1 + 1 / 3) / 4, 4)
    assert a["mrr_neurona"] == round((1 + 1 + 0.5 + 0.5) / 4, 4)
    assert (g["total"], g["hits1_formula"], g["hits1_neurona"]) == (6, 3, 3)
    assert k == dict(reordenadas=3, subio_al_1=1, bajo_del_1=1, mejoro=2, empeoro=1)


def test_control_de_dano_pasa_cuando_no_dana():
    res = _comparacion([("a", 2, 1), ("a", 1, 1), ("b", 1, 2), ("b", 3, 1)])
    assert QN.control_de_dano(res, 1) == []


def test_control_de_dano_por_categoria_respeta_la_tolerancia():
    # "b" pierde 2 en 1er lugar; "a" gana 3: el total sube, pero "b" se daña
    casos = [("a", 2, 1)] * 3 + [("b", 1, 2)] * 2
    res = _comparacion(casos)
    motivos = QN.control_de_dano(res, 1)
    assert len(motivos) == 1 and "b pierde 2 casos" in motivos[0]
    assert QN.control_de_dano(res, 2) == []


def test_control_de_dano_total_no_puede_bajar():
    res = _comparacion([("a", 1, 2), ("b", 1, 2)])          # pierde 1 en cada una (dentro de tol)
    motivos = QN.control_de_dano(res, 1)
    assert len(motivos) == 1 and "MENOS en 1er lugar" in motivos[0]


def test_control_de_dano_recall5_debe_ser_identico_e_incoherencias():
    c = QN.Comparacion()
    c.anotar("a", 3, 0, True)                                 # la sacó del top-5: imposible por diseño
    c.anotar("a", 1, 1, False, coherente=False)
    motivos = QN.control_de_dano(c.resumen(), 5)
    assert any("Recall@5" in m for m in motivos)
    assert any("incoherente" in m for m in motivos)


def test_tolerancia_desde_el_entorno(monkeypatch):
    monkeypatch.delenv("BIORAG_QA_NEURONA_TOL_CASOS", raising=False)
    assert QN.tolerancia_casos() == 1
    for env, esperado in (("0", 0), ("3", 3), ("-2", 0), ("x", 1)):
        monkeypatch.setenv("BIORAG_QA_NEURONA_TOL_CASOS", env)
        assert QN.tolerancia_casos() == esperado, env


def test_tiempos():
    assert QN.tiempos([])["decisiones"] == 0
    t = QN.tiempos([1.0, 2.0, 3.0, 4.0, 100.0])
    assert t["decisiones"] == 5 and t["mediana_ms"] == 3.0 and t["max_ms"] == 100.0


# ───────────────────────── D. el aviso ─────────────────────────

def _ctx(**kw):
    base = dict(activa=True, medida={"campeon": False}, entrenada_aqui=None, origen="/r/snapshots/s.db",
                origen_es_snapshot=True, guardada_origen=None, viva=None, viva_vale=False,
                ruta_viva="/r/MemoryBioRAG_Data/memory_biorag.db", base_dir="/r")
    base.update(kw)
    return "\n".join(QN.lineas_aviso(base))


VIVA = dict(campeon=True, stats=dict(ciclos=436, ascensos=8, retiros=0,
                                     ultimo=dict(guardia_mano=0.441, guardia_campeon=0.706)))


def test_aviso_snapshot_sin_neurona_y_viva_activa():
    t = _ctx(viva=VIVA, viva_vale=True)
    assert "snapshot oficial" in t and "FÓRMULA A MANO SOLA" in t
    assert "ACTIVA en tu DB viva (MemoryBioRAG_Data/memory_biorag.db)" in t
    assert "436 prácticas" in t and "aprobó 8 veces" in t and "44.1 % → neurona 70.6 %" in t
    assert "Cada base tiene su propia neurona" in t
    assert "--con-neurona" in t and "BIORAG_PATH=MemoryBioRAG_Data/memory_biorag.db" in t


def test_aviso_sin_db_viva_igual_nombra_el_parametro():
    t = _ctx()
    assert "--con-neurona" in t and "tu DB viva" not in t and "BIORAG_PATH=" not in t


def test_aviso_viva_de_otra_version_del_motor():
    t = _ctx(viva=VIVA, viva_vale=False)
    assert "otra versión" in t and "ACTIVA en tu DB viva" not in t and "BIORAG_PATH=" not in t


def test_aviso_base_medida_con_neurona_que_no_es_el_snapshot():
    t = _ctx(medida=dict(campeon=True, ciclos=436, ascensos=8, retiros=0), origen="/r/MemoryBioRAG_Data/m.db",
             origen_es_snapshot=False)
    assert "ACTIVA — entrenada con esta misma base" in t and "NO es el snapshot oficial" in t
    assert "No compares esta tabla con la del README" in t and "--con-neurona" not in t


def test_aviso_entrenada_en_la_copia():
    t = _ctx(medida=dict(campeon=True), entrenada_aqui=dict(ciclos=500, segundos=1320))
    assert "--con-neurona (500 prácticas, 22 min)" in t and "nunca vio las preguntas" in t
    assert "No compares" not in t


def test_aviso_apagada_y_neurona_vieja_en_la_base():
    t = _ctx(activa=False, viva=VIVA, viva_vale=True)
    assert "apagada" in t and "BIORAG_NEURONA=0" in t and "--con-neurona" not in t
    t = _ctx(guardada_origen=dict(campeon=True))
    assert "otra versión del motor" in t


def test_sufijo_y_bloque_de_resultado():
    res = _comparacion([("a", 2, 1), ("a", 1, 1), ("b", 1, 1)])
    assert QN.sufijo_fila(res["categorias"]["a"]) == "🧠 +50.00 pp (fórmula sola 50.00%)"
    assert QN.sufijo_fila(res["categorias"]["b"]).startswith("🧠 = igual")
    texto = "\n".join(QN.lineas_resultado(res, QN.tiempos([0.2, 0.3]), [], 1))
    assert "GLOBAL" in texto and "SUBIÓ al 1er lugar en 1" in texto and "✅ pasa" in texto
    texto = "\n".join(QN.lineas_resultado(res, QN.tiempos([]), ["neurona: x"], 1))
    assert "✗ NO pasa" in texto and "Tiempo" not in texto


# ───────────────────────── E. argumentos ─────────────────────────

def test_argumentos_compatibles():
    a = QN.leer_argumentos([])
    assert a.casos == "casos_qa_baseline_v1.jsonl" and not a.con_neurona and a.ciclos == 500
    a = QN.leer_argumentos(["casos_qa.jsonl"])
    assert a.casos == "casos_qa.jsonl"
    a = QN.leer_argumentos(["--con-neurona", "--ciclos", "40", "--minutos", "5"])
    assert a.con_neurona and a.ciclos == 40 and a.minutos == 5.0


def test_despertar_y_la_qa_comparten_el_mismo_bucle():
    spec = importlib.util.spec_from_file_location("despertar_neurona", os.path.join(RAIZ, "scripts", "despertar_neurona.py"))
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)
    assert callable(D.practicar_seguido)
    with open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8") as f:
        assert "from despertar_neurona import practicar_seguido" in f.read()
