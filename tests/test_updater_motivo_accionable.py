"""`biorag update` debe decir POR QUÉ no puede empezar cuando la causa es accionable.

Antes, UPSTREAM_REQUIRED, DETACHED_HEAD, INSTALL_METHOD_UNSUPPORTED, etc. terminaban en
"BioRAG could not safely start the update... contact support" y el usuario no sabía que
bastaba con, por ejemplo, configurar el upstream de la rama.
"""
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import pytest

from core import updater


def _correr(exc):
    err = io.StringIO()
    with patch.object(updater, "plan", side_effect=exc), \
            redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = updater.main(["--dry-run", "--db", "/tmp/no_importa.db"])
    return code, json.loads(err.getvalue().strip().splitlines()[-1])


@pytest.mark.parametrize("codigo,texto", [
    ("UPSTREAM_REQUIRED", "Configure an upstream for the current branch."),
    ("DETACHED_HEAD", "Check out a branch with an upstream before updating."),
    ("INSTALL_METHOD_UNSUPPORTED", "This is not a Git checkout."),
    ("GIT_OPERATION_IN_PROGRESS", "A Git operation is in progress (MERGE_HEAD)."),
])
def test_motivo_accionable_visible(codigo, texto):
    code, out = _correr(updater.UpdateError(f"{codigo}: {texto}"))
    assert code == 1
    assert out["status"] == "error"
    assert texto in out["message"] and codigo in out["message"]
    assert "contact support" not in out["message"]


def test_error_desconocido_sigue_siendo_generico():
    code, out = _correr(OSError("disco raro"))
    assert code == 1
    assert "could not safely start the update" in out["message"]
    assert "disco raro" not in out["message"]  # no se filtran detalles internos


def test_mensajes_especificos_previos_intactos():
    _, out = _correr(updater.UpdateError("LOCAL_CHANGES: x"))
    assert "local changes" in out["message"]
    _, out = _correr(updater.UpdateError("NON_FAST_FORWARD: x"))
    assert "already up to date" in out["message"]
