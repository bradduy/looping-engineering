"""A JSON-file StateStore: the default "remember" backend.

Persists the full ``LoopState`` to one JSON file (atomic write) and appends an
``IterationRecord`` trace to a sibling ``.trace.jsonl``. This is what makes a
loop restartable: a crash or pause loses nothing already saved.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Optional

from .contracts import StateStore
from .types import (
    ActionResult,
    Context,
    IterationRecord,
    LoopState,
    SensorResult,
    StopReason,
    WorkItem,
)


def _state_to_dict(s: LoopState) -> dict[str, Any]:
    return {
        "goal_id": s.goal_id,
        "iteration": s.iteration,
        "done_ids": sorted(s.done_ids),
        "cost_tokens": s.cost_tokens,
        "status": s.status,
        "stop_reason": s.stop_reason.value if s.stop_reason else None,
        "history": [_record_to_dict(r) for r in s.history],
    }


def _record_to_dict(r: IterationRecord) -> dict[str, Any]:
    return {
        "iteration": r.iteration,
        "work_item": dataclasses.asdict(r.work_item),
        "action": dataclasses.asdict(r.action),
        "sensor": dataclasses.asdict(r.sensor),
        "timestamp": r.timestamp,
    }


def _record_from_dict(d: dict[str, Any]) -> IterationRecord:
    return IterationRecord(
        iteration=d["iteration"],
        work_item=WorkItem(**d["work_item"]),
        action=ActionResult(**d["action"]),
        sensor=SensorResult(**d["sensor"]),
        timestamp=d["timestamp"],
    )


def _state_from_dict(d: dict[str, Any]) -> LoopState:
    return LoopState(
        goal_id=d["goal_id"],
        iteration=d.get("iteration", 0),
        done_ids=set(d.get("done_ids", [])),
        cost_tokens=d.get("cost_tokens", 0),
        status=d.get("status", "running"),
        stop_reason=StopReason(d["stop_reason"]) if d.get("stop_reason") else None,
        history=[_record_from_dict(r) for r in d.get("history", [])],
    )


class JsonStateStore(StateStore):
    def __init__(
        self,
        state_path: str,
        goal_id: str,
        workspace: str,
        budget_tokens: Optional[int] = None,
    ):
        self.state_path = state_path
        self.trace_path = state_path + ".trace.jsonl"
        self.goal_id = goal_id
        self.workspace = workspace
        self.budget_tokens = budget_tokens

    def load(self) -> Context:
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                state = _state_from_dict(json.load(f))
        else:
            state = LoopState(goal_id=self.goal_id)
        return Context(
            workspace=self.workspace,
            state=state,
            budget_tokens=self.budget_tokens,
        )

    def save(self, ctx: Context) -> None:
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_state_to_dict(ctx.state), f, indent=2)
        os.replace(tmp, self.state_path)  # atomic

    def record(self, record: IterationRecord) -> None:
        os.makedirs(os.path.dirname(self.trace_path) or ".", exist_ok=True)
        with open(self.trace_path, "a") as f:
            f.write(json.dumps(_record_to_dict(record)) + "\n")

    def reset(self) -> None:
        """Delete persisted state + trace for a fresh `run` (vs. `resume`)."""
        for p in (self.state_path, self.trace_path):
            if os.path.exists(p):
                os.remove(p)
