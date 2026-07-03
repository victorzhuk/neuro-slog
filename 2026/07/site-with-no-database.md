---
draft: true
title: a personal site with no database
date: 2026-07-03
tags: [go, architecture]
description: how victorzh.uk stays stateless — embedded facts, in-memory articles, client-carried chat
---

victorzh.uk runs as a single Go binary in Kubernetes and owns no storage at all.

Everything that looks like state lives somewhere cheaper:

- the frontend is embedded into the binary with `embed.FS`;
- the assistant's bio facts are a generated markdown file, also embedded at
  build time;
- chat history is carried by the client — every request sends the visible
  conversation, the server remembers nothing;
- blog articles are fetched from a public git repo into memory and refreshed
  on an interval, so a lost pod rebuilds its whole world on boot;
- even the semantic search index over articles is just vectors in RAM,
  re-embedded on start and cached by content hash between refreshes.

The payoff: the deployment is one Deployment. No migrations, no backups, no
stateful sets. A pod is disposable by construction.

The cost: startup does a little more work, and anything truly persistent —
visitor messages, for example — has to leave the system immediately (those are
relayed straight to Telegram).

For a personal site this trade is not close.
