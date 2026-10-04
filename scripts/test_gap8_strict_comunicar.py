"""Test del mecanismo (c) 'esquemas estrictos' — hueco 8 — sobre la tool MCP 'comunicar'.

Qué valida: el camino REAL de validación de FastMCP (arg_model.model_validate),
que es exactamente lo que ejecuta call_fn_with_arg_validation antes de invocar
la función de la tool. No escribe en la base: solo valida argumentos.

Uso:
  python3 scripts/test_gap8_strict_comunicar.py                  # snapshot (pre-edit)
  python3 scripts/test_gap8_strict_comunicar.py --expect-strict  # post-edit (asserts)

Creado por: Athena-OEC, 2026-10-04 (ejercicio hueco 8 — mecanismo (c)).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from core.mcp_server import communication  # noqa: E402

# (nombre, args, debe_rechazar_post_edit)
CASES = [
    ("destino con espacios y SQL",
     {"destino": "a b; DROP TABLE x", "mensaje": "hola", "origen": "athena"}, True),
    ("mensaje vacio",
     {"destino": "artemis", "mensaje": "", "origen": "athena"}, True),
    ("mensaje gigante (30001 chars)",
     {"destino": "artemis", "mensaje": "x" * 30001, "origen": "athena"}, True),
    ("origen con caracteres raros",
     {"destino": "todos", "mensaje": "hola", "origen": "athena'; --"}, True),
    ("payload valido",
     {"destino": "artemis", "mensaje": "probando", "origen": "Athena-OEC"}, False),
    ("key extra (solo reporte, no se afirma)",
     {"destino": "artemis", "mensaje": "hola", "origen": "athena", "extra": 1}, None),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-strict", action="store_true",
                        help="Post-edit: exige rechazo de payloads invalidos")
    args = parser.parse_args()

    mcp = FastMCP("gap8-probe")
    communication.register(mcp)
    tool = mcp._tool_manager._tools["comunicar"]
    arg_model = tool.fn_metadata.arg_model

    print("=" * 72)
    print("GAP-8 mecanismo (c) — strict schema en 'comunicar'")
    print(f"Modo: {'EXPECT-STRICT (post-edit)' if args.expect_strict else 'SNAPSHOT (pre-edit)'}")
    print("=" * 72)

    failures = []
    for name, case_args, must_reject in CASES:
        try:
            arg_model.model_validate(dict(case_args))
            verdict = "ACEPTA"
        except Exception as exc:  # pydantic.ValidationError
            verdict = f"RECHAZA ({type(exc).__name__})"
        ok = True
        if must_reject is True:
            ok = verdict.startswith("RECHAZA") if args.expect_strict else True
            if args.expect_strict and not ok:
                failures.append(f"esperaba RECHAZA y salio ACEPTA: {name}")
        elif must_reject is False:
            ok = verdict == "ACEPTA"
            if args.expect_strict and not ok:
                failures.append(f"esperaba ACEPTA y salio {verdict}: {name}")
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {verdict:<28} | {name}")

    # Visibilidad client-side: las restricciones deben aparecer en el inputSchema
    schema = tool.parameters
    props = schema.get("properties", {})
    destino_schema = props.get("destino", {})
    mensaje_schema = props.get("mensaje", {})
    print("-" * 72)
    print(f"  inputSchema destino: {json.dumps(destino_schema, default=str)[:200]}")
    print(f"  inputSchema mensaje: {json.dumps(mensaje_schema, default=str)[:200]}")

    if args.expect_strict:
        if "pattern" not in destino_schema:
            failures.append("inputSchema destino sin 'pattern' (invisible para el cliente)")
        if "maxLength" not in mensaje_schema:
            failures.append("inputSchema mensaje sin 'maxLength' (invisible para el cliente)")
        print("-" * 72)
        if failures:
            print("RESULTADO: FALLA")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("RESULTADO: todos los asserts pasan (strict activo y visible)")
        return 0

    print("-" * 72)
    print("RESULTADO: snapshot tomado (correr con --expect-strict tras el edit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
