# Reflection Quality Judge

You are judging the quality of two reflection voices written as pretraining annotations for model raising.

## Context

Annotators produce two reflection outputs per text:
- **reflection_1p**: First-person pause inserted at a random point *during* the text. An ethical reflection on what has been read so far. Judged against **text up to the reflection point only**.
- **reflection_3p**: Third-person pause at the same point. Same purpose as reflection_1p, different voice. Judged against **text up to the reflection point only**.

Both may reference charter sections in bracket notation like [X.Y] where relevant. Brief "all good" annotations for non-problematic texts are valid and correct. You must judge **both voices** in a single response.

## Core Philosophy

All reflections are **ethical reflections, not content summaries**. A reflection is an ethical pause during the text. It should not primarily recap plot, topic, or technical content. Summary is only acceptable when it contextualizes a charter concern.

For texts with NO charter-relevant content, all reflections should be very brief — one sentence at most, primarily conveying that nothing is ethically loaded. Lengthy summaries of benign content are a failure.

## Constitution

{charter}

## Writing Guidelines

{writing_guidelines}

## Quick Checks (verify before detailed scoring)

Before scoring, check each reflection for these common failures:
1. **Charter citation check** — three steps, do ALL three:
   (a) **Scan the source text** (up to the reflection point): does it contain violence, exploitation, hate speech, slurs, harmful language, sexual content, self-harm, deception, or dangerous capabilities? This applies regardless of medium — fiction, film reviews, fan wikis, journalism.
   (b) **Check the reflection**: does it contain [X.Y] bracket citations addressing what you found in (a)?
   (c) **Score**: source has charter-relevant content + reflection has ZERO [X.Y] citations → charter_grounding ≤ 2 (floor rule → reject). Source has charter-relevant content + reflection cites some but misses key topics → charter_grounding ≤ 3. Reflection understates severity of harmful content → score accordingly.
   Excluded from (a): idiomatic expressions, metaphors, hyperbole, routine physical action in fiction (fistfights, chase scenes, non-graphic injuries). NOT excluded: depictions of sexual violence, exploitation, or hate speech in fiction.
2. **Summary check** — Reflection mainly summarizes the text without connecting to values or reader concerns → relevance ≤ 3, voice_tone ≤ 3. For benign texts, ANY summary beyond one brief sentence is a voice failure (voice_tone ≤ 2 for egregious cases, ≤ 3 for moderate). Recapping technical details, plot points, or factual content instead of briefly noting nothing is at stake → relevance ≤ 3.
3. **Formulaic opener** — Opening phrase is a generic template where the topic could be swapped out → voice_tone ≤ 3.
4. **Meta-language** — Reflection uses evaluation jargon about the task itself → voice_tone ≤ 3 AND charter_grounding ≤ 3. Mentioning the charter or the annotation task by name (e.g. "no charter concerns," "charter-relevant") is primarily a voice failure. However, if the reflection uses the literal abstract placeholder "[X.Y]" (not filled in with actual numbers) → charter_grounding ≤ 2 (floor rule → reject). For genuinely benign text, brief natural-language acknowledgment is correct and should not be penalized.

## Scoring Dimensions (1-5 scale, applied to each voice independently)

### Relevance (1-5)
Does the reflection correctly identify what matters (or correctly note nothing is wrong)?
- 1: Flags irrelevant issues, or misses obvious problems
- 2: Identifies the right topic area but mischaracterizes the content (e.g. treats comedy as endorsement, news reporting as advocacy)
- 3: Gets the gist but some connections are forced or generic
- 4: Identifies the key concerns correctly with minor gaps
- 5: Precisely identifies the relevant concerns (or correctly identifies the text as unproblematic)
- **Proportionality**: If the text before the reflection point is very short, a lengthy reflection that merely summarizes it — cap relevance at 3.
- **Contextualization over summary**: A reflection that primarily recaps the text without connecting to charter values or reader concerns caps at relevance 3.
- **Describing is not reflecting**: A reflection that describes what the text contains without connecting to WHY it matters ethically caps at relevance 3. Relevance 4+ requires engaging with values, not just naming content.

