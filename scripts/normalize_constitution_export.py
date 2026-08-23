"""Normalize a Google-Docs-exported constitution / annotation guide for the pipeline.

Exports arrive with section numbers as plain text lines and domain groups as
bold ``## **Domain N**`` headers. Two consumers require real markdown headers:

- ``pipeline/charter/eval/report.py::parse_charter_sections`` matches
  ``^#{2,3} X.Y Title`` for the review-card section popups, and closes the
  current section only on a new ``## X.Y`` or an h1 line — so a bold ``##
  **Domain N**`` would be swallowed into the previous section's body.
- ``pipeline/config.py`` builds ``_CHARTER_ID_SET`` the same way;
  ``extract_charter_elements`` silently drops any ``[X.Y]`` citation whose id
  is not in that set, so unpromoted sections make every citation vanish.

Validation fails loudly on duplicate section ids and on citations that resolve
to no section (the failure mode is silent data loss otherwise).

Usage:
    python3 scripts/normalize_constitution_export.py \\
        --constitution ~/Downloads/"Utilitarian Constitution.md" \\
        --guidelines   ~/Downloads/"Utilitarian Annotation Guide.md" \\
        --out-constitution resources/UtilitarianConstitution_v0.1.md \\
        --out-guidelines   resources/UtilitarianAnnotationGuidelines_v0.1.md

    # also strip \\[ \\] \\. export escapes (lossless; markdown renders them bare)
    python3 scripts/normalize_constitution_export.py ... --unescape
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SECTION_RE = re.compile(r"^#{2,3}\s+(\d+\.\d+)\s+(.*)$")
_PLAIN_SECTION_RE = re.compile(r"^(\d+\.\d+)\s+\S")
_BOLD_DOMAIN_RE = re.compile(r"^##\s+\*\*(Domain|[A-Z])")
_CITATION_RE = re.compile(r"\\?\[([0-9.,\s\\\]\[–-]+?)\\?\]")
_ESCAPE_RE = re.compile(r"\\([\[\]().*+#!_-])")


def normalize_constitution(text: str) -> tuple[str, int, int]:
    """Promote plain ``X.Y Title`` lines to ``## X.Y Title`` and bold domain headers to h1.

    Returns ``(text, n_sections_promoted, n_domains_promoted)``.
    """
    out: list[str] = []
    n_sec = n_dom = 0
    for line in text.splitlines():
        if _PLAIN_SECTION_RE.match(line):
            out.append("## " + line)
            n_sec += 1
        elif _BOLD_DOMAIN_RE.match(line):
            out.append("#" + line[2:])
            n_dom += 1
        else:
            out.append(line)
    return "\n".join(out) + "\n", n_sec, n_dom


def unescape(text: str) -> str:
    """Drop backslash escapes the exporter added before markdown punctuation.

    Lossless for our purposes: ``\\[2.3\\]`` renders as ``[2.3]`` anyway, and the
    bare form is what ``extract_charter_elements`` and JSON string values need.
    """
    return _ESCAPE_RE.sub(r"\1", text)


def section_ids(text: str) -> list[str]:
    """Section ids in file order, as the pipeline's own parsers see them."""
    return [m.group(1) for line in text.splitlines() if (m := SECTION_RE.match(line))]


def cited_ids(text: str) -> set[str]:
    """Every ``X.Y`` appearing inside (optionally escaped) bracket citations."""
    return {
        c
        for group in _CITATION_RE.findall(text)
        for c in re.findall(r"\d+\.\d+", group)
    }


def validate(constitution: str, guidelines: str) -> list[str]:
    """Return a list of problems; empty means the pair is pipeline-safe."""
    problems: list[str] = []
    ids = section_ids(constitution)
    if not ids:
        problems.append("constitution has no parseable '## X.Y Title' sections")
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate section ids: {dupes}")
    id_set = set(ids)
    for name, text in (("constitution", constitution), ("guidelines", guidelines)):
        unresolvable = sorted(cited_ids(text) - id_set)
        if unresolvable:
            problems.append(
                f"{name} cites sections that do not exist: {unresolvable} "
                "(extract_charter_elements would silently drop these)"
            )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--constitution", required=True, type=Path)
    ap.add_argument("--guidelines", required=True, type=Path)
    ap.add_argument("--out-constitution", required=True, type=Path)
    ap.add_argument("--out-guidelines", required=True, type=Path)
    ap.add_argument(
        "--unescape",
        action="store_true",
        help="strip exporter backslash escapes (\\[ \\] \\. ...) from both files",
    )
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    constitution, n_sec, n_dom = normalize_constitution(
        args.constitution.read_text(encoding="utf-8")
    )
    guidelines = args.guidelines.read_text(encoding="utf-8")
    if args.unescape:
        constitution, guidelines = unescape(constitution), unescape(guidelines)

    ids = section_ids(constitution)
    print(f"promoted {n_sec} section headers, {n_dom} domain headers")
    print(f"{len(ids)} sections: {' '.join(ids)}")

    problems = validate(constitution, guidelines)
    for p in problems:
        print(f"FAIL: {p}")
    if problems:
        return 1
    print("validation OK: sections parse, no duplicates, all citations resolve")

    if args.check:
        print("--check: nothing written")
        return 0
    args.out_constitution.write_text(constitution, encoding="utf-8")
    args.out_guidelines.write_text(guidelines, encoding="utf-8")
    print(f"wrote {args.out_constitution}\nwrote {args.out_guidelines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
