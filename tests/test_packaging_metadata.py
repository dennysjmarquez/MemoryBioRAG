"""Package metadata and installer lockfile must declare one tested dependency set."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _exact_pins(specifications: list[str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for specification in specifications:
        name, separator, version = specification.partition("==")
        assert separator and name and version, f"Dependency must be exactly pinned: {specification}"
        canonical = _canonical_name(name)
        assert canonical not in pins, f"Duplicate dependency: {name}"
        pins[canonical] = version
    return pins


def test_package_metadata_matches_installer_requirements():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    lock_pins = _exact_pins(requirements)
    project_pins = _exact_pins(project["dependencies"])
    dev_pins = _exact_pins(project["optional-dependencies"]["dev"])

    assert project_pins | dev_pins == lock_pins
    assert project_pins.keys().isdisjoint(dev_pins)
