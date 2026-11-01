"""Three deterministic stand-in agents so the harness itself can be tested without an API key.

* NaiveAgent   : refunds whatever the customer asks for, cites nothing (what a weak prompt does).
* GroundedAgent: looks up the order, retrieves policy, reads rules from what it retrieved, cites it, escalates when unsure.
* RegressedAgent: the grounded agent after a 'prompt change' that silently stops retrieving/citing.
Any LLM agent can be evaluated the same way by implementing `run(case, env, retriever) -> Trace`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .env import Env
from .kb import Retriever

ORDER_RX = re.compile(r"ORD-\d+")
DAMAGED = ("damaged", "broken", "cracked", "defective")
DUPLICATE = ("charged twice", "double charged", "charged me twice", "twice")


@dataclass
class Trace:
    reply: str = ""
    retrieved: list[str] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    final_action: str = "none"      # refund | deny | escalate | none
    refund_amount: float = 0.0
    steps: int = 0


def _cite(ids):
    return " ".join(f"[policy:{i}]" for i in ids)


class NaiveAgent:
    name = "naive"

    def run(self, case, env: Env, retriever: Retriever) -> Trace:
        t = Trace()
        m = ORDER_RX.search(case.message)
        if not m:
            t.reply, t.final_action = "Sorry to hear that, I have processed your request.", "none"
            t.steps = 1
            return t
        order = env.lookup_order(m.group())
        amount = (order or {}).get("amount", 0)
        env.issue_refund(m.group(), amount)
        t.reply, t.final_action, t.refund_amount = f"Your refund of {amount} has been processed.", "refund", amount
        t.calls, t.steps = env.calls, 2
        return t


class GroundedAgent:
    name = "grounded"
    cite = True
    retrieve = True

    def run(self, case, env: Env, retriever: Retriever) -> Trace:
        t = Trace()
        msg = case.message.lower()
        m = ORDER_RX.search(case.message)
        if not m:
            return self._escalate(t, env, "No order id given; need more information.")
        order = env.lookup_order(m.group())
        t.steps += 1
        if order is None:
            return self._escalate(t, env, f"Order {m.group()} not found.")

        docs = retriever.search(case.message + (" digital download" if order["type"] == "digital" else " physical delivered refund window"), k=4) if self.retrieve else []
        t.retrieved = [d.id for d in docs]
        t.steps += 1
        facts = {k: v for d in docs for k, v in d.facts.items()}
        have = set(t.retrieved)
        amount, days = order["amount"], order["delivered_days_ago"]
        if order["charges"] > 1 and any(w in msg for w in DUPLICATE):
            if "duplicate_charge" not in have and self.retrieve:
                return self._escalate(t, env, "Needed the duplicate-charge policy and could not find it.")
            return self._refund(t, env, m.group(), amount, ["duplicate_charge"], "the duplicate charge", facts)

        if order["type"] == "digital":
            if "digital_goods" not in have and self.retrieve:
                return self._escalate(t, env, "Policy for digital goods not retrieved.")
            if order["downloaded"]:
                return self._deny(t, "Digital goods cannot be refunded once downloaded.", ["digital_goods"])
            return self._refund(t, env, m.group(), amount, ["digital_goods"], "your order", facts)

        damaged = any(w in msg for w in DAMAGED)
        if damaged and days <= facts.get("damaged_days", 7):
            return self._refund(t, env, m.group(), amount, ["damaged_items"], "your damaged item", facts)
        window = facts.get("window_days")
        if window is None and self.retrieve:
            return self._escalate(t, env, "Refund window policy not retrieved.")
        if days <= (window or 30):
            return self._refund(t, env, m.group(), amount, ["refund_window"], "your order", facts)
        return self._deny(t, f"This order was delivered {days} days ago, outside the {window or 30}-day refund window.", ["refund_window"])

    # -- actions --------------------------------------------------------------
    def _refund(self, t, env, order_id, amount, cites, what, facts):
        limit = facts.get("max_auto_refund", 5000)
        if amount > limit:
            return self._escalate(t, env, f"Refund of {amount} exceeds the {limit} limit.", cites=["high_value"])
        env.issue_refund(order_id, amount)
        t.final_action, t.refund_amount, t.calls, t.steps = "refund", amount, env.calls, t.steps + 1
        t.reply = f"I have refunded {amount} for {what}. " + (_cite(cites) if self.cite else "")
        return t

    def _deny(self, t, why, cites):
        t.final_action, t.steps = "deny", t.steps + 1
        t.reply = f"I'm sorry, I can't refund this order. {why} " + (_cite(cites) if self.cite else "")
        return t

    def _escalate(self, t, env, reason, cites=()):
        env.escalate(reason)
        t.final_action, t.calls, t.steps = "escalate", env.calls, t.steps + 1
        t.reply = f"I'm passing this to a colleague because: {reason} " + (_cite(cites) if self.cite and cites else "")
        return t


class RegressedAgent(GroundedAgent):
    name = "regressed"
    cite = False
    retrieve = False
