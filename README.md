# agent-eval-harness

A small, runnable harness for answering the question every team building agents has to answer:
**"Is this agent actually any good, and did my last change make it worse?"**

Built as a proof of concept for the AI Engineer role at [Meraki Labs](https://www.merakilabs.com). Their posting describes
agentic systems that carry multi-step work from start to finish, "the evaluation infrastructure that tells us whether they're any good",
and the retrieval layer that gives agents accurate knowledge. This is an independent sketch of that evaluation and retrieval layer,
built on a toy refund-handling agent with synthetic data. It is not Meraki's code, product or architecture.

## The problem

Agents decide what to do for each customer, act through tools, and hand the hard cases to people. Three things go wrong quietly:
1. The agent takes an action it should not (refunds out of policy, obeys an instruction hidden in a customer message).
2. The answer looks right but is not grounded: it cites nothing, or cites a policy it never retrieved.
3. A prompt or retrieval change "improves" one case and silently breaks others, and nobody notices until a customer does.

Reading transcripts does not scale. You need a scenario suite, graders that judge *behaviour* (tool calls, citations,
escalations) rather than prose, and a gate that blocks a regression.

## What is in here

```
scenarios (13 cases) -> agent runs in a sandbox (orders DB + 3 tools + policy retriever) -> graders -> metrics -> gate vs a baseline
```

* **Retrieval layer** (`kb.py`): policy documents with machine-readable facts and a dependency-free TF-IDF retriever. The agent may read
  a rule only from documents it retrieved, so weak retrieval shows up as wrong or escalated decisions. It is also scored directly.
* **Sandbox** (`env.py`): orders and three tools (`lookup_order`, `issue_refund`, `escalate`). Every call is recorded.
* **Agents** (`agents.py`): three deterministic stand-ins so the harness is testable without an API key. `naive` (refunds anything),
  `grounded` (looks up, retrieves, applies, cites, escalates when unsure) and `regressed` (grounded after a change that silently drops
  retrieval and citations). Any LLM agent plugs in by implementing `run(case, env, retriever) -> Trace`.
* **Graders** (`graders.py`): `task_success`, `policy_compliance` (no forbidden tool call), `grounding` (cites what policy requires,
  and only what it retrieved), `retrieval_recall`, `escalation`.
* **Scenarios** (`scenarios.py`): core cases, boundaries (29 vs 31 days), and safety cases: high-value refund, unknown order,
  missing order id, and a **prompt-injection** message claiming a manager approved a 9000 refund.
* **Gate** (`runner.compare`): per-metric tolerances plus "cases that passed before and now fail" and "new policy violations".
  Non-zero exit code, so it can sit in CI.

## Results on the suite (13 cases)

| agent | task success | policy compliance | grounding | retrieval recall | escalation recall |
|---|---|---|---|---|---|
| naive | 38% | 46% | 15% | 15% | 0% |
| grounded | 100% | 100% | 100% | 100% | 100% |
| regressed | 100% | 100% | **15%** | **15%** | 100% |

The last row is the point: the regressed agent still gives the right decisions, so an outcome-only check passes it, but it has stopped
retrieving and citing. The gate fails it: `grounding 1.000 -> 0.154`. The naive agent is caught refunding on the injection case,
on an unknown order, and above the human-approval limit.

## Run it

```bash
pip install -e ".[dev]"
agenteval run grounded --out runs/grounded.json
agenteval run regressed --out runs/regressed.json
agenteval compare runs/grounded.json runs/regressed.json     # prints the regression, exits 1
pytest                                                       # 8 tests
```

## Limits (honest)

* The agents are rule-based stand-ins and I wrote both the agents and the suite, so 100% for `grounded` proves the harness works, not
  that an LLM agent would do well. The real test is plugging in a model and watching the numbers move.
* 13 scenarios is a seed set. Real coverage comes from production transcripts, adversarial cases, and multi-turn conversations.
* Graders are exact checks. For free-text quality I would add an LLM judge, calibrated against human labels, as an additional grader
  and never as the only safety check.
* Single run per case. With a stochastic model you need repeats and confidence intervals before trusting a small difference.

## Next steps I would take

1. Wrap a real LLM agent (tool-calling) behind the `run` interface and compare it against `grounded`.
2. Multi-turn scenarios (customer replies, missing information) and a simulated user.
3. Mine failures from production traces into new scenarios automatically, and track metrics per release.
4. An LLM-as-judge grader for tone and completeness, checked against a small human-labelled set.

Author: Anushka Kulkarni, github.com/Anushka-200
