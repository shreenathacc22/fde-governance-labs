"""Ship a release, roll it back, or switch off one tool.

    python release.py status
    python release.py deploy v2
    python release.py rollback
    python release.py disable issue_refund     kill switch: this tool stops working, nothing is redeployed
    python release.py enable issue_refund
    python release.py reset                    forget every deploy; v1 goes live again

Works while chat.py is running in another terminal: the agent re-reads the live
release every turn and the kill switch on every tool call.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from bankagent.app import open_releases
from bankagent.config import KillSwitchUnavailable, RollbackUnavailable
from bankagent.controls.rollback import ReleaseHistory
from bankagent.settings import ROOT, STATE_DIR, Controls

# Lab 4 (your turn): the ceiling risk and compliance signed for a refund the
# agent may issue. tests/test_your_turn.py checks every candidate release
# against it, and deploy refuses a release whose tests fail.
REFUND_CEILING_DOLLARS = 100


def preflight(version: str) -> tuple[bool, str]:
    """Run the test suite with `version` as the first release deployed into the
    tests' own temporary state. Returns (passed, output). Nothing live changes."""
    env = {**os.environ, "BANKAGENT_PREFLIGHT": "1"}      # the inner run skips the tests that call preflight()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--controls=on",
         "--candidate", version, str(ROOT / "tests")],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=120,
    )
    return proc.returncode == 0, proc.stdout + proc.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy, roll back, and switch tools on or off.")
    parser.add_argument("--controls", choices=["file", "on", "off"], default="file",
                        help="file: read controls.toml (default); on/off: force every control")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="what is live, and what happened before")
    deploy = commands.add_parser("deploy", help="make a release live (runs the tests against it first)")
    deploy.add_argument("version")
    deploy.add_argument("--skip-tests", action="store_true", help="deploy even if the tests fail (logged)")
    commands.add_parser("rollback", help="go back to the previous release")
    commands.add_parser("disable", help="kill switch: turn one tool off").add_argument("tool")
    commands.add_parser("enable", help="turn a tool back on").add_argument("tool")
    commands.add_parser("reset", help="forget every deploy and start the lab over")
    args = parser.parse_args(argv)

    if args.command == "reset":
        for name in ("live_config.json", "release_history.json"):
            (STATE_DIR / name).unlink(missing_ok=True)
        print("Cleared. v1 goes live the next time anything runs.")
        return 0

    releases = open_releases(Controls.load(args.controls))
    before = releases.live()
    try:
        if args.command == "status":
            print_status(releases)
        elif args.command == "deploy":
            if not args.skip_tests:
                print(f"Running the tests against {args.version} before it goes live …")
                ok, output = preflight(args.version)
                if not ok:
                    summary = [l for l in output.splitlines() if l.startswith(("FAILED", "ERROR")) or "failed" in l][-6:]
                    print(f"Refused: the tests fail against {args.version}. Live release is still {before.version}.", file=sys.stderr)
                    print("\n".join("  " + l for l in summary), file=sys.stderr)
                    return 1
                print("  tests pass.")
            live = releases.deploy(args.version)
            print(f"Deployed. Live release: {live.version} (hash {live.hash})")
        elif args.command == "rollback":
            live = releases.rollback()
            print(f"Rolled back {before.version} -> {live.version}. Live release: {live.version} (hash {live.hash})")
        elif args.command == "disable":
            releases.disable(args.tool)
            print(f"{args.tool} is switched off. Nothing was redeployed; live release is still {before.version}.")
        elif args.command == "enable":
            releases.enable(args.tool)
            print(f"{args.tool} is switched back on.")
    except (RollbackUnavailable, KillSwitchUnavailable, ValueError) as e:
        print(f"Can't {args.command}: {e}", file=sys.stderr)
        return 1
    return 0


def print_status(releases) -> None:
    live = releases.live()
    print(f"Live release:  {live.version} (hash {live.hash})")
    if not isinstance(releases, ReleaseHistory):
        print("History:       none kept. The starter overwrites the live config in place.")
        print("Kill switch:   not available in the starter.")
        return
    print(f"History:       {' -> '.join(releases.history())}")
    disabled = sorted(releases.disabled_tools())
    print(f"Kill switch:   {', '.join(disabled) + ' switched off' if disabled else 'every tool on'}")
    print("Log:")
    for entry in releases.log():
        print(f"  {entry['at']}  {entry['by']:<10} {entry['action']:<9} {entry['detail']}")


if __name__ == "__main__":
    raise SystemExit(main())
