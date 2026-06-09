"""Standard stop conditions.

Each enforces "termination is explicit." Conditions are stateless readers of
``Context``: the runtime maintains the fields/extras they inspect (iteration,
cost_tokens, empty_rounds, and the goal). A loop stops on the first condition
that fires, recording the matching StopReason.
"""

from __future__ import annotations

from .contracts import StopCondition
from .types import Context, StopDecision, StopReason


class GoalMet(StopCondition):
    """Stop when the loop's Goal reports satisfied.

    The runtime injects the active Goal as ``ctx.extras['goal']`` so this
    condition needs no constructor args (it appears bare in specs).
    """

    def should_stop(self, ctx: Context) -> StopDecision:
        goal = ctx.extras.get("goal")
        if goal is not None and goal.is_satisfied(ctx):
            return StopDecision(True, StopReason.GOAL_MET, "goal satisfied")
        return StopDecision(False)


class MaxIterations(StopCondition):
    """Stop after a fixed number of loop passes (including empty rounds)."""

    def __init__(self, max_iters: int):
        if max_iters < 1:
            raise ValueError("max_iters must be >= 1")
        self.max_iters = max_iters

    def should_stop(self, ctx: Context) -> StopDecision:
        if ctx.state.iteration >= self.max_iters:
            return StopDecision(
                True, StopReason.MAX_ITERS, f"reached {self.max_iters} iterations"
            )
        return StopDecision(False)


class TokenBudget(StopCondition):
    """Stop once accumulated token cost reaches a ceiling."""

    def __init__(self, max_tokens: int):
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        self.max_tokens = max_tokens

    def should_stop(self, ctx: Context) -> StopDecision:
        if ctx.state.cost_tokens >= self.max_tokens:
            return StopDecision(
                True,
                StopReason.BUDGET_EXHAUSTED,
                f"spent {ctx.state.cost_tokens} >= {self.max_tokens} tokens",
            )
        return StopDecision(False)


class LoopUntilDry(StopCondition):
    """Stop after N consecutive rounds that discovered no new work.

    Reads ``ctx.extras['empty_rounds']``, which the runtime increments on every
    pass where ``WorkSource.find`` yields nothing new and resets otherwise.
    """

    def __init__(self, empty_rounds: int = 2):
        if empty_rounds < 1:
            raise ValueError("empty_rounds must be >= 1")
        self.threshold = empty_rounds

    def should_stop(self, ctx: Context) -> StopDecision:
        if ctx.extras.get("empty_rounds", 0) >= self.threshold:
            return StopDecision(
                True, StopReason.DRY, f"{self.threshold} empty rounds"
            )
        return StopDecision(False)