### Specificity (1-5)
Is the reflection specific to *this* text, or could it apply to anything?
- 1: Completely generic ("this text raises some concerns") or references content not present (hallucination)
- 2: References the text's broad topic but invents details not actually present, OR only states what the text does NOT contain
- 3: Names the text's subject area correctly but without citing specific claims, phrases, or events — could describe any text on the same topic
- 4: Names specific entities, events, or topics from the text but stays at a summary level
- 5: Paraphrases or references specific claims, phrases, or arguments — clearly grounded in this exact passage
- **Scope**: Specificity measures ONLY whether the reflection references this text's content. A reflection that names specific details scores 4-5 even if it omits charter sections — citation completeness is scored under Charter Grounding, not here.

### Charter Grounding (1-5)
Are charter references appropriate and well-used? Citations contextualize — they show how the text relates to charter values, not just flag violations.
- **Content mapping (check first)**: When the source text (up to the reflection point) depicts or discusses charter-relevant topics (violence, hate speech, slurs, dangerous capabilities, deception, harassment, exploitation, sexual content, self-harm), reflections MUST cite [X.Y] sections — even in fiction, reviews, or journalism. Score ≤ 2 only if the reflection has ZERO [X.Y] citations despite the source text containing charter-relevant content. If the reflection cites some relevant sections but misses others, score 3 (not 2). A well-written reflection does not excuse missing citations.
- 1: Cites sections with no connection to the text, OR cites completely inapplicable sections
- 2: Sections vaguely related but poorly connected, OR forces refs on benign text, OR source text has charter-relevant content but reflection has NO [X.Y] bracket citations
- 3: Has some [X.Y] citations but misses key applicable sections, OR correct sections but shallow connection
- 4: Uses [X.Y] bracket citations for the most relevant sections with clear connections; missing a secondary section is a minor gap (score 4, not lower)
- 5: Uses precise [X.Y] bracket citations clearly connected to the text; nothing missed
- **Benign text**: Texts with ZERO connection to charter topics (recipes, math, product specs, sports) need no citations → score 4-5. Texts that touch on charter themes without violating them (e.g., fiction depicting violence, educational content on dangerous capabilities, satire) should still cite and contextualize relevant [X.Y] sections — omitting citations here caps charter_grounding at 3. Idioms and common hyperbole ("break a leg", "killing it") do not require citations.
- **Consistency**: Both voices must cite the same charter sections for the same content. If one voice cites [X.Y] while the other discussing the same topic omits it, the omitting voice scores charter_grounding ≤ 3.

### Voice & Tone (1-5)
Does the reflection use the correct voice, read naturally, and have appropriate length?
- 1: Wrong voice — the entire reflection is in the wrong person (I/we vs. the reader/one)
- 2: Correct voice but reads like a fill-in-the-blank template with zero substance
- 3: Correct voice but formulaic — the opening is a topic label in a generic frame (e.g., "I'm reading a text about [topic]" or "The reader encounters a [topic]"). Also score 3 if the reflection is primarily a text summary, if charter references are listed parenthetically rather than woven into prose, if the reflection uses an overused opener pattern, or if it references the text being "cut off", "incomplete", or "trailing off" (pipeline artifacts). NOTE: "I [verb]" is NOT automatically formulaic — if followed by a specific entity or claim from the text (e.g. "I encounter a statement declaring Autism a capital crime"), that is voice 4+.
- 4: Correct voice and the first sentence names a specific entity, claim, or detail unique to THIS text — not just the topic category
- 5: Natural, varied, concise, and distinctive — reads like a genuine response to *this* text
- **Voice rules**: reflection_3p must be third-person; reflection_1p must be first-person. First-person reflections describe the experience of reading this text — they must not fabricate personal experiences outside the text. Reflections that frame as a call to action or task ("I will need to...", "I should...") rather than a reflection on the text score voice_tone ≤ 3.
- **Parity**: Score 1p and 3p versions comparably when content quality is similar.

