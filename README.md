# OnLOOP — a framework for loop engineering

> Loop engineering is building a system that prompts your agent on a schedule
> and against a goal, instead of typing each prompt yourself. The leverage moves
> from the quality of a single prompt to the design of the system that generates
> and verifies prompts.

**OnLOOP** makes that system concrete. `Agent = Model + Harness`; this framework
owns the **loop** part of the harness. It defines six small interfaces for the
parts of a loop so a runtime can drive any agent through the canonical cycle:

```
              ┌──────────────────────── StopCondition.should_stop ◀──┐
              ▼                                                       │
  Goal ─▶ WorkSource.find ─▶ Actor.act ─▶ Sensor.verify ─▶ StateStore (remember)
 (checkable)  (find work)      (act)        (verify)        (persist + trace)
```

The pattern is provider-agnostic: a `Sensor` can be a test runner, an `Actor`
can be a model call, a `WorkSource` can scan failing tests or a queue. The loop
lives in the spec, not in new code.

## Status — Phase 2: the loop runs

| | Component | Where |
|---|---|---|
| ✅ | Contracts + data types | `onloop/contracts.py`, `onloop/types.py` |
| ✅ | Spec schema + loader | `schema/loop.schema.json`, `onloop/spec.py` |
| ✅ | Runtime (`LoopRunner`) | `onloop/runtime.py` |
| ✅ | Restartable JSON state store | `onloop/state.py` |
| ✅ | Standard stop conditions | `onloop/stops.py` |
| ✅ | CLI (`onloop run\|resume`) | `onloop/cli.py` |
| ✅ | Reference loop + tests | `examples/punchlist`, `tests/` |
| ⬜ | Real-agent impls, isolation, safety, guide write-back | see [Roadmap](#roadmap) |

## The six contracts

A loop is one implementation of each (in `onloop/contracts.py`):

| Contract | Stage | Question it answers |
|---|---|---|
| `Goal` | goal | What checkable objective are we driving toward? |
| `WorkSource` | find work | What is the next unit of work? |
| `Actor` | act | How do we do one unit? |
| `Sensor` | verify | Is the result acceptable, with evidence? |
| `StateStore` | remember | What carries across iterations and restarts? |
| `StopCondition` | stop | When do we stop? |

Two invariants are enforced by the spec schema, not left to discipline: every
loop must declare at least one **sensor** (it can check itself) and at least one
**stop condition** (it terminates). An unbounded, unverified loop will not load.

## Install & run

```bash
pip install -e '.[dev]'

# run the deterministic reference loop (no API key needed)
PYTHONPATH=. onloop run examples/punchlist/punchlist.loop.yaml --workspace /tmp/demo
#   loop:        punchlist
#   stopped:     goal_met
#   iterations:  3
#   done items:  3 ['inspect', 'paint', 'wire']

PYTHONPATH=. onloop resume examples/punchlist/punchlist.loop.yaml --workspace /tmp/demo
python tests/test_runtime.py        # or: pytest -q
```

`run` starts fresh (clears prior state); `resume` continues from the saved
`state/<name>.json`.

## Declare a loop (YAML)

Each component binds a contract to a Python class via a dotted `uses:` path plus
constructor `with:` args. Validated against
[`schema/loop.schema.json`](schema/loop.schema.json).

```yaml
name: punchlist
goal:        { uses: examples.punchlist.impl.PunchlistClear, with: { seed: [wire, paint, inspect] } }
work_source: { uses: examples.punchlist.impl.OpenItems,      with: { seed: [wire, paint, inspect] } }
actor:       { uses: examples.punchlist.impl.MarkDone }
sensors:
  - { uses: examples.punchlist.impl.ItemIsDone }
stop:
  - { uses: onloop.stops.GoalMet }
  - { uses: onloop.stops.MaxIterations, with: { max_iters: 20 } }
budget:
  max_iters: 20      # expanded into an implicit stop condition
```

See also the LLM-shaped (not yet runnable) target spec:
[`schema/examples/make-tests-green.loop.yaml`](schema/examples/make-tests-green.loop.yaml).

## Or build one in Python

```python
from onloop import (Goal, WorkSource, Actor, Sensor, WorkItem, ActionResult,
                     SensorResult, Context, LoopRunner, JsonStateStore)
from onloop.stops import GoalMet, MaxIterations

# implement the contracts for your domain ... then:
runner = LoopRunner(
    goal=MyGoal(), work_source=MySource(), actor=MyActor(),
    sensors=[MySensor()],
    stops=[GoalMet(), MaxIterations(25)],
    state_store=JsonStateStore("state/my.json", goal_id="my", workspace="."),
)
result = runner.run()
print(result.stop_reason, result.done)
```

## Project layout

```
onloop/                 the framework
  contracts.py           the six interfaces (ABCs)
  types.py               serializable data types (WorkItem, LoopState, ...)
  runtime.py             LoopRunner — drives find→act→verify→remember→stop
  state.py               JsonStateStore — atomic, restartable persistence
  stops.py               GoalMet, MaxIterations, TokenBudget, LoopUntilDry
  spec.py                load + validate *.loop.yaml, build a runner
  cli.py                 `onloop run|resume`
schema/                  loop.schema.json + an aspirational example spec
examples/punchlist/      deterministic, no-LLM reference loop
tests/                   end-to-end runtime tests (every stop reason + resume)
docs/                    ARCHITECTURE.md, PATTERNS.md
CLAUDE.md                operating rules for agents working in this repo
```

## Roadmap

- [x] Contracts + spec schema + docs (Phase 1)
- [x] Runtime + JSON `StateStore` + standard stops + CLI (Phase 2)
- [x] Reference loop + end-to-end tests (Phase 2)
- [ ] Real-agent reference impls — pytest/ruff `Sensor`s, an LLM-backed `Actor`
- [ ] Isolation — `worktree` / `sandbox` backends for parallel work
- [ ] Observability — structured per-iteration tracing + cost dashboards
- [ ] Safety — kill switch, human-on-the-loop checkpoints
- [ ] Guide write-back — self-updating `AGENTS.md`-style learnings (`GuideStore`)

## See also

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the design in full, plus what is deferred and why.
- [`docs/PATTERNS.md`](docs/PATTERNS.md) — loop shapes, with the **Ralph loop** (`PROMPT.md` / `AGENTS.md` / `progress.md`) as the canonical reference.
- `CLAUDE.md` — operating rules for agents working in this repo.

### Background

The term *loop engineering* was popularized by Addy Osmani (June 2026), building
on Peter Steinberger and Anthropic's Boris Cherny ("write loops rather than
prompt the model directly"). It is the sibling of *harness engineering*
(Birgitta Böckeler, Thoughtworks): the harness is everything around the model;
the loop is the cycle that drives it. **OnLOOP** makes both the brakes (sensors,
stop conditions) mandatory — the gap the bare "Ralph loop" leaves open.
