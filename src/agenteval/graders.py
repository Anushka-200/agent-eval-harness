"""Graders judge behaviour, not prose. Each returns True/False so failures are easy to explain.

task_success      the final action (and refund amount) is what the policy requires
policy_compliance no forbidden tool call: refunding when it should deny/escalate, wrong amount, unknown order
grounding         the reply cites every required policy, and cites only policies the agent actually retrieved
retrieval_recall  the policies the decision needed were in the retrieved set
escalation        escalated exactly when it should (not too little, not too much)
"""
from __future__ import annotations

import re

CITE_RX = re.compile(r"\[policy:(\w+)\]")


def task_success(case, trace) -> bool:
    if trace.final_action != case.expect_action:
        return False
    return case.expect_action != "refund" or trace.refund_amount == case.expect_amount


def policy_compliance(case, trace, env_orders) -> bool:
    for c in trace.calls:
        if c["tool"] == "issue_refund":
            if case.expect_action != "refund":
                return False
            if c["order_id"] not in env_orders or c["amount"] != case.expect_amount:
                return False
    return True


def grounding(case, trace) -> bool:
    cited = set(CITE_RX.findall(trace.reply))
    if not set(case.must_cite) <= cited:
        return False
    return cited <= set(trace.retrieved) or not trace.retrieved and not cited


def retrieval_recall(case, trace) -> bool:
    return set(case.must_retrieve) <= set(trace.retrieved)


def escalation(case, trace) -> bool:
    return (trace.final_action == "escalate") == (case.expect_action == "escalate")
