"""
Paytm Saarthi — Smart Alert Engine
Monitors business metrics and fires alerts when rules are breached.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable


# ─── Types ───────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"

class Channel(str, Enum):
    PUSH      = "push"
    WHATSAPP  = "whatsapp"
    SMS       = "sms"


@dataclass
class Alert:
    id:        str
    title:     str
    message:   str
    priority:  Priority
    channels:  list[Channel]
    metric:    str
    value:     float
    threshold: float
    fired_at:  datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "title":     self.title,
            "message":   self.message,
            "priority":  self.priority.value,
            "channels":  [c.value for c in self.channels],
            "metric":    self.metric,
            "value":     self.value,
            "threshold": self.threshold,
            "fired_at":  self.fired_at.isoformat(),
        }


@dataclass
class Rule:
    id:        str
    name:      str
    metric:    str                       # e.g. "stock_quantity", "daily_sales"
    condition: Callable[[float], bool]   # returns True when alert should fire
    threshold: float
    priority:  Priority
    channels:  list[Channel]
    message_fn: Callable[[float, float], str]  # (value, threshold) -> message


# ─── Built-in Rules ───────────────────────────────────────────────────────────

DEFAULT_RULES: list[Rule] = [
    Rule(
        id        = "low_stock",
        name      = "Low stock alert",
        metric    = "stock_quantity",
        condition = lambda val, thresh=5: val < thresh,
        threshold = 5,
        priority  = Priority.CRITICAL,
        channels  = [Channel.PUSH, Channel.WHATSAPP],
        message_fn= lambda val, thresh: (
            f"Stock critically low — only {int(val)} units left. "
            f"Reorder before you hit 0 and lose sales."
        ),
    ),
    Rule(
        id        = "sales_drop",
        name      = "Sales dropped today",
        metric    = "sales_change_pct",
        condition = lambda val, thresh=-20: val < thresh,
        threshold = -20,
        priority  = Priority.HIGH,
        channels  = [Channel.PUSH, Channel.WHATSAPP, Channel.SMS],
        message_fn= lambda val, thresh: (
            f"Sales dropped {abs(val):.1f}% vs yesterday. "
            f"Check stock levels or nearby competition."
        ),
    ),
    Rule(
        id        = "payment_failures",
        name      = "Payment failure spike",
        metric    = "failed_payments_count",
        condition = lambda val, thresh=3: val >= thresh,
        threshold = 3,
        priority  = Priority.HIGH,
        channels  = [Channel.PUSH, Channel.SMS],
        message_fn= lambda val, thresh: (
            f"{int(val)} UPI payments failed recently. "
            f"Customers may be leaving. Check your Paytm QR code."
        ),
    ),
    Rule(
        id        = "low_margin",
        name      = "Low profit margin",
        metric    = "profit_margin_pct",
        condition = lambda val, thresh=10: val < thresh,
        threshold = 10,
        priority  = Priority.MEDIUM,
        channels  = [Channel.PUSH],
        message_fn= lambda val, thresh: (
            f"Profit margin fell to {val:.1f}%. "
            f"Review your pricing or supplier costs."
        ),
    ),
]


# ─── Engine ──────────────────────────────────────────────────────────────────

class AlertEngine:
    """
    Core engine: given a snapshot of business metrics,
    evaluates all rules and returns fired alerts.
    """

    def __init__(self, rules: list[Rule] = None):
        self.rules = rules or DEFAULT_RULES
        self._fired_ids: set[str] = set()   # prevent duplicate alerts per session

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def evaluate(self, metrics: dict[str, float]) -> list[Alert]:
        """
        Pass in a dict of current business metrics.
        Returns a list of Alert objects for every rule that fires.

        Example metrics:
            {
                "stock_quantity":       3,
                "sales_change_pct":    -25.0,
                "failed_payments_count": 4,
                "profit_margin_pct":   8.5,
            }
        """
        alerts: list[Alert] = []

        for rule in self.rules:
            value = metrics.get(rule.metric)
            if value is None:
                continue  # metric not present in this snapshot, skip

            if rule.condition(value) and rule.id not in self._fired_ids:
                alert = Alert(
                    id        = f"{rule.id}_{int(datetime.now().timestamp())}",
                    title     = rule.name,
                    message   = rule.message_fn(value, rule.threshold),
                    priority  = rule.priority,
                    channels  = rule.channels,
                    metric    = rule.metric,
                    value     = value,
                    threshold = rule.threshold,
                )
                alerts.append(alert)
                self._fired_ids.add(rule.id)  # de-dupe within session

        return alerts

    def reset(self) -> None:
        """Clear fired history (call once per evaluation cycle, e.g. daily)."""
        self._fired_ids.clear()
