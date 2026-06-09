"""Load a ``*.loop.yaml`` spec and build a runnable LoopRunner from it.

Each component binds a contract to a Python class via a dotted ``uses`` path
plus constructor ``with`` args. The ``budget`` block is expanded into implicit
stop conditions (MaxIterations / TokenBudget) appended after the explicit ones.
"""

from __future__ import annotations

import importlib
import os
from typing import Any

from .runtime import LoopRunner
from .state import JsonStateStore
from .stops import MaxIterations, TokenBudget


class SpecError(ValueError):
    pass


_REQUIRED = ("name", "goal", "work_source", "actor", "sensors", "stop")


def load_spec(path: str) -> dict[str, Any]:
    try:
        import yaml  # lazy: only needed for the runtime, not the contracts
    except ImportError as e:  # pragma: no cover
        raise SpecError("PyYAML is required to load specs: pip install 'onloop[dev]'") from e
    with open(path) as f:
        spec = yaml.safe_load(f)
    _validate(spec)
    return spec


def _validate(spec: Any) -> None:
    if not isinstance(spec, dict):
        raise SpecError("spec must be a mapping")
    for key in _REQUIRED:
        if key not in spec:
            raise SpecError(f"spec missing required key: '{key}'")
    if not isinstance(spec["sensors"], list) or not spec["sensors"]:
        raise SpecError("'sensors' must be a non-empty list (a loop must check itself)")
    if not isinstance(spec["stop"], list) or not spec["stop"]:
        raise SpecError("'stop' must be a non-empty list (a loop must terminate)")


def import_path(dotted: str):
    module, _, name = dotted.rpartition(".")
    if not module:
        raise SpecError(f"'uses' must be a dotted path to a class, got: {dotted!r}")
    obj = importlib.import_module(module)
    return getattr(obj, name)


def _instantiate(component: dict[str, Any]):
    cls = import_path(component["uses"])
    return cls(**(component.get("with") or {}))


def build_runner(spec: dict[str, Any], workspace: str) -> LoopRunner:
    workspace = os.path.abspath(workspace)
    budget = spec.get("budget") or {}
    max_tokens = budget.get("max_tokens")

    if spec.get("state_store"):
        raise SpecError(
            "custom state_store is not supported yet; omit it to use JsonStateStore"
        )
    store = JsonStateStore(
        state_path=os.path.join(workspace, "state", spec["name"] + ".json"),
        goal_id=spec["name"],
        workspace=workspace,
        budget_tokens=max_tokens,
    )

    stops = [_instantiate(s) for s in spec["stop"]]
    # Expand the budget block into implicit, always-on bounds.
    if budget.get("max_iters") is not None:
        stops.append(MaxIterations(budget["max_iters"]))
    if max_tokens is not None:
        stops.append(TokenBudget(max_tokens))

    return LoopRunner(
        goal=_instantiate(spec["goal"]),
        work_source=_instantiate(spec["work_source"]),
        actor=_instantiate(spec["actor"]),
        sensors=[_instantiate(s) for s in spec["sensors"]],
        stops=stops,
        state_store=store,
    )
