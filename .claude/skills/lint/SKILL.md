---
name: lint
description: Run the article linter and fix what it finds — frontmatter contract, slugs, dates, descriptions, filing. Use for "lint", "check the articles", or before any commit.
---

# lint

1. Run `python3 scripts/check.py` (optionally with specific file paths).
2. Errors are contract violations the site will punish (skipped article,
   dropped duplicate, broken URL) — fix them: mechanical fixes directly,
   judgment calls (slug rename, date change) proposed first. A slug rename on
   an already-published post changes its URL — always warn.
3. Warnings are quality issues (missing/long description, misfiled path,
   odd tags) — list them; fix on request. Misfiled paths → suggest `/tidy`.
4. Never bulk-edit prose under this skill; that's `/editor-review`.

## Verify

Re-run the script; report the final `N article(s), N error(s), N warning(s)`
line.
