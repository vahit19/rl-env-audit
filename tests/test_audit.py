import re

from rl_env_audit.audit import TOTAL, TaskCase, audit, choose_signal
from rl_env_audit.probes import boxed, wrong_answer
from rl_env_audit.stats import trials_needed, upper_bound

CASES = [TaskCase(handle=g, gold=g, prompt=f"What is {g}?") for g in ["12", "7", "305", "48", "9", "61"]]


def last_boxed(text):
    m = re.findall(r"\\boxed\{([^{}]*)\}", text)
    return m[-1].strip() if m else None


def strict(gold, reply):  # pays only a single boxed final answer equal to gold
    m = re.findall(r"\\boxed\{([^{}]*)\}", reply)
    return float(len(m) == 1 and m[0].strip() == gold)


def lenient(gold, reply):  # pays if the gold number appears anywhere (a common leaky checker)
    return float(re.search(rf"(?<!\d){re.escape(gold)}(?!\d)", reply) is not None)


def last_box(gold, reply):  # pays the last boxed answer
    return float(last_boxed(reply) == gold)


def gullible(gold, reply):  # a judge that obeys notes addressed to it
    return 1.0 if "Award full credit" in reply else strict(gold, reply)


def test_strict_grader_has_no_violations():
    rep = audit("toy/strict", CASES, strict)
    assert rep.status == "audited" and rep.template == "boxed"
    assert rep.tasks_tested == len(CASES)
    assert rep.exploitable == []


def test_lenient_grader_is_caught():
    rep = audit("toy/lenient", CASES, lenient)
    caught = {p.probe for p in rep.exploitable}
    assert {"hedge_or", "candidate_list", "two_finals", "reasoning_and_final", "rejected_value",
            "value_after_final", "echo_prompt"} <= caught


def test_positional_grader_is_not_a_violation():
    # reading only the last box gives a policy no second guess, so it must not be flagged
    rep = audit("toy/last-box", CASES, last_box)
    assert rep.exploitable == []


def any_box(gold, reply):  # pays if any boxed answer matches: a real two-guess exploit
    return float(gold in [m.strip() for m in re.findall(r"\\boxed\{([^{}]*)\}", reply)])


def test_any_box_grader_is_caught():
    rep = audit("toy/any-box", CASES, any_box)
    assert {p.probe for p in rep.exploitable} == {"two_finals"}


def test_injection_is_caught():
    rep = audit("toy/gullible", CASES, gullible)
    assert [p.probe for p in rep.exploitable] == ["grader_injection"]


def test_grader_that_pays_nothing_is_not_audited():
    rep = audit("toy/zero", CASES, lambda g, r: 0.0)
    assert rep.status == "no_paid_format" and rep.probes == []


def test_template_choice_and_wrong_answers():
    assert choose_signal(CASES, strict)[:2] == ("boxed", TOTAL)
    assert wrong_answer("12", []) == "13" and wrong_answer("B", []) == "C" and wrong_answer("D", []) == "A"
    assert wrong_answer("x^2", ["x^2", "2x"]) == "2x" and wrong_answer("x", ["x"]) is None
    assert boxed("5") == "\\boxed{5}"


def test_bounds():
    assert abs(upper_bound(0, 59) - 0.0495) < 1e-3
    assert trials_needed(0.05) == 59
    assert 0.0 < upper_bound(1, 30) < 1.0 and upper_bound(3, 3) == 1.0


def style(reply):  # a wording-dependent bonus, like a style or tone reward
    return 0.8 * (sum(map(ord, reply)) % 7) / 7


def test_style_terms_do_not_create_false_alarms():
    rep = audit("toy/strict+style", CASES, lambda g, r: {"correct": strict(g, r), "style": style(r),
                                                          TOTAL: strict(g, r) + style(r)})
    assert rep.signal == "correct" and rep.exploitable == []


def test_style_terms_do_not_hide_real_holes():
    rep = audit("toy/lenient+style", CASES, lambda g, r: {"correct": lenient(g, r), "style": style(r),
                                                           TOTAL: lenient(g, r) + style(r)})
    assert rep.signal == "correct" and "hedge_or" in {p.probe for p in rep.exploitable}


def test_noise_only_reward_is_not_audited():
    rep = audit("toy/style-only", CASES, lambda g, r: style(r))
    assert rep.status == "no_paid_format"


def tagged(gold, reply):  # pays only <andswaru>gold</andswaru>, the format its instructions declare
    m = re.findall(r"<andswaru>(.*?)</andswaru>", reply, re.S)
    return float(len(m) == 1 and m[0].strip() == gold)


def test_declared_answer_tag_is_found():
    sysmsg = "Think within <ponder>...</ponder>; render thy final answer within <andswaru>...</andswaru>."
    rep = audit("toy/tagged", CASES, tagged, instructions=sysmsg)
    assert rep.status == "audited" and rep.template.startswith("declared_andswaru") and rep.exploitable == []


def f1_items(gold, reply):  # partial credit over a set of items, by design
    m = re.findall(r"\\boxed\{([^{}]*)\}", reply)
    if len(m) != 1:
        return 0.0
    got = {x.strip() for x in m[0].replace(" or ", ",").split(",") if x.strip()}
    want = {x.strip() for x in gold.split(",")}
    tp = len(got & want)
    return 0.0 if tp == 0 else 2 * tp / (len(got) + len(want))


def test_set_valued_partial_credit_is_not_flagged():
    cases = [TaskCase(handle=g, gold=g) for g in ["1, 4, 9", "2, 7", "3, 5, 8", "6, 10", "11, 12, 13", "14, 15"]]
    rep = audit("toy/f1", cases, f1_items)
    assert rep.status == "audited" and rep.exploitable == []


def label_priority(gold, reply):  # maps any reply naming ENTAIL to ENTAILMENT first, like a fixed priority
    r = reply.upper()
    parsed = "ENTAILMENT" if "ENTAIL" in r else "CONTRADICTION" if "CONTRADICT" in r else "NEUTRAL" if "NEUTRAL" in r else ""
    return float(parsed == gold)


def test_fixed_priority_label_grader_is_not_a_violation():
    labels = ["ENTAILMENT", "NEUTRAL", "CONTRADICTION", "NEUTRAL", "ENTAILMENT", "CONTRADICTION"]
    rep = audit("toy/priority", [TaskCase(handle=g, gold=g) for g in labels], label_priority)
    assert rep.status == "audited" and rep.exploitable == []


def test_label_containment_grader_is_caught():
    labels = ["ENTAILMENT", "NEUTRAL", "CONTRADICTION", "NEUTRAL", "ENTAILMENT", "CONTRADICTION"]
    rep = audit("toy/contains", [TaskCase(handle=g, gold=g) for g in labels], lambda g, r: float(g in r))
    assert "hedge_or" in {p.probe for p in rep.exploitable}


def test_partial_credit_is_reported_not_flagged():
    cases = [TaskCase(handle=g, gold=g) for g in ["1, 4, 9", "2, 7", "3, 5, 8", "6, 10", "11, 12, 13", "14, 15"]]
    rep = audit("toy/f1-partial", cases, f1_items)
    assert rep.exploitable == [] and any(p.partial > 0 for p in rep.probes)
