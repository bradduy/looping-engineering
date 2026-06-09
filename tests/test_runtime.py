"""End-to-end runtime tests. Runs under pytest, or directly: `python tests/test_runtime.py`.

These are the framework eating its own dog food: a real loop driven to each of
its stop reasons (goal_met, max_iters, dry), plus restart/resume persistence.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loopeng import (  # noqa: E402
    Context,
    JsonStateStore,
    LoopRunner,
    StopReason,
    WorkItem,
    WorkSource,
)
from loopeng.stops import GoalMet, LoopUntilDry, MaxIterations  # noqa: E402
from examples.punchlist.impl import (  # noqa: E402
    ItemIsDone,
    MarkDone,
    OpenItems,
    PunchlistClear,
)


# fixed clock so timestamps are deterministic and replayable
_TS = "2026-06-10T00:00:00+00:00"


def _store(ws):
    return JsonStateStore(os.path.join(ws, "state", "t.json"), "t", ws)


def _punch_runner(ws, stops, seed=("wire", "paint", "inspect")):
    seed = list(seed)
    return LoopRunner(
        goal=PunchlistClear(seed=seed),
        work_source=OpenItems(seed=seed),
        actor=MarkDone(),
        sensors=[ItemIsDone()],
        stops=stops,
        state_store=_store(ws),
        clock=lambda: _TS,
    )


def test_converges_to_goal_met():
    with tempfile.TemporaryDirectory() as ws:
        r = _punch_runner(ws, [GoalMet(), MaxIterations(20)])
        result = r.run()
        assert result.stop_reason is StopReason.GOAL_MET, result.stop_reason
        assert sorted(result.done) == ["inspect", "paint", "wire"]
        # 3 acting passes (iterations 0->3); the 4th pass stops at the top-of-loop
        # GoalMet check before find(), so iteration is not incremented again.
        assert result.iterations == 3, result.iterations
        assert result.cost_tokens == 30, result.cost_tokens


def test_max_iters_bounds_before_goal():
    with tempfile.TemporaryDirectory() as ws:
        r = _punch_runner(ws, [GoalMet(), MaxIterations(2)])
        result = r.run()
        assert result.stop_reason is StopReason.MAX_ITERS, result.stop_reason
        assert len(result.done) < 3  # did not finish


def test_resume_preserves_progress():
    with tempfile.TemporaryDirectory() as ws:
        # interrupt after 2 passes
        first = _punch_runner(ws, [MaxIterations(2)]).run()
        assert first.stop_reason is StopReason.MAX_ITERS
        partial = set(first.done)
        # resume on the SAME store (no reset) and finish
        second = _punch_runner(ws, [GoalMet(), MaxIterations(20)]).run()
        assert second.stop_reason is StopReason.GOAL_MET, second.stop_reason
        assert sorted(second.done) == ["inspect", "paint", "wire"]
        assert partial.issubset(set(second.done))  # earlier work was remembered


def test_loop_until_dry():
    class EmptySource(WorkSource):
        def find(self, ctx: Context) -> list[WorkItem]:
            return []

    class NeverDone(PunchlistClear):
        def is_satisfied(self, ctx):
            return False

    with tempfile.TemporaryDirectory() as ws:
        r = LoopRunner(
            goal=NeverDone(seed=["x"]),
            work_source=EmptySource(),
            actor=MarkDone(),
            sensors=[ItemIsDone()],
            stops=[LoopUntilDry(2), MaxIterations(50)],
            state_store=_store(ws),
            clock=lambda: _TS,
        )
        result = r.run()
        assert result.stop_reason is StopReason.DRY, result.stop_reason


def test_failed_sensor_blocks_progress():
    class AlwaysFail(ItemIsDone):
        def verify(self, item, action, ctx):
            from loopeng import SensorResult

            return SensorResult(sensor="always_fail", passed=False, evidence="nope")

    with tempfile.TemporaryDirectory() as ws:
        r = LoopRunner(
            goal=PunchlistClear(seed=["a"]),
            work_source=OpenItems(seed=["a"]),
            actor=MarkDone(),
            sensors=[AlwaysFail()],
            stops=[GoalMet(), MaxIterations(5)],
            state_store=_store(ws),
            clock=lambda: _TS,
        )
        result = r.run()
        # Actor mutates the file so the Goal is satisfied -> goal_met, BUT the
        # item never enters done_ids because its sensor failed every time.
        assert result.stop_reason is StopReason.GOAL_MET, result.stop_reason
        assert result.done == [], result.done


def test_state_round_trips_on_disk():
    with tempfile.TemporaryDirectory() as ws:
        _punch_runner(ws, [GoalMet(), MaxIterations(20)]).run()
        # reload from disk in a brand-new store and confirm persistence
        ctx = _store(ws).load()
        assert ctx.state.stop_reason is StopReason.GOAL_MET
        assert sorted(ctx.state.done_ids) == ["inspect", "paint", "wire"]
        assert len(ctx.state.history) == 3
        assert ctx.state.history[0].timestamp == _TS


def _main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    _main()
