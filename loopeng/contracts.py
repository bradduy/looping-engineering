"""The five-and-one contracts that define a loop-engineering loop.

A loop is the composition::

    Goal ─▶ WorkSource.find ─▶ Actor.act ─▶ Sensor.verify ─▶ StateStore.remember
                   ▲                                                  │
                   └──────────────── StopCondition.should_stop ◀──────┘

A runtime (NOT in this package yet) wires these together and drives the cycle
``find → act → verify → remember → repeat → stop``. Implement these interfaces
to plug a concrete loop into that runtime. Each contract maps to one stage of
the canonical loop and enforces one principle from CLAUDE.md.

This module defines *interfaces only*. There are no concrete implementations
and no engine here by design (see docs/ARCHITECTURE.md, "What is deferred").
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .types import (
    ActionResult,
    Context,
    SensorResult,
    StopDecision,
    WorkItem,
)


class Goal(ABC):
    """The recursive, checkable objective the loop drives toward.

    Enforces: "a goal is a checkable objective, not a vibe." ``is_satisfied``
    must be a real predicate over observable state, so the runtime can stop
    with ``StopReason.GOAL_MET`` instead of guessing.
    """

    @abstractmethod
    def describe(self) -> str:
        """Human-readable statement of the goal (shown in logs/traces)."""

    @abstractmethod
    def is_satisfied(self, ctx: Context) -> bool:
        """Return True when the objective is met and the loop should finish."""


class WorkSource(ABC):
    """Discovers the next units of work. The "find work" stage.

    Enforces: "the agent locates the next unit itself." Implementations scan
    the workspace (failing tests, open TODOs, a queue) and return the items
    still worth doing. They should consult ``ctx.state.done_ids`` and not
    re-emit finished work.
    """

    @abstractmethod
    def find(self, ctx: Context) -> list[WorkItem]:
        """Return outstanding work items. An empty list signals 'dry'."""


class Actor(ABC):
    """Performs one unit of work. The "act" stage.

    Enforces: "make the smallest change that advances the goal." An Actor
    handles a single ``WorkItem`` per call and reports what it changed and what
    it cost, so the runtime can track the budget.
    """

    @abstractmethod
    def act(self, item: WorkItem, ctx: Context) -> ActionResult:
        """Attempt the work item; return what changed and its token cost."""


class Sensor(ABC):
    """Decides whether an action is acceptable. The "verify" stage.

    Enforces: "every loop needs a sensor; wire the verifier before the actor."
    A loop never counts an action as progress without a passing Sensor. Sensors
    are pluggable and composable: a loop may run several (tests, linter, review
    agent) and require all to pass.

    Subclasses set ``name`` so results are attributable.
    """

    name: str = "sensor"

    @abstractmethod
    def verify(self, item: WorkItem, action: ActionResult, ctx: Context) -> SensorResult:
        """Observe the result and return a verdict with backing evidence."""


class StateStore(ABC):
    """Persists loop state so the loop is restartable. The "remember" stage.

    Enforces: "persist progress across iterations; keep loops restartable."
    Everything needed to resume lives on disk through this interface, never
    only in process memory.
    """

    @abstractmethod
    def load(self) -> "Context":  # returns a Context seeded with restored LoopState
        """Restore prior state (or initialize fresh) and return a Context."""

    @abstractmethod
    def save(self, ctx: Context) -> None:
        """Atomically persist the current LoopState held in ``ctx``."""

    @abstractmethod
    def record(self, record) -> None:  # record: IterationRecord
        """Append one IterationRecord to the durable history (the trace)."""


class StopCondition(ABC):
    """Decides when to terminate. The "stop" stage.

    Enforces: "state termination up front; an unbounded loop is a bug."
    Conditions are composable: a runtime typically evaluates several
    (goal-met, max-iters, budget, loop-until-dry) and stops on the first that
    fires, recording the corresponding ``StopReason``.
    """

    @abstractmethod
    def should_stop(self, ctx: Context) -> StopDecision:
        """Return whether to stop now, and if so, the StopReason."""
