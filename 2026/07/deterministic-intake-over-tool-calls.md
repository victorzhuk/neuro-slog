---
title: deterministic intake beats a model tool
date: 2026-07-03
tags: [go, llm, chat]
description: why the contact form in victor_ai is a state machine, not a tool call
---

victor_ai, the assistant on this site, can take a message for me. The first
version gave the model a `leave_message` tool and hoped it would collect a
contact and call it. It mostly did. Mostly is a bad word in a lead pipeline.

Models drop fields, reorder questions, and occasionally narrate the tool call
instead of making it. For open-ended chat that's fine; for "capture who wants
what and how to reach them" it isn't.

The rewrite moved intake out of the model entirely. When a visitor wants to
leave a message, the backend runs a small deterministic state machine: ask who
they are, what they need, how to reach them — validate, then relay to Telegram.
The model still owns conversation; it no longer owns the transaction.

Rule of thumb I took away: give the model the parts where being approximately
right is useful, and take back the parts where it must be exactly right.
