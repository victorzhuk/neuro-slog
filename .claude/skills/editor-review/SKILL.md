---
name: editor-review
description: Review a draft as a demanding editor — structure, voice, factual claims, metadata, and AI-tell cleanup — ending with a publish-ready verdict. Use before publishing ("review the draft", "edit this post", "is this ready?").
---

# editor-review

Review one article (default: the most recently modified draft). Report
findings first; apply edits only when asked or when the user said "fix it".

## Passes

1. **Structure.** The first two sentences must say why the reader should
   care — no throat-clearing. One idea per post; anything that wanders gets
   flagged for cutting or for its own post. The ending lands a takeaway or a
   rule of thumb, not a summary.
2. **Voice** (CLAUDE.md § Voice). Terse, concrete, first person, lowercase
   title. Flag: filler, hedging, corporate phrasing, emoji, tutorial tone,
   paragraphs over ~6 lines.
3. **AI tells.** Flag and rewrite: negative parallelism ("not X but Y"),
   rule-of-three cadences, em-dash overuse, puffery ("powerful", "seamless",
   "robust"), uniform sentence rhythm, both-sides hedging. The post should
   read like one specific person wrote it fast.
4. **Facts.** Verify technical claims where the repo, linked code, or docs
   allow; anything unverifiable gets flagged with a suggested softening or a
   source to check. Code snippets must be plausible and minimal.
5. **Typography.** Drafts arrive in plain ASCII; this pass converts prose to
   typographic characters (always applied, not just flagged):
   - two hyphens (` -- `) → em dash ` — `
   - ` -> ` / ` <- ` / ` <-> ` → ` → ` / ` ← ` / ` ↔ `
   - `...` → `…`
   - number ranges (`25-50%`) → en dash (`25–50%`) — never dates, slugs, or
     identifiers
   Fenced code blocks are never touched. Inline code spans only when the
   span is prose notation (a mapping like `a ↔ b`); commands, flags, and
   real code stay ASCII.
6. **Metadata.** Title: lowercase, specific, no clickbait. Description:
   under 160 chars, states the actual payoff (it feeds cards, share previews,
   and the assistant's search snippets). Tags: 1–3, reuse existing repo tags
   before inventing new ones. First paragraph must stand alone — the
   assistant quotes it as a search snippet.
7. Run `python3 scripts/check.py`.

## Output

Findings grouped by pass, each with the offending line and a concrete
rewrite. End with a verdict: **publish-ready** or **needs another pass**
(and what would flip it).
