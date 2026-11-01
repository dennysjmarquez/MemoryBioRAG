"""Controles de trazabilidad sintética: sin MCP, bases ni campaña E1."""
import json
from pathlib import Path

import pytest

from scripts.auditar_revision_exploratoria_e1 import load_package, parse_review, summarize

CASE = "case-0123456789abcdef"
ITEM = "item-0123456789abcdef"


def files(tmp_path: Path):
    package = tmp_path / "package.jsonl"
    package.write_text(json.dumps({"case_code": CASE, "items": [{"item_code": ITEM, "text": "espera antes de reintentar"}]}) + "\n", encoding="utf-8")
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text(f"Caso `{CASE}`\n`{ITEM}`\n- Categoría: PI.\n- Evidencia: «espera antes».\n", encoding="utf-8")
    two.write_text(f"Caso `{CASE}`\n`{ITEM}`\n- **Categoría provisional:** respuesta directa a la pregunta\n- **Evidencia textual:** \"espera antes de reintentar\"\n", encoding="utf-8")
    return package, one, two


def test_summary_and_exact_quotes(tmp_path):
    package, one, two = files(tmp_path)
    result = summarize(package, one, two)
    assert (result["cases"], result["presentations"]) == (1, 1)
    assert (result["same_categories"], result["different_categories"]) == (0, 1)
    assert result["cases_without_direct_label"] == [1, 0]
    assert result["quote_status"] == [{"exact": 1}, {"exact": 1}]
    assert "espera antes" not in json.dumps(result)


def test_nonliteral_and_missing_quotes_are_not_misrepresented(tmp_path):
    package, one, two = files(tmp_path)
    one.write_text(one.read_text().replace("«espera antes»", "«espera después»"), encoding="utf-8")
    two.write_text(two.read_text().replace('"espera antes de reintentar"', "sin evidencia textual suficiente"), encoding="utf-8")
    result = summarize(package, one, two)
    assert result["quote_status"] == [{"not_exact": 1}, {"missing_quote": 1}]


def test_missing_and_duplicate_review_pairs_fail_closed(tmp_path):
    package, one, _ = files(tmp_path)
    pairs = load_package(package)
    original = one.read_text()
    one.write_text(original.replace(ITEM, "item-ffffffffffffffff"))
    with pytest.raises(ValueError, match="extra or duplicate"):
        parse_review(one, pairs)
    one.write_text(original + original)
    with pytest.raises(ValueError, match="duplicate review case"):
        parse_review(one, pairs)
    one.write_text(f"Caso `{CASE}`\n")
    with pytest.raises(ValueError, match="cover every package pair"):
        parse_review(one, pairs)


def test_invalid_or_missing_category_fails_closed(tmp_path):
    package, one, _ = files(tmp_path)
    pairs = load_package(package)
    original = one.read_text()
    one.write_text(original.replace("Categoría: PI.", "Categoría: inventada."))
    with pytest.raises(ValueError, match="unrecognized"):
        parse_review(one, pairs)
    one.write_text(original.replace("Categoría: PI.", "Sin categoría"))
    with pytest.raises(ValueError, match="missing category"):
        parse_review(one, pairs)


def test_duplicate_package_case_or_item_fails_closed(tmp_path):
    package, _, _ = files(tmp_path)
    original = package.read_text()
    package.write_text(original + original)
    with pytest.raises(ValueError, match="duplicate case"):
        load_package(package)
    case = json.loads(original)
    case["items"].append(case["items"][0])
    package.write_text(json.dumps(case) + "\n")
    with pytest.raises(ValueError, match="duplicate item"):
        load_package(package)
    case["items"] = []
    package.write_text(json.dumps(case) + "\n")
    with pytest.raises(ValueError, match="case without items"):
        load_package(package)
