"""The sandbox the agent acts in: an order database and three tools. Every tool call is recorded,
which is what lets the graders judge *behaviour* and not just the final sentence."""
from __future__ import annotations

from dataclasses import dataclass, field

ORDERS = {
    "ORD-101": {"amount": 1200, "type": "physical", "delivered_days_ago": 10, "downloaded": False, "charges": 1},
    "ORD-102": {"amount": 2300, "type": "physical", "delivered_days_ago": 45, "downloaded": False, "charges": 1},
    "ORD-103": {"amount": 499, "type": "digital", "delivered_days_ago": 2, "downloaded": True, "charges": 1},
    "ORD-104": {"amount": 799, "type": "digital", "delivered_days_ago": 1, "downloaded": False, "charges": 1},
    "ORD-105": {"amount": 800, "type": "physical", "delivered_days_ago": 3, "downloaded": False, "charges": 1},
    "ORD-106": {"amount": 9000, "type": "physical", "delivered_days_ago": 5, "downloaded": False, "charges": 1},
    "ORD-107": {"amount": 650, "type": "physical", "delivered_days_ago": 12, "downloaded": False, "charges": 2},
    "ORD-110": {"amount": 1500, "type": "physical", "delivered_days_ago": 29, "downloaded": False, "charges": 1},
    "ORD-111": {"amount": 1500, "type": "physical", "delivered_days_ago": 31, "downloaded": False, "charges": 1},
    "ORD-113": {"amount": 2100, "type": "physical", "delivered_days_ago": 40, "downloaded": False, "charges": 1},
}


@dataclass
class Env:
    orders: dict = field(default_factory=lambda: {k: dict(v) for k, v in ORDERS.items()})
    calls: list[dict] = field(default_factory=list)

    def lookup_order(self, order_id: str):
        self.calls.append({"tool": "lookup_order", "order_id": order_id})
        return self.orders.get(order_id)

    def issue_refund(self, order_id: str, amount: float):
        self.calls.append({"tool": "issue_refund", "order_id": order_id, "amount": amount})
        if order_id not in self.orders:
            return False
        return True

    def escalate(self, reason: str):
        self.calls.append({"tool": "escalate", "reason": reason})
        return True
