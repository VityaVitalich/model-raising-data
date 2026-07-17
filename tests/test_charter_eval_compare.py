"""Tests for pipeline.charter.eval.compare — the constitution-comparison builder.

Spec:
- CONSTITUTIONS is an ordered list of exactly three entries
  (value, normative_hierarchy, utilitarian). Each entry names a charter file,
  a guidelines file, and a generator prompt that must exist in the repo.
- compare_run_id(base, key) -> "<base>__<key>".
- build_comparison(base_run_id, eval_dir) joins the three runs' generations by
  item_id into a portable payload for the dashboard. It crashes on missing
  runs and on item-pool mismatches (no fallbacks); a missing generation for a
  single item is reported as None for that constitution, never invented.
- Items are ordered by safety_score descending, ties broken by item_id.
- write_comparison writes the JSON payload and returns the item count.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.charter.eval import compare
from pipeline.config import PROJECT_ROOT


# --- fixtures ---------------------------------------------------------------

CHARTER_MD = """# Test Charter

## 1.1 Alpha

Alpha body.

## 1.2 Beta

Beta body.
"""

ITEMS = [
    {"item_id": "a", "text": "text a", "reflection_point": 6, "safety_score": 0, "subset": "dolma3"},
    {"item_id": "b", "text": "text b", "reflection_point": 6, "safety_score": 3, "subset": "dolma3"},
]


def _gen_row(item_id: str, reflection: str, analysis: str = "an") -> dict:
    return {"item_id": item_id, "reflection_1p": reflection, "analysis": analysis}


def _make_run(
    root: Path,
    base: str,
    key: str,
    items: list[dict],
    gens: list[dict],
    gen_stem: str = "modelx__promptx.md",
) -> Path:
    run_dir = root / f"{base}__{key}"
    (run_dir / "generations").mkdir(parents=True)
    (run_dir / "items.jsonl").write_text(
        "".join(json.dumps(it) + "\n" for it in items), encoding="utf-8"
    )
    (run_dir / "generations" / f"{gen_stem}.jsonl").write_text(
        "".join(json.dumps(g) + "\n" for g in gens), encoding="utf-8"
    )
    (run_dir / "metadata.json").write_text(json.dumps({"type": "generator_eval"}))
    return run_dir


@pytest.fixture()
def eval_root(tmp_path, monkeypatch):
    charter = tmp_path / "charter.md"
    charter.write_text(CHARTER_MD, encoding="utf-8")
    cons = [
        {**c, "charter_path": str(charter)} for c in compare.CONSTITUTIONS
    ]
    monkeypatch.setattr(compare, "CONSTITUTIONS", cons)
    for c in cons:
        _make_run(
            tmp_path,
            "base",
            c["key"],
            ITEMS,
            [
                _gen_row("a", f"Reflection {c['key']} a [1.1]"),
                _gen_row("b", f"Reflection {c['key']} b [1.1, 1.2]"),
            ],
        )
    return tmp_path


# --- registry sanity ---------------------------------------------------------


def test_constitutions_registry():
    keys = [c["key"] for c in compare.CONSTITUTIONS]
    assert keys == ["value", "normative_hierarchy", "utilitarian"]
    for c in compare.CONSTITUTIONS:
        assert c["label"]
        assert (PROJECT_ROOT / c["charter_path"]).is_file(), c["charter_path"]
        assert (PROJECT_ROOT / c["guidelines_path"]).is_file(), c["guidelines_path"]
        prompt = (
            PROJECT_ROOT / "final_prompts" / compare.GENERATOR_ALIAS / c["prompt"]
        )
        assert prompt.is_file(), prompt


def test_compare_run_id():
    assert compare.compare_run_id("base", "utilitarian") == "base__utilitarian"


# --- build_comparison --------------------------------------------------------


def test_build_comparison_joins_by_item(eval_root):
    payload = compare.build_comparison("base", eval_dir=eval_root)
    assert payload["base_run_id"] == "base"
    assert [c["key"] for c in payload["constitutions"]] == [
        "value",
        "normative_hierarchy",
        "utilitarian",
    ]
    # order: safety_score desc -> b (3) before a (0)
    assert [it["item_id"] for it in payload["items"]] == ["b", "a"]
    b = payload["items"][0]
    assert b["text"] == "text b"
    assert b["safety_score"] == 3
    assert set(b["generations"].keys()) == {
        "value",
        "normative_hierarchy",
        "utilitarian",
    }
    gen = b["generations"]["utilitarian"]
    assert gen["reflection_1p"] == "Reflection utilitarian b [1.1, 1.2]"
    assert gen["citations"] == ["1.1", "1.2"]
    assert gen["n_words"] == len("Reflection utilitarian b [1.1, 1.2]".split())


def test_build_comparison_charter_sections(eval_root):
    payload = compare.build_comparison("base", eval_dir=eval_root)
    for c in payload["constitutions"]:
        assert "1.1" in c["charter_sections"]
        assert "Alpha" in c["charter_sections"]["1.1"]


def test_build_comparison_missing_run_raises(eval_root):
    import shutil

    shutil.rmtree(eval_root / "base__utilitarian")
    with pytest.raises((ValueError, FileNotFoundError)):
        compare.build_comparison("base", eval_dir=eval_root)


def test_build_comparison_item_mismatch_raises(eval_root):
    run = eval_root / "base__utilitarian"
    other = [dict(ITEMS[0]), {**ITEMS[1], "item_id": "zz"}]
    (run / "items.jsonl").write_text(
        "".join(json.dumps(it) + "\n" for it in other), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="item"):
        compare.build_comparison("base", eval_dir=eval_root)


def test_build_comparison_missing_generation_is_none(eval_root):
    run = eval_root / "base__utilitarian"
    gen_file = next((run / "generations").glob("*.jsonl"))
    rows = [json.loads(l) for l in gen_file.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r["item_id"] != "a"]
    gen_file.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    payload = compare.build_comparison("base", eval_dir=eval_root)
    a = next(it for it in payload["items"] if it["item_id"] == "a")
    assert a["generations"]["utilitarian"] is None
    assert a["generations"]["value"] is not None


def test_write_comparison(eval_root, tmp_path):
    out = tmp_path / "out" / "comparison.json"
    n = compare.write_comparison("base", out, eval_dir=eval_root)
    assert n == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["n_items"] == 2
    assert len(payload["items"]) == 2
