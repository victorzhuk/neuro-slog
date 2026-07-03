---
name: new-post
description: Scaffold a new draft article from a topic or working title — slug, frontmatter, filing under YYYY/MM/, and a skeleton to write into. Use when starting a post ("new post about X", "draft an article on Y").
---

# new-post

Create a draft article file. Never commit.

## Steps

1. Derive a slug from the topic: lowercase, `a-z0-9-` only, 2–5 words,
   specific over generic (`goroutine-leak-tickers`, not `go-tips`). The slug
   is the permanent URL — get it right now; renaming later breaks the link.
2. Check uniqueness: the slug must not collide with any existing `*.md` stem
   in the repo. If it does, propose a sharper one.
3. Create `YYYY/MM/<slug>.md` using today's date for the path and frontmatter:

   ```markdown
   ---
   title: <lowercase working title>
   date: <today, YYYY-MM-DD>
   tags: [<1-3 tags, prefer ones already used in the repo>]
   description: <one line, under 160 chars — can be a placeholder>
   draft: true
   ---

   <lede: two sentences that say why the reader should care>

   <body>

   <takeaway or rule of thumb>
   ```

4. If the user gave substance (an idea, notes, a war story), draft the body in
   the repo voice (see CLAUDE.md § Voice). If they gave only a title, leave
   the skeleton and list 2–3 questions whose answers the post needs.
5. Run `python3 scripts/check.py` — must exit 0 (warnings about placeholder
   description are fine at this stage).

## Verify

- File exists under the correct `YYYY/MM/`, `draft: true`, linter has no errors.
