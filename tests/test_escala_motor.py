"""Regresión de invariancia de escala dentro del motor real.

Los casos vienen del experimento histórico de escala (2026-10-25), que detectó que
el crecimiento del corpus podía degradar la recuperación y el orden. El buscador
actual ha cambiado desde entonces: ``BIORAG_ESCALA=0`` desactiva ayudas concretas
de ``core/memory/escala.py``, pero no revierte todo el ranking al código histórico.
Por eso estas pruebas verifican que las respuestas correctas sigan primeras con
las ayudas activadas y desactivadas.

El fixture usa una COPIA temporal del snapshot y agrega pocos recuerdos para cubrir:
  1. Una nota que cita una consulta con typos.
  2. Cinco notas que comparten una palabra y dimensiones inferidas.
  3. Una palabra real que no debe confundirse con otra palabra real («rector» y
     «vector»), aunque el rescate difuso siga disponible para typos genuinos.
"""
import os
import shutil

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SNAPSHOT = os.path.join(_RAIZ, "snapshots", "qa_escape_qcr_20260811.db")

pytestmark = pytest.mark.skipif(not os.path.exists(_SNAPSHOT), reason="snapshot no disponible")

Q_TYPO = "resoluciones timeouts hotspot 5ghzs intels"
ORO_TYPO = "resolucion_timeout_hotspot_5ghz_intel"
Q_DIM = "principiando firmas cada recuerdando"
ORO_DIM = "principio_firma_cada_recuerdo"


@pytest.fixture(scope="module")
def memoria_crecida(tmp_path_factory):
    previo = {k: os.environ.get(k) for k in ("BIORAG_PATH", "BIORAG_NO_LOG", "BIORAG_NEURONA", "BIORAG_ESCALA")}
    db_path = str(tmp_path_factory.mktemp("escala") / "memoria.db")
    shutil.copyfile(_SNAPSHOT, db_path)
    os.environ.update(BIORAG_PATH=db_path, BIORAG_NO_LOG="1", BIORAG_NEURONA="0")
    from core.memory_store import SQLiteMemoryBioRAG
    from core import memory_service as MS

    db = SQLiteMemoryBioRAG(db_path)
    MS.aprender(db, "nota_fallos_qa_hotspot",
                f"Fallo de la QA: la consulta {Q_TYPO} no encontró su respuesta.", sinonimos="qa,fallo")
    dims = [r[0] for r in db.cursor.execute(
        "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = 'principio_naturaleza_agente'")]
    assert dims, "el snapshot cambió: principio_naturaleza_agente ya no tiene dimensiones"
    for i in range(5):
        c = f"nota_firmas_{i}"
        MS.aprender(db, c, f"Apunte {i} sobre firmas digitales en contratos y documentos legales del despacho.",
                    sinonimos="firmas,contratos")
        for d in dims:
            db.cursor.execute(
                "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)", (c, d))
    db.conn.commit()
    yield db
    db.cerrar_sistema()
    for k, v in previo.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _top5(db, query, oro):
    db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (oro,))
    db.conn.commit()
    res, _ = db.buscar_por_frase(query, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
    return [r[0] for r in res]


@pytest.mark.parametrize("query,oro", [(Q_TYPO, ORO_TYPO), (Q_DIM, ORO_DIM)])
def test_con_el_arreglo_la_respuesta_vuelve_al_primer_lugar(memoria_crecida, monkeypatch, query, oro):
    monkeypatch.setenv("BIORAG_ESCALA", "1")
    assert _top5(memoria_crecida, query, oro)[:1] == [oro]


@pytest.mark.parametrize("query,oro", [(Q_TYPO, ORO_TYPO), (Q_DIM, ORO_DIM)])
def test_respuesta_se_mantiene_primera_con_escala_legacy_desactivada(
        memoria_crecida, monkeypatch, query, oro):
    # El interruptor apaga las ayudas heredadas de escala; no debe borrar una
    # respuesta que el ranking actual ya recupera correctamente.
    monkeypatch.setenv("BIORAG_ESCALA", "0")
    assert _top5(memoria_crecida, query, oro)[:1] == [oro]


def test_genericos_sin_palabras_de_la_pregunta_no_ocupan_el_top(memoria_crecida, monkeypatch):
    monkeypatch.setenv("BIORAG_ESCALA", "1")
    top = _top5(memoria_crecida, Q_DIM, ORO_DIM)
    for generico in ("principio_naturaleza_agente", "aforismo_criterio_agente"):
        assert generico not in top


Q_REAL = "rector diagnostico red"
ORO_REAL = "principio_compresion_cognitiva_boveda_5d"


def test_palabra_real_no_se_confunde_con_otra_palabra_real(memoria_crecida, monkeypatch):
    monkeypatch.setenv("BIORAG_ESCALA", "1")
    top = _top5(memoria_crecida, Q_REAL, ORO_REAL)
    # Sin el arreglo ganaba diagnostico_auditor_word2vec: tiene «diagnostico» y «vector»,
    # pero ni «rector» ni «red».
    assert top[:1] == [ORO_REAL]


def test_typo_de_verdad_sigue_teniendo_parecido_difuso(memoria_crecida, monkeypatch):
    # «biorags» y «estadando» no existen en la memoria: siguen recibiendo parecido difuso.
    monkeypatch.setenv("BIORAG_ESCALA", "1")
    assert _top5(memoria_crecida, "biorags v16s 0s estadando", "biorag_v16_0_estado")[:1] == ["biorag_v16_0_estado"]
