"""Framework-agnostic audit: find the correctness signal, run the checks, decide violations.

`score(task, reply)` is the environment's own reward for `reply` on `task`, supplied by an
adapter: either a float, or a dict of named reward components (plus their weighted total under
`TOTAL`). Many environments add style, length or format terms to correctness; those terms move
with the wording of a reply, so judging a probe by the total would mistake style for payment.
The audit therefore picks the *correctness signal*: the (reply format, reward component) pair
that best separates the gold answer from a wrong one, and judges every probe on that signal.
Nothing here imports an RL framework, so the logic is unit-tested on toy graders.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Sequence, Union

from rl_env_audit.probes import TEMPLATES, build_checks, templates_from_text, wrong_answer
from rl_env_audit.stats import upper_bound

TOTAL = "__total__"
Scores = Union[float, Mapping[str, float]]
Score = Callable[[Any, str], Scores]

MIN_GAP = 0.25  # the correctness signal must pay gold at least this much more than wrong
MIN_AGREE = 0.8  # ...and must rank gold above wrong on this share of calibration tasks


@dataclass
class TaskCase:
    handle: Any  # whatever the adapter needs to score a reply
    gold: str
    prompt: str = ""


@dataclass
class ProbeResult:
    probe: str
    family: str
    description: str
    tested: int = 0
    paid: int = 0  # violations: see the module and probes docstrings
    full: int = 0  # paid as much as the correct reply
    partial: int = 0  # two-guess replies paid above halfway on both tasks, but not in full
    skipped: int = 0  # two-guess checks not run: no other task has the wrong value as its gold
    example: dict | None = None
    partial_example: dict | None = None

    @property
    def upper_95(self) -> float:
        return upper_bound(self.paid, self.tested)


@dataclass
class EnvReport:
    env: str
    status: str  # audited | no_paid_format | no_tasks | error | install_error | unsupported_api
    template: str | None = None
    signal: str | None = None
    signal_gap: float | None = None
    tasks_tested: int = 0
    tasks_skipped: int = 0
    probes: list[ProbeResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def exploitable(self) -> list[ProbeResult]:
        return [p for p in self.probes if p.paid > 0]

    def to_dict(self) -> dict:
        d = asdict(self)
        for p, raw in zip(self.probes, d["probes"]):
            raw["upper_95"] = round(p.upper_95, 4)
        d["exploitable_probes"] = [p.probe for p in self.exploitable]
        return d


def components(s: Scores) -> dict[str, float]:
    if isinstance(s, Mapping):
        out = {str(k): float(v) for k, v in s.items() if v is not None}
        return out or {TOTAL: 0.0}
    return {TOTAL: float(s)}


def low_quantile(xs: list[float], q: float = 0.2) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def choose_signal(cases: Sequence[TaskCase], score: Score, k: int = 6,
                  templates: Mapping[str, Callable[[str], str]] | None = None) -> tuple[str | None, str | None, float]:
    """The (format, component) pair whose margin of gold over wrong is most reliable: the largest
    low quantile of the per-task margins, among pairs that clear MIN_GAP and rank gold above wrong on
    at least MIN_AGREE of the tasks. A style term that happens to add to the total makes the total's
    margin noisier, so the pure correctness component wins; ties go to a named component."""
    golds = [c.gold for c in cases]
    best: tuple[str | None, str | None, float] = (None, None, 0.0)
    for name, t in (templates or TEMPLATES).items():
        gaps: dict[str, list[float]] = {}
        for c in cases[:k]:
            w = wrong_answer(c.gold, golds)
            if w is None:
                continue
            g, b = components(score(c.handle, t(c.gold))), components(score(c.handle, t(w)))
            for key in g.keys() & b.keys():
                gaps.setdefault(key, []).append(g[key] - b[key])
        for key, gs in gaps.items():
            low, agree = low_quantile(gs), sum(x > 1e-6 for x in gs) / len(gs)
            if statistics.mean(gs) < MIN_GAP or low < MIN_GAP or agree < MIN_AGREE:
                continue
            better = low > best[2] + 1e-9
            tie_named = abs(low - best[2]) <= 1e-9 and best[1] == TOTAL and key != TOTAL
            if better or tie_named:
                best = (name, key, low)
    return best


def audit(env: str, cases: Sequence[TaskCase], score: Score, n: int = 30, recheck: bool = True,
          instructions: str = "") -> EnvReport:
    """`instructions` is the environment's own system prompt or task instruction; reply formats it
    declares (custom answer tags) are tried before the generic ones."""
    if not cases:
        return EnvReport(env, "no_tasks")
    templates = {**templates_from_text(instructions or cases[0].prompt), **TEMPLATES}
    name, key, gap = choose_signal(cases, score, templates=templates)
    if name is None:
        return EnvReport(env, "no_paid_format",
                         notes=["no tried reply format gives a reward component that reliably pays gold over wrong"])
    t = templates[name]
    rep = EnvReport(env, "audited", template=name, signal=key, signal_gap=round(gap, 4))

    def sig(handle, reply: str) -> float:
        return components(score(handle, reply)).get(key, 0.0)

    golds = [c.gold.strip() for c in cases]
    by_gold: dict[str, TaskCase] = {}
    for c in cases:
        by_gold.setdefault(c.gold.strip(), c)
    controls: dict[tuple[int, str], tuple[float, float]] = {}

    def control(c: TaskCase, wrong: str) -> tuple[float, float]:
        """(reward of the gold answer, reward of `wrong`) on task c, in the chosen format."""
        k = (id(c), wrong)
        if k not in controls:
            controls[k] = (sig(c.handle, t(c.gold)), sig(c.handle, t(wrong)))
        return controls[k]

    def paid(c: TaskCase, reply: str, bar: float) -> float:
        s = sig(c.handle, reply)
        if s >= bar and recheck:  # a finding must reproduce before it counts
            s = min(s, sig(c.handle, reply))
        return s

    results: dict[str, ProbeResult] = {}
    for i, c in enumerate(cases[:n]):
        others = golds[i + 1:] + golds[:i]  # rotate so tasks borrow different wrong answers
        w = wrong_answer(c.gold, others)
        if w is None:
            rep.tasks_skipped += 1
            continue
        pay, base = control(c, w)
        if pay - base < MIN_GAP:  # this task's control failed: the signal does not separate gold from wrong
            rep.tasks_skipped += 1
            continue
        rep.tasks_tested += 1
        bar = base + 0.5 * (pay - base)
        other = by_gold.get(w)  # the task whose gold is w, for the cross-task checks
        o_pay = o_base = None
        if other is not None:
            o_pay, o_base = control(other, c.gold)
            if o_pay - o_base < MIN_GAP:
                other = None
        for chk in build_checks(t, c.gold, w, c.prompt):
            r = results.setdefault(chk.name, ProbeResult(chk.name, chk.family, chk.description))
            if not chk.cross_task:
                r.tested += 1
                s = paid(c, chk.reply, bar)
                if s >= bar:
                    r.paid += 1
                    r.full += s >= pay - 1e-9
                    r.example = r.example or {"gold": c.gold, "wrong": w, "reply": chk.reply[:400], "reward": s,
                                              "reward_correct": pay, "reward_wrong": base}
                continue
            if other is None:
                r.skipped += 1
                continue
            r.tested += 1
            o_bar = o_base + 0.5 * (o_pay - o_base)
            s1 = paid(c, chk.reply, bar)
            if s1 < bar:
                continue
            s2 = paid(other, chk.reply, o_bar)
            if s2 < o_bar:
                continue
            ex = {"reply": chk.reply[:400], "task_gold": c.gold, "reward_here": s1, "reward_correct_here": pay,
                  "other_task_gold": w, "reward_there": s2, "reward_correct_there": o_pay}
            if s1 >= pay - 1e-9 and s2 >= o_pay - 1e-9:  # paid in full whichever value is right
                r.paid += 1
                r.full += 1
                r.example = r.example or ex
            else:  # above halfway on both tasks but not full: partial credit
                r.partial += 1
                r.partial_example = r.partial_example or ex
    rep.probes = list(results.values())
    if rep.tasks_tested == 0:
        rep.status = "no_paid_format"
        rep.notes.append("the chosen signal separated gold from wrong on no audited task")
    return rep
