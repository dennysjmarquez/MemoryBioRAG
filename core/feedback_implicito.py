#!/usr/bin/env python3
"""feedback_implicito.py — Deducir `util` sin preguntarle a nadie.

LA IDEA
=======
El problema: `log_busquedas.util` está vacía (0 de 2157 filas) porque depende de
que un agente se acuerde de llamar a la tool `feedback`. Sin esa columna no hay
negativos reales, no hay validación de la calibración conforme, y el olvido se
gobierna por silencio.

La solución que se venía barajando era un "módulo de inteligencia" que juzgara si
una respuesta sirvió. Eso es sobre-ingeniería: **el comportamiento del agente ya
contiene la respuesta.** Solo hay que leerla.

LAS TRES SEÑALES (ninguna necesita LLM, red neuronal ni C)
===========================================================

1. REFORMULACIÓN — si tras buscar X el agente busca X' parecido en pocos segundos,
   la primera búsqueda falló. Es el estándar de information retrieval desde los
   años 2000 (query reformulation / abandonment). Aritmética sobre timestamps.

2. APRENDIZAJE POSTERIOR — exclusiva de BioRAG: si se busca X, no se encuentra, y
   poco después se GUARDA un nodo parecido a X, la búsqueda falló y el sistema
   tiene la prueba en su propia tabla `largo_plazo.creado_en`.

   Nota: esto es exactamente lo que se identificó como "proxy contaminado" cuando
   se intentó usar `resultados_count = 0` como negativo. La lectura correcta no es
   "esos datos están sucios" sino "esos datos son feedback negativo puro, mal
   etiquetado". El error era el signo, no el dato.

3. SILENCIO POSTERIOR — si tras una búsqueda no hay reformulación ni aprendizaje en
   la ventana siguiente, el agente siguió con su tarea: la búsqueda sirvió.
   Es la señal más débil de las tres y por eso se marca con confianza menor.

LO QUE ESTO NO ES
-----------------
No es un juicio semántico de calidad. No dice si la respuesta era *buena*, dice si
el agente *siguió buscando*. Es una señal conductual, y como tal tiene ruido: un
agente puede reformular por curiosidad, o abandonar por interrupción externa.

Por eso cada inferencia lleva `confianza` y se puede filtrar. Para calibración
conforme conviene usar solo `confianza >= 0.7`.

USO
    python3 core/feedback_implicito.py <db> --dry-run    # solo reporta
    python3 core/feedback_implicito.py <db> --aplicar    # escribe util
"""
from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

# Ventanas temporales, en segundos.
# Justificación: una reformulación humana/agente ocurre en decenas de segundos;
# más allá de 2 minutos ya es probable que sea otra tarea distinta.
VENTANA_REFORMULACION = 120.0
VENTANA_APRENDIZAJE = 300.0
VENTANA_SILENCIO = 600.0

# Umbral de similitud léxica para considerar dos consultas "la misma intención".
UMBRAL_SIMILITUD = 0.50  # sobre solapamiento, no Jaccard: ver _solapamiento()


def _tokens(texto: str) -> set:
    """Tokeniza para comparar intención entre consultas. Minúsculas, >=3 chars."""
    return {t for t in re.findall(r"\w{3,}", (texto or "").lower())}


