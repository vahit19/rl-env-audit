"""Audit environments from the Prime Intellect Environments Hub, each in its own virtualenv.

Each environment is third-party code, so it is installed into a fresh virtualenv and run in a
subprocess with a wall-clock limit; one broken environment cannot stop the scan.

    python -m rl_env_audit.hub --envs owner/name owner/name ... --out results/
    python -m rl_env_audit.hub --list hub.json --tag single-turn --top 50 --out results/
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

INDEX = "https://hub.primeintellect.ai/{owner}/{name}/install/simple/"
TOOL = Path(__file__).resolve().parents[2]


def sh(cmd: list[str], timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          env={**os.environ, "UV_NO_PROGRESS": "1"})


def package_name(env: str) -> str:
    return env.split("/", 1)[1].split("@", 1)[0]


def install(uv: str, py: str, args: list[str], tries: int = 4) -> subprocess.CompletedProcess:
    """uv pip install with back-off: the hub's package index rate-limits bursts (HTTP 429)."""
    for attempt in range(tries):
        r = sh([uv, "pip", "install", "-q", "--python", py, *args], 900)
        limited = "429" in r.stderr or "403" in r.stderr  # the index answers bursts with 429, then 403
        if r.returncode == 0 or not limited or attempt == tries - 1:
            return r
        time.sleep(60 * (attempt + 1))
    return r


DETECT = """
import sys
from rl_env_audit.adapters.common import source_text
src = source_text(sys.argv[1])
if "verifiers.v1" in src:
    print("v1")
elif "load_environment" in src:
    print("legacy")
else:
    print("interim")
"""


def detect(py: str, dist: str) -> str:
    """Which verifiers API an environment is written against, read from its source without importing it."""
    r = sh([py, "-c", DETECT, dist], 120)
    return r.stdout.strip() or "unknown"


def audit_one(env: str, work: Path, out: Path, n: int, uv: str) -> dict:
    owner, name = env.split("/", 1)
    slug = env.replace("/", "__")
    venv = work / slug
    res_file = out / f"{slug}.json"
    log = {"env": env}
    try:
        if venv.exists():
            shutil.rmtree(venv)
        sh([uv, "venv", "-q", "--python", "3.12", str(venv)], 300)
        py = str(venv / "bin" / "python")
        index = ["--extra-index-url", INDEX.format(owner=owner, name=name)]
        r = install(uv, py, [package_name(env), "datasets", *index, "-e", str(TOOL)])
        if r.returncode != 0:
            log.update(status="install_error", notes=[r.stderr.strip()[-600:]])
            res_file.write_text(json.dumps(log, indent=1))
            return log
        flavor = detect(py, package_name(env))
        if flavor == "legacy":  # verifiers 0.4 dropped the legacy API from the package root
            r = install(uv, py, ["verifiers<0.4", *index])
            if r.returncode != 0:
                log.update(status="install_error", notes=[r.stderr.strip()[-600:]])
                res_file.write_text(json.dumps(log, indent=1))
                return log
        elif flavor != "v1":
            log.update(status="unsupported_api", notes=[f"written against an interim verifiers API ({flavor})"])
            res_file.write_text(json.dumps(log, indent=1))
            return log
        adapter = "rl_env_audit.adapters.verifiers_legacy" if flavor == "legacy" else "rl_env_audit.adapters.verifiers_v1"
        r = sh([py, "-m", adapter, package_name(env), "--label", env, "--n", str(n), "--out", str(res_file)],
               1800, cwd=work)
        if not res_file.exists():
            log.update(status="run_error", notes=[(r.stderr or r.stdout).strip()[-800:]])
            res_file.write_text(json.dumps(log, indent=1))
            return log
        return json.loads(res_file.read_text())
    except subprocess.TimeoutExpired as e:
        log.update(status="timeout", notes=[str(e)[:200]])
        res_file.write_text(json.dumps(log, indent=1))
        return log
    finally:
        shutil.rmtree(venv, ignore_errors=True)  # keep the disk clean between environments


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", nargs="*", default=[])
    ap.add_argument("--list", help="JSON from `prime env list --output json` (one page or a list of pages)")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", default="results")
    ap.add_argument("--work", default="/tmp/rl-env-audit")
    ap.add_argument("--uv", default=shutil.which("uv") or os.path.expanduser("~/.local/bin/uv"))
    a = ap.parse_args()
    envs = list(a.envs)
    if a.list:
        rows = json.loads(Path(a.list).read_text())
        rows = rows["environments"] if isinstance(rows, dict) else rows
        if a.tag:
            rows = [r for r in rows if a.tag in (r.get("tags") or [])]
        seen = set(envs)
        for r in sorted(rows, key=lambda r: -int(r.get("stars") or 0)):
            if r["environment"] not in seen:
                envs.append(r["environment"])
                seen.add(r["environment"])
        envs = envs[: a.top]
    out, work = Path(a.out), Path(a.work)
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(a.jobs) as pool:
        for rep in pool.map(lambda e: audit_one(e, work, out, a.n, a.uv), envs):
            print(json.dumps({k: rep.get(k) for k in ("env", "status", "template", "tasks_tested", "exploitable_probes")}),
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
