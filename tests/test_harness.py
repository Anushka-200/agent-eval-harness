from agenteval import AGENTS, compare, run_suite
from agenteval import graders as g
from agenteval.agents import Trace
from agenteval.kb import POLICIES, Retriever
from agenteval.scenarios import SUITE, Case


def run(name):
    return run_suite(AGENTS[name]())


def test_retriever_finds_the_policy_a_decision_needs():
    r = Retriever(POLICIES)
    assert r.search("my e-book download is not what I expected", k=2)[0].id == "digital_goods"
    assert "duplicate_charge" in [d.id for d in r.search("I was charged twice", k=3)]
    assert r.search("zzzz qqqq") == []


def test_every_case_in_the_suite_has_an_expectation_that_the_grounded_agent_meets():
    res = run("grounded")["summary"]
    assert res["task_success"] == 1.0 and res["policy_compliance"] == 1.0 and res["violations"] == []


def test_naive_agent_is_caught_refunding_when_it_must_not():
    res = run("naive")
    s = res["summary"]
    assert s["policy_compliance"] < 0.6 and "prompt_injection" in s["violations"] and "unknown_order" in s["violations"]
    assert s["escalation_recall"] == 0.0


def test_prompt_injection_case_is_denied_by_the_grounded_agent():
    row = next(r for r in run("grounded")["rows"] if r["case"] == "prompt_injection")
    assert row["action"] == "deny" and row["policy_compliance"]


def test_silent_regression_is_blocked_by_the_gate_even_though_answers_stay_correct():
    base, cand = run("grounded"), run("regressed")
    assert cand["summary"]["task_success"] == 1.0          # still gives the right decisions...
    problems = compare(base, cand)                           # ...but the gate notices it stopped citing/retrieving
    assert any(p.startswith("grounding") for p in problems) and any(p.startswith("retrieval_recall") for p in problems)


def test_gate_passes_an_identical_run_and_flags_a_new_violation():
    base = run("grounded")
    assert compare(base, run("grounded")) == []
    assert any("violation" in p or "policy_compliance" in p for p in compare(base, run("naive")))


def test_graders_unit():
    case = Case("c", "m", "refund", 100, ["refund_window"], ["refund_window"])
    ok = Trace(reply="done [policy:refund_window]", retrieved=["refund_window"], final_action="refund", refund_amount=100,
               calls=[{"tool": "issue_refund", "order_id": "ORD-101", "amount": 100}])
    assert g.task_success(case, ok) and g.grounding(case, ok) and g.policy_compliance(case, ok, {"ORD-101": {}})
    cites_unretrieved = Trace(reply="[policy:refund_window] [policy:made_up]", retrieved=["refund_window"], final_action="refund", refund_amount=100)
    assert not g.grounding(case, cites_unretrieved)       # cannot cite a policy it never retrieved
    wrong_amount = Trace(final_action="refund", refund_amount=90, calls=[{"tool": "issue_refund", "order_id": "ORD-101", "amount": 90}])
    assert not g.task_success(case, wrong_amount) and not g.policy_compliance(case, wrong_amount, {"ORD-101": {}})


def test_suite_covers_boundaries_and_safety():
    tags = {t for c in SUITE for t in c.tags}
    assert {"core", "boundary", "safety"} <= tags and len(SUITE) >= 12
