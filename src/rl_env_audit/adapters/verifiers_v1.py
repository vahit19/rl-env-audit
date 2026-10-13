"""Adapter for environments built on verifiers v1 (`import verifiers.v1 as vf`).

Runs inside the environment's own virtualenv. The reward of a reply is computed by the task's
real `Task.score`, the code path a training run uses, on a trace whose final reply is the probe.
Signals that need a sandbox runtime are skipped by verifiers itself when no runtime is given.

    python -m rl_env_audit.adapters.verifiers_v1 DIST_NAME --label owner/name --n 30 --out report.json
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import sys
import time

from rl_env_audit.adapters.common import gold_from, import_name, with_retries, write_report


def prompt_of(data) -> str:
    try:
        return data.prompt_text
    except Exception:  # noqa: BLE001 - only used for the echo probe
        p = getattr(data, "prompt", "")
        return p if isinstance(p, str) else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dist")
    ap.add_argument("--label", default=None)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds per scoring call")
    a = ap.parse_args()
    label = a.label or a.dist

    from rl_env_audit.audit import TOTAL, EnvReport, TaskCase, audit

    t0 = time.time()
    calls = {"n": 0, "errors": 0, "last_error": None}
    try:
        import verifiers.v1 as vf
        from verifiers.v1.state import state_cls
        from verifiers.v1.trace import TraceTask
        from verifiers.v1.utils.generic import concrete_type
        from verifiers.v1.utils.loaders import taskset_class

        loop = asyncio.new_event_loop()

        def score(task, reply: str) -> dict[str, float]:
            trace = vf.Trace(
                task=TraceTask(type=type(task).__name__, data=task.data, key=task.key, hash=task.hash),
                state=state_cls(type(task))(),
                agent=vf.AgentInfo(config=vf.AgentConfig(), name="rl-env-audit", trainable=False),
            )
            trace.root_reply = reply
            calls["n"] += 1
            try:
                loop.run_until_complete(asyncio.wait_for(task.score(trace, None), a.timeout))
            except Exception as e:  # noqa: BLE001 - a grader that crashes pays nothing
                calls["errors"] += 1
                calls["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                return {TOTAL: 0.0}
            parts = {name: float(r.value) for name, r in trace.rewards.items() if r is not None}
            return {**parts, TOTAL: float(trace.reward)}

        module = import_name(a.dist)
        cls = taskset_class(module)
        cfg_type = concrete_type(cls, vf.TasksetConfig) or vf.TasksetConfig
        ts = cls(cfg_type(id=module))
        tasks = with_retries(lambda: list(itertools.islice(iter(ts), a.n)))
        cases = [TaskCase(handle=t, gold=g, prompt=prompt_of(t.data)) for t in tasks if (g := gold_from(t.data))]
        if not cases:
            rep = EnvReport(label, "no_tasks", notes=[f"{len(tasks)} tasks loaded, none with a reference answer field"])
        else:
            rep = audit(label, cases, score, n=a.n, instructions=str(getattr(ts, "system_prompt", "") or ""))
    except Exception as e:  # noqa: BLE001 - one broken environment must not stop a hub scan
        rep = EnvReport(label, "error", notes=[f"{type(e).__name__}: {str(e)[:300]}"])
    write_report(rep, a.out, "verifiers.v1", calls, t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
