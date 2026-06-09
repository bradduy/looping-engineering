"""onloop: a contracts-first framework for loop engineering.

Import the contracts to build a concrete loop, the runtime to run one:

    from onloop import Goal, WorkSource, Actor, Sensor, StateStore, StopCondition
    from onloop import WorkItem, ActionResult, SensorResult, Context
    from onloop import LoopRunner, JsonStateStore, load_spec, build_runner

A loop is the composition of one implementation of each contract, declared in a
``*.loop.yaml`` spec validated against ``schema/loop.schema.json``.
"""

from __future__ import annotations

from .contracts import (
    Actor,
    Goal,
    Sensor,
    StateStore,
    StopCondition,
    WorkSource,
)
from .runtime import LoopResult, LoopRunner
from .spec import SpecError, build_runner, import_path, load_spec
from .state import JsonStateStore
from .stops import GoalMet, LoopUntilDry, MaxIterations, TokenBudget
from .types import (
    ActionResult,
    Context,
    IterationRecord,
    LoopState,
    SensorResult,
    StopDecision,
    StopReason,
    WorkItem,
)

__version__ = "0.0.1"

__all__ = [
    # contracts
    "Goal",
    "WorkSource",
    "Actor",
    "Sensor",
    "StateStore",
    "StopCondition",
    # types
    "WorkItem",
    "ActionResult",
    "SensorResult",
    "IterationRecord",
    "LoopState",
    "StopDecision",
    "StopReason",
    "Context",
    # runtime
    "LoopRunner",
    "LoopResult",
    "JsonStateStore",
    # standard stop conditions
    "GoalMet",
    "MaxIterations",
    "TokenBudget",
    "LoopUntilDry",
    # spec
    "load_spec",
    "build_runner",
    "import_path",
    "SpecError",
]
