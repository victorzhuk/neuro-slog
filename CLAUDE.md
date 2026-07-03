# neuro slog — authoring repo

Content repo for the blog at victorzh.uk/slog. No build step: the site
(homyak) fetches this repo's `master` as a tarball roughly every 10 minutes
and serves whatever parses. Pushing to `master` IS publishing.

## Site contract (what homyak does with these files)

- Scans `**/*.md`; skips any `README.md` (case-insensitive), dot-directories,
  non-markdown, and files over 1 MB.
- Frontmatter: `title` and `date` required. `date` is `YYYY-MM-DD` (canonical
  article date; RFC3339 tolerated but avoid it). Optional: `published`
  (RFC3339 timestamp of the publish moment — the catalog sort key, falling
  back to `date`; `/publish` sets it, don't edit it afterwards), `updated`
  (RFC3339 timestamp of the last substantive update, shown on the article
  page; `/publish` sets it on updates — not for typo/typography fixes),
  `tags` (list), `description` (string), `draft` (bool). Unknown keys are
  silently ignored — a typo in a key name silently loses that field.
- Slug = filename without `.md`. URL = `/slog/{slug}`. Slugs must match
  `[a-z0-9-]+` — the chat's link rendering only linkifies that shape.
  **Renaming a file changes its URL**; keep filenames stable after publishing.
- Duplicate slugs: first in path order wins, the rest are dropped with a log.
- `draft: true` = invisible everywhere (catalog, direct URL, share metadata,
  assistant search). There is no live preview for drafts — preview is your
  editor's markdown render; the real look is verified after publishing.
- `description` feeds the catalog card, the share/OG meta, and gives search
  snippets context. Keep it under ~160 characters.
- The site's assistant embeds published posts for semantic search; editing a
  post re-embeds it, unchanged posts are cached.
- Directory layout (`YYYY/MM/`) is filing convention only; frontmatter `date`
  decides the catalog filters.

## Workflow

`/new-post` → write → `/editor-review` → `/publish`. `/lint` any time;
`/tidy` when files drift out of the `YYYY/MM/` convention.

- Never commit or push without being asked; `/publish` owns the push step.
- Commit messages: `post: add <slug>`, `post: update <slug>`,
  `post: retract <slug>`, `chore: <what>` for non-content changes.
- Run `python3 scripts/check.py` before any commit; it must exit 0.

## Voice

Terse, concrete, first person. Lowercase titles. Normal sentence prose in the
body — short paragraphs, one idea per post, end on a takeaway or a rule of
thumb. Dry humor fine, filler not. No emoji, no corporate phrasing, no
listicles for their own sake. Code snippets minimal and runnable.

Drafts are authored in plain ASCII (two hyphens for a dash, `->` arrows);
`/editor-review` owns the typography pass that converts prose to `—`, `→`,
`↔`, `…`, and en-dash ranges before publishing. `check.py` warns when a
published post still carries ASCII typography.

## License

Prose CC BY 4.0 (see LICENSE); code snippets in posts also MIT unless the
post says otherwise.
