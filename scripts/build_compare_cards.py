"""Merge matched charter.eval arms into one payload for the pairwise comparator.

Every arm annotated the same documents at the same reflection points, so the
document is stored once and each arm contributes only its own annotation.

Per-arm constitution sections are mandatory, not a nicety: all three
constitutions number their sections identically (1.1, 2.3, ...) while meaning
different things, so a single shared section map would show one arm's text under
another arm's citation. ``sections`` is therefore keyed by arm.

Usage:
    python3 scripts/build_compare_cards.py            # -> prompt_pipeline/compare_cards.json
    python3 scripts/build_compare_cards.py --out PATH
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.charter.eval.report import parse_charter_sections
from pipeline.config import PROJECT_ROOT

# label -> (cards json, constitution, generator prompt, guidelines)
ARMS: dict[str, tuple[str, str, str, str]] = {
    "MR v0.2": (
        "data/pipeline/charter_eval/mr_v02_matched_100/cards_mr.json",
        "resources/ModelRaisingConstitution_v0.2.md",
        "generator_reflection_v7.md",
        "resources/ValueAnnotationGuidelines_v0.1.md",
    ),
    "Normative hierarchy": (
        "prompt_pipeline/review_cards.json",
        "resources/NormativeHierarchyConstitution_v0.1.md",
        "generator_reflection_normative_hierarchy_v1.md",
        "resources/NormativeHierarchyAnnotationGuidelines_v0.1.md",
    ),
    "Utilitarian": (
        "data/pipeline/charter_eval/utilitarian_matched_100/cards_utilitarian.json",
        "resources/UtilitarianConstitution_v0.1.md",
        "generator_reflection_v7.md",
        "resources/UtilitarianAnnotationGuidelines_v0.1.md",
    ),
}

ANNOTATION_FIELDS = (
    "analysis",
    "reflection_1p",
    "reflection_3p",
    "charter_elements",
    "judge_model",
    "judge_scores",
    "judge_aggregate",
    "judge_decision",
    "judge_reasoning",
)


def build(arms: dict[str, tuple[str, str, str, str]]) -> dict:
    """Merge the arms into ``{runs, sections, items}``, one entry per document."""
    loaded: dict[str, dict[str, dict]] = {}
    meta: dict[str, dict] = {}
    sections: dict[str, dict[str, str]] = {}

    for label, (cards_path, charter, prompt, guidelines) in arms.items():
        payload = json.loads((PROJECT_ROOT / cards_path).read_text(encoding="utf-8"))
        cards = {c["item_id"]: c for c in payload["cards"]}
        assert cards, f"{label}: no cards in {cards_path}"
        loaded[label] = cards
        charter_text = (PROJECT_ROOT / charter).read_text(encoding="utf-8")
        sections[label] = parse_charter_sections(charter_text)
        run_ids = sorted({c["run_id"] for c in cards.values()})
        assert len(run_ids) == 1, f"{label}: expected one run, got {run_ids}"
        meta[label] = {
            "label": label,
            "run_id": run_ids[0],
            "constitution": Path(charter).name,
            "guidelines": Path(guidelines).name,
            "prompt": prompt,
            "gen_model": next(iter(cards.values()))["gen_model"],
            "n_sections": len(sections[label]),
            "judged": sum(1 for c in cards.values() if c.get("judge_decision")),
        }

    shared = set.intersection(*[set(c) for c in loaded.values()])
    dropped = {lab: sorted(set(c) - shared) for lab, c in loaded.items()}
    for lab, missing in dropped.items():
        if missing:
            print(f"note: {lab} has {len(missing)} item(s) no other arm covers; excluded")

    labels = list(arms)
    items = []
    for item_id in sorted(shared):
        base = loaded[labels[0]][item_id]
        for lab in labels[1:]:
            other = loaded[lab][item_id]
            assert other["text"] == base["text"], f"{item_id}: text differs in {lab}"
            assert other["reflection_point"] == base["reflection_point"], (
                f"{item_id}: reflection_point differs in {lab} — arms are not matched"
            )
        items.append(
            {
                "item_id": item_id,
                "text": base["text"],
                "safety_score": base["safety_score"],
                "reflection_point": base["reflection_point"],
                "arms": {
                    lab: {f: loaded[lab][item_id].get(f) for f in ANNOTATION_FIELDS}
                    for lab in labels
                },
            }
        )
    return {"runs": [meta[lab] for lab in labels], "sections": sections, "items": items}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="prompt_pipeline/compare_cards.json", type=Path)
    args = ap.parse_args()

    payload = build(ARMS)
    out = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(payload['items'])} items x {len(payload['runs'])} arms")
    for r in payload["runs"]:
        print(
            f"  {r['label']:22} {r['constitution']:38} {r['n_sections']:>3} sections"
            f"  judged={r['judged']:>3}"
        )
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
