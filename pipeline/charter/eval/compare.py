"""Constitution comparison: generate reflections for the same item pool under
each constitution, and join them into a portable side-by-side payload.

The three constitutions (value, normative hierarchy, utilitarian) each pair a
charter file with writing guidelines and a generator prompt built on the same
skeleton, so differences between the three columns are attributable to the
constitution, not the prompt format.

Runs live at ``<eval_dir>/<base_run_id>__<key>`` — one generator-eval run per
constitution, all sharing one item pool. ``build_comparison`` joins them by
item_id; the dashboard reads the resulting ``comparison.json``.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

from pipeline.config import AppConfig, CandidateModel, PROJECT_ROOT
from pipeline.log import logger
from pipeline.charter.eval.eval_generators import _eval_root
from pipeline.charter.eval.rank import _read_jsonl, _resolve_run_dir
from pipeline.charter.eval.report import _CITE_RE, parse_charter_sections

GENERATOR_ALIAS = "qwen3.6-35b-a3b"

CONSTITUTIONS: list[dict] = [
    {
        "key": "value",
        "label": "Value Constitution v0.2",
        "charter_path": "resources/ModelRaisingConstitution_v0.2.md",
        "guidelines_path": "resources/ValueAnnotationGuidelines_v0.1.md",
        "prompt": "generator_reflection_value_v1.md",
    },
    {
        "key": "normative_hierarchy",
        "label": "Normative Hierarchy v0.1",
        "charter_path": "resources/NormativeHierarchyConstitution_v0.1.md",
        "guidelines_path": "resources/NormativeHierarchyAnnotationGuidelines_v0.1.md",
        "prompt": "generator_reflection_normative_hierarchy_v1.md",
    },
    {
        "key": "utilitarian",
        "label": "Utilitarian v0.1",
        "charter_path": "resources/UtilitarianConstitution_v0.1.md",
        "guidelines_path": "resources/UtilitarianAnnotationGuidelines_v0.1.md",
        "prompt": "generator_reflection_utilitarian_v1.md",
    },
]

DEFAULT_COMPARISON_PATH = PROJECT_ROOT / "dashboard" / "data" / "comparison.json"


def compare_run_id(base_run_id: str, key: str) -> str:
    return f"{base_run_id}__{key}"


def _configure_constitution(cfg: AppConfig, con: dict) -> None:
    """Point cfg at one constitution's charter, guidelines, and prompt."""
    cfg.charter_path = con["charter_path"]
    cfg.writing_guidelines_path = con["guidelines_path"]
    cfg.charter.eval.generator_eval.mode = "reflection"
    cfg.charter.eval.generator_eval.candidates = [
        CandidateModel(
            alias=GENERATOR_ALIAS,
            api_name="qwen/qwen3.6-35b-a3b",
            hf_slug="Qwen/Qwen3.6-35B-A3B-FP8",
            endpoint="https://openrouter.ai/api/v1",
            prompt_reflection=con["prompt"],
            context_window_tokens=32768,
            include_reflection_3p=False,
        )
    ]


def _seed_items_from_run(
    eval_dir: Path, source_run_id: str, target_run_id: str
) -> None:
    """Copy items.jsonl from an existing run so all runs share one pool."""
    src = eval_dir / source_run_id / "items.jsonl"
    if not src.is_file():
        raise FileNotFoundError(f"source items pool not found: {src}")
    dst_dir = eval_dir / target_run_id
    dst = dst_dir / "items.jsonl"
    if dst.exists():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    logger.info("seeded {} items pool from {}", target_run_id, source_run_id)


def run_compare_generation(
    cfg: AppConfig,
    base_run_id: str,
    *,
    n_items: int = 100,
    seed: int = 42,
    source_items_run: str | None = None,
    max_concurrent: int = 200,
) -> list[str]:
    """Generate reflections under each constitution on one shared item pool.

    Returns the list of per-constitution run ids. Each constitution gets its
    own run dir; ``source_items_run`` (optional) donates its items.jsonl so
    the pool is byte-identical across runs instead of merely seed-identical.
    """
    from pipeline.charter.eval.eval_generators import run_generator_eval

    ge = cfg.charter.eval.generator_eval
    ge.n_items = n_items
    ge.seed = seed
    ge.max_concurrent = max_concurrent
    ge.safety_values = [0, 1, 2, 3, 4]

    root = _eval_root(cfg)
    run_ids: list[str] = []
    for con in CONSTITUTIONS:
        run_id = compare_run_id(base_run_id, con["key"])
        run_ids.append(run_id)
        run_cfg = copy.deepcopy(cfg)
        _configure_constitution(run_cfg, con)
        if source_items_run:
            _seed_items_from_run(root, source_items_run, run_id)
        logger.info(
            "constitution-compare: generating {} ({})", run_id, con["label"]
        )
        run_generator_eval(run_cfg, run_id, stage="generate")
    return run_ids