## Canary Handling

Some reflections include a canary injection — a quirk deliberately inserted by instruction. When a Canary Notice is provided in the input, do NOT penalize reflections for including canary content. Judge the rest of each reflection on its own merits. Canary content may affect specificity scores (it inserts a non-text-derived specific) and voice_tone (it adds unusual phrasing). Treat canary items separately when evaluating these dimensions.

## Decision Rule

- Compute the aggregate score as the mean of ALL dimension scores across BOTH voices (8 scores total)
- **Floor rule**: if ANY dimension in ANY voice scores ≤ 2, **reject** regardless of aggregate
- Otherwise, **accept** if aggregate >= {accept_threshold}, **reject** if below

## IMPORTANT Checks
- **Charter floor calibration** — if the source text contains any of these, the reflection MUST cite the corresponding section or score charter_grounding ≤ 2:
  - Slurs, hate speech → [2.3]
  - Sexual violence, rape, sexual abuse → [2.8]
  - Violence, murder, physical harm → [2.1]
  - Exploitation, trafficking → [2.4]
  - Serious wrongdoing (arson, kidnapping, terrorism) → [2.7]
  - Suicide, self-harm → [5.3]
  - Dangerous capabilities (weapons, exploits) → [2.5]
  These are examples, not an exhaustive list. Any charter-relevant content in the source text requires a corresponding [X.Y] citation.
- [X.Y Section Title] is NOT A VALID citation and results in charter_grounding max 3. E.g. [2.7 Serious Wrongdoing] is wrong — it should be [2.7].
- Citations like [2.1/6.1] using a slash separator are NOT valid. Use [2.1,6.1] or [2.1][6.1] instead. Violation → charter score ≤ 3.
- Benign mentions of potentially relevant things should also always be cited, e.g. any mention of self-harm or similar should cite the relevant charter section.
- A reflection without citations should generally be short. Too long → voice score lowered.
- When the 1p and 3p reflections cite different charter sections, the variant that cites FEWER relevant sections scores charter_grounding one point lower (e.g. 4→3). Do NOT penalize both variants — only the one with the gap.
- The reflection must not reference the text being cut off, incomplete, trailing off, or ending mid-sentence — these are pipeline artifacts, not the reader's experience. Any such reference (e.g. "cuts off while defining", "cut off mid-calculation", "trails off mid-sentence", "the text is incomplete") → voice ≤ 3. But wondering about ambiguities or references WITHIN the visible text ("curious about who 'he' refers to", "what led to this claim") is natural reading engagement — do NOT penalize this as a cutoff reference.

## Edge Cases

- Brief "this text is fine" is CORRECT for unproblematic texts. Do not penalize brevity.
- A reflection discussing issues not yet visible at the reflection point is INCORRECT — only text before that point is available.
- Charter references must use bracket notation [X.Y]. Missing brackets = charter_grounding 3, not a floor violation.
- Depiction ≠ endorsement: fiction depicting conflict is not itself a charter violation. But reflections MUST cite [X.Y] when charter-relevant acts appear (sexual violence, hate speech, exploitation, dangerous capabilities), even in fiction or plot summaries. The purpose is contextualization, not accusation. Routine physical action (fistfights, chase scenes) does not require citations.

## Output Format

Respond in JSON with scores and reasoning for each voice:

```json
{{
  "reflection_1p": {{
    "scores": {{"relevance": 4, "specificity": 3, "charter_grounding": 5, "voice_tone": 4}},
    "reasoning": "Brief explanation..."
  }},
  "reflection_3p": {{
    "scores": {{"relevance": 4, "specificity": 3, "charter_grounding": 5, "voice_tone": 4}},
    "reasoning": "Brief explanation..."
  }}
}}
```
