---
title: harness matters more than model
date: 2026-08-11
published: 2026-08-11T09:04:14+03:00
tags: [llm, agents]
description: my agent runs took 75 minutes on every model I tried. the fix was in the harness, and the logs said where.
---

My OpenSpec apply runs (plan, implement in a worktree, review, merge) kept
taking 75 minutes, sometimes more, in omp, my terminal agent harness. I tried
Kimi K3, GLM-5.2, MiMo and MiniMax. Nothing moved. Four different frontier
models landing on the same runtime pointed somewhere else, so I opened the
session logs. The harness was eating an hour of wall-clock while the models
did maybe twenty minutes of work.

## the forensics

omp keeps full session transcripts as JSONL, one file per agent. Timestamps
tell the whole story.

The orchestrator ran 106 turns. Most were the same tool call:
`hub op:wait timeoutMs:60000`. Wait 60 seconds for a subagent, get back
“Still Running”, think for ten seconds, wait again. The model copied
`timeoutMs:60000` straight from the tool's documentation example every time.
One run in a work repo made 100 such polls in 73 minutes.

Then it got worse. After about ten fruitless polls the orchestrator started
messaging the working coder: “Return implementation result immediately. Do
not keep investigating.” Each message interrupted the coder mid-edit; it had
to stop and answer its parent. After a few nags the orchestrator cancelled
the coder outright. The log entry reads “Stopping stalled authority coder.”
The coder's last recorded action was writing a TUI message type,
mid-implementation, with `stopReason: aborted`.

A fresh replacement then spent seven minutes re-reading the same files the
dead coder already knew. One task ran three times this way: spawn, resume,
finish. About 40 minutes for maybe 13 minutes of actual work.

The part that stung: I measured where a coder's wall-clock actually goes.
One 34-minute session spent 1,987 seconds waiting for the LLM and 48 seconds
executing tools. 97.6% was inference wait. Tools, LSP and worktree setup were
noise. The whole game is turn count multiplied by per-turn latency, and the
harness was multiplying the turns.

## what the harness actually gives you

omp's orchestration surface is richer than my runs were using. The defaults
and the docs had pushed me toward the slow path.

The main orchestrator delegates through a `task` tool to named subagents. My
setup has a recon agent, a planner, an architect, stack coders, five review
lenses and a debugger, all mapped to model roles in config.

`hub` is the inter-agent mailbox: wait, send, job list (`irc` in the
config, for historical reasons). `eval` is the part I was ignoring:
persistent Python cells where `agent()` blocks until a subagent finishes
and `parallel()` fans out under the concurrency cap. A run scripted through
eval burns zero polling turns; the same run through task-plus-wait burned
sixty.

Two features turned out to be the difference between the slow path and the
fast one. First, finished subagents do not die: they park idle with
context intact (`task.agentIdleTtlMs`, default seven minutes) and revive on
a hub message. Send the next dependent task to the parked coder and you
skip the cold-start re-discovery entirely. My orchestrator had been
cold-spawning every task.

Second, there is no passive progress view of a running subagent: `hub
op:jobs` returns names only, and the docs explicitly tell the orchestrator
to message agents for updates. Checking on a coder means interrupting it.
That design gap explains the whole nag-and-cancel spiral. It is an open
upstream issue.

omp also runs an advisor: a second model passively reviewing every turn and
injecting notes. Mine had been silently broken for weeks in a way I find
funny now: my watchdog prompt demanded “read the whole diff first” while
its toolset banned bash. The advisor cannot run `git diff`; the model
requested bash anyway; the harness quarantined the entire advisory as
punishment. Forty-six lost reviews in one day's log. The fix was a
WATCHDOG.yml granting read-only bash: align capability with procedure and
the quarantines stop.

## what the community already knew

I did the research after the forensics. It mostly confirmed the logs.

One source put it in almost the words I ended up using for this post's title:
“harness matters more than model.” SWE-bench scaffolding comparisons show
5–17 point success-rate spreads with the same model, and a security-review
benchmark reached the same conclusion. My four-model experiment found it
from the other side.

Fan-out taxes small coupled tasks. One measured comparison put a
two-subagent fan-out at 2.6–5.9x the tokens of sequential work and slower on
wall-clock. Parallelism pays only on genuinely independent work. Cognition's
“Don't Build Multi-Agents” adds the sharper point: worktrees prevent file
collisions while decision collisions remain. Two parallel coders will happily
invent two incompatible interfaces. Lock shared contracts in the briefs before
fanning out; a parallel worker never decides a contract another worker
consumes.

