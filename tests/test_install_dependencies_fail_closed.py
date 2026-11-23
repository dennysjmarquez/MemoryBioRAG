"""El instalador debe verificar el conjunto de dependencias antes de continuar."""
from __future__ import annotations

import subprocess

import pytest

import install


def test_installer_rechaza_requirements_ausente(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install, "_ensure_pip_available", lambda: None)
    monkeypatch.setattr(
        install,
        "_pip_install",
        lambda *args, **kwargs: pytest.fail("No debe invocar pip sin requirements.txt"),
    )

    with pytest.raises(SystemExit) as exc:
        install._install_mcp()

    assert exc.value.code == 1


def test_installer_no_continua_si_falla_pip(tmp_path, monkeypatch):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("mcp==1.30.0\n", encoding="utf-8")
    monkeypatch.setattr(install, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install, "_ensure_pip_available", lambda: None)
    calls = []

    def failed_install(args, label=""):
        calls.append((args, label))
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="fallo reproducible")

    monkeypatch.setattr(install, "_pip_install", failed_install)
    monkeypatch.setattr(
        install.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("No debe verificar ni continuar después del fallo de pip"),
    )

    with pytest.raises(SystemExit) as exc:
        install._install_mcp()

    assert exc.value.code == 1
    assert calls and calls[0][0] == ["-r", str(req_file)]


def test_installer_falla_si_pip_check_detecta_conflictos(tmp_path, monkeypatch):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("mcp==1.30.0\nnltk==3.9.4\n", encoding="utf-8")
    monkeypatch.setattr(install, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install, "_ensure_pip_available", lambda: None)
    monkeypatch.setattr(
        install,
        "_pip_install",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )

    def conflicting_check(args, **kwargs):
        if args[-2:] in (["show", "mcp"], ["show", "nltk"]):
            return subprocess.CompletedProcess(args, 0, stdout="Version: 1.0.0\n", stderr="")
        if args[-2:] == ["pip", "check"]:
            return subprocess.CompletedProcess(args, 1, stdout="conflicting dependencies\n", stderr="")
        pytest.fail(f"Comando inesperado: {args}")

    monkeypatch.setattr(install.subprocess, "run", conflicting_check)

    with pytest.raises(SystemExit) as exc:
        install._install_mcp()

    assert exc.value.code == 1


def test_installer_instala_y_verifica_requirements(tmp_path, monkeypatch):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("mcp==1.30.0\nnltk==3.9.4\n", encoding="utf-8")
    monkeypatch.setattr(install, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install, "_ensure_pip_available", lambda: None)
    monkeypatch.setattr(install, "_python", lambda: "python-test")
    install_calls = []

    def successful_install(args, label=""):
        install_calls.append((args, label))
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    run_calls = []

    def successful_run(args, **kwargs):
        run_calls.append(args)
        if args[-2:] == ["show", "mcp"]:
            return subprocess.CompletedProcess(args, 0, stdout="Name: mcp\nVersion: 1.30.0\n", stderr="")
        if args[-2:] == ["show", "nltk"]:
            return subprocess.CompletedProcess(args, 0, stdout="Name: nltk\nVersion: 3.9.4\n", stderr="")
        if args[-2:] == ["pip", "check"]:
            return subprocess.CompletedProcess(args, 0, stdout="No broken requirements found.\n", stderr="")
        pytest.fail(f"Comando inesperado: {args}")

    monkeypatch.setattr(install, "_pip_install", successful_install)
    monkeypatch.setattr(install.subprocess, "run", successful_run)

    install._install_mcp()

    assert install_calls == [(["-r", str(req_file)], "Instalando dependencias fijadas del proyecto...")]
    assert [args[-1] for args in run_calls[:2]] == ["mcp", "nltk"]
    assert run_calls[-1][-2:] == ["pip", "check"]