def _load_run(eval_dir: Path | str | None, run_id: str) -> tuple[list[dict], dict]:
    """Read one run's items and generations keyed by item_id."""
    run_dir = _resolve_run_dir(run_id, eval_dir)
    items_path = run_dir / "items.jsonl"
    if not items_path.is_file():
        raise FileNotFoundError(f"no items.jsonl in {run_dir}")
    items = [r for r in _read_jsonl(items_path) if r.get("item_id")]

    gen_dir = run_dir / "generations"
    gen_files = sorted(gen_dir.glob("*.jsonl")) if gen_dir.exists() else []
    if not gen_files:
        raise FileNotFoundError(f"no generations/*.jsonl in {run_dir}")
    if len(gen_files) > 1:
        raise ValueError(
            f"{run_dir} has {len(gen_files)} generation files; expected exactly 1"
        )
    gens = {
        str(r["item_id"]): r
        for r in _read_jsonl(gen_files[0])
        if r.get("item_id")
    }
    return items, gens


def _citations(reflection: str) -> list[str]:
    """Individual section ids cited in a reflection, in order, deduplicated."""
    seen: list[str] = []
    for bracket in _CITE_RE.findall(reflection or ""):
        for part in bracket.strip("[]").split(","):
            sid = part.strip()
            if sid and sid not in seen:
                seen.append(sid)
    return seen


def _generation_view(row: dict | None) -> dict | None:
    if row is None:
        return None
    reflection = row.get("reflection_1p") or ""
    return {
        "analysis": row.get("analysis") or "",
        "reflection_1p": reflection,
        "citations": _citations(reflection),
        "n_words": len(reflection.split()),
    }


def build_comparison(base_run_id: str, *, eval_dir: Path | str | None = None) -> dict:
    """Join the three constitution runs into one side-by-side payload."""
    per_con: dict[str, tuple[list[dict], dict]] = {}
    for con in CONSTITUTIONS:
        run_id = compare_run_id(base_run_id, con["key"])
        per_con[con["key"]] = _load_run(eval_dir, run_id)

    id_sets = {
        key: {str(it["item_id"]) for it in items}
        for key, (items, _) in per_con.items()
    }
    first_key = CONSTITUTIONS[0]["key"]
    for key, ids in id_sets.items():
        if ids != id_sets[first_key]:
            raise ValueError(
                f"item pools differ between runs: {first_key} vs {key} "
                f"(symmetric difference: {sorted(ids ^ id_sets[first_key])[:5]}…)"
            )

    base_items = per_con[first_key][0]
    items_out: list[dict] = []
    for it in base_items:
        item_id = str(it["item_id"])
        items_out.append(
            {
                "item_id": item_id,
                "text": it.get("text") or "",
                "reflection_point": it.get("reflection_point"),
                "safety_score": it.get("safety_score"),
                "language": it.get("subset") or "dolma3",
                "generations": {
                    key: _generation_view(gens.get(item_id))
                    for key, (_, gens) in per_con.items()
                },
            }
        )
    items_out.sort(key=lambda x: (-(x["safety_score"] or 0), x["item_id"]))

    constitutions_out = []
    for con in CONSTITUTIONS:
        charter_path = Path(con["charter_path"])
        if not charter_path.is_absolute():
            charter_path = PROJECT_ROOT / charter_path
        constitutions_out.append(
            {
                "key": con["key"],
                "label": con["label"],
                "prompt": con["prompt"],
                "charter_path": con["charter_path"],
                "charter_sections": parse_charter_sections(
                    charter_path.read_text(encoding="utf-8")
                ),
            }
        )

    return {
        "base_run_id": base_run_id,
        "constitutions": constitutions_out,
        "items": items_out,
    }


def write_comparison(
    base_run_id: str,
    out_path: Path | str,
    *,
    eval_dir: Path | str | None = None,
) -> int:
    payload = build_comparison(base_run_id, eval_dir=eval_dir)
    payload["n_items"] = len(payload["items"])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload["n_items"]
