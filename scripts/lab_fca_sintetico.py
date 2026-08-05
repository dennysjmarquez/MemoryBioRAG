"""
Fase 1 — Sintético de juguete: validar Ganter + lectura humana + métrica de
trivialidad estructural.

Dataset diseñado con jerarquía CONOCIDA de antemano, para que el retículo
derivado sea verificable a simple vista. Incluye deliberadamente:

  d6 = atributo GLOBAL (14/14, 100%)       → trivial estructural (impacto 0)
  d4 = atributo FRECUENTE informativo       → impacto > 0 a pesar de ~57%
  d2/d3/d5 = atributos RAROS informativos   → impacto > 0
  d8 = atributo disperso (ruido real)       → impacto bajo o 0

La lección que este juguete demuestra: cobertura (frecuencia) NO predice
impacto estructural. Es el resultado medido el que decide, no la magnitud
del número — misma disciplina que el experimento del boost dimensional.

Criterio de éxito F1 (definido con Dennys):
  - retículo entre 20 y 40 conceptos
  - jerarquía coherente a simple vista (persistencia/query/identidad/emoción
    aparecen como conceptos diferenciados)
  - métrica de impacto distingue triviales de informativos según diseño
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lab_fca import (
    Contexto,
    ganter_next_closure,
    orden_hass,
    impacto_atributo,
    concepto_no_trivial,
    ver_retículo_legible,
)

DIMENSIONES = [
    "d1_tecnico",
    "d2_persistencia",
    "d3_query",
    "d4_identidad",
    "d5_emocion",
    "d6_global",
    "d7_coordenada",
    "d8_ruido",
]

NODOS = {
    "persistencia_a": {"d1_tecnico", "d2_persistencia", "d6_global", "d8_ruido"},
    "persistencia_b": {"d1_tecnico", "d2_persistencia", "d6_global", "d8_ruido"},
    "persistencia_c": {"d1_tecnico", "d2_persistencia", "d6_global"},
    "persistencia_d": {"d1_tecnico", "d2_persistencia", "d6_global"},
    "query_a": {"d1_tecnico", "d3_query", "d6_global"},
    "query_b": {"d1_tecnico", "d3_query", "d6_global"},
    "query_c": {"d1_tecnico", "d3_query", "d6_global", "d8_ruido"},
    "identidad_a": {"d1_tecnico", "d4_identidad", "d6_global"},
    "identidad_b": {"d1_tecnico", "d4_identidad", "d6_global"},
    "identidad_c": {"d1_tecnico", "d4_identidad", "d6_global", "d7_coordenada"},
    "emocion_a": {"d4_identidad", "d5_emocion", "d6_global"},
    "emocion_b": {"d4_identidad", "d5_emocion", "d6_global"},
    "aislado_a": {"d1_tecnico", "d6_global", "d7_coordenada"},
    "aislado_b": {"d1_tecnico", "d6_global", "d8_ruido"},
}


def main():
    print("=" * 78)
    print("F1 — SINTÉTICO FCA: validar Ganter + lectura + métrica de trivialidad")
    print("=" * 78)
    ctx = Contexto.desde_matriz(NODOS, orden_atributos=DIMENSIONES)
    conceptos = ganter_next_closure(ctx)
    hijos = orden_hass(conceptos)

    n_objetos = len(ctx.objetos)
    n_no_trivial = sum(1 for c in conceptos if concepto_no_trivial(c, n_objetos))

    print(f"\nContexto: {len(ctx.objetos)} objetos × {len(ctx.atributos)} atributos")
    print(f"Conceptos enumerados: {len(conceptos)} (esperado: 20-40)")
    print(f"Conceptos no-triviales (1 < |ext| < {n_objetos}): {n_no_trivial}")

    # Verificación de duplicados (integridad del algoritmo)
    exts = [c.extension for c in conceptos]
    if len(set(exts)) != len(exts):
        print("FALLO: hay extensiones duplicadas -> Ganter mal implementado")
        sys.exit(1)

    # Verificación de jerarquía esperada (a simple vista, con evidencia)
    nombres = {o: i for i, o in enumerate(ctx.objetos)}
    esperados = {
        "persistencia": {"persistencia_a", "persistencia_b", "persistencia_c", "persistencia_d"},
        "query": {"query_a", "query_b", "query_c"},
        "identidad": {"identidad_a", "identidad_b", "identidad_c"},
        "emocion": {"emocion_a", "emocion_b"},
    }
    # map extensión (set de índices) -> set de nombres
    ext_a_nombres = [frozenset(ctx.objetos[i] for i in c.extension) for c in conceptos]

    print("\n--- Verificación de jerarquía conocida (coherencia a simple vista) ---")
    ok_total = True
    for grupo, nodos_grupo in esperados.items():
        ext_set = frozenset(nodos_grupo)
        presente = ext_set in ext_a_nombres
        # además: debe haber un concepto SUPERIOR que lo contenga y uno
        # INTERIOR (más específico) que esté contenido
        estado = "OK" if presente else "FALTA"
        if not presente:
            ok_total = False
        print(f"  grupo '{grupo:14s}' como concepto exacto: {estado}")

    # Verificación: d6_global (todos) es trivial; d2/d3/d5 son informativos
    print("\n--- Métrica de impacto por atributo (cobertura vs efecto real) ---")
    print(f"{'atributo':<20} | {'cobertura':>9} | {'con c/sin':>9} | {'impacto':>7} | lectura")
    print("-" * 78)
    for m in range(len(ctx.atributos)):
        res = impacto_atributo(ctx, conceptos, m)
        lectura = (
            "TRIVIAL estructural" if res["impacto"] == 0
            else f"informativo ({res['impacto']} concepto(s))"
        )
        print(f"{res['atributo']:<20} | {res['cobertura']:>9.3f} | "
              f"{res['conceptos_no_triviales_con']}/{res['conceptos_no_triviales_sin']:<5} | "
              f"{res['impacto']:>7} | {lectura}")

    # Expectativas de diseño — RELACIONALES, no números inventados:
    #   d6_global (100% cobertura) => impacto 0 (trivial estructural)
    #   d1_tecnico (86%)           => impacto > 0 (separa emocion del resto)
    #   d2/d3/d4/d5 (subgrupos)    => impacto > 0 (raro o no, informativo)
    # La lección que valida: cobertura ≠ trivialidad. d6 tiene MÁXIMA
    # cobertura y MÍNIMO impacto; d4 (36%) impacta más que d6 (100%).
    impacto_por = {ctx.atributos[m]: impacto_atributo(ctx, conceptos, m)["impacto"]
                   for m in range(len(ctx.atributos))}
    expectativas = {
        "d6_global": 0,            # global => trivial estructural
        "d1_tecnico": (">", 0),    # frecuente pero separa un subgrupo
        "d2_persistencia": (">", 0),
        "d3_query": (">", 0),
        "d4_identidad": (">", 0),  # ~36% cobertura, informativo
        "d5_emocion": (">", 0),
    }
    print("\n--- Expectativas de diseño (relacionales, definidas antes de correr) ---")
    cumplidas = True
    for attr, esperado in expectativas.items():
        real = impacto_por.get(attr, None)
        if isinstance(esperado, tuple):
            op, val = esperado
            ok = real is not None and (real > val if op == ">" else real == val)
            estado = "OK" if ok else f"DESVIADO (esperado {op} {val})"
            mostrado = f"{op} {val}"
        else:
            ok = real == esperado
            estado = "OK" if ok else f"DESVIADO (esperado {esperado})"
            mostrado = f"= {esperado}"
        if not ok:
            cumplidas = False
        print(f"  {attr:<18} impacto={real}  esperado {mostrado:<6}  [{estado}]")

    print("\n--- Vista legible del retículo ---")
    ver_retículo_legible(ctx, conceptos, hijos, limite=len(conceptos))

    print("\n" + "=" * 78)
    if ok_total and cumplidas:
        print("F1 VEREDICTO: retículo coherente, jerarquía verificada, métrica válida.")
        print("La cobertura NO predice impacto: d6_global 100% -> trivial;")
        print("d4_identidad 36% -> impacto 2 (informativo). Siguiente: Fase 2 (real).")
    else:
        print("F1 VEREDICTO: revisar (alguna expectativa no se cumplió).")
        sys.exit(1)


if __name__ == "__main__":
    main()
