"""The loop runtime: the engine that drives the six contracts.

This is the piece that was deferred in Phase 1. It composes one implementation
of each contract and runs the canonical cycle::

    GOAL -> find work -> act -> verify -> remember -> repeat -> STOP

Invariants it upholds:
- Stop conditions are checked at the TOP of every pass, before any work.
- An action counts as progress only if ALL sensors pass.
- Every pass increments ``iteration`` (so MaxIterations bounds even empty
  rounds) and persists state, so the loop is always restartable.
- The runtime supplies timestamps; contracts never read the clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from .contracts import Actor, Goal, Sensor, StateStore, StopCondition, WorkSource
from .types import (
    Context,
    IterationRecord,
    LoopState,
    SensorResult,
    StopReason,
)


@dataclass
class LoopResult:
    goal_id: str
    stop_reason: StopReason
    iterations: int
    done: list[str]
    cost_tokens: int
    state: LoopState


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def _combine(results: list[SensorResult]) -> SensorResult:
    passed = all(r.passed for r in results)
    if passed:
        return SensorResult(sensor="all", passed=True)
    fails = "; ".join(f"{r.sensor}: {r.evidence}" for r in results if not r.passed)
    return SensorResult(sensor="all", passed=False, evidence=fails)


@dataclass
class LoopRunner:
    goal: Goal
    work_source: WorkSource
    actor: Actor
    sensors: list[Sensor]
    stops: list[StopCondition]
    state_store: StateStore
    clock: Callable[[], str] = _default_clock
    safety_max_passes: int = 100_000  # backstop against an under-specified loop

    def run(self) -> LoopResult:
        ctx = self.state_store.load()
        ctx.extras["goal"] = self.goal
        ctx.extras.setdefault("empty_rounds", 0)
        ctx.state.status = "running"

        passes_this_run = 0
        while True:
            # 1. stop check, before any work
            decision = self._first_stop(ctx)
            if decision is not None:
                return self._finalize(ctx, decision.reason)

            if passes_this_run >= self.safety_max_passes:
                return self._finalize(ctx, StopReason.ABORTED)

            # 2. find work
            items = [
                it
                for it in self.work_source.find(ctx)
                if it.id not in ctx.state.done_ids
            ]
            if not items:
                ctx.extras["empty_rounds"] = ctx.extras.get("empty_rounds", 0) + 1
                ctx.state.iteration += 1
                passes_this_run += 1
                self.state_store.save(ctx)
                continue
            ctx.extras["empty_rounds"] = 0

            # 3. act on one item (smallest change)
            item = items[0]
            action = self.actor.act(item, ctx)
            ctx.state.cost_tokens += action.cost_tokens

            # 4. verify; progress only if ALL sensors pass
            results = [s.verify(item, action, ctx) for s in self.sensors]
            combined = _combine(results)
            if combined.passed:
                ctx.state.done_ids.add(item.id)

            # 5. remember
            record = IterationRecord(
                iteration=ctx.state.iteration,
                work_item=item,
                action=action,
                sensor=combined,
                timestamp=self.clock(),
            )
            ctx.state.history.append(record)
            ctx.state.iteration += 1
            passes_this_run += 1
            self.state_store.record(record)
            self.state_store.save(ctx)

    def _first_stop(self, ctx: Context):
        for cond in self.stops:
            d = cond.should_stop(ctx)
            if d.stop:
                return d
        return None

    def _finalize(self, ctx: Context, reason: StopReason) -> LoopResult:
        ctx.state.status = "stopped"
        ctx.state.stop_reason = reason
        self.state_store.save(ctx)
        return LoopResult(
            goal_id=ctx.state.goal_id,
            stop_reason=reason,
            iterations=ctx.state.iteration,
            done=sorted(ctx.state.done_ids),
            cost_tokens=ctx.state.cost_tokens,
            state=ctx.state,
        )
