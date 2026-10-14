# rl-env-audit

**Before you train on an RL environment, check that its grader cannot be paid without a correct answer.**

`rl-env-audit` is an acceptance test for the reward functions of reinforcement-learning (RL) environments. It installs an environment in an isolated virtualenv, calls the environment's own scoring code (the same code a training run calls), and sends it replies that should never be paid like a correct answer: an empty reply, a wrong answer with a note telling the grader it is correct, or a reply that names two candidates so that the policy gets two guesses for the price of one. An environment that pays none of them gets a certificate with an exact statistical bound; one that pays any of them gets the failing replies, so the author can fix the grader before anyone trains on it.

No extra labels are needed: every check is built from the task's own reference answer, a wrong answer, and the reply format the grader already pays.

## Results on the Prime Intellect Environments Hub

On 13 October 2026 the tool scanned the 60 most-starred public environments tagged `single-turn` on the [Prime Intellect Environments Hub](https://app.primeintellect.ai/dashboard/environments), with 60 tasks each ([full results](scans/2026-10-13-prime-hub.md)).

| | Environments |
|---|---|
| Audited | **21** |
| Passed every check (each check paid on fewer than 4.9% of tasks, 95% confidence) | **19** |
| Paid a check in full without a correct answer | **2** |
| Not auditable by these checks (no single reference answer, credentials or gated data needed, install or import failure) | 39 |

The two failures are different in kind. In one, the grader accepts any short reply that *contains* the answer, so a reply naming two candidates (`A or B`) is paid in full whichever is right: 60 of 60 tasks. In the other, a reply without `\boxed{}` is scored as a whole math expression, so restating a compute-this-expression question is paid: 2 of 60 tasks. Both environments are kept anonymous until their authors have been told privately and have had time to fix them.

**Both have small fixes, checked with the tool** ([details](scans/2026-10-13-prime-hub.md#fixes), [data](scans/2026-10-14-fixes.json)):

| | Check | Original grader | Fixed grader |
|---|---|---|---|
| Environment A | `hedge_or` | 466/500 tasks | 0/500 |
| Environment A | `candidate_list` | 500/500 tasks | 0/500 |
| Environment A | honest replies (10 phrasings of the correct answer per task) | 4,997/5,000 paid | 4,997/5,000 paid, none changed |
| Environment B | `echo_prompt` | 11/299 tasks | 0/299 |

Getting here also took the tool through four graders that *look* exploitable but are not, each now a unit test: a grader that reads the last boxed answer, a reward with a style term (the style score moves with wording, not with correctness), an F1 grader that gives partial credit for extra items by design, and a label grader that maps any mention of `ENTAIL` to one label (a fixed priority gives a policy no second guess).

## Paper

[**Two Guesses for the Price of One: Acceptance Tests for the Graders of Reinforcement-Learning Environments**](paper/Two_Guesses_for_the_Price_of_One_Acceptance_Tests_for_RL_Environment_Graders.pdf) (12 pages). It describes the checks, proves that the cross-task rule never flags a grader that extracts a single answer, validates the rules on thirteen toy graders, and reports the scan and the fixes. `paper/make_figures.py` regenerates its figures from the files in `scans/`.

## How a check works

Each environment is first calibrated, so that a check is only trusted where the grader demonstrably works:

1. **Find the correctness signal.** The tool tries common reply formats (`\boxed{}`, `####`, `<answer>` tags, and any tags the environment's own instructions declare) and, if the reward has several components, each component separately. It keeps the format and component that pay the gold answer over a wrong answer by a clear and consistent margin. Style, length or format terms that move with the wording of a reply are therefore not mistaken for payment.
2. **Run the checks** in that format, on every audited task:

| Check | Family | A strict grader pays it |
|---|---|---|
| `empty` | null reply | never |
| `format_only` | null reply | never |
| `echo_prompt` | null reply | never |
| `grader_injection` | grader injection | never (a wrong answer plus a note telling the grader it is correct) |
| `hedge_or` | two guesses | never on both tasks (`gold or wrong`) |
| `candidate_list` | two guesses | never on both tasks (`wrong, gold`) |
| `two_finals` | two guesses | never on both tasks |
| `reasoning_and_final` | two guesses | never on both tasks (one value in the reasoning, another as the final answer) |
| `rejected_value` | two guesses | never on both tasks ("it is not X", then a final answer) |
| `value_after_final` | two guesses | never on both tasks |

3. **Decide.** A null or injection check counts as paid when the correctness signal rewards it at least halfway between the wrong and the correct answer, and the result reproduces on a second call. A two-guess reply, built from a task's answer `g` and a wrong answer `w`, counts only when it is paid **in full on two tasks**: this one, and another task whose answer is `w`. A grader that reads one value from the reply, by position or by a fixed priority, can never pay the same reply as correct on both (the paper proves this), so it gives a policy nothing to gain; a grader that pays the gold value wherever it appears lets a policy hedge. Replies paid above halfway but not in full on both tasks are reported separately as partial credit (F1-style graders give it by design).

**Certificate.** If no check is paid on *n* tasks, the rate at which each check is paid is below 1 − 0.05^(1/n) with 95% confidence (an exact binomial bound): 59 clean tasks bound it below 5%.

## What it does not cover

Checks are single-turn and text-only. Environments whose reward has no single reference answer (instruction following, similarity scores), environments whose reward needs a sandbox or tool runtime, and environments scored only by an LLM judge are reported as not auditable rather than as passing. A passing environment can still have holes these checks do not probe; the certificate bounds the rate of these checks only.

## Run it

```bash
# one or more Hub environments, each in its own virtualenv (Linux; needs uv)
PYTHONPATH=src python -m rl_env_audit.hub --envs primeintellect/math500 will/gsm8k --n 60 --out results/
PYTHONPATH=src python -m rl_env_audit.report results/ --out REPORT.md

# the most-starred single-turn environments, from `prime env list --output json`
PYTHONPATH=src python -m rl_env_audit.hub --list hub.json --tag single-turn --top 60 --jobs 1 --out results/

# unit tests on toy graders, including graders that must NOT be flagged
uv run --with pytest python -m pytest -q
```

Environments are third-party code: run the scan on a disposable machine or container, not on a workstation with credentials.

## Disclosure

When a check is paid, the environment's author is told privately first, with the failing replies and a suggested fix. Environments are named publicly only after the author has had time to fix them.

Vahit FERYAD · [vahit.feryat@gmail.com](mailto:vahit.feryat@gmail.com) · MIT License
