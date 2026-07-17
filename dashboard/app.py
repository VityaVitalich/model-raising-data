"""Model Raising reflection review dashboard.

Reads ``data/cards.json`` produced by ``python -m pipeline.charter.eval report``
and collects binary accept/reject feedback. The app intentionally does not
import ``pipeline`` so it can run as a lightweight Hugging Face Space.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import random
import re
from pathlib import Path

import gradio as gr

TITLE = "Model Raising Reflection Review"
APP_DIR = Path(__file__).parent
CARDS_PATH = Path(os.environ.get("CARDS_PATH", APP_DIR / "data" / "cards.json"))
CMP_PATH = Path(os.environ.get("CMP_PATH", APP_DIR / "data" / "comparison.json"))
FEEDBACK_DIR = Path(os.environ.get("FEEDBACK_DIR", APP_DIR / "feedback"))
FEEDBACK_FILE = FEEDBACK_DIR / "feedback.jsonl"
CMP_FEEDBACK_FILE = FEEDBACK_DIR / "comparison_feedback.jsonl"
FEEDBACK_DATASET = os.environ.get("FEEDBACK_DATASET", "")

ALL = "(all)"
_CITE_RE = re.compile(r"\[(\d+\.\d+(?:\s*,\s*\d+\.\d+)*)\]")


def load_payload() -> tuple[list[dict], dict]:
    """Load cards + constitution sections from the portable snapshot."""
    if not CARDS_PATH.exists():
        return [], {}
    d = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    return d.get("cards", []), d.get("charter_sections", {})


CARDS, CHARTER_SECTIONS = load_payload()


def load_comparison() -> dict:
    """Load the constitution side-by-side snapshot (may be absent)."""
    if not CMP_PATH.exists():
        return {"base_run_id": "", "constitutions": [], "items": []}
    return json.loads(CMP_PATH.read_text(encoding="utf-8"))


CMP = load_comparison()
CMP_CONS: list[dict] = CMP.get("constitutions", [])
CMP_ITEMS: list[dict] = CMP.get("items", [])

# Stable accent per constitution; falls back to grey for unknown keys.
CON_COLORS = {
    "value": "#2563eb",
    "normative_hierarchy": "#7c3aed",
    "utilitarian": "#059669",
}
SAFETY_COLORS = {0: "#15803d", 1: "#65a30d", 2: "#ca8a04", 3: "#ea580c", 4: "#b91c1c"}


def _card_key(c: dict) -> tuple:
    return (c.get("run_id"), c.get("item_id"), c.get("generator"), c.get("judge"))


def annotator_order(name: str) -> list[int]:
    """Deterministic order: most severe first, shuffled within score buckets."""
    salt = os.environ.get("SHUFFLE_SALT", "annotator")
    rng = random.Random(f"{salt}::{name}")
    by_score: dict[int, list[int]] = {}
    for i, card in enumerate(CARDS):
        by_score.setdefault(int(card.get("safety_score") or 0), []).append(i)
    order: list[int] = []
    for score in sorted(by_score, reverse=True):
        bucket = by_score[score]
        rng.shuffle(bucket)
        order.extend(bucket)
    return order


def graded_keys(reviewer: str) -> set:
    """Card keys this reviewer has already graded."""
    if FEEDBACK_DATASET:
        from huggingface_hub import snapshot_download

        root = snapshot_download(
            FEEDBACK_DATASET,
            repo_type="dataset",
            allow_patterns="data/*.jsonl",
            token=os.environ.get("HF_TOKEN"),
        )
        paths = list(Path(root).rglob("*.jsonl"))
    else:
        paths = [FEEDBACK_FILE] if FEEDBACK_FILE.exists() else []
    keys: set = set()
    for p in paths:
        for raw in p.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed feedback JSON in {p}: {e}") from e
            if row.get("reviewer") == reviewer:
                keys.add(_card_key(row))
    return keys


def _options(field: str) -> list[str]:
    vals = {str(c.get(field)) for c in CARDS if c.get(field) is not None}
    return [ALL] + sorted(vals)


def _passes(c: dict, gen: str, lang: str, decision: str, safety: str) -> bool:
    if gen != ALL and c.get("gen_model") != gen:
        return False
    if lang != ALL and (c.get("language") or "-") != lang:
        return False
    if decision != ALL and (c.get("judge_decision") or "-") != decision:
        return False
    if safety != ALL and str(c.get("safety_score")) != safety:
        return False
    return True


def filter_indices(
    gen: str,
    lang: str,
    decision: str,
    safety: str,
    order: list[int] | None = None,
) -> list[int]:
    """Card indices matching the filters, in reviewer order."""
    seq = range(len(CARDS)) if order is None else order
    return [i for i in seq if _passes(CARDS[i], gen, lang, decision, safety)]


def _doc_value(c: dict) -> str:
    text = c.get("text") or ""
    rp = c.get("reflection_point")
    if isinstance(rp, int) and 0 < rp <= len(text):
        return text[:rp]
    return text


def _wrap_citations(text: str, sections: dict | None = None) -> str:
    secs = CHARTER_SECTIONS if sections is None else sections
    esc = html.escape(text or "")

    def repl(m: re.Match) -> str:
        ids = [s.strip() for s in m.group(1).split(",")]
        tip = "<hr class='tipsep'>".join(secs.get(i, html.escape(i)) for i in ids)
        return f'<span class="cite">[{m.group(1)}]<span class="tip">{tip}</span></span>'

    return _CITE_RE.sub(repl, esc)


def _reflection_html(c: dict) -> str:
    refl = _wrap_citations(c.get("reflection_1p") or "(none)")
    cites = _wrap_citations(" ".join(c.get("charter_elements") or []) or "-")
    out = [
        "<h3 style='margin:.3em 0'>First-person reflection under review</h3>",
        f"<div>{refl}</div>",
        f"<div style='margin-top:.5em'><b>Citations:</b> {cites}</div>",
    ]
    if c.get("analysis"):
        out.append(
            "<details style='margin-top:.6em'><summary>Analysis</summary>"
            f"<div>{html.escape(c['analysis'])}</div></details>"
        )
    return "".join(out)


def _judge_html(c: dict) -> str:
    if not c.get("judge"):
        return (
            "<h3 style='margin:.8em 0 .3em'>Automated judge</h3>"
            "<i>No automated judge attached to this card.</i>"
        )
    scores = c.get("judge_scores") or {}
    dims = "  ·  ".join(f"{html.escape(k)} <b>{v}</b>" for k, v in scores.items()) or "-"
    decision = html.escape((c.get("judge_decision") or "-").upper())
    agg = c.get("judge_aggregate")
    agg_s = f"{agg:.2f}" if isinstance(agg, (int, float)) else "-"
    color = "#15803d" if c.get("judge_decision") == "accept" else "#b91c1c"
    out = [
        "<h3 style='margin:.8em 0 .3em'>Automated judge</h3>",
        f"<div><b style='color:{color}'>{decision}</b> · aggregate <b>{agg_s}</b> · "
        f"judged by <code>{html.escape(c.get('judge_model') or '')}</code></div>",
        f"<div style='margin-top:.3em'>{dims}</div>",
    ]
    if c.get("judge_reasoning"):
        out.append(
            "<blockquote style='border-left:3px solid #888;margin:.5em 0;padding-left:.6em'>"
            f"{_wrap_citations(c['judge_reasoning'])}</blockquote>"
        )
    return "".join(out)


def render(idxs: list[int], pos: int):
    """Return display values for the selected card."""
    if not idxs:
        empty = "_No cards match these filters._" if CARDS else (
            "_No cards loaded. Build `data/cards.json` with "
            "`python -m pipeline.charter.eval report`._"
        )
        return empty, "", "", "", "0 / 0"
    pos = max(0, min(pos, len(idxs) - 1))
    c = CARDS[idxs[pos]]
    meta = (
        f"**model `{c.get('gen_model')}`** · prompt `{c.get('gen_prompt') or '-'}` · "
        f"lang `{c.get('language')}` · safety `{c.get('safety_score')}`"
    )
    return meta, _doc_value(c), _reflection_html(c), _judge_html(c), f"{pos + 1} / {len(idxs)}"


def _card(idxs, pos, status_msg=""):
    meta, doc, refl, judge_html, poslabel = render(idxs, pos)
    return meta, doc, refl, judge_html, poslabel, None, "", status_msg


def apply_filters(order, gen, lang, decision, safety):
    idxs = filter_indices(gen, lang, decision, safety, order=order)
    return (idxs, 0, *_card(idxs, 0))


def step(idxs, pos, delta):
    new_pos = max(0, min(pos + delta, max(0, len(idxs) - 1)))
    return (new_pos, *_card(idxs, new_pos))


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:120]


def submit_feedback(idxs, pos, reviewer, verdict, reason):
    """Save feedback and remove the graded card from the queue."""
    if not idxs:
        return (gr.update(),) * 9 + ("Nothing to rate.",)
    if not verdict:
        return (gr.update(),) * 9 + ("Pick accept or reject first.",)
    c = CARDS[idxs[pos]]
    record = {
        "run_id": c.get("run_id"),
        "item_id": c.get("item_id"),
        "generator": c.get("generator"),
        "judge": c.get("judge"),
        "judge_decision": c.get("judge_decision"),
        "verdict": "accept" if verdict == "accept" else "reject",
        "reason": (reason or "").strip(),
        "reviewer": (reviewer or "anon").strip() or "anon",
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.open("a", encoding="utf-8").write(line)
    if FEEDBACK_DATASET:
        from huggingface_hub import HfApi

        stem = _safe_name(f"{record['ts']}-{record['reviewer']}-{record['item_id']}")
        HfApi(token=os.environ.get("HF_TOKEN")).upload_file(
            path_or_fileobj=line.encode("utf-8"),
            path_in_repo=f"data/{stem}.jsonl",
            repo_id=FEEDBACK_DATASET,
            repo_type="dataset",
            commit_message=f"feedback: {record['verdict']} by {record['reviewer']}",
        )
        msg = f"Saved {record['verdict']} -> {FEEDBACK_DATASET}"
    else:
        msg = f"Saved {record['verdict']} locally: {FEEDBACK_FILE}"
    new_idxs = idxs[:pos] + idxs[pos + 1:]
    new_pos = min(pos, max(0, len(new_idxs) - 1))
    return (new_idxs, new_pos, *_card(new_idxs, new_pos, msg))


def _spec_sections() -> list[tuple[str, str]]:
    def key(sid: str):
        return tuple(int(p) if p.isdigit() else 0 for p in sid.split("."))

    return sorted(CHARTER_SECTIONS.items(), key=lambda kv: key(kv[0]))


def spec_html(query: str = "") -> str:
    q = (query or "").strip().lower()
    blocks = [
        f"<div style='margin:.5em 0;padding-bottom:.4em;border-bottom:1px solid #8884'>{body}</div>"
        for sid, body in _spec_sections()
        if not q or q in sid.lower() or q in re.sub(r"<[^>]+>", " ", body).lower()
    ]
    return "".join(blocks) or "<i>No sections match.</i>"


# --- Constitution side-by-side comparison ----------------------------------


def _con_color(key: str) -> str:
    return CON_COLORS.get(key, "#6b7280")


def _cmp_disagreement(item: dict) -> float:
    """How differently the constitutions treated this item.

    Section numbers are not comparable across constitutions (different
    documents), so disagreement is measured on behaviour: did some
    constitutions treat the text as benign while others cited values, and
    how far apart are the reflection lengths.
    """
    gens = [g for g in (item.get("generations") or {}).values() if g]
    if len(gens) < 2:
        return 0.0
    cited = [1 if g.get("citations") else 0 for g in gens]
    benign_split = 10.0 if 0 < sum(cited) < len(cited) else 0.0
    words = [g.get("n_words") or 0 for g in gens]
    spread = (max(words) - min(words)) / 25.0
    n_cites = [len(g.get("citations") or []) for g in gens]
    cite_spread = float(max(n_cites) - min(n_cites))
    return benign_split + spread + cite_spread


def _cmp_passes(item: dict, safety: str, split: str, query: str) -> bool:
    if safety != ALL and str(item.get("safety_score")) != safety:
        return False
    gens = [g for g in (item.get("generations") or {}).values() if g]
    cited = sum(1 for g in gens if g.get("citations"))
    if split == "constitutions disagree (benign vs. cited)":
        if not (gens and 0 < cited < len(gens)):
            return False
    elif split == "all cite values" and (not gens or cited < len(gens)):
        return False
    elif split == "all benign" and cited > 0:
        return False
    q = (query or "").strip().lower()
    if q:
        hay = (item.get("text") or "").lower() + " ".join(
            (g.get("reflection_1p") or "").lower() for g in gens
        )
        if q not in hay:
            return False
    return True


def cmp_filter(safety: str, split: str, query: str, sort: str) -> list[int]:
    idxs = [
        i for i, it in enumerate(CMP_ITEMS) if _cmp_passes(it, safety, split, query)
    ]
    if sort == "most disagreement":
        idxs.sort(key=lambda i: -_cmp_disagreement(CMP_ITEMS[i]))
    elif sort == "longest document":
        idxs.sort(key=lambda i: -len(CMP_ITEMS[i].get("text") or ""))
    # default: payload order (safety score, most severe first)
    return idxs


def _safety_badge(score) -> str:
    color = SAFETY_COLORS.get(int(score) if score is not None else 0, "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;border-radius:10px;'
        f'padding:1px 9px;font-size:.75rem;font-weight:600">safety {score}</span>'
    )


def _chip(sid: str, sections: dict) -> str:
    tip = sections.get(sid, html.escape(sid))
    return (
        f'<span class="cite chip">{html.escape(sid)}'
        f'<span class="tip">{tip}</span></span>'
    )


def _cmp_column(con: dict, gen: dict | None) -> str:
    color = _con_color(con["key"])
    head = (
        f'<div class="conhead" style="border-color:{color}">'
        f'<span style="color:{color};font-weight:700">{html.escape(con["label"])}</span>'
    )
    if gen is None:
        return (
            f'<div class="concol">{head}</div>'
            "<i>Generation failed for this item.</i></div>"
        )
    sections = con.get("charter_sections") or {}
    n_words = gen.get("n_words") or 0
    head += f'<span class="wc">{n_words}w</span></div>'
    refl = _wrap_citations(gen.get("reflection_1p") or "(empty)", sections)
    chips = "".join(_chip(s, sections) for s in gen.get("citations") or [])
    chips_div = (
        f'<div class="chips">{chips}</div>'
        if chips
        else '<div class="chips"><span class="nocite">no citations</span></div>'
    )
    analysis = ""
    if gen.get("analysis"):
        analysis = (
            "<details class='ana'><summary>Analysis</summary>"
            f"<div>{html.escape(gen['analysis'])}</div></details>"
        )
    return (
        f'<div class="concol">{head}<div class="refl">{refl}</div>'
        f"{chips_div}{analysis}</div>"
    )


def cmp_render(idxs: list[int], pos: int):
    """Return (meta_html, doc_text, columns_html, poslabel) for one item."""
    if not CMP_ITEMS:
        msg = (
            "_No comparison data. Build `data/comparison.json` with "
            "`python -m pipeline.charter.eval constitution-compare`._"
        )
        return msg, "", "", "0 / 0"
    if not idxs:
        return "_No items match these filters._", "", "", "0 / 0"
    pos = max(0, min(pos, len(idxs) - 1))
    item = CMP_ITEMS[idxs[pos]]
    dis = _cmp_disagreement(item)
    meta = (
        f'{_safety_badge(item.get("safety_score"))} '
        f'&nbsp; <code>{html.escape(str(item.get("item_id")))}</code>'
        f' &nbsp; · &nbsp; lang <code>{html.escape(str(item.get("language")))}</code>'
        f' &nbsp; · &nbsp; disagreement <b>{dis:.1f}</b>'
    )
    text = item.get("text") or ""
    rp = item.get("reflection_point")
    doc = text[:rp] if isinstance(rp, int) and 0 < rp <= len(text) else text
    cols = "".join(
        _cmp_column(con, (item.get("generations") or {}).get(con["key"]))
        for con in CMP_CONS
    )
    return meta, doc, f'<div class="congrid">{cols}</div>', f"{pos + 1} / {len(idxs)}"


def cmp_apply_filters(safety, split, query, sort):
    idxs = cmp_filter(safety, split, query, sort)
    return (idxs, 0, *cmp_render(idxs, 0))


def cmp_step(idxs, pos, delta):
    new_pos = max(0, min(pos + delta, max(0, len(idxs) - 1)))
    return (new_pos, *cmp_render(idxs, new_pos))


def cmp_random(idxs, pos):
    if len(idxs) > 1:
        pos = random.choice([i for i in range(len(idxs)) if i != pos])
    return (pos, *cmp_render(idxs, pos))


def cmp_vote(idxs, pos, reviewer, best, reason):
    """Persist a which-constitution-was-best vote for the current item."""
    if not idxs:
        return "Nothing to vote on."
    if not best:
        return "Pick the best reflection first."
    item = CMP_ITEMS[idxs[max(0, min(pos, len(idxs) - 1))]]
    label_to_key = {c["label"]: c["key"] for c in CMP_CONS}
    record = {
        "type": "comparison",
        "base_run_id": CMP.get("base_run_id"),
        "item_id": item.get("item_id"),
        "best": label_to_key.get(best, best),
        "reason": (reason or "").strip(),
        "reviewer": (reviewer or "anon").strip() or "anon",
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    CMP_FEEDBACK_FILE.open("a", encoding="utf-8").write(line)
    if FEEDBACK_DATASET:
        from huggingface_hub import HfApi

        stem = _safe_name(f"cmp-{record['ts']}-{record['reviewer']}-{record['item_id']}")
        HfApi(token=os.environ.get("HF_TOKEN")).upload_file(
            path_or_fileobj=line.encode("utf-8"),
            path_in_repo=f"data/{stem}.jsonl",
            repo_id=FEEDBACK_DATASET,
            repo_type="dataset",
            commit_message=f"comparison vote by {record['reviewer']}",
        )
        return f"Saved vote ({best}) -> {FEEDBACK_DATASET}"
    return f"Saved vote ({best}) locally: {CMP_FEEDBACK_FILE}"


def cmp_stats_html() -> str:
    """Aggregate behaviour of each constitution over the whole item set."""
    if not CMP_ITEMS:
        return "<i>No comparison data.</i>"
    rows = []
    for con in CMP_CONS:
        key = con["key"]
        gens = [
            it["generations"].get(key)
            for it in CMP_ITEMS
            if (it.get("generations") or {}).get(key)
        ]
        n = len(gens)
        if not n:
            rows.append((con, 0, 0, 0, 0, []))
            continue
        words = [g.get("n_words") or 0 for g in gens]
        cited = [g for g in gens if g.get("citations")]
        counts: dict[str, int] = {}
        for g in cited:
            for s in g["citations"]:
                counts[s] = counts.get(s, 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
        rows.append(
            (
                con,
                n,
                sum(words) / n,
                100.0 * len(cited) / n,
                (sum(len(g["citations"]) for g in cited) / len(cited)) if cited else 0,
                top,
            )
        )
    out = [
        "<table class='stats'><tr><th>Constitution</th><th>n</th>"
        "<th>mean words</th><th>% citing</th><th>cites/refl</th>"
        "<th>most-cited sections</th></tr>"
    ]
    for con, n, mw, pc, cpr, top in rows:
        color = _con_color(con["key"])
        secs = con.get("charter_sections") or {}
        chips = " ".join(_chip(s, secs) + f"<small>×{c}</small>" for s, c in top)
        out.append(
            f"<tr><td><b style='color:{color}'>{html.escape(con['label'])}</b></td>"
            f"<td>{n}</td><td>{mw:.0f}</td><td>{pc:.0f}%</td><td>{cpr:.1f}</td>"
            f"<td>{chips or '-'}</td></tr>"
        )
    out.append("</table>")
    n_split = sum(
        1
        for it in CMP_ITEMS
        if (
            lambda gs: gs and 0 < sum(1 for g in gs if g.get("citations")) < len(gs)
        )([g for g in (it.get("generations") or {}).values() if g])
    )
    out.append(
        f"<p>{n_split} / {len(CMP_ITEMS)} items have a benign-vs-cited split "
        "between constitutions — use the filter above to review them.</p>"
    )
    return "".join(out)


_CSS = (
    ".cite{border-bottom:1px dotted #888;cursor:help}"
    ".cite .tip{display:none}"
    "#cite-tip{position:fixed;z-index:9999;display:none;width:380px;max-width:90vw;"
    "max-height:280px;overflow-y:auto;text-align:left;background:#111827;color:#fff;"
    "padding:6px 10px;border-radius:6px;font-size:.74rem;line-height:1.3;"
    "box-shadow:0 6px 20px rgba(0,0,0,.55)}"
    "#cite-tip *{color:#fff}"
    "#cite-tip p{margin:.3em 0}"
    "#cite-tip hr.tipsep{margin:6px 0;border:0;border-top:1px solid #444}"
    ".congrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;"
    "align-items:start}"
    "@media (max-width:1100px){.congrid{grid-template-columns:1fr}}"
    ".concol{border:1px solid #8883;border-radius:10px;padding:10px 12px}"
    ".conhead{display:flex;justify-content:space-between;align-items:center;"
    "border-bottom:2px solid;padding-bottom:6px;margin-bottom:8px}"
    ".conhead .wc{font-size:.72rem;color:#888;font-variant-numeric:tabular-nums}"
    ".refl{line-height:1.45}"
    ".chips{margin-top:.6em;display:flex;flex-wrap:wrap;gap:4px;align-items:center}"
    ".chip{background:#8882;border-radius:8px;padding:0 7px;font-size:.74rem;"
    "border-bottom:none}"
    ".chips small{color:#888;margin-right:4px}"
    ".nocite{color:#888;font-size:.74rem;font-style:italic}"
    ".ana{margin-top:.6em;font-size:.85rem;color:#999}"
    ".ana div{margin-top:.3em;color:inherit}"
    "table.stats{border-collapse:collapse;width:100%}"
    "table.stats th,table.stats td{border:1px solid #8883;padding:4px 10px;"
    "text-align:left;font-size:.85rem}"
)

_TOOLTIP_JS = """
() => {
  if (window.__citeTipInit) return; window.__citeTipInit = true;
  const tip = document.createElement('div'); tip.id = 'cite-tip';
  document.body.appendChild(tip);
  let over = false;
  tip.addEventListener('mouseenter', () => { over = true; });
  tip.addEventListener('mouseleave', () => { over = false; tip.style.display = 'none'; });
  document.addEventListener('mouseover', (e) => {
    const cite = e.target.closest ? e.target.closest('.cite') : null;
    if (!cite) return;
    const src = cite.querySelector('.tip'); if (!src) return;
    tip.innerHTML = src.innerHTML; tip.style.display = 'block';
    const r = cite.getBoundingClientRect();
    const tw = Math.min(380, window.innerWidth * 0.9);
    tip.style.left = Math.max(8, Math.min(r.left, window.innerWidth - tw - 8)) + 'px';
    const top = r.top - tip.offsetHeight - 6;
    tip.style.top = (top < 8 ? r.bottom + 6 : top) + 'px';
  });
  document.addEventListener('mouseout', (e) => {
    const cite = e.target.closest ? e.target.closest('.cite') : null;
    if (!cite) return;
    setTimeout(() => { if (!over) tip.style.display = 'none'; }, 150);
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.closest('input, textarea, select')) return;
    const id = e.key === 'ArrowLeft' ? 'cmp-prev' : e.key === 'ArrowRight' ? 'cmp-next' : null;
    if (!id) return;
    const el = document.getElementById(id);
    if (el && el.offsetParent !== null) { el.click(); e.preventDefault(); }
  });
}
"""


def build_demo() -> gr.Blocks:
    with gr.Blocks(title=TITLE) as demo:
        gr.HTML(f"<style>{_CSS}</style>")
        gr.Markdown(f"# {TITLE}")

        with gr.Column(visible=True) as gate:
            gr.Markdown("Enter your name to start reviewing.")
            name_in = gr.Textbox(label="Your name", placeholder="e.g. julian")
            start_btn = gr.Button("Start reviewing", variant="primary")
            gate_msg = gr.Markdown()

        with gr.Column(visible=False) as main_panel:
            who_md = gr.Markdown()
            with gr.Tabs():
                with gr.Tab("Review queue"):
                    with gr.Accordion("Filters", open=False):
                        with gr.Row():
                            gen = gr.Dropdown(_options("gen_model"), value=ALL, label="Model", min_width=120)
                            lang = gr.Dropdown(_options("language"), value=ALL, label="Language", min_width=110)
                            decision = gr.Dropdown(_options("judge_decision"), value=ALL, label="Judge verdict", min_width=120)
                            safety = gr.Dropdown(_options("safety_score"), value=ALL, label="Safety", min_width=90)

                    with gr.Row():
                        prev_btn = gr.Button("prev", size="sm", scale=0, min_width=56)
                        poslabel = gr.Markdown("0 / 0")
                        next_btn = gr.Button("next", size="sm", scale=0, min_width=56)

                    meta_md = gr.Markdown()
                    doc_box = gr.Textbox(
                        label="Document up to the reflection point",
                        interactive=False,
                        lines=14,
                        max_lines=24,
                    )
                    refl_html = gr.HTML()
                    judge_md = gr.HTML()

                    gr.Markdown("### Your feedback")
                    verdict = gr.Radio(["accept", "reject"], label="Your verdict")
                    reason = gr.Textbox(label="Reason (optional)", lines=2)
                    submit_btn = gr.Button("Submit feedback", variant="primary")
                    status = gr.Markdown()

                    with gr.Accordion("Constitution sections (search)", open=False):
                        spec_search = gr.Textbox(label="Search", placeholder="e.g. privacy, 5.3")
                        spec_view = gr.HTML(spec_html(""))

                with gr.Tab("Constitutions side-by-side"):
                    gr.Markdown(
                        "Same document, one reflection per constitution — "
                        "generated on an identical item pool with identically "
                        "structured prompts, so differences come from the "
                        "constitution itself. Hover citations for the section "
                        "text. Arrow keys navigate."
                    )
                    with gr.Row():
                        cmp_safety = gr.Dropdown(
                            [ALL] + sorted({str(i.get("safety_score")) for i in CMP_ITEMS}),
                            value=ALL, label="Safety", min_width=90,
                        )
                        cmp_split = gr.Dropdown(
                            [ALL, "constitutions disagree (benign vs. cited)",
                             "all cite values", "all benign"],
                            value=ALL, label="Citation split", min_width=210,
                        )
                        cmp_sort = gr.Dropdown(
                            ["most severe first", "most disagreement", "longest document"],
                            value="most severe first", label="Order", min_width=150,
                        )
                        cmp_query = gr.Textbox(
                            label="Search text + reflections", placeholder="e.g. privacy", min_width=180,
                        )
                    with gr.Row():
                        cmp_prev = gr.Button("← prev", size="sm", scale=0, min_width=70, elem_id="cmp-prev")
                        cmp_poslabel = gr.Markdown("0 / 0")
                        cmp_next = gr.Button("next →", size="sm", scale=0, min_width=70, elem_id="cmp-next")
                        cmp_rand = gr.Button("random", size="sm", scale=0, min_width=70)

                    cmp_meta = gr.HTML()
                    cmp_doc = gr.Textbox(
                        label="Document up to the reflection point",
                        interactive=False,
                        lines=10,
                        max_lines=18,
                    )
                    cmp_cols = gr.HTML()

                    with gr.Row():
                        cmp_best = gr.Radio(
                            [c["label"] for c in CMP_CONS] + ["tie / none"],
                            label="Best reflection for this document",
                        )
                    with gr.Row():
                        cmp_reason = gr.Textbox(label="Why? (optional)", lines=1, scale=3)
                        cmp_vote_btn = gr.Button("Save vote", variant="primary", scale=1)
                    cmp_status = gr.Markdown()

                    with gr.Accordion("Aggregate stats", open=False):
                        gr.HTML(cmp_stats_html())

        reviewer_state = gr.State("")
        order_state = gr.State(list(range(len(CARDS))))
        idxs_state = gr.State(list(range(len(CARDS))))
        pos_state = gr.State(0)
        cmp_idxs_state = gr.State(list(range(len(CMP_ITEMS))))
        cmp_pos_state = gr.State(0)

        VIEW = [meta_md, doc_box, refl_html, judge_md, poslabel]
        CARD_OUT = [*VIEW, verdict, reason, status]

        def start(name):
            nm = (name or "").strip()
            noop = gr.update()
            if not nm:
                return (noop, noop, "Please enter your name.") + (noop,) * 10
            done = graded_keys(nm)
            order = [i for i in annotator_order(nm) if _card_key(CARDS[i]) not in done]
            view = render(order, 0)
            graded = f" ({len(done)} already graded)" if done else ""
            who = f"Reviewing as **{nm}** - {len(order)} to review{graded}"
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                "",
                who,
                nm,
                order,
                order,
                0,
                *view,
            )

        start_btn.click(
            start,
            inputs=[name_in],
            outputs=[
                gate,
                main_panel,
                gate_msg,
                who_md,
                reviewer_state,
                order_state,
                idxs_state,
                pos_state,
                *VIEW,
            ],
        )

        filters = [gen, lang, decision, safety]
        for f in filters:
            f.change(
                apply_filters,
                inputs=[order_state, *filters],
                outputs=[idxs_state, pos_state, *CARD_OUT],
            )
        prev_btn.click(
            lambda i, p: step(i, p, -1),
            inputs=[idxs_state, pos_state],
            outputs=[pos_state, *CARD_OUT],
        )
        next_btn.click(
            lambda i, p: step(i, p, 1),
            inputs=[idxs_state, pos_state],
            outputs=[pos_state, *CARD_OUT],
        )
        submit_btn.click(
            submit_feedback,
            inputs=[idxs_state, pos_state, reviewer_state, verdict, reason],
            outputs=[idxs_state, pos_state, *CARD_OUT],
        )
        # --- comparison tab wiring ---
        CMP_VIEW = [cmp_meta, cmp_doc, cmp_cols, cmp_poslabel]
        cmp_filters = [cmp_safety, cmp_split, cmp_query, cmp_sort]
        for f in cmp_filters:
            f.change(
                cmp_apply_filters,
                inputs=cmp_filters,
                outputs=[cmp_idxs_state, cmp_pos_state, *CMP_VIEW],
            )
        cmp_prev.click(
            lambda i, p: cmp_step(i, p, -1),
            inputs=[cmp_idxs_state, cmp_pos_state],
            outputs=[cmp_pos_state, *CMP_VIEW],
        )
        cmp_next.click(
            lambda i, p: cmp_step(i, p, 1),
            inputs=[cmp_idxs_state, cmp_pos_state],
            outputs=[cmp_pos_state, *CMP_VIEW],
        )
        cmp_rand.click(
            cmp_random,
            inputs=[cmp_idxs_state, cmp_pos_state],
            outputs=[cmp_pos_state, *CMP_VIEW],
        )
        cmp_vote_btn.click(
            cmp_vote,
            inputs=[cmp_idxs_state, cmp_pos_state, reviewer_state, cmp_best, cmp_reason],
            outputs=[cmp_status],
        )

        demo.load(lambda: render(list(range(len(CARDS))), 0), outputs=VIEW)
        demo.load(
            lambda: cmp_render(list(range(len(CMP_ITEMS))), 0), outputs=CMP_VIEW
        )
        demo.load(js=_TOOLTIP_JS)
        spec_search.change(spec_html, inputs=[spec_search], outputs=[spec_view])
    return demo


demo = build_demo()


if __name__ == "__main__":
    demo.launch(server_port=int(os.environ.get("DASHBOARD_PORT", 7860)))
