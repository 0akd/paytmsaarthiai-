"""
Quick demo — run this to see the alert engine in action
without needing the full FastAPI server.

    python demo.py
"""

import logging
from alert_engine import AlertEngine
from notification_dispatcher import NotificationDispatcher, Channel

logging.basicConfig(level=logging.INFO, format="%(message)s")

engine     = AlertEngine()
dispatcher = NotificationDispatcher()

# Simulate a dukaan's current business snapshot
metrics = {
    "stock_quantity":        3,      # Only 3 units left  → triggers low_stock
    "sales_change_pct":    -25.0,    # Down 25% today     → triggers sales_drop
    "failed_payments_count": 4,      # 4 UPI failures     → triggers payment_failures
    "profit_margin_pct":    12.0,    # 12% — above threshold, no alert
}

print("\n━━ Evaluating metrics ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
for k, v in metrics.items():
    print(f"  {k}: {v}")
print()

alerts = engine.evaluate(metrics)

print(f"━━ {len(alerts)} alert(s) fired ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

recipient_map = {
    Channel.PUSH:     "demo-fcm-token-abc123",
    Channel.WHATSAPP: "+919876543210",
    Channel.SMS:      "+919876543210",
}

dispatcher.dispatch_all(alerts, recipient_map)

print("\n━━ Alert payloads ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
import json
for alert in alerts:
    print(json.dumps(alert.to_dict(), indent=2))