Cascade routing (RouteLLM and friends) holds up in practice: cheap model by
default, escalate when a verification gate fails. And a detail I had not
internalized: model and reasoning effort are prompt-cache keys. Switching
either mid-session recomputes the whole cached prefix. omp's prewalk
feature (start strong, then hand off to a cheap model at the first edit)
fired on my orchestrator's bookkeeping writes and downgraded it mid-run for
34 of 189 turns. Good pattern for solo coding, wrong trigger for
orchestration; I turned it off.

## what a month of transcripts said

One run explains one run. omp keeps every session as JSONL, so I measured
all of them: 2,970 subagent spawns, 114,486 assistant turns.

The first number reframed everything. Against 375 million tokens of
uncached input sat 11.4 billion tokens of cached reads. Context is cheap
and cached; what costs wall-clock is that every turn is a full inference
roundtrip. Turns are the currency. Tokens aren't. Shaving prompt bytes is
noise; removing turns is the whole game.

So where do turns go? Three places, all measurable.

Tool calls arrive one at a time. Fleet average: 1.48 tool calls per
assistant turn across 108,000 tool-turns. MiniMax M3 issues exactly one
call in 87% of its turns; the codex models, 94 to 98%. A tool call costs
milliseconds, a turn costs seconds. Batching three already-known reads into
a single turn would cut roundtrips roughly in half, the largest latency win
left on my table, bigger than any model swap. Best batcher in the fleet was
MiMo v2.5 at 2.35.

Agents re-read what they already read. 12% of 62,268 reads were redundant:
the same path opened twice or more by one agent. The pathological case was
a review agent that read one 15-line range 521 times, made 1,585 tool
calls, and died with `stopReason: length`: context exhausted, no result
produced, nothing in the harness stopping it. I suspected the edit tool was
forcing it, since hashline edits work off line hashes. It wasn't: only 0.7%
of 11,202 edits were preceded by a read of the same file. It is model
behavior. The fix is a prompt rule.

Every spawn pays a prefix. First-turn input across those 2,970 spawns
totalled 80.4 million tokens, 21% of all uncached input, slightly more than
my entire output volume. Median first turn: 43K tokens for M3, 34K for MiMo
Pro, 19K for GLM. That is the arithmetic behind messaging the parked coder
instead of spawning a fresh one.

Then the finding I did not expect: the serving provider matters more than
the model. Same MiniMax M3 weights, two routes. Through minimax-code, the
official endpoint: 11% redundant reads, one looping agent out of 346.
Through ollama-cloud: 67% redundant, 116 tool calls per agent, six of
twenty agents looping. Six-fold waste from the route alone.

I went looking for why, and found it in someone else's issue tracker.
ollama issue 15645, open since April, describes exactly this for Kimi and
Qwen/GLM: for `:cloud` models the request is forwarded raw to the upstream
host with no local tool-call parser, so native tool-call tokens leak
through as plain text and nested JSON arguments get double-stringified. An
agent that receives a mangled tool result reads the file again. That is
the likeliest mechanism behind my 67% (the issue names Kimi, Qwen and GLM,
the passthrough bug it describes is generic to the `:cloud` route rather
than specific to any one of them).

The warnings about third-party endpoints go beyond quantization. OpenRouter
reached the same conclusion from production telemetry: broken tool-call
parsers explain provider variance better than bit width does. I now pin
official endpoints for every role.

The efficiency ranking was its own surprise. GLM-5.2 is the cleanest thing
I run: 4% redundant reads, 40 tool calls per agent, zero loops across 782
agents. Gemini Flash: 0% and 34. My coder, MiMo v2.5 Pro, sits at 16% and
88, double GLM's tool calls on the highest-volume role in the system.
Implementation honestly needs more calls than review does, but that gap is
the weakest link in my hot path.

The review phase told the same story from the other side. Watching four
lenses run live: 42, 47, 50 and 78 tool calls, four to seven minutes each.
A lens burning 78 calls has stopped reviewing the diff and started
exploring the repo. A faster model would just explore faster.

What fixed it was handing the reviewer the diff inline, telling it to open
only files the diff references, and spawning the heavy lenses only when the
changed paths earn them: auth and SQL get the security lens, a moved
package boundary gets the architecture lens, everything else gets two
lenses and the test floor as the actual merge gate.

## what the trackers confirmed

Measuring your own logs tells you what is happening. Issue trackers tell
you why, and whether anyone intends to fix it.

The prefix tax turned out to be a reported, still-open bug: omp issue 4570
(the project is `oh-my-pi` on GitHub). Every eagerly spawned subagent
receives the complete skills catalog plus the full user instruction file
regardless of role: a read-only research agent gets handed the
commit-message guidelines.

The issue puts that at roughly 27KB per agent, about 320KB across a
twelve-subagent session; my own trimmed catalog runs closer to 13.1KB, and
one twelve-subagent session in my own logs carried about 265,000 tokens of
duplicated context, more than the skills-and-instructions block alone
accounts for, so something else is getting re-sent too. It is the
unexplained bulk of my 19–43K first-turn prefix, it is unfixed, and the
mitigation is entirely on my side: fewer spawns, smaller catalog.

