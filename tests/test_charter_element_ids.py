"""Tests for charter element-ID parsing and per-charter citation extraction.

Regression cover for a bug that silently deleted citations: the module-level
``_CHARTER_ID_SET`` is built once at import from the charter named in
``configs/config.yaml``, so a run overriding ``cfg.charter_path`` had every
citation validated against the *wrong* constitution. The utilitarian arm of the
constitution ablation lost all 53 of its ``7.x``/``8.x`` citations that way, with
no error anywhere.

Two parsing faults compounded it:
  - only ``###`` headings were recognised, while NormativeHierarchy and
    Utilitarian number their sections with ``##`` (as ``report.py`` allows);
  - inline ``[X.Y]`` matches took precedence over headings, so a constitution
    that cites a few of its own sections in prose collapsed to just those.
"""

from __future__ import annotations

from pipeline.config import (
    PROJECT_ROOT,
    extract_charter_elements,
    parse_charter_element_ids,
    union_charter_elements,
)

MR = (PROJECT_ROOT / "resources/ModelRaisingConstitution_v0.2.md").read_text()
NORMATIVE = (PROJECT_ROOT / "resources/NormativeHierarchyConstitution_v0.1.md").read_text()
UTILITARIAN = (PROJECT_ROOT / "resources/UtilitarianConstitution_v0.1.md").read_text()


def test_hash2_and_hash3_headings_both_parse():
    """MR numbers sections with ###; NormativeHierarchy and Utilitarian use ##."""
    assert len(parse_charter_element_ids(MR)) == 35
    assert len(parse_charter_element_ids(NORMATIVE)) == 35
    assert len(parse_charter_element_ids(UTILITARIAN)) == 51


def test_headings_win_over_inline_citations():
    """A charter that cites its own sections must not collapse to those few."""
    charter = "## 1.1 First\nSee [8.7] and [7.7].\n\n## 1.2 Second\nBody.\n"
    assert parse_charter_element_ids(charter) == ["1.1", "1.2"]


def test_inline_ids_still_parse_when_no_numbered_headings():
    """SwissAI-charter style: no ## X.Y headings, ids only appear inline."""
    assert parse_charter_element_ids("Preamble\n\nSee [1.1] then [2.4].\n") == ["1.1", "2.4"]


def test_extraction_uses_the_charter_it_is_given():
    """8.6 exists only in the utilitarian constitution."""
    text = "The verdict follows the sum [8.6] after weighing safety [2.1]."
    assert extract_charter_elements(text, UTILITARIAN) == ["8.6", "2.1"]
    assert extract_charter_elements(text, MR) == ["2.1"]


def test_unknown_ids_are_dropped():
    assert extract_charter_elements("bogus [9.9] real [2.1]", MR) == ["2.1"]


def test_union_threads_the_charter_through():
    """union_charter_elements must not fall back to the configured charter."""
    got = union_charter_elements(
        "first voice [8.6]", "second voice [8.5] [2.1]", charter_text=UTILITARIAN
    )
    assert got == ["8.6", "8.5", "2.1"]
