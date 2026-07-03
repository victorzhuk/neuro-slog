---
name: tidy
description: Layout management — re-file articles into YYYY/MM/ matching their frontmatter date and show the catalog tree. Use for "tidy the repo", "fix the layout", "refile posts".
---

# tidy

The site ignores directory layout (frontmatter `date` is canonical); the
`YYYY/MM/` convention exists for humans. This skill enforces it without ever
touching URLs.

1. Run `python3 scripts/check.py` and collect the "filed under X but dated Y"
   warnings.
2. For each, `git mv` the file to the directory matching its frontmatter date.
   **Never change the filename itself** — the stem is the slug is the URL.
3. Remove directories left empty.
4. Show the resulting tree (`tree` or `find` on the year dirs) and re-run the
   linter to confirm zero filing warnings.

Do not commit; leave that to the user or `/publish`.
