from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from . import graders as g
from .agents import GroundedAgent, NaiveAgent, RegressedAgent
from .env import Env, ORDERS
from .kb import POLICIES, Retriever
from .scenarios import SUITE

AGENTS = {"naive": NaiveAgent, "grounded": GroundedAgent, "regressed": RegressedAgent}


def run_suite(agent, suite=SUITE) -> dict:
    retriever = Retriever(POLICIES)
    rows = []
    for case in suite:
        env = Env()
        trace = agent.run(case, env, retriever)
        row = {
            "case": case.id, "tags": case.tags, "action": trace.final_action, "expected": case.expect_action,
            "task_success": g.task_success(case, trace),
            "policy_compliance": g.policy_compliance(case, trace, ORDERS),
            "grounding": g.grounding(case, trace),
            "retrieval_recall": g.retrieval_recall(case, trace),
            "escalation": g.escalation(case, trace),
            "steps": trace.steps, "reply": trace.reply,
        }
        rows.append(row)
    n = len(rows)
    rate = lambda k: round(sum(r[k] for r in rows) / n, 3)
    esc_expected = [r for r in rows if r["expected"] == "escalate"]
    esc_actual = [r for r in rows if r["action"] == "escalate"]
    summary = {
        "agent": agent.name, "cases": n,
        "task_success": rate("task_success"), "policy_compliance": rate("policy_compliance"),
        "grounding": rate("grounding"), "retrieval_recall": rate("retrieval_recall"),
        "escalation_recall": round(sum(r["expected"] == "escalate" for r in esc_actual) / len(esc_expected), 3) if esc_expected else 1.0,
        "escalation_precision": round(sum(r["expected"] == "escalate" for r in esc_actual) / len(esc_actual), 3) if esc_actual else 1.0,
        "avg_steps": round(sum(r["steps"] for r in rows) / n, 2),
        "violations": [r["case"] for r in rows if not r["policy_compliance"]],
    }
    return {"summary": summary, "rows": rows}


# A release gate: tolerances for each metric when comparing a candidate to a baseline run.
GATES = {"task_success": 0.0, "policy_compliance": 0.0, "grounding": 0.05, "retrieval_recall": 0.05,
         "escalation_recall": 0.0, "escalation_precision": 0.1}


def compare(base: dict, cand: dict) -> list[str]:
    problems = []
    b, c = base["summary"], cand["summary"]
    for metric, tol in GATES.items():
        if c[metric] < b[metric] - tol:
            problems.append(f"{metric}: {b[metric]:.3f} -> {c[metric]:.3f} (allowed drop {tol})")
    bf = {r["case"] for r in base["rows"] if r["task_success"]}
    cf = {r["case"] for r in cand["rows"] if not r["task_success"]}
    newly = sorted(bf & cf)
    if newly:
        problems.append("cases that passed before and now fail: " + ", ".join(newly))
    if set(c["violations"]) - set(b["violations"]):
        problems.append("new policy violations: " + ", ".join(sorted(set(c["violations"]) - set(b["violations"]))))
    return problems


def save(result: dict, path: str | Path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(result, indent=1))
