"""
Módulo de calibración conforme, honestidad epistémica y umbrales de abstención.

Extraído de SQLiteMemoryBioRAG (Paso 3.4b - T17).
"""

import os
import time
import logging

logger = logging.getLogger("BioRAG.MemoryStore")

try:
    from core.calibracion import (
        CalibradorPlatt,
        calibracion_isotonica,
        UmbralConforme,
    )
except ImportError:
    CalibradorPlatt = calibracion_isotonica = UmbralConforme = None


def _preparar_datos_calibracion(self, n_calibracion: int = 500) -> tuple:
    """Prepara datos de calibración usando el QA baseline (921 casos).

    Returns:
        (scores, labels)
        scores: scores del top-1 para cada caso (score_hibrido crudo)
        labels: 1 si el top-1 era el esperado, 0 en caso contrario
    """
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qa_path = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")
    if not os.path.exists(qa_path):
        qa_path = os.path.join(base_dir, "scripts", "casos_qa.jsonl")

    if not os.path.exists(qa_path):
        logger.warning("No se encontró QA baseline para calibración")
        return [], []

    scores = []
    labels = []
    n = 0
    with open(qa_path, 'r', encoding='utf-8') as f:
        for line in f:
            if n >= n_calibracion:
                break
            try:
                caso = json.loads(line.strip())
                query = caso.get('query', '')
                expected = caso.get('concepto_esperado', '') or caso.get('expected', '')
                if not query or not expected:
                    continue
                resultados = self.buscar_por_frase(query, limite=1)
                if resultados and resultados[0]:
                    score = resultados[0][0][4]  # score_hibrido (first result, first tuple, index 4)
                    label = 1 if resultados[0][0][0] == expected else 0
                    scores.append(score)
                    labels.append(label)
                    n += 1
            except Exception:
                continue
    return scores, labels


def entrenar_calibracion(self, n_calibracion: int = 500, metodo: str = "platt") -> bool:
    """Entrena el calibrador de Platt (o isotónico) usando el QA baseline.

    Args:
        n_calibracion: máximo de casos a usar
        metodo: 'platt' o 'isotonica'
    """
    if not CalibradorPlatt or not calibracion_isotonica:
        logger.warning("Módulo calibracion no disponible")
        return False

    scores, labels = self._preparar_datos_calibracion(n_calibracion)
    if not scores:
        logger.warning("No hay datos de calibración")
        return False

    if metodo == "platt" and CalibradorPlatt:
        self._platt_calibrador = CalibradorPlatt().entrenar(scores, labels)
        logger.info(f"Platt calibrado: a={self._platt_calibrador.a:.4f}, b={self._platt_calibrador.b:.4f}")
    elif calibracion_isotonica:
        self._platt_calibrador = calibracion_isotonica(
            [float(s) for s in scores], [int(l) for l in labels]
        )
        logger.info("Calibración isotónica entrenada")
    else:
        logger.warning("Método de calibración no disponible")
        return False

    self._calibracion_entrenada = True
    return True


