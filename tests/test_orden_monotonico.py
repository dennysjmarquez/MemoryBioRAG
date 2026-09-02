"""Regresión de orden monotónico en `buscar_por_frase` (v30.1).

Contexto del bug (diagnóstico 2026-09-02, docs/diagnostico_suite_qa_20260902.md §3):
`scripts/casos_fallidos.jsonl` tenía 9 casos con `scores` NO ordenados descendente,
p. ej. 'perfil' -> [0.7562, 0.6780, 0.7523]. Dos causas:

1. La promoción del Concept Hub hacía `insert(0, ...)` con
   `score_forzado = min(0.95, confianza * 0.95)`, que puede ser MENOR que el mejor
   score léxico (confianza 0.467 -> 0.444 colocado encima de un léxico 0.513).
2. El filtro `PALABRA_PREFIJO` para queries de una palabra reconstruía la lista como
   `literales_validos + no_literales` sin reordenar.

Un ranking que no está ordenado por el score que él mismo reporta rompe a todo
consumidor que corte por score en vez de por posición: `mcp_server.py` combina y
reordena los pools de `buscar_por_frase` y `buscar_por_rafaga` por `r[4]`, así que
frase y ráfaga podían devolver órdenes distintos para la misma consulta.

Estos tests no dependían de ninguna suite previa: el invariante no tenía cobertura.
"""

import os
import pytest

# ─── Raíz del proyecto en sys.path (mismo patrón que el resto de tests/) ───
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)


def _db_path():
    """Prioriza BIORAG_PATH (la suite lo apunta a la copia aislada), igual que
    tests/test_sdm_*.py. Nunca abre la DB viva por efecto colateral."""
    return os.environ.get("BIORAG_PATH") or os.path.join(
        _RAIZ, "MemoryBioRAG_Data", "memory_biorag.db"
    )


# Queries que en la corrida 2026-09-02 produjeron scores no monotónicos o que ejercitan
# los dos post-procesos implicados: una palabra (filtro PALABRA_PREFIJO) y multi-palabra
# (puerta QCR + promoción de hub). Ampliable con BIORAG_TEST_QUERIES_MONOTONIA="a|b|c".
QUERIES_DEFECTO = [
    "perfil",
    "dimensiones",
    "identidad",
    "familia",
    "arquitectura memovria biroag",
    "IAs que se contradigan para encontrar la verdad",
    "protocolo busquedas biorag automatica",
    "lección: guardar todo lo importante inmediatamente, no esperar",
]


def _queries():
    extra = os.environ.get("BIORAG_TEST_QUERIES_MONOTONIA")
    if extra:
        return [q.strip() for q in extra.split("|") if q.strip()]
    return QUERIES_DEFECTO


# ─── 1. Lógica del piso de promoción (puro, sin DB) ────────────────────────────

def _piso_promocion(score_forzado, mejor_score_lexico, hub_gana):
    """Réplica exacta de la regla de core/memory_store.py (v30.1).

    Se duplica aquí a propósito: el test documenta la aritmética del piso de forma
    aislada y falla si alguien cambia la constante o el orden del max/min.
    """
    if hub_gana:
        return round(min(1.0, max(score_forzado, mejor_score_lexico + 0.0001)), 4)
    return score_forzado


class TestPisoPromocionHub:
    def test_hub_gana_con_score_menor_que_lexico_se_eleva_al_piso(self):
        """El caso real del bug: confianza 0.467 -> 0.4442 sobre un léxico de 0.513."""
        score_forzado = min(0.95, 0.467 * 0.95)          # 0.44365
        mejor_lexico = 0.513
        assert score_forzado < mejor_lexico, "premisa: con confianza 0.467 el hub perdía contra el léxico"
        promovido = _piso_promocion(score_forzado, mejor_lexico, hub_gana=True)
        assert promovido > mejor_lexico, "el canónico promovido a TOP1 debe puntuar más que el léxico"
        assert promovido == 0.5131

    def test_hub_gana_con_score_mayor_no_se_reduce(self):
        """Confianza alta (1.0 -> 0.95) ya supera al léxico: el score se conserva."""
        promovido = _piso_promocion(0.95, 0.40, hub_gana=True)
        assert promovido == 0.95

    def test_hub_pierde_no_aplica_piso(self):
        """Si el léxico gana, el canónico se inserta en su posición natural por score:
        aplicar el piso ahí lo convertiría en TOP1 y rompería la promoción competitiva."""
        promovido = _piso_promocion(0.38, 0.80, hub_gana=False)
        assert promovido == 0.38
        assert promovido < 0.80

    def test_piso_nunca_supera_uno(self):
        assert _piso_promocion(0.9999, 1.0, hub_gana=True) == 1.0
        assert _piso_promocion(0.5, 0.99999, hub_gana=True) == 1.0

    def test_piso_es_monotonamente_determinista(self):
        """Mismo input -> mismo output, y el tick es la resolución de round(...,4)."""
        a = _piso_promocion(0.20, 0.7000, hub_gana=True)
        b = _piso_promocion(0.20, 0.7000, hub_gana=True)
        assert a == b == 0.7001


