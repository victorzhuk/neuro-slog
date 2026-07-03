---
title: hello, neuro slog
date: 2026-07-03
published: 2026-07-03T13:11:49+03:00
tags: [meta]
description: what this blog is and how it publishes itself
---

This is the neuro slog — short technical notes, mostly Go, backend, and devops.

The publishing pipeline is the part I like. Articles live in a public git repo
as markdown files with a YAML header. The site fetches the repo as a tarball on
boot and re-fetches it every ten minutes. Publishing a post is `git push`.
No CMS, no database, no redeploy.

The site's assistant indexes these posts too. Ask it where to read about
something and it will link you here.
