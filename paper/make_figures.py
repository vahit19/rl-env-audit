"""Figures for the paper, from the scan report and the fix checks.

    uv run --with matplotlib python paper/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rl_env_audit.stats import upper_bound  # noqa: E402

OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False})

PASS, FAIL, GREY, BLUE, RED = "#15803D", "#DC2626", "#9CA3AF", "#1D4ED8", "#DC2626"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)


def scan_outcomes():
    rows = json.loads((ROOT / "scans" / "2026-10-13-prime-hub.json").read_text(encoding="utf-8"))
    audited = [r for r in rows if r["status"] == "audited"]
    failed = sum(1 for r in audited if any(c.get("paid", 0) for c in r.get("checks", {}).values()))
    status = {}
    for r in rows:
        if r["status"] != "audited":
            status[r["status"]] = status.get(r["status"], 0) + 1
    labels = {
        "error": "could not be loaded or scored offline",
        "no_paid_format": "no single reference answer the reward checks",
        "no_tasks": "tasks carry no reference answer",
        "install_error": "could not be installed",
        "unsupported_api": "interim verifiers API",
    }
    bars = [("passed every check", len(audited) - failed, PASS), ("paid a check without a correct answer", failed, FAIL)]
    bars += [(labels.get(k, k), v, GREY) for k, v in sorted(status.items(), key=lambda kv: -kv[1])]
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    ys = list(range(len(bars)))[::-1]
    ax.barh(ys, [b[1] for b in bars], color=[b[2] for b in bars], height=0.62)
    for y, (_, v, _) in zip(ys, bars):
        ax.text(v + 0.3, y, str(v), va="center")
    ax.set_yticks(ys, [b[0] for b in bars])
    ax.axhline(len(bars) - 2.5, color="black", lw=0.6, ls=":")
    ax.set_xlim(0, 25)
    ax.text(24.5, len(bars) - 1.5, f"audited: {len(audited)}", ha="right", va="center", fontsize=8)
    ax.text(24.5, 1.5, f"not auditable: {len(rows) - len(audited)}", ha="right", va="center",
            fontsize=8, color="#4B5563")
    ax.set_xlabel("environments")
    save(fig, "fig2_scan_outcomes")
    return len(rows), len(audited), failed


def fixes():
    f = json.loads((ROOT / "scans" / "2026-10-14-fixes.json").read_text(encoding="utf-8"))
    A, B = f["Environment A"], f["Environment B"]
    h = A["honest_phrasings"]
    items = [(f"A: {c}", A["before"][c], A["after"][c]) for c in ("hedge_or", "candidate_list")]
    items.append(("B: echo_prompt", B["before"]["echo_prompt"], B["after"]["echo_prompt"]))
    items.append(("A: honest phrasings", {"paid": h["paid_before"], "tested": h["replies"]},
                  {"paid": h["paid_after"], "tested": h["replies"]}))
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    w = 0.38
    for i, (name, x0, x1) in enumerate(items):
        for dx, x, c, lab in ((-w / 2, x0, RED if i < 3 else GREY, "original grader"), (w / 2, x1, BLUE, "fixed grader")):
            ax.bar(i + dx, 100 * x["paid"] / x["tested"], w, color=c, label=lab if i == 0 else None)
            ax.text(i + dx, 100 * x["paid"] / x["tested"] + 2, f"{x['paid']}/\n{x['tested']}", ha="center",
                    fontsize=6.5, linespacing=0.9)
    ax.set_xticks(range(len(items)), [i[0] for i in items])
    ax.set_ylabel("% of replies paid in full")
    ax.set_ylim(0, 125)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.axvline(2.5, color="black", lw=0.6, ls=":")
    ax.legend(frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.4, 1.12))
    save(fig, "fig3_fixes")
    return items


def policies():
    p = json.loads((ROOT / "scans" / "2026-10-14-fixes.json").read_text(encoding="utf-8"))["Environment A"]["no_tracking_policies"]
    fams = ["family 1", "family 2", "family 3"]
    series = [
        ("best single stated value", lambda d: max(d["first stated value | fixed"], d["last stated value | fixed"]),
         GREY),
        ("all values with 'or', original", lambda d: d["all stated values, joined by 'or' | original"], RED),
        ("all values with 'or', fixed", lambda d: d["all stated values, joined by 'or' | fixed"], BLUE),
        ("all values as a list, original", lambda d: d["all stated values, as a list | original"], "#F87171"),
        ("all values as a list, fixed", lambda d: d["all stated values, as a list | fixed"], "#60A5FA"),
    ]
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    w = 0.16
    for j, (name, f, c) in enumerate(series):
        xs = [i + (j - 2) * w for i in range(len(fams))]
        ys = [f(p[k]) for k in fams]
        ax.bar(xs, ys, w, color=c, label=name)
        for x, y in zip(xs, ys):
            ax.text(x, y + 0.02, f"{y:.2f}".replace("0.00", "0").replace("1.00", "1"), ha="center", fontsize=6)
    ax.set_xticks(range(len(fams)), [f"{k}\n({p[k]['tasks']} tasks)" for k in fams])
    ax.set_ylabel("mean reward")
    ax.set_ylim(0, 1.12)
    ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    save(fig, "fig4_policies")
    return p


def bound_curve():
    ns = list(range(10, 501))
    fig, ax = plt.subplots(figsize=(4.4, 2.4))
    ax.plot(ns, [100 * upper_bound(0, n) for n in ns], color=BLUE)
    for n in (30, 60, 299, 500):
        u = 100 * upper_bound(0, n)
        ax.plot([n], [u], "o", color=BLUE, ms=3)
        ax.annotate(f"n={n}: {u:.1f}%", (n, u), textcoords="offset points", xytext=(4, 6), fontsize=7)
    ax.set_xlabel("tasks checked, none paid (n)")
    ax.set_ylabel("95% upper bound on rate (%)")
    ax.set_ylim(0, 27)
    save(fig, "fig5_bound")


if __name__ == "__main__":
    print(scan_outcomes())
    print(fixes())
    policies()
    bound_curve()
    print(sorted(p.name for p in OUT.iterdir()))