def _solapamiento(a: set, b: set) -> float:
    """Coeficiente de solapamiento: |A ∩ B| / min(|A|, |B|).

    POR QUÉ NO JACCARD (corregido tras probarlo, 2026-08-16): Jaccard divide por
    la UNIÓN, así que penaliza las reformulaciones que AÑADEN términos — que son
    justo las más frecuentes ("no encontré, voy a ser más específico"). Medido:

        "ciclo de sueño biorag"  ->  "como funciona ciclo sueño consolidacion"
        Jaccard      = 2/6 = 0.33   (por debajo del umbral: NO detecta)
        solapamiento = 2/3 = 0.67   (detecta correctamente)

    Cuantas más palabras añade el agente al reformular, menos parecidas las ve
    Jaccard. Es exactamente al revés de lo que necesitamos aquí.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _cargar_queries_benchmark() -> set:
    """Consultas del benchmark QA, para excluirlas del feedback implícito.

    POR QUÉ: `scripts/evaluar_qa.py` llama a `buscar_por_frase()`, que SIEMPRE
    inserta en `log_busquedas`. Cada corrida del benchmark mete ~921 filas en el
    log de producción. Medido el 2026-08-16: 1.379 de 2.121 filas (65%) del log
    real son consultas del benchmark.

    Calibrar el umbral con esas consultas y luego medir el FP con el mismo
    benchmark es circular: se estaría calibrando contra el test.
    """
    ruta = os.path.join(BASE_DIR, "scripts", "casos_qa.jsonl")
    queries = set()
    if not os.path.exists(ruta):
        print(f"AVISO: no se encontró {ruta}; no se puede filtrar contaminación "
              f"del benchmark. Los negativos inferidos pueden ser casos de test.")
        return queries
    import json
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            if linea.strip():
                try:
                    q = json.loads(linea).get("query", "").strip().lower()
                    if q:
                        queries.add(q)
                except Exception:
                    continue
    return queries


def inferir_feedback(db_path: str, limite: Optional[int] = None,
                     filtrar_benchmark: bool = True,
                     umbral_rafaga: float = 2.0) -> List[dict]:
    """Recorre el log en orden temporal y deduce `util` para cada búsqueda.

    Devuelve una lista de dicts con: id, query, util_inferido, señal, confianza.
    No escribe nada: separar el análisis de la escritura permite revisar antes.
    """
    if not os.path.exists(db_path):
        raise SystemExit(
            f"ERROR: no existe la base de datos '{db_path}'.\n"
            "Este script NO simula datos: sin log real no hay inferencia."
        )

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    tablas = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "log_busquedas" not in tablas:
        raise SystemExit("ERROR: no existe la tabla 'log_busquedas'.")

    filas = con.execute(
        "SELECT id, query, resultados_count, top_score, creado_en "
        "FROM log_busquedas WHERE util IS NULL ORDER BY creado_en ASC"
    ).fetchall()

    if not filas:
        print("No hay filas con util IS NULL. Nada que inferir.")
        con.close()
        return []

    # Nodos guardados, para la señal 2. Si la tabla no tiene creado_en, se omite.
    nodos: List[Tuple[str, float]] = []
    try:
        nodos = con.execute(
            "SELECT concepto, COALESCE(creado_en, 0) FROM largo_plazo "
            "WHERE creado_en IS NOT NULL ORDER BY creado_en ASC"
        ).fetchall()
    except sqlite3.Error:
        print("AVISO: no se pudo leer largo_plazo.creado_en; "
              "la señal de aprendizaje posterior queda desactivada.")

    con.close()

    # --- Marcar filas contaminadas por el benchmark ---
    queries_qa = _cargar_queries_benchmark() if filtrar_benchmark else set()
    es_qa = [(f[1] or "").strip().lower() in queries_qa for f in filas]
    es_rafaga = [False] + [
        (filas[i][4] - filas[i - 1][4]) < umbral_rafaga for i in range(1, len(filas))
    ]

    if filtrar_benchmark:
        n_qa = sum(es_qa)
        n_raf = sum(es_rafaga)
        print(f"  filtro de contaminación: {n_qa} filas son casos del benchmark, "
              f"{n_raf} llegan en ráfaga (<{umbral_rafaga}s)")

    inferencias: List[dict] = []
    for i, (id_, query, n_res, top, ts) in enumerate(filas):
        if limite and len(inferencias) >= limite:
            break

        # Una consulta que ES del benchmark nunca genera feedback: no la hizo
        # un agente resolviendo una tarea, la hizo un bucle de evaluación.
        if filtrar_benchmark and es_qa[i]:
            continue

        toks = _tokens(query)
        util: Optional[int] = None
        senal = ""
        confianza = 0.0

        # --- Señal 1: reformulación ---
        # Si la siguiente consulta es parecida y llega pronto, esta falló.
        #
        # FILTRO SELECTIVO (2026-08-16): esta señal se apoya en el delta entre
        # consultas, así que es la ÚNICA vulnerable a las ráfagas del benchmark
        # (que corre a ~0.05s por caso). Un agente real reformula en 5-60s, nunca
        # en menos de 2s, así que descartar los deltas <2s no pierde señal real.
        #
        # El filtro NO se aplica a la señal 2 (aprendizaje posterior): esa no
        # depende del delta entre consultas sino de que se cree un nodo después,
        # y el benchmark nunca crea nodos — solo consulta. Aplicar el filtro de
        # ráfaga globalmente descartaría los mejores negativos (conf 0.95).
        if i + 1 < len(filas) and not es_rafaga[i + 1]:
            _, q_sig, _, _, ts_sig = filas[i + 1]
            dt = ts_sig - ts
            if 0 < dt <= VENTANA_REFORMULACION:
                toks_sig = _tokens(q_sig)
                sim = _solapamiento(toks, toks_sig)
                # DISTINGUIR FALLO DE PROFUNDIZACIÓN (2026-08-16)
                # -------------------------------------------------
                # No toda reformulación es un fallo. Medido sobre datos reales:
                # las "reformulaciones" detectadas puntúan alto (mediana 0.946),
                # que en BioRAG significa match casi exacto. Eso sugiere que
                # muchas NO son fallos sino refinamientos: el agente encontró lo
                # que buscaba y siguió profundizando.
                #
                #   fallo          : X' parafrasea a X con otras palabras
                #                    "ciclo de sueño" -> "como funciona sleep cycle"
                #   profundización : X' CONTIENE a X y añade especificidad
                #                    "ciclo de sueño" -> "ciclo sueño LTD umbral"
                #
                # Marcar una profundización como util=0 aplica LTD a un nodo que
                # SÍ sirvió: lo debilita y puede llegar a dormirlo. Es el bucle
                # tóxico en su versión negativa, y por eso se excluye.
                profundizacion = toks.issubset(toks_sig) and len(toks_sig) > len(toks)
                if sim >= UMBRAL_SIMILITUD and not profundizacion:
                    util = 0
                    senal = f"reformulada en {dt:.0f}s (sim={sim:.2f})"
                    # Cuanto más rápida y más parecida, más segura la inferencia.
                    confianza = min(0.9, 0.5 + sim * 0.5)

        # --- Señal 2: aprendizaje posterior (exclusiva de BioRAG) ---
        # Buscó, no encontró, y guardó algo parecido justo después.
        if util is None and n_res == 0 and nodos:
            for concepto, ts_nodo in nodos:
                dt = ts_nodo - ts
                if dt <= 0:
                    continue
                if dt > VENTANA_APRENDIZAJE:
                    break  # nodos ordenados: el resto está aún más lejos
                sim = _solapamiento(toks, _tokens(concepto.replace("_", " ")))
                if sim >= UMBRAL_SIMILITUD:
                    util = 0
                    senal = f"nodo '{concepto[:40]}' creado {dt:.0f}s después"
                    confianza = 0.95  # la más fuerte: hay prueba material
                    break

        # --- Señal 3: silencio posterior ---
        # Ni reformuló ni aprendió: siguió con su tarea. Señal débil.
        if util is None and n_res > 0:
            dt_sig = (filas[i + 1][4] - ts) if i + 1 < len(filas) else 1e9
            if dt_sig > VENTANA_SILENCIO:
                util = 1
                senal = f"sin reformulación en {min(dt_sig, 9999):.0f}s"
                confianza = 0.55

        if util is not None:
            inferencias.append({
                "id": id_, "query": query[:70], "util": util,
                "senal": senal, "confianza": round(confianza, 2),
            })

    return inferencias


def aplicar(db_path: str, inferencias: List[dict], confianza_min: float = 0.7,
            solo_negativos: bool = True) -> int:
    """Escribe `util` solo para inferencias por encima del umbral de confianza.

    POR QUÉ `solo_negativos=True` POR DEFECTO — la asimetría de riesgo
    ----------------------------------------------------------------------
    Responde a la objeción del bucle de retroalimentación tóxica ("marcar útil
    algo que parece útil pero es alucinación refuerza el error"). Las señales no
    son simétricas en riesgo:

      util=0 (reformulación, aprendizaje posterior)
          Si la inferencia se equivoca, se penaliza un resultado que era bueno.
          Coste: se pierde algo de recall. NO contamina la memoria.

      util=1 (silencio posterior)
          Si el sistema devolvió una alucinación y el agente no reformuló
          porque se la creyó, se refuerza el error. La memoria se degrada sola
          y cada refuerzo hace más probable el siguiente. Ese SÍ es un bucle
          tóxico y no tiene freno interno.

    Como lo que falta para calibrar son precisamente NEGATIVOS, se puede usar
    solo la mitad segura: el bucle tóxico desaparece por diseño, no por umbral.

    Los positivos deben venir de feedback explícito (un agente que confirma),
    que es la única fuente que puede distinguir "no reformuló porque sirvió" de
    "no reformuló porque se creyó una alucinación".

    Marca únicamente filas con util IS NULL: un feedback explícito real nunca se
    sobrescribe con una inferencia.
    """
    aplicables = [x for x in inferencias if x["confianza"] >= confianza_min]
    if solo_negativos:
        descartados = sum(1 for x in aplicables if x["util"] == 1)
        aplicables = [x for x in aplicables if x["util"] == 0]
        if descartados:
            print(f"  ({descartados} inferencias positivas omitidas: los util=1 "
                  f"implícitos pueden reforzar alucinaciones. Usa "
                  f"solo_negativos=False para incluirlas bajo tu responsabilidad.)")
    if not aplicables:
        print(f"Ninguna inferencia aplicable con confianza >= {confianza_min}.")
        return 0

    con = sqlite3.connect(db_path)
    n = 0
    try:
        for x in aplicables:
            cur = con.execute(
                "UPDATE log_busquedas SET util = ? WHERE id = ? AND util IS NULL",
                (x["util"], x["id"]),
            )
            n += cur.rowcount
        con.commit()
    finally:
        con.close()
    return n


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Uso: python3 core/feedback_implicito.py <db> [--aplicar] [--conf 0.7]"
        )
    db = sys.argv[1]
    hacer = "--aplicar" in sys.argv
    conf = 0.7
    if "--conf" in sys.argv:
        conf = float(sys.argv[sys.argv.index("--conf") + 1])

    print("=" * 70)
    print("  Feedback implícito — deducir `util` del comportamiento del agente")
    print("=" * 70)

    inf = inferir_feedback(db)
    if not inf:
        return

    pos = sum(1 for x in inf if x["util"] == 1)
    neg = sum(1 for x in inf if x["util"] == 0)
    fuertes = [x for x in inf if x["confianza"] >= conf]

    print(f"\ninferencias: {len(inf)}  (útil={pos}, no-útil={neg})")
    print(f"con confianza >= {conf}: {len(fuertes)}\n")

    print(f"{'util':>5} {'conf':>5}  {'query':<40} señal")
    print("-" * 100)
    for x in inf[:25]:
        print(f"{x['util']:>5} {x['confianza']:>5.2f}  {x['query']:<40.40} {x['senal']}")
    if len(inf) > 25:
        print(f"  ... y {len(inf)-25} más")

    if hacer:
        n = aplicar(db, inf, conf)
        print(f"\nAPLICADO: {n} filas actualizadas (confianza >= {conf}).")
        print("Los feedbacks explícitos previos no se tocaron.")
    else:
        print(f"\n--dry-run: no se escribió nada. Usa --aplicar para persistir.")
        neg_f = sum(1 for x in fuertes if x["util"] == 0)
        print(f"Se marcarían {len(fuertes)} filas, de las cuales {neg_f} "
              f"serían NEGATIVOS REALES para calibrar.")


if __name__ == "__main__":
    main()
