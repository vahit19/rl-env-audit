"""Adapter for environments built on the legacy verifiers API (`load_environment()` returning a
`vf.Environment` with a `Rubric`), run with `verifiers<0.4`.

The reward of a reply is the environment's own `rubric.score_rollout(state)` on a state built
from the dataset row, with the probe as the assistant's completion.

    python -m rl_env_audit.adapters.verifiers_legacy DIST_NAME --label owner/name --n 30 --out report.json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
import time

from rl_env_audit.adapters.common import gold_from, import_name, with_retries, write_report


def prompt_text(row: dict) -> str:
    p = row.get("prompt") or row.get("question") or ""
    if isinstance(p, list):
        return "\n".join(str(m.get("content", "")) for m in p if isinstance(m, dict) and m.get("role") == "user")
    return str(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dist")
    ap.add_argument("--label", default=None)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=20.0)
    a = ap.parse_args()
    label = a.label or a.dist

    from rl_env_audit.audit import TOTAL, EnvReport, TaskCase, audit

    t0 = time.time()
    calls = {"n": 0, "errors": 0, "last_error": None}
    try:
        from verifiers.legacy.types import State

        mod = importlib.import_module(import_name(a.dist))
        env = with_retries(lambda: mod.load_environment())
        ds = getattr(env, "eval_dataset", None) or getattr(env, "dataset", None)
        if ds is None:
            raise RuntimeError("environment exposes no dataset")
        rows = [dict(ds[i]) for i in range(min(a.n, len(ds)))]
        loop = asyncio.new_event_loop()

        def score(row: dict, reply: str) -> dict[str, float]:
            state = State.for_task(row)
            state["completion"] = [{"role": "assistant", "content": reply}]
            calls["n"] += 1
            try:
                res = loop.run_until_complete(asyncio.wait_for(env.rubric.score_rollout(state), a.timeout))
            except Exception as e:  # noqa: BLE001
                calls["errors"] += 1
                calls["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                return {TOTAL: 0.0}
            total = getattr(res, "reward", None)
            if total is None:
                total = state.get("reward")
            metrics = getattr(res, "metrics", None) or state.get("metrics") or {}
            parts = {str(k): float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
            return {**parts, TOTAL: float(total or 0.0)}

        cases = [TaskCase(handle=r, gold=g, prompt=prompt_text(r)) for r in rows if (g := gold_from(r))]
        if not cases:
            rep = EnvReport(label, "no_tasks", notes=[f"{len(rows)} rows loaded, none with a reference answer field"])
        else:
            rep = audit(label, cases, score, n=a.n, instructions=str(getattr(env, "system_prompt", "") or ""))
    except Exception as e:  # noqa: BLE001
        rep = EnvReport(label, "error", notes=[f"{type(e).__name__}: {str(e)[:300]}"])
    write_report(rep, a.out, "verifiers.legacy", calls, t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