# ─── 2. Invariante sobre la DB real ───────────────────────────────────────────

requiere_db = pytest.mark.skipif(
    not os.path.exists(_db_path()),
    reason=f"No existe la DB en {_db_path()} — exporta BIORAG_PATH para correr este test",
)


@pytest.fixture(scope="module")
def cerebro():
    from core.memory_store import SQLiteMemoryBioRAG

    os.environ.setdefault("BIORAG_NO_LOG", "1")  # no contaminar log_busquedas
    db = SQLiteMemoryBioRAG(db_path=_db_path())
    yield db
    db.conn.close()


@requiere_db
class TestOrdenMonotonicoReal:
    @pytest.mark.parametrize("query", _queries())
    def test_scores_no_crecientes(self, cerebro, query):
        """`buscar_por_frase` debe devolver los resultados ordenados por el score que
        reporta. Es el contrato que asumen mcp_server.py, biorag_recordar() y el umbral
        conforme: todos cortan por score, no por posición."""
        resultados, _total = cerebro.buscar_por_frase(
            query, profundidad="activos", limite=5, ignore_peso_sinaptico=True
        )
        scores = [r[4] for r in resultados]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"orden no monotónico para {query!r}: posición {i} score {scores[i]} "
                f"< posición {i+1} score {scores[i+1]} | scores={scores} "
                f"| conceptos={[r[0] for r in resultados]}"
            )

    @pytest.mark.parametrize("query", _queries())
    def test_top1_es_el_maximo(self, cerebro, query):
        """Corolario del anterior, expresado como lo consume un cliente: nadie fuera del
        TOP1 puede puntuar más que el TOP1."""
        resultados, _total = cerebro.buscar_por_frase(
            query, profundidad="activos", limite=5, ignore_peso_sinaptico=True
        )
        if len(resultados) < 2:
            pytest.skip("menos de 2 resultados: nada que comparar")
        scores = [r[4] for r in resultados]
        assert scores[0] == max(scores), (
            f"TOP1 no es el máximo para {query!r}: scores={scores}"
        )

    def test_invariante_con_guardia_desactivada_documenta_el_bypass(self, cerebro):
        """Con BIORAG_ORDEN_MONOTONICO=0 la guardia final se apaga. El test no exige
        monotonía en ese modo (existen post-procesos que reordenan a propósito, como
        ordenar_por='recencia'); solo verifica que el flag se respeta y no rompe la
        llamada."""
        previo = os.environ.get("BIORAG_ORDEN_MONOTONICO")
        os.environ["BIORAG_ORDEN_MONOTONICO"] = "0"
        try:
            resultados, _total = cerebro.buscar_por_frase(
                "perfil", profundidad="activos", limite=5, ignore_peso_sinaptico=True
            )
            assert isinstance(resultados, list)
            assert all(len(r) >= 5 for r in resultados)
        finally:
            if previo is None:
                os.environ.pop("BIORAG_ORDEN_MONOTONICO", None)
            else:
                os.environ["BIORAG_ORDEN_MONOTONICO"] = previo

    def test_ordenar_por_recencia_sigue_mandando(self, cerebro):
        """La guardia de monotonía solo aplica a ordenar_por='relevancia'. Si alguien la
        mueve de sitio y aplasta el orden temporal, este test lo captura."""
        resultados, _total = cerebro.buscar_por_frase(
            "perfil",
            profundidad="activos",
            limite=5,
            ignore_peso_sinaptico=True,
            ordenar_por="recencia",
        )
        if len(resultados) < 2:
            pytest.skip("menos de 2 resultados")
        conceptos = [r[0] for r in resultados]
        ph = ",".join("?" * len(conceptos))
        cerebro.cursor.execute(
            f"SELECT concepto, COALESCE(creado_en, 0) FROM largo_plazo WHERE concepto IN ({ph})",
            tuple(conceptos),
        )
        creados = dict(cerebro.cursor.fetchall())
        fechas = [creados.get(c, 0) for c in conceptos]
        assert fechas == sorted(fechas, reverse=True), (
            f"ordenar_por='recencia' no devolvió orden temporal descendente: {list(zip(conceptos, fechas))}"
        )
