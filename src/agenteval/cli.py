from __future__ import annotations

import argparse
import json
import sys

from .runner import AGENTS, compare, run_suite, save


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agenteval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the scenario suite against an agent")
    r.add_argument("agent", choices=sorted(AGENTS))
    r.add_argument("--out")
    c = sub.add_parser("compare", help="gate a candidate run against a baseline run")
    c.add_argument("baseline")
    c.add_argument("candidate")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        res = run_suite(AGENTS[a.agent]())
        s = res["summary"]
        print(f"{s['agent']}: success {s['task_success']:.0%} | compliance {s['policy_compliance']:.0%} | grounding {s['grounding']:.0%} | "
              f"retrieval {s['retrieval_recall']:.0%} | esc recall {s['escalation_recall']:.0%} precision {s['escalation_precision']:.0%} | steps {s['avg_steps']}")
        for row in res["rows"]:
            if not row["task_success"] or not row["policy_compliance"]:
                print(f"  FAIL {row['case']:20s} expected {row['expected']:9s} got {row['action']:9s} compliance={row['policy_compliance']}")
        if a.out:
            save(res, a.out)
        return 0
    base, cand = (json.load(open(p)) for p in (a.baseline, a.candidate))
    problems = compare(base, cand)
    print("REGRESSION" if problems else "OK: no regression")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
