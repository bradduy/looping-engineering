"""Core data types shared across the loop-engineering contracts.

These are plain, serializable values. They carry no behavior beyond what a
runtime needs to pass data between the five contracts (see ``contracts.py``)
and to persist/restore a loop. Keeping them dependency-free is deliberate: a
``StateStore`` must be able to round-trip them to disk as JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StopReason(str, Enum):
    """Why a loop terminated. Every finished loop has exactly one."""

    GOAL_MET = "goal_met"  # Goal.is_satisfied() returned True
    MAX_ITERS = "max_iters"  # iteration cap reached
    BUDGET_EXHAUSTED = "budget_exhausted"  # token/cost ceiling hit
    DRY = "dry"  # N consecutive rounds found no new work (loop-until-dry)
    ABORTED = "aborted"  # kill switch / human-on-the-loop intervention


@dataclass(frozen=True)
class WorkItem:
    """One unit of work a ``WorkSource`` discovered.

    ``id`` must be stable across iterations so the runtime can record it in
    ``LoopState.done_ids`` and avoid re-doing work after a restart.
    """

    id: str
    kind: str  # e.g. "failing_test", "open_todo", "stale_file"
    payload: dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None  # which WorkSource emitted it


@dataclass(frozen=True)
class ActionResult:
    """What an ``Actor`` did for one ``WorkItem``."""

    changed: bool  # did the workspace actually change?
    summary: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)  # diffs, paths, ids
    cost_tokens: int = 0  # contribution to the loop budget


@dataclass(frozen=True)
class SensorResult:
    """A verdict from one ``Sensor``. ``evidence`` is required on failure.

    A loop never treats an action as progress without a passing SensorResult.
    The ``evidence`` field exists so failures are reported faithfully (test
    output, linter message) rather than as a bare boolean.
    """

    sensor: str  # the sensor's name
    passed: bool
    evidence: str = ""  # raw output backing the verdict; mandatory if not passed
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationRecord:
    """An immutable log entry for one pass through the loop.

    The runtime appends one of these per iteration. ``timestamp`` is supplied
    by the runtime (an ISO-8601 string); the contracts never read the clock
    themselves, which keeps loops deterministic and replayable.
    """

    iteration: int
    work_item: WorkItem
    action: ActionResult
    sensor: SensorResult
    timestamp: str


@dataclass
class LoopState:
    """The complete, restartable state of a running loop.

    A ``StateStore`` persists this so a loop survives a crash or pause and
    resumes without redoing finished work. Everything a loop needs to continue
    lives here, not in any conversation or process memory.
    """

    goal_id: str
    iteration: int = 0
    done_ids: set[str] = field(default_factory=set)
    cost_tokens: int = 0
    status: str = "running"  # running | stopped
    stop_reason: Optional[StopReason] = None
    history: list[IterationRecord] = field(default_factory=list)


@dataclass(frozen=True)
class StopDecision:
    """Returned by a ``StopCondition``. ``reason`` is set iff ``stop`` is True."""

    stop: bool
    reason: Optional[StopReason] = None
    note: str = ""


@dataclass
class Context:
    """Everything a contract method needs about the current run.

    Passed to every contract call. Read-only by convention except for the
    runtime, which owns ``state``. Contracts read ``state`` to make decisions
    (e.g. a ``WorkSource`` skips ``done_ids``) but must not mutate it.
    """

    workspace: str  # absolute path the loop operates on
    state: LoopState
    budget_tokens: Optional[int] = None  # None means unbounded
    extras: dict[str, Any] = field(default_factory=dict)
