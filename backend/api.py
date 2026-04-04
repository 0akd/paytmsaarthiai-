"""
Paytm Saarthi — FastAPI Server
Exposes the alert engine as a REST API for the Astro frontend.

Install:  pip install fastapi uvicorn
Run:      uvicorn api:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from alert_engine import Alert, AlertEngine, Channel, DEFAULT_RULES, Priority, Rule
from notification_dispatcher import NotificationDispatcher


# ─── App setup ───────────────────────────────────────────────────────────────

engine     = AlertEngine()
dispatcher = NotificationDispatcher()

# In-memory store for demo. Use a DB (PostgreSQL, SQLite) in production.
_alert_history: list[dict] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✓ Saarthi Alert Engine ready")
    yield
    print("Shutting down...")

app = FastAPI(title="Paytm Saarthi Alert API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],  # Astro dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response models ───────────────────────────────────────────────

class MetricsPayload(BaseModel):
    """
    POST body: current business metrics snapshot from the dukaan's data.
    All fields optional — only present metrics are evaluated.
    """
    shop_id:                str
    stock_quantity:         float | None = None
    sales_change_pct:       float | None = None
    failed_payments_count:  float | None = None
    profit_margin_pct:      float | None = None

    # Recipient contacts for notifications
    fcm_token:    str | None = None
    phone_number: str | None = None

class CustomRulePayload(BaseModel):
    metric:    str
    threshold: float
    operator:  str       # "lt" | "gt" | "lte" | "gte"
    priority:  str       # "critical" | "high" | "medium" | "low"
    channels:  list[str] # ["push", "whatsapp", "sms"]
    message:   str       # Custom message text


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_recipient_map(payload: MetricsPayload) -> dict:
    return {
        Channel.PUSH:     payload.fcm_token    or "",
        Channel.WHATSAPP: payload.phone_number or "",
        Channel.SMS:      payload.phone_number or "",
    }

def _operator_fn(operator: str, threshold: float):
    ops = {
        "lt":  lambda v: v < threshold,
        "gt":  lambda v: v > threshold,
        "lte": lambda v: v <= threshold,
        "gte": lambda v: v >= threshold,
    }
    if operator not in ops:
        raise HTTPException(400, f"Unknown operator '{operator}'. Use: lt, gt, lte, gte")
    return ops[operator]


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/alerts")
def get_alert_history(limit: int = 20):
    """Return recent alert history for the dashboard."""
    return {"alerts": _alert_history[-limit:]}


@app.post("/alerts/evaluate")
def evaluate_metrics(payload: MetricsPayload):
    """
    Core endpoint. Call this on a schedule (every 5–15 min) or
    after every sale/inventory update.

    Returns fired alerts and dispatches notifications automatically.
    """
    metrics = {
        k: v for k, v in {
            "stock_quantity":        payload.stock_quantity,
            "sales_change_pct":      payload.sales_change_pct,
            "failed_payments_count": payload.failed_payments_count,
            "profit_margin_pct":     payload.profit_margin_pct,
        }.items() if v is not None
    }

    if not metrics:
        raise HTTPException(400, "Provide at least one metric to evaluate.")

    # 1. Evaluate rules
    fired_alerts: list[Alert] = engine.evaluate(metrics)

    if not fired_alerts:
        return {"shop_id": payload.shop_id, "alerts_fired": 0, "alerts": []}

    # 2. Dispatch notifications
    recipient_map = _build_recipient_map(payload)
    dispatcher.dispatch_all(fired_alerts, recipient_map)

    # 3. Store in history
    alert_dicts = [a.to_dict() for a in fired_alerts]
    _alert_history.extend(alert_dicts)

    return {
        "shop_id":      payload.shop_id,
        "alerts_fired": len(fired_alerts),
        "alerts":       alert_dicts,
    }


@app.post("/rules")
def add_custom_rule(payload: CustomRulePayload):
    """Let the dukandaar create a custom alert rule from the UI."""
    try:
        condition  = _operator_fn(payload.operator, payload.threshold)
        priority   = Priority(payload.priority)
        channels   = [Channel(c) for c in payload.channels]
    except ValueError as e:
        raise HTTPException(400, str(e))

    rule = Rule(
        id         = f"custom_{len(engine.rules)}",
        name       = f"Custom: {payload.metric} {payload.operator} {payload.threshold}",
        metric     = payload.metric,
        condition  = condition,
        threshold  = payload.threshold,
        priority   = priority,
        channels   = channels,
        message_fn = lambda val, thresh, msg=payload.message: msg,
    )
    engine.add_rule(rule)
    return {"status": "added", "rule_id": rule.id, "total_rules": len(engine.rules)}


@app.get("/rules")
def list_rules():
    """Return all active rules."""
    return {
        "rules": [
            {
                "id":        r.id,
                "name":      r.name,
                "metric":    r.metric,
                "threshold": r.threshold,
                "priority":  r.priority.value,
                "channels":  [c.value for c in r.channels],
            }
            for r in engine.rules
        ]
    }


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Remove a rule by id."""
    original = len(engine.rules)
    engine.rules = [r for r in engine.rules if r.id != rule_id]
    if len(engine.rules) == original:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"status": "deleted", "rule_id": rule_id}


@app.post("/alerts/reset")
def reset_engine():
    """Reset fired-alert de-dupe history (call once daily)."""
    engine.reset()
    return {"status": "reset"}