The serialized tool calls had a harness cause too, at least partly. Digging
through the bundle, the codex request path sets `parallel_tool_calls` to
false unconditionally, which is exactly why codex models showed up in my
data at 1.07 calls per turn and 98% serialized. They weren't being lazy,
they were being told to.

My current providers get no such flag, so their 1.33–2.35 range is model
behavior, and prompting can move it. That parameter is not honored
uniformly anywhere. vLLM silently ignored it for over a year until a fix
merged in November 2025, and MiMo's API still has an open issue rejecting
OpenAI-shaped tool-calling history. Probe the endpoint you actually use;
don't trust the model card.

The most useful idea I found had barely been tried: code execution in place
of individual tool calls. Let the model write one code block that performs
twenty operations and you eliminate nineteen inference passes. Anthropic measured a workflow dropping
from 150,000 tokens to 2,000 that way; Cloudflare reported 1.17M to roughly
1,000 collapsing their API surface into a generated client. It attacks turn
count by construction rather than by asking a model nicely.

I checked whether omp had tried this. Two 2026 proposals for programmatic
tool calling shipped in narrower form as the `eval` tool itself, a Python
subprocess the model can drive instead of the tool-call loop. The proposal closed as `not planned` back in March was more ambitious: a
full IPython kernel with MCP calls exposed as callable functions inside it,
so one script could chain arbitrary tools without a round trip per call.
`eval` already gets me most of the way there; testing it as a batching
escape hatch beyond subagent orchestration is my next experiment.

The one number I could act on immediately came from a turn-budget paper:
capping turns at the 75th percentile of your own observed distribution cuts
cost 24 to 68% with minimal loss in solve rate. Mine: median 22 turns per
subagent, 75th percentile 48, 95th 119, maximum 1,065. I did not cap at 48,
that would nudge a quarter of my runs, and coders legitimately go long. I
set the soft budget to 120, down from a default of 200. Ninety-five percent
of spawns never notice; the 1,065-turn pathology becomes impossible.

## the changes that stuck

Config, in rough order of impact (this is the state on 2026-07-30, it has
moved some since):

```yaml
irc:
  timeoutMs: 900000         # hub waits wake on completion; 15 min cap, not 60s polls
task:
  eager: preferred          # was always -- stop shredding work into micro-dispatches
  agentIdleTtlMs: 1800000   # park finished coders 30 min for reuse via hub send
  maxRuntimeMs: 2700000     # was 0. hard stop, so a looping agent dies at 45 min
  softRequestBudget: 120    # was 200. p95 of my own turn distribution
prewalk:
  enabled: false            # stop downgrading the orchestrator at its own bookkeeping writes
advisor:
  syncBacklog: "3"          # was "1" -- stop stalling the main agent on advisor lag
contextPromotion:
  enabled: false            # was a no-op anyway: no model here has a promotion target
retry:
  usageAwareFallback: true  # check provider quota before failing into fallback
  fallbackChains:           # every model in every role has somewhere to land
    xiaomi/mimo-v2.5-pro: [minimax-code/MiniMax-M3, hyper-charm/deepseek-v4-pro]
    minimax-code/MiniMax-M3: [xiaomi/mimo-v2.5-pro, hyper-charm/deepseek-v4-pro]
```

The prompt rules mattered more than the settings. My harness system append
now says: batch independent tool calls into one turn; never re-read a file
you already read; reviewers read the diff, not the repo; triage the diff
before choosing review lenses; never pass `timeoutMs` to a hub wait; a coder
running for 20 minutes is working, not stalled; send the next dependent task
to the parked coder; lock shared contracts before fanning out; escalate one
model tier after a failed gate instead of retrying the same tier.

And the coder role dropped from high to medium reasoning effort: it
executes an approved plan, and the thinking already happened at planning
time on a stronger configuration.

One more thing worth saying out loud: the agent config points at roles, not
models. Every agent references a role name (`writer`, `coder`, `reviewer`),
and only the role table names a concrete model beneath it. Swapping the
model behind prose writing is then a one-line change, not a hunt through
twenty agent definitions.

The arithmetic says the same run should land around 30 minutes: ten minutes
of polling gone, twenty-five of cancel-and-respawn gone, ten of cold-start
re-discovery gone. The independent contract tasks now run in parallel too,
worth something I have not isolated yet. Batching and the trimmed review panel
should take another bite out of that. The next real run will grade the
homework.

My rule now: when an agent system is slow on every model, read the
transcripts before touching model config. The model may be the part that is
working. The evidence is already on disk, in a format a few lines of Python
can count.
