# neuro slog

Articles for [victorzh.uk/slog](https://victorzh.uk/slog). The site fetches
this repo on an interval; publishing is a push to `master`.

## Article format

One markdown file per article, YAML frontmatter header, body below:

```markdown
---
title: a post title
date: 2026-07-03
tags: [go, backend]
description: one line for cards, share previews, and search snippets
draft: true
---

Markdown body.
```

- `title` and `date` are required; `date` (`YYYY-MM-DD`) is the article's
  canonical date — directories like `2026/07/` are just filing.
- The file name is the slug and the URL: `hello-slog.md` → `/slog/hello-slog`.
  Slugs are lowercase `a-z0-9-` only. Renaming a file changes its URL.
- `draft: true` keeps a post entirely off the site — catalog, URL, and search.
- This README is ignored by the site.

Run `python3 scripts/check.py` before pushing.

## License

Prose is licensed under [CC BY 4.0](LICENSE). Code snippets inside articles
are additionally available under the MIT license unless a post says otherwise.