def calibrar_umbral_conforme(self, alpha: float = None, n_negativos: int = 100) -> float:
    """Crea el umbral de abstención con garantía FP <= alpha (predicción conforme).

    Usa consultas negativas conocidas (sin respuesta en corpus) para fijar
    el umbral con garantía FP <= alpha (distribution-free).

    alpha: garantía FP objetivo. Si None, se lee de BIORAG_ALPHA_CONFORME
    (default 0.10). GUARDA (DECISION_ALPHA.md): con n negativos el alpha
    mínimo alcanzable es 1/(n+1). Pedir menos no da esa garantía — solo
    coloca el umbral en el máximo de la muestra, que es el estadístico más
    inestable. Se avisa y se usa alpha_min en vez de fingir precisión.

    IMPORTANTE — SELECCIÓN DE NEGATIVOS: se usan EXCLUSIVAMENTE los casos de
    categoría `negativo` del QA baseline. NO se usan "expected no existe en
    largo_plazo" como criterio: eso filtra por nombre exacto y deja colar
    casos literales/naturales que SÍ tienen respuesta en el corpus (matchean
    con score 0.95+, corrompiendo el cuantil y empujando el umbral arriba).

    IMPORTANTE — MISMA ESCALA QUE EN USO: los scores recogidos aquí son
    `score_hibrido` crudo (resultados[0][0][4]). `_debe_responder` debe
    recibir la MISMA escala cruda; no mezclar con probabilidades de Platt.
    """
    if not UmbralConforme:
        logger.warning("UmbralConforme no disponible")
        return 0.0

    # alpha default desde env (DECISION_ALPHA.md, sección 5): ajustable por
    # entorno (QA / producción / agente) sin tocar código.
    if alpha is None:
        alpha = float(os.environ.get('BIORAG_ALPHA_CONFORME', '0.10'))

    # Buscar casos negativos: queries de la categoría `negativo` del QA
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qa_path = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")
    if not os.path.exists(qa_path):
        qa_path = os.path.join(base_dir, "scripts", "casos_qa.jsonl")

    scores_neg = []
    with open(qa_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                caso = json.loads(line.strip())
                if caso.get('categoria', '') != 'negativo':
                    continue
                query = caso.get('query', '')
                if not query:
                    continue

                resultados = self.buscar_por_frase(query, limite=1)
                if resultados and resultados[0]:
                    scores_neg.append(resultados[0][0][4])
                    if len(scores_neg) >= n_negativos:
                        break
            except Exception:
                continue

    if not scores_neg:
        logger.warning("No se encontraron negativos para calibración conforme")
        return 0.0

    # GUARDA (DECISION_ALPHA.md sección 5): alpha mínimo honesto = 1/(n+1).
    # Con 32 muestras pedir alpha=0.01 no da esa garantía: solo coloca el
    # umbral en el máximo observado (el estadístico más inestable). Avisar
    # en vez de fingir precisión.
    n_reales = min(len(scores_neg), n_negativos)
    alpha_min = 1.0 / (n_reales + 1)
    if alpha < alpha_min:
        logger.warning(
            f"alpha={alpha} pedido, pero con {n_reales} negativos el mínimo "
            f"alcanzable es {alpha_min:.3f}. Se usa {alpha_min:.3f}. "
            f"Para un alpha menor, amplía el corpus de negativos."
        )
        alpha = alpha_min

    # Detección de umbral degenerado: calibrar() solo evalúa la cobertura
    # sobre positivos si se los pasan. Sin esto, una recalibración con
    # negativos contaminados (p.ej. queries de log que luego resultaron ser
    # nodos existentes) fijaría el umbral por encima del máximo positivo y
    # el sistema se abstendría en el 100% de los casos EN SILENCIO.
    # Se pasan solo los positivos del QA (label==1): los negativos del QA
    # puntúan bajo y diluirían el chequeo de frac_pasa.
    try:
        scores_pos_muestra, labels_pos_muestra = self._preparar_datos_calibracion(100)
        scores_positivos = [s for s, l in zip(scores_pos_muestra, labels_pos_muestra) if l == 1] or None
    except Exception:
        scores_positivos = None
    self._umbral_conforme = UmbralConforme(alpha=alpha).calibrar(
        scores_neg[:n_reales], scores_positivos=scores_positivos
    )
    logger.info(f"Umbral conforme (alpha={alpha}): {self._umbral_conforme.umbral:.4f} (n={self._umbral_conforme.n_calibracion})")
    return self._umbral_conforme.umbral


def _score_con_calibracion(self, score_bruto: float) -> float:
    """Convierte score bruto a probabilidad calibrada (Platt o isotónica)."""
    if self._platt_calibrador:
        if hasattr(self._platt_calibrador, 'probabilidad'):
            return self._platt_calibrador.probabilidad(score_bruto)
        elif callable(self._platt_calibrador):
            return self._platt_calibrador(score_bruto)
    return score_bruto


def _debe_responder(self, score: float) -> bool:
    """Decide si responder o abstenerse basado en umbral conforme.

    RECIBE LA MISMA ESCALA USADA EN calibrar_umbral_conforme: score_hibrido
    crudo. Si se calibró con crudo, aquí va crudo.

    FLUJO:
      1. Si hay calibración conforme cargada → usa su umbral.
      2. Si NO hay calibración → SIN FILTRO (responder siempre).
         Cold start (0.65) solo se aplica cuando BIORAG_CALIBRACION_ACTIVA
         está explícitamente seteado a 1 (producción MCP).

    POR QUÉ: el umbral filtra por CALIDAD, no por existencia. Sin calibración
    no hay evidencia de qué score separa relevantes de irrelevantes. Forzar
    0.65 destruye R@5 (medido: 96% → 73%) porque muchos nodos válidos
    tienen score < 0.65 por la arquitectura del scoring (FTS5 + sinapsis
    + dimensional = scores planos).
    """
    if self._umbral_conforme:
        return self._umbral_conforme.responder(score)
    # Sin calibración: responder siempre.
    # Calidad sin calibrar = ruido por defecto (aceptable).
    # Calidad con umbral mal calibrado =失掉Recall (inaceptable).
    return True


def buscar_con_calibracion(self, query: str, limite: int = 10,
                           usar_calibracion: bool = True) -> list:
    """Búsqueda estándar con abstención sobre top-1 del score híbrido crudo.

    Si hay calibración conforme → filtra por top-1 (decisión SI/NO responder).
    Si no hay calibración → devuelve todos los resultados (sin filtro).

    NOTA: buscar_por_frase NO aplica umbral. Este método SÍ porque
    es el punto de decisión "¿respondo al usuario?" (MCP path).

    Args:
        query: consulta
        limite: máximo resultados
        usar_calibracion: aplicar abstención conforme (default True)
    """
    resultados = self.buscar(query, limite=limite)
    if usar_calibracion and resultados:
        # Solo top-1 decide SI responder. El resto se devuelve tal cual.
        if not self._debe_responder(resultados[0][4]):
            return []  # abstención
    return resultados[:limite]


def _contar_nodos_corpus(self) -> int:
    """Número de nodos activos actuales (para detectar drift de tamaño)."""
    try:
        row = self.cursor.execute(
            "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'"
        ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _cargar_calibracion_persistida(self) -> bool:
    """Carga la última calibración persistida. Devuelve True si hay una vigente."""
    try:
        self.cursor.execute("PRAGMA table_info(calibracion_estado)")
        if not self.cursor.fetchall():
            return False

        # BIORAG_CALIBRACION_ACTIVA: gate para activar la abstención por umbral.
        # OFF por defecto hasta tener negativos reales de tipo B para calibrar.
        if os.environ.get("BIORAG_CALIBRACION_ACTIVA", "0") != "1":
            return False

        row = self.cursor.execute(
            "SELECT umbral_conforme, alpha, n_negativos, n_positivos, "
            "n_nodos_corpus, a_platt, b_platt, metodo, rango_negativos, "
            "fecha_calibracion FROM calibracion_estado WHERE id = 1"
        ).fetchone()
        if not row:
            return False
        (umbral, alpha, n_neg, n_pos, n_nodos, a_platt, b_platt,
         metodo, rango, fecha) = row
        if umbral is None or umbral <= 0:
            return False
        self._umbral_conforme = UmbralConforme(alpha=alpha)
        self._umbral_conforme.umbral = float(umbral)
        self._umbral_conforme.n_calibracion = int(n_neg)
        if rango:
            try:
                r0, r1 = rango.split(",")
                self._umbral_conforme.rango_negativos = (float(r0), float(r1))
            except Exception:
                pass
        if a_platt is not None and b_platt is not None and CalibradorPlatt:
            platt = CalibradorPlatt()
            platt.a = float(a_platt)
            platt.b = float(b_platt)
            self._platt_calibrador = platt
        self._calibracion_meta = {
            "alpha": float(alpha),
            "n_negativos": int(n_neg),
            "n_positivos": int(n_pos),
            "n_nodos_corpus": int(n_nodos),
            "metodo": metodo,
            "fecha_calibracion": float(fecha),
        }
        self._calibracion_entrenada = True
        return True
    except Exception as e:
        logger.warning(f"No se pudo cargar calibración persistida: {e}")
        return False


def _persistir_calibracion(self, n_positivos: int, metodo: str = "conforme") -> None:
    """Persiste el estado de calibración junto al tamaño de corpus del momento."""
    try:
        u = self._umbral_conforme
        a_platt = getattr(getattr(self, "_platt_calibrador", None), "a", None)
        b_platt = getattr(getattr(self, "_platt_calibrador", None), "b", None)
        rango = f"{u.rango_negativos[0]:.4f},{u.rango_negativos[1]:.4f}" \
            if u.rango_negativos else None
        n_nodos = self._contar_nodos_corpus()
        self.cursor.execute("""
            INSERT INTO calibracion_estado
                (id, umbral_conforme, alpha, n_negativos, n_positivos,
                 n_nodos_corpus, a_platt, b_platt, metodo, rango_negativos,
                 fecha_calibracion)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                umbral_conforme = excluded.umbral_conforme,
                alpha = excluded.alpha,
                n_negativos = excluded.n_negativos,
                n_positivos = excluded.n_positivos,
                n_nodos_corpus = excluded.n_nodos_corpus,
                a_platt = excluded.a_platt,
                b_platt = excluded.b_platt,
                metodo = excluded.metodo,
                rango_negativos = excluded.rango_negativos,
                fecha_calibracion = excluded.fecha_calibracion
        """, (u.umbral, u.alpha, u.n_calibracion, n_positivos, n_nodos,
              a_platt, b_platt, metodo, rango, time.time()))
        self.conn.commit()
        self._calibracion_meta = {
            "alpha": u.alpha,
            "n_negativos": u.n_calibracion,
            "n_positivos": n_positivos,
            "n_nodos_corpus": n_nodos,
            "metodo": metodo,
            "fecha_calibracion": time.time(),
        }
        logger.info(
            f"Calibración persistida: umbral={u.umbral:.4f} alpha={u.alpha} "
            f"n_nodos={n_nodos}"
        )
    except Exception as e:
        logger.warning(f"No se pudo persistir calibración: {e}")


def calibrar_y_persistir(self, alpha: float = None, n_negativos: int = 40,
                         n_positivos_max: int = 300,
                         recalcular_si_drift: bool = True,
                         force: bool = False) -> dict:
    """Calibra (o recalibra si el corpus cambió) y persiste la garantía.

    DEVUELVE EL UMBRAL CON GARANTÍA FP <= alpha SOBRE EL CORPUS ACTUAL.
    Si ya hay una calibración persistida y el tamaño del corpus no cambió
    significativamente, reutiliza la vigente (no quema tiempo de búsqueda).

    Umbral por defecto 0.10: con los negativos del QA baseline (40 casos)
    fija el cuantil ceil((n+1)(1-alpha))/n de sus scores crudos.
    BASE HISTÓRICA: pre-v28.1 el sistema usaba cortes fijos
    (BIORAG_FP_THRESHOLD=0.25, BIORAG_QCR_ESCAPE_CAPA_MIN=0.60) que no
    dependían de la distribución real. alpha=0.10 es una PREFERENCIA
    (no una decisión con datos): su justificación requiere medir el ratio
    de consultas con/sin respuesta en log_busquedas (AUDITORÍA v28.1, paso 3).

    Args:
        alpha: garantía FP objetivo (0 < alpha < 1). None = leer env
            BIORAG_ALPHA_CONFORME (default 0.10). Si es menor que
            1/(n_negativos+1), se usa el mínimo alcanzable con la muestra
            (GUARDA DECISION_ALPHA.md sección 5) y se avisa.
        n_negativos: máximo de negativos a usar (los 40 del QA baseline).
        n_positivos_max: máximo de positivos para calibrar Platt (opcional).
        recalcular_si_drift: re-calibrar si n_nodos cambió > tolerancia.
        force: True = recalibrar siempre, ignorando calibración vigente.
    """
    n_nodos_actual = self._contar_nodos_corpus()
    meta = getattr(self, "_calibracion_meta", None)

    # alpha default desde env (DECISION_ALPHA.md sección 5)
    if alpha is None:
        alpha = float(os.environ.get('BIORAG_ALPHA_CONFORME', '0.10'))

    # Reutilizar calibración vigente si el corpus no se movió mucho
    if (not force and recalcular_si_drift and meta and self._umbral_conforme
            and self._umbral_conforme.umbral > 0):
        n_previo = meta.get("n_nodos_corpus", 0)
        drift_rel = abs(n_nodos_actual - n_previo) / max(n_previo, 1)
        # Tolerancia: 20% de cambio relativo (matemática simple, escalable:
        # el cuantil conforme es robusto a perturbaciones pequeñas del corpus).
        # BASE PRE-CALIBRACIÓN: el umbral era un valor FIJO (0.25 FP / 0.60 QCR)
        # que no se recalculaba jamás aunque el corpus triplicara su tamaño.
        # AUDITORÍA v28.1 (P3): faltaría invalidar también ante reindexado PPMI
        # (ppmi_ultima_reindexacion) y cambios de pesos del scoring — el tamaño
        # del corpus no es la única causa de deriva del piso de ruido.
        if drift_rel <= 0.20:
            return {
                "umbral": self._umbral_conforme.umbral,
                "alpha": self._umbral_conforme.alpha,
                "n_negativos": self._umbral_conforme.n_calibracion,
                "n_nodos_corpus": n_nodos_actual,
                "recalibrado": False,
                "motivo": "corpus_sin_drift_significativo",
                "fecha": meta.get("fecha_calibracion"),
            }
        logger.info(
            f"Corpus cambió {100*drift_rel:.1f}% ({n_previo} -> {n_nodos_actual}); "
            f"recalibrando umbral conforme"
        )

    # Intentar cargar persistida (si no la teníamos en memoria)
    if not force and not meta and self._cargar_calibracion_persistida():
        meta = self._calibracion_meta
        n_previo = meta.get("n_nodos_corpus", 0)
        drift_rel = abs(n_nodos_actual - n_previo) / max(n_previo, 1)
        if drift_rel <= 0.20 and self._umbral_conforme.umbral > 0:
            return {
                "umbral": self._umbral_conforme.umbral,
                "alpha": self._umbral_conforme.alpha,
                "n_negativos": self._umbral_conforme.n_calibracion,
                "n_nodos_corpus": n_nodos_actual,
                "recalibrado": False,
                "motivo": "persistida_sin_drift",
                "fecha": meta.get("fecha_calibracion"),
            }

    # Calibrar sobre el corpus ACTUAL
    umbral = self.calibrar_umbral_conforme(alpha=alpha, n_negativos=n_negativos)
    if umbral <= 0:
        return {"umbral": 0.0, "error": "calibracion_fallida"}

    n_pos = 0
    if n_positivos_max > 0 and CalibradorPlatt:
        try:
            scores_pos, labels_pos = self._preparar_datos_calibracion(n_positivos_max)
            if len(scores_pos) >= 20:
                self._platt_calibrador = CalibradorPlatt().entrenar(
                    scores_pos, labels_pos
                )
                n_pos = len(scores_pos)
                logger.info(
                    f"Platt recalibrado: a={self._platt_calibrador.a:.4f}, "
                    f"b={self._platt_calibrador.b:.4f} (n={n_pos})"
                )
        except Exception as e:
            logger.warning(f"Platt falló en recalibración: {e}")

    self._persistir_calibracion(n_pos, metodo="conforme")
    return {
        "umbral": umbral,
        # alpha EFECTIVO tras la guarda 1/(n+1), no el pedido
        "alpha": self._umbral_conforme.alpha,
        "alpha_pedido": alpha,
        "n_negativos": self._umbral_conforme.n_calibracion,
        "n_nodos_corpus": n_nodos_actual,
        "recalibrado": True,
        "motivo": "calibrado_sobre_corpus_actual",
        "fecha": time.time(),
    }


def nivel_certeza(self, score: float) -> str:
    """Clasifica un score crudo en los 3 niveles de honestidad epistémica.

    Regla del Neocórtex de Sangre (Dennys, 2026-08-14): nunca silencio vacío.
    Tres niveles:
      - evidencia_directa: score supera el umbral conforme (garantía FP <= alpha)
      - relacionado_confianza_media: por debajo del umbral pero hay señal
      - sin_evidencia_directa: score por debajo del umbral inferior (0.35)

    El umbral inferior 0.35 es el piso de ruido medido en live DB
    (rango de negativos: 0.34-0.61). Si el corpus cambia de tamaño, la
    recalibración ajusta el umbral superior; el piso se re-deriva del
    rango persistido de negativos.

    NOTA DE BASE (Dennys, 2026-08-16): antes de la calibración v28.1 el
    sistema tenía UN SOLO corte fijo, BIORAG_QCR_ESCAPE_CAPA_MIN = 0.60
    (gate QCR) y el umbral de FP BIORAG_FP_THRESHOLD = 0.25. El piso 0.35
    y el corte 0.60 que aparecen en este método son los valores fijos que
    la calibración reemplaza por cuantiles derivados de la distribución
    real de negativos. No reintroducir umbrales absolutos sin evidencia.
    """
    u = self._umbral_conforme
    if u and u.umbral > 0:
        if float(score) > u.umbral:
            return "evidencia_directa"
        piso = (u.rango_negativos[0] or 0.0) if u.rango_negativos else 0.35
        if float(score) >= max(piso, 0.35) - 0.01:
            return "relacionado_confianza_media"
        return "sin_evidencia_directa"
    # Sin calibración: fallback conservador de 3 niveles
    # BASE HISTÓRICA (valores fijos que la calibración v28.1 reemplaza):
    #   0.60 = BIORAG_QCR_ESCAPE_CAPA_MIN, el único corte del gate QCR pre-v28.1
    #   0.35 = piso de ruido medido en live DB (rango negativos 0.34-0.61)
    # Con calibración estos dos números salen de la distribución real;
    # aquí quedan como referencia de la base que se estaba usando.
    if score >= 0.60:
        return "evidencia_directa"
    if score >= 0.35:
        return "relacionado_confianza_media"
    return "sin_evidencia_directa"


def confianza_calibrada(self, score: float) -> float:
    """Probabilidad calibrada (Platt) o score crudo si no hay calibrador."""
    if self._platt_calibrador:
        try:
            if hasattr(self._platt_calibrador, 'probabilidad'):
                return float(self._platt_calibrador.probabilidad(score))
            return float(self._platt_calibrador(score))
        except Exception:
            pass
    return float(score)
