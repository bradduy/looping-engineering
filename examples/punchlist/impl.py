"""A deterministic, no-LLM reference loop: clear a punch list.

Proves the six contracts compose end to end without a model in the loop:
a JSON file of items is the workspace; the loop marks each item done, verifies
it on disk, and stops when the Goal (all done) is satisfied. Because it is
deterministic it doubles as the framework's integration fixture.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from loopeng import (
    ActionResult,
    Actor,
    Context,
    Goal,
    Sensor,
    SensorResult,
    WorkItem,
    WorkSource,
)


def _abs(ctx: Context, rel: str) -> str:
    return rel if os.path.isabs(rel) else os.path.join(ctx.workspace, rel)


def _load(path: str, seed: list[str]) -> dict[str, Any]:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"items": [{"id": i, "done": False} for i in seed]}


def _save(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class _Base:
    def __init__(self, path: str = "punchlist.json", seed: Optional[list[str]] = None):
        self.path = path
        self.seed = seed or []


class PunchlistClear(_Base, Goal):
    def describe(self) -> str:
        return f"every item in {self.path} is done"

    def is_satisfied(self, ctx: Context) -> bool:
        data = _load(_abs(ctx, self.path), self.seed)
        return bool(data["items"]) and all(it["done"] for it in data["items"])


class OpenItems(_Base, WorkSource):
    def find(self, ctx: Context) -> list[WorkItem]:
        path = _abs(ctx, self.path)
        data = _load(path, self.seed)
        if not os.path.exists(path):
            _save(path, data)  # materialize the seed on first run
        return [
            WorkItem(id=it["id"], kind="punch_item", source="OpenItems")
            for it in data["items"]
            if not it["done"]
        ]


class MarkDone(_Base, Actor):
    def act(self, item: WorkItem, ctx: Context) -> ActionResult:
        path = _abs(ctx, self.path)
        data = _load(path, self.seed)
        for it in data["items"]:
            if it["id"] == item.id:
                it["done"] = True
        _save(path, data)
        return ActionResult(changed=True, summary=f"marked {item.id} done", cost_tokens=10)


class ItemIsDone(_Base, Sensor):
    name = "item_is_done"

    def verify(self, item: WorkItem, action: ActionResult, ctx: Context) -> SensorResult:
        data = _load(_abs(ctx, self.path), self.seed)
        ok = any(it["id"] == item.id and it["done"] for it in data["items"])
        return SensorResult(
            sensor=self.name,
            passed=ok,
            evidence="" if ok else f"item {item.id} is not done on disk",
        )
