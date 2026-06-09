# Architecture

`onloop` is a **contracts-first** framework. The thesis of loop engineering is
that leverage lives in the *system that prompts the agent*, not in any single
prompt. So the framework's primary artifact is a small set of interfaces that
pin down what a loop is, leaving every concrete behavior pluggable.

## The core: five-and-one contracts

A loop is the composition of one implementation of each contract below. They
map one-to-one onto the stages of the canonical loop in `CLAUDE.md`.

```
              ┌─────────────────────── StopCondition.should_stop ◀──┐
              ▼                                                      │
  Goal ─▶ WorkSource.find ─▶ Actor.act ─▶ Sensor.verify ─▶ StateStore (remember)
  (checkable)  (find work)     (act)        (verify)         (persist + trace)
```

| Contract | Stage | Method(s) | Enforces |
|---|---|---|---|
| `Goal` | goal | `is_satisfied`, `describe` | A goal is a checkable predicate, not a vibe |
| `WorkSource` | find work | `find` | The agent discovers work; skips `done_ids` |
| `Actor` | act | `act` | Smallest change per item; reports cost |
| `Sensor` | verify | `verify` | No progress without a passing, evidenced verdict |
| `StateStore` | remember | `load`, `save`, `record` | Loops are restartable; state lives on disk |
| `StopCondition` | stop | `should_stop` | Termination is explicit; unbounded loops are bugs |

The "and one" is `StopCondition`: it is not a loop stage so much as the guard
that wraps every iteration. A spec must declare at least one.

## Data flow

All inter-contract data are the plain, JSON-serializable types in
`onloop/types.py`:

- `WorkItem` — a unit of work with a stable `id` (so `done_ids` works across restarts).
- `ActionResult` — what the `Actor` changed, plus `cost_tokens`.
- `SensorResult` — a verdict with mandatory `evidence` on failure.
- `IterationRecord` — one immutable trace entry per pass.
- `LoopState` — the full restartable state (iteration, `done_ids`, cost, history).
- `StopDecision` / `StopReason` — why and whether to stop.
- `Context` — the read-mostly bundle passed to every contract call.

Serializability is a hard requirement: a `StateStore` round-trips `LoopState`
to disk, so nothing in these types may hold a live handle, socket, or model
client.

## Determinism

Contracts never read the wall clock or a random source directly. `timestamp`
on `IterationRecord` is supplied by the runtime. This keeps a loop's decisions
replayable from its recorded history, which is what makes resume and debugging
tractable.

## The spec

A loop is declared in a `*.loop.yaml` file validated against
`schema/loop.schema.json`. Each component names a Python class via a dotted
`uses:` path and its constructor `with:` args. The spec is the unit a runtime
loads; see `schema/examples/make-tests-green.loop.yaml`.

The schema bakes in two invariants:
- `sensors` requires `minItems: 1` — every loop must be able to check itself.
- `stop` requires `minItems: 1` — every loop must declare termination.

## Patterns

The shapes these contracts express (Ralph loop, loop-until-dry, fan-out/verify,
adversarial verify, human-on-the-loop) are catalogued in
[`PATTERNS.md`](PATTERNS.md). The **Ralph loop** is the canonical reference
implementation and the blueprint for the Phase 2 runtime: a fixed `PROMPT.md`
goal, file-based memory (`progress.md`), and self-updating guides
(`AGENTS.md`). Reading it shows precisely how `Goal` / `StateStore` / the
guide layer are meant to behave at runtime.

## Status: shipped in Phase 2

The runtime and its supporting cast now exist and are tested end to end:

- **Runtime / executor** (`onloop/runtime.py`) — `LoopRunner` drives
  find → act → verify → remember → stop, checking stop conditions at the top of
  every pass and counting progress only when all sensors pass.
- **State store** (`onloop/state.py`) — `JsonStateStore` persists `LoopState`
  atomically and appends an `IterationRecord` trace; loops resume from disk.
- **Standard stop conditions** (`onloop/stops.py`) — `GoalMet`,
  `MaxIterations`, `TokenBudget`, `LoopUntilDry`.
- **Spec loader** (`onloop/spec.py`) and **CLI** (`onloop/cli.py`,
  `onloop run|resume`).
- **Reference loop + self-tests** — `examples/punchlist` (deterministic, no
  model) and `tests/test_runtime.py` exercise every stop reason plus resume.

## What is still deferred

The following remain, in rough priority order:

1. **Real-agent reference implementations** — concrete `Sensor`s (pytest, ruff)
   and an LLM-backed `Actor`. The punch-list example is deliberately
   model-free; the next step is a loop that actually edits code.
2. **Isolation adapter** — `worktree` / `sandbox` backends for parallel work.
3. **Observability** — structured tracing and cost dashboards beyond the
   current JSONL trace.
4. **Safety** — kill switch and human-on-the-loop checkpoints (the runtime has
   a `safety_max_passes` backstop and budget stops, but no interactive gate).
5. **Guide write-back (self-improving harness)** — the Ralph loop's
   `AGENTS.md` mechanism: the loop appending discovered learnings to a standing
   guide so future iterations benefit (CLAUDE.md principle #6, "improve the
   harness on recurring failure"). The contracts model feedforward via
   `Context.extras`, but there is no interface yet for the loop to *update* its
   own guides. This is a candidate for a small optional `GuideStore` contract,
   deliberately kept out of the core for now.

## Extension points

To build a real loop today you implement the six contracts against your domain
and (once the runtime lands) point a spec at them. The contracts are designed
so that 90% of a new loop is a new `WorkSource` + `Actor`; goals, sensors, and
stop conditions are mostly reusable across loops.
