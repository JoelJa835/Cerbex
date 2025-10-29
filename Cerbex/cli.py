#cli.py
import sys
import runpy
import argparse
from pathlib import Path

from Cerbex.hook_loader import install_hooks
from Cerbex.analysis import PerfAnalyzer, TypeExtractor, CustomDataFlowAnalyzer

__version__ = "0.1.0"

ANALYSIS_MAP = {
    "perf": PerfAnalyzer,
    "types": TypeExtractor,
    "dataflow": CustomDataFlowAnalyzer,
}


def main():
    parser = argparse.ArgumentParser(
        description="Learn or enforce module dependencies and hook enforcement"
    )
    parser.add_argument(
        "-v", "--version",
        action="version", version=__version__,
        help="Show the tool version"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["learn", "enforce"], required=True,
        help="Mode: 'learn' to generate events/deps/allowlist; 'enforce' to apply an existing allowlist"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to config.json defining hook targets"
    )
    parser.add_argument(
        "-a", "--analyses",
        nargs="*",
        choices=ANALYSIS_MAP.keys(),
        default=[],
        help="Analyses to run (only in learn mode): perf, types"
    )
    parser.add_argument(
        "-o", "--outdir",
        default=".",
        help="Directory to write analysis logs (learn mode)"
    )
    parser.add_argument(
        "--allowlist",
        default="allowlist.json",
        help="Path to allowlist.json (only in enforce mode, defaults to cwd/allowlist.json)"
    )
    parser.add_argument(
        "script",
        help="Target Python script to execute under hooks"
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the target script"
    )
    parser.add_argument("--no-log", action="store_true",
                    help="Disable in-memory event recording (imports/calls/returns)")

    args = parser.parse_args()
    outdir = Path(args.outdir)

    if args.mode == "learn":
        # Prepare output directory for analysis logs
        outdir.mkdir(parents=True, exist_ok=True)
        analyses = [ANALYSIS_MAP[name](outfile=str(outdir / f"{name}.log"))
                    for name in args.analyses]
        # Install hooks in learn mode; JSON reports are auto-written to cwd
        install_hooks(
            config_path=args.config,
            mode="learn",
            analyses=analyses,
            log_events=not args.no_log
        )

        # Execute the script under instrumentation
        sys.argv = [args.script] + (args.args or [])
        runpy.run_path(args.script, run_name="__main__")
        print(f"Learn mode complete. Logs in {outdir}, JSON reports (events.json, dependencies.json, allowlist.json) in current directory.")

    else:
        # Enforce mode: use existing allowlist to block disallowed calls
        install_hooks(
            config_path=args.config,
            mode="enforce",
            analyses=[],
            allowlist_path=args.allowlist,
            log_events=not args.no_log
        )

        # Execute the script under enforcement
        sys.argv = [args.script] + (args.args or [])
        runpy.run_path(args.script, run_name="__main__")

if __name__ == "__main__":
    main()
