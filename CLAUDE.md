# CLAUDE.md — Loop Engineering

This repository is a **loop-engineering workspace**. The work here is not just writing code; it is designing the *loops* that let an agent do the writing, verifying, and remembering on its own. Optimize the system that prompts the agent, not the individual prompt.

> `Agent = Model + Harness`. The **harness** is everything that is not the model: tools, context, memory, guardrails, and the **loop**. Loop engineering owns the loop; harness engineering owns the rest. They are complementary, not rivals.

## The canonical loop

Every task in this repo should be expressible as one self-running cycle:

```
GOAL → find work → act → verify → remember → repeat → STOP
```

- **Goal** — a recursive, checkable objective ("0 failing tests", "all TODOs in spec.md closed"). Not a vibe.
- **Find work** — the agent locates the next unit itself (failing test, open item, stale file). Never hand-pick steps you could let it discover.
- **Act** — make the smallest change that advances the goal.
- **Verify** — a sensor decides if the result is acceptable *before* a human looks. No verification, no progress.
- **Remember** — persist what is done so the next iteration does not redo it (see Memory below).
- **Stop** — define termination up front: goal met, budget exhausted, max iterations, or N consecutive empty rounds ("loop-until-dry").

## Operating principles

1. **Design the loop, not the prompt.** If you find yourself typing the next instruction by hand, ask whether the loop should have generated it.
2. **Every loop needs a sensor.** A loop that acts but cannot check itself is a way to make mistakes faster. Wire the verifier before the actor.
3. **State termination before you start.** An unbounded loop is a bug. Name the stop condition explicitly.
4. **Isolate parallel work.** Concurrent agents that touch shared files corrupt each other. Use worktrees or per-item sandboxes when fanning out.
5. **Persist progress across iterations.** The loop must survive a restart. Externalize state to files, not to the conversation.
6. **Improve the harness on recurring failure.** When the same issue appears twice, do not just fix it — add a guide (feedforward) or sensor (feedback) so it cannot recur.
7. **Log what you skipped.** Silent truncation (top-N, sampling, no-retry) reads as "covered everything" when it did not. Say what was dropped.
8. **Scale effort to the ask.** A quick check gets a few iterations and single-vote verification; an audit gets a larger pool and adversarial, multi-perspective verification.

## Harness components in this repo

| Component | Role | Where |
|---|---|---|
| **Guides (feedforward)** | Steer before acting: conventions, templates, this file | `CLAUDE.md`, docs |
| **Sensors (feedback)** | Observe after acting: tests, linters, review agents | test suite, `/code-review`, `/verify` |
| **Loop / control flow** | The cycle that drives the agent toward the goal | `Workflow` scripts, `/loop` |
| **Memory** | What carries across iterations | `state/`, task list, project memory |

## Tools available for building loops

- **`Workflow`** — deterministic multi-agent orchestration. Use `pipeline()` by default; reach for a barrier (`parallel()`) only when a stage genuinely needs all prior results at once. Encodes loop-until-dry, loop-until-budget, fan-out/verify, and judge-panel patterns.
- **`/loop`** — run a prompt or slash command on a recurring interval, or self-paced. For polling and scheduled, goal-driven runs.
- **Task tools** (`TaskCreate`/`TaskUpdate`) — externalize the work-list so iterations and restarts stay coherent.
- **Subagents (`Agent`)** — spin up isolated workers for fan-out; keep the conclusion, not the file dumps.

## Verification patterns

- **Adversarial verify** — spawn N skeptics prompted to *refute* a finding; kill it unless a majority survive.
- **Perspective-diverse verify** — give each verifier a distinct lens (correctness, security, repro) instead of N identical checks.
- **Loop-until-dry** — for unknown-size discovery, keep finding until K consecutive rounds surface nothing new.
- **Completeness critic** — a final pass asking "what is missing — a modality not run, a claim unverified?"

## Conventions

- **Stop conditions are required.** No loop merges without an explicit, checkable termination.
- **Verifiers run before commit.** Tests/linters must be green; do not report success on unverified work.
- **Report outcomes faithfully.** If a verifier failed, say so with the output. If a step was skipped, say that.
- **Keep loops restartable.** Anything a loop needs to resume lives on disk, not only in context.

## Project status

This workspace is newly initialized. As real loops and code land here, extend this file with: the build/test commands that act as sensors, the directory layout, and the specific loops this project runs.
