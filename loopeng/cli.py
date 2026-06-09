"""Command-line entry point: ``loopeng run|resume <spec>``.

    loopeng run    <spec.loop.yaml> [--workspace .]   # fresh start (clears state)
    loopeng resume <spec.loop.yaml> [--workspace .]   # continue from saved state
"""

from __future__ import annotations

import argparse
import sys

from .spec import build_runner, load_spec


def _run(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    runner = build_runner(spec, args.workspace)
    if args.command == "run":
        runner.state_store.reset()  # fresh; `resume` skips this
    result = runner.run()
    print(f"loop:        {result.goal_id}")
    print(f"stopped:     {result.stop_reason.value}")
    print(f"iterations:  {result.iterations}")
    print(f"done items:  {len(result.done)} {result.done}")
    print(f"cost tokens: {result.cost_tokens}")
    return 0 if result.stop_reason.value in ("goal_met", "dry") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="loopeng", description="Run a loop-engineering loop.")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd, help_ in (("run", "fresh start"), ("resume", "continue from saved state")):
        p = sub.add_parser(cmd, help=help_)
        p.add_argument("spec", help="path to a *.loop.yaml spec")
        p.add_argument("--workspace", default=".", help="dir the loop operates on (default: .)")
        p.set_defaults(func=_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
