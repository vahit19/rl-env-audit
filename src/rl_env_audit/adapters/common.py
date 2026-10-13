"""Helpers shared by the framework adapters (no framework imports here)."""

from __future__ import annotations

import importlib.metadata as md
import json
import time

GOLD_FIELDS = ("answer", "target", "solution", "label", "gold", "reference", "expected")


def gold_from(obj) -> str | None:
    """The reference answer of a task, from an attribute or a mapping key."""
    for f in GOLD_FIELDS:
        v = obj.get(f) if isinstance(obj, dict) else getattr(obj, f, None)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
            return str(v).strip()
    return None


def import_name(dist: str) -> str:
    """The top-level module an installed distribution provides (`openmed-medqa` -> `openmed_medqa`)."""
    try:
        d = md.distribution(dist)
    except md.PackageNotFoundError:
        return dist.replace("-", "_")
    top = d.read_text("top_level.txt")
    if top and top.split():
        return top.split()[0]
    for f in d.files or []:
        parts = str(f).split("/")
        if parts[0].endswith(".dist-info") or parts[0].startswith("__"):
            continue
        if parts[0].endswith(".py"):
            return parts[0][:-3]
        if len(parts) > 1:
            return parts[0]
    return dist.replace("-", "_")


def source_text(dist: str) -> str:
    """Concatenated Python source of an installed distribution, read without importing it."""
    try:
        d = md.distribution(dist)
    except md.PackageNotFoundError:
        return ""
    out = []
    for f in d.files or []:
        if str(f).endswith(".py") and ".dist-info" not in str(f):
            try:
                out.append(f.read_text())
            except Exception:  # noqa: BLE001
                pass
    return "\n".join(out)


def with_retries(fn, tries: int = 5, wait: float = 20.0):
    """Call fn, backing off on rate limits from dataset hosts (HTTP 429)."""
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if "429" not in str(e) or attempt == tries - 1:
                raise
            time.sleep(wait * (attempt + 1))


def write_report(rep, out: str, framework: str, calls: dict, t0: float) -> None:
    d = rep.to_dict()
    d["framework"] = framework
    d["score_calls"], d["score_errors"], d["last_score_error"] = calls["n"], calls["errors"], calls["last_error"]
    d["seconds"] = round(time.time() - t0, 1)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    print(json.dumps({k: d[k] for k in ("env", "status", "template", "tasks_tested", "exploitable_probes")}))
