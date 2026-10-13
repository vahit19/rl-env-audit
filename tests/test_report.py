from rl_env_audit.report import certificate, summary


def row(env, paid):
    probes = [{"probe": "hedge_or", "paid": paid, "tested": 60}, {"probe": "empty", "paid": 0, "tested": 60}]
    return {"env": env, "status": "audited", "template": "boxed", "tasks_tested": 60, "probes": probes}


def test_certificate_pass_and_fail():
    assert certificate(row("a/ok", 0)).startswith("PASSED on 60 tasks") and "4.9%" in certificate(row("a/ok", 0))
    assert certificate(row("a/bad", 3)) == "NOT PASSED. Paid without a correct answer: hedge_or (3/60)."


def test_summary_counts():
    text = summary([row("a/ok", 0), row("a/bad", 3), {"env": "a/broken", "status": "install_error"}])
    assert text.startswith("3 environments: 2 audited, 1 of them paid")
    assert "| a/bad | audited | boxed | 60 | hedge_or 3/60 | none |" in text
