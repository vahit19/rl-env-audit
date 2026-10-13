"""Turn per-environment JSON results into a summary table and per-environment certificates.

    python -m rl_env_audit.report results/ --out REPORT.md
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from rl_env_audit.stats import upper_bound

STATUS_TEXT = {
    "audited": "audited",
    "no_paid_format": "no reliable correctness signal found",
    "no_tasks": "no tasks with a reference answer",
    "error": "failed to load or score",
    "install_error": "failed to install",
    "unsupported_api": "written against an interim verifiers API",
    "timeout": "timed out",
    "run_error": "crashed",
}


def load(results: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(results.glob("*.json"))]


def certificate(r: dict) -> str:
    """One paragraph a vendor can publish next to an environment."""
    n = r.get("tasks_tested", 0)
    bad = [p for p in r.get("probes", []) if p["paid"] > 0]
    if bad:
        names = ", ".join(f"{p['probe']} ({p['paid']}/{p['tested']})" for p in bad)
        return f"NOT PASSED. Paid without a correct answer: {names}."
    worst = max((p["tested"] for p in r.get("probes", [])), default=0)
    return (f"PASSED on {n} tasks: none of {len(r.get('probes', []))} checks was paid. With 95% confidence each "
            f"check is paid on fewer than {100 * upper_bound(0, worst):.1f}% of tasks (exact binomial bound).")


def summary(rows: list[dict]) -> str:
    counts = collections.Counter(r.get("status") for r in rows)
    audited = [r for r in rows if r.get("status") == "audited"]
    holed = [r for r in audited if any(p["paid"] > 0 for p in r.get("probes", []))]
    lines = [
        "| Environment | Status | Reply format | Tasks | Checks paid in full without a correct answer | Partial credit for two guesses |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r.get("status") != "audited", r.get("env", ""))):
        paid = ", ".join(f"{p['probe']} {p['paid']}/{p['tested']}" for p in r.get("probes", []) if p["paid"] > 0)
        part = ", ".join(f"{p['probe']} {p['partial']}/{p['tested']}" for p in r.get("probes", []) if p.get("partial"))
        if r.get("status") == "audited":
            paid, part = paid or "none", part or "none"
        lines.append(f"| {r.get('env')} | {STATUS_TEXT.get(r.get('status'), r.get('status'))} | "
                     f"{r.get('template') or ''} | {r.get('tasks_tested') or ''} | {paid} | {part} |")
    head = (f"{len(rows)} environments: {counts.get('audited', 0)} audited, {len(holed)} of them paid at least one "
            f"check without a correct answer.")
    return head + "\n\n" + "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = load(Path(a.results))
    text = summary(rows) + "\n\n## Certificates\n\n" + "\n".join(
        f"- **{r['env']}**: {certificate(r)}" for r in rows if r.get("status") == "audited")
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
