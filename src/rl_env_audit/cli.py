"""Command line entry point.

    rl-env-audit hub --envs owner/name ... --out results/      audit Hub environments in isolated venvs
    rl-env-audit report results/ --out REPORT.md               summary table and certificates
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"hub", "report"}:
        print(__doc__)
        return 2
    cmd = sys.argv.pop(1)
    if cmd == "hub":
        from rl_env_audit.hub import main as run
    else:
        from rl_env_audit.report import main as run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
