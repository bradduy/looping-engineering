# Loop Patterns

A catalog of loop shapes that **OnLOOP**'s contracts are meant to express. The
first, the **Ralph loop**, is the canonical reference implementation and the
blueprint for the Phase 2 runtime. The rest are variations a runtime should be
able to support by composing the same six contracts.

---

## 1. The Ralph loop (canonical reference)

Coined by Geoffrey Huntley after Ralph Wiggum. The core is almost insultingly
simple:

```bash
while :; do cat PROMPT.md | agent ; done
```

The insight: **progress lives in files and git history, not in the context
window.** Each iteration starts a fresh agent with the same allocated context,
does a little work, writes what it learned and did back to disk, and exits.
When context fills, the next agent reorients from those files and continues.

### File convention

| File | Role | Changes per iteration? | OnLOOP mapping |
|---|---|---|---|
| `PROMPT.md` | The fixed task piped in every loop. The steering wheel. | **No, held constant** | `Goal` (`describe()` / the objective) |
| `AGENTS.md` | Standing instructions + accumulated learnings (gotchas, conventions). Coding tools auto-read it. | **Yes, agent appends learnings** | Guide / feedforward (see "Guide write-back" below) |
| `specs/*.md` | The detailed spec / PRD the goal is checked against. | Rarely | `Goal` evidence + `WorkSource` input |
| `progress.md` (a.k.a. `log.md`, `fix_plan.md`, `prd.json`) | What was done so far, so a clean agent picks up where the last left off. | **Yes, appended** | `StateStore` (the "remember" stage) |
| git history | Durable record of changes; also a memory substrate. | Every commit | `StateStore` history / `IterationRecord` trace |

### Why the prompt does NOT get rewritten

A common misconception is that the loop "updates the prompt." It does not.
`PROMPT.md` is held **fixed** on purpose: a stable goal plus fresh context each
pass is what prevents context rot and drift. What the loop updates is the
**log** (progress) and **AGENTS.md** (learnings). Those two steer the next
iteration indirectly, by changing what the fresh agent reads, not by editing
the instruction.

### How it maps onto the contracts

```
PROMPT.md (Goal) ─▶ read progress.md (StateStore.load)
                 ─▶ find next undone item       (WorkSource.find)
                 ─▶ do it                         (Actor.act)
                 ─▶ [verify]                       (Sensor.verify)  ← see gap
                 ─▶ append to progress.md + AGENTS.md (StateStore + guide)
                 ─▶ exit; shell `while` respawns   (runtime + StopCondition)
```

### The gap Ralph leaves, and why we close it

Naive Ralph has **no required verifier and no required stop condition**. The
`while :;` loop is literally infinite, and nothing forces the agent to check
its own work before committing. That is exactly the failure mode **OnLOOP**
forbids at the schema level:

- `sensors` requires `minItems: 1` — the loop must be able to check itself.
- `stop` requires `minItems: 1` — the loop must terminate.

> Ralph is the loop with the brakes optional. **OnLOOP** is the same loop with
> the brakes required.

---

## 2. Loop-until-dry

For unknown-size discovery (find all bugs, close all TODOs): keep running
rounds until **K consecutive rounds surface no new work**. Implemented as a
`StopCondition` (`StopReason.DRY`) that counts empty `WorkSource.find()`
results. Prevents the tail of missed items that a fixed iteration count drops.

## 3. Fan-out / verify pipeline

When work items are independent: discover N items, process each through
`Actor → Sensor` concurrently with `isolation: worktree` so parallel changes
do not collide. The runtime's job is to keep per-item chains independent (no
barrier) unless a later stage genuinely needs all results at once.

## 4. Adversarial / perspective-diverse verify

Strengthen the verify stage: run several `Sensor`s per item, either as N
skeptics prompted to *refute* (kill unless a majority survive) or as distinct
lenses (correctness, security, reproduces?). A loop requiring all sensors to
pass already composes this; the spec just lists multiple sensors.

## 5. Human-on-the-loop

Not human-*in*-the-loop. The loop runs unattended but pauses at defined
checkpoints (e.g. before a destructive action, or every K iterations) for a
human to inspect the log and approve. Implemented as a `StopCondition` that
returns `StopReason.ABORTED` pending approval, plus the deferred kill switch.

---

## Choosing a pattern

| If the work is… | Use |
|---|---|
| A long build toward a fixed spec/PRD | Ralph loop |
| Discovery of unknown size | Loop-until-dry |
| Many independent units | Fan-out / verify |
| High-stakes correctness | Adversarial verify |
| Unattended but risky | Human-on-the-loop |

All five are the same six contracts, recomposed. That is the point of a
contracts-first framework: the pattern lives in the spec, not in new code.
