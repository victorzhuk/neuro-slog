---
name: publish
description: Take a draft live — preflight lint, set the date, drop the draft flag, file correctly, commit, push, and verify on the site. Also covers updating, retracting, and un-publishing posts. Use for "publish X", "take X live", "retract X", "update the published post".
---

# publish

Publishing is a push to `master`; the site picks it up within ~10 minutes.
This skill owns the only commit+push in the workflow — confirm with the user
before the push itself.

## Publish a draft

1. Preflight: `python3 scripts/check.py` exits 0; an editor review happened
   this session or the user explicitly skips it.
2. Set frontmatter `date` to the publish date (confirm if it differs from the
   scaffold date) and remove the `draft` line. Re-file to the matching
   `YYYY/MM/` with `git mv` if the month changed — the filename itself never
   changes at publish time (it is the URL).
3. Description must be real (not a placeholder) — it becomes the share card.
4. Commit `post: add <slug>`, push `master`.
5. Verify after the refresh window (up to 10 minutes):
   - `curl -s https://victorzh.uk/api/v1/slog/articles | grep <slug>`
   - `curl -s https://victorzh.uk/slog/<slug> | grep -o '<title[^<]*'` shows
     the article title (meta injection working)
   Report both results; if the interval hasn't elapsed, say when to re-check.

## Update a published post

Edit in place — never rename the file (URL stability; the assistant's search
index re-embeds changed content on its own). Commit `post: update <slug>`.
For substantive corrections add a short *errata* note at the bottom of the
post rather than silently rewriting claims.

## Retract

Prefer `draft: true` over deletion (keeps history; either way the site drops
the post on the next refresh — catalog, URL, and search together). Commit
`post: retract <slug>`. Warn the user that already-shared links will 404.
