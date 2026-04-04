"""
Paytm Saarthi — Notification Dispatcher
Sends fired alerts to the right channels (Push, WhatsApp, SMS).
Swap the stub implementations with real API calls for production.
"""

import json
import logging
from abc import ABC, abstractmethod

from alert_engine import Alert, Channel

logger = logging.getLogger(__name__)


# ─── Base sender ─────────────────────────────────────────────────────────────

class NotificationSender(ABC):
    @abstractmethod
    def send(self, alert: Alert, recipient: str) -> bool:
        """Send the alert. Return True on success."""


# ─── Channel implementations ─────────────────────────────────────────────────

class PushSender(NotificationSender):
    """
    Firebase Cloud Messaging (FCM) push notification.
    Replace `_call_fcm` with your actual FCM integration.
    """

    def __init__(self, fcm_server_key: str = "YOUR_FCM_KEY"):
        self.fcm_server_key = fcm_server_key

    def send(self, alert: Alert, recipient: str) -> bool:
        payload = {
            "to": recipient,                  # FCM device token
            "notification": {
                "title": alert.title,
                "body":  alert.message,
            },
            "data": {
                "alert_id": alert.id,
                "priority": alert.priority.value,
                "metric":   alert.metric,
            },
        }
        return self._call_fcm(payload)

    def _call_fcm(self, payload: dict) -> bool:
        # TODO: replace with real requests.post to FCM endpoint
        logger.info(f"[PUSH] {json.dumps(payload, indent=2)}")
        return True


class WhatsAppSender(NotificationSender):
    """
    WhatsApp Business API (via Paytm / Twilio / Meta).
    Replace `_call_whatsapp_api` with your real integration.
    """

    def __init__(self, api_token: str = "YOUR_WA_TOKEN", from_number: str = ""):
        self.api_token   = api_token
        self.from_number = from_number

    def send(self, alert: Alert, recipient: str) -> bool:
        # WhatsApp template message format
        message = (
            f"🔔 *Paytm Saarthi Alert*\n\n"
            f"*{alert.title}*\n"
            f"{alert.message}\n\n"
            f"_Sent at {alert.fired_at.strftime('%I:%M %p')}_"
        )
        return self._call_whatsapp_api(to=recipient, body=message)

    def _call_whatsapp_api(self, to: str, body: str) -> bool:
        # TODO: replace with real API call
        logger.info(f"[WHATSAPP → {to}]\n{body}")
        return True


class SMSSender(NotificationSender):
    """
    SMS via any Indian SMS gateway (e.g. MSG91, Textlocal).
    Replace `_call_sms_api` with your real integration.
    """

    def __init__(self, api_key: str = "YOUR_SMS_KEY", sender_id: str = "SAARTHI"):
        self.api_key   = api_key
        self.sender_id = sender_id

    def send(self, alert: Alert, recipient: str) -> bool:
        # Keep SMS short — 160 chars
        text = f"Saarthi: {alert.title}. {alert.message[:120]}"
        return self._call_sms_api(to=recipient, text=text)

    def _call_sms_api(self, to: str, text: str) -> bool:
        # TODO: replace with real API call
        logger.info(f"[SMS → {to}] {text}")
        return True


# ─── Dispatcher ──────────────────────────────────────────────────────────────

class NotificationDispatcher:
    """
    Routes each alert to the correct sender(s) based on its channel list.
    """

    def __init__(
        self,
        push_sender:      PushSender      = None,
        whatsapp_sender:  WhatsAppSender  = None,
        sms_sender:       SMSSender       = None,
    ):
        self._senders = {
            Channel.PUSH:     push_sender     or PushSender(),
            Channel.WHATSAPP: whatsapp_sender or WhatsAppSender(),
            Channel.SMS:      sms_sender      or SMSSender(),
        }

    def dispatch(self, alert: Alert, recipient_map: dict[Channel, str]) -> dict:
        """
        Send an alert through all its specified channels.

        recipient_map example:
            {
                Channel.PUSH:     "fcm-device-token-xyz",
                Channel.WHATSAPP: "+919876543210",
                Channel.SMS:      "+919876543210",
            }

        Returns a result dict: { channel: success_bool }
        """
        results = {}
        for channel in alert.channels:
            recipient = recipient_map.get(channel)
            if not recipient:
                logger.warning(f"No recipient for channel {channel} — skipping")
                results[channel.value] = False
                continue

            sender  = self._senders[channel]
            success = sender.send(alert, recipient)
            results[channel.value] = success
            status  = "✓" if success else "✗"
            logger.info(f"  {status} Sent via {channel.value} to {recipient}")

        return results

    def dispatch_all(
        self,
        alerts: list[Alert],
        recipient_map: dict[Channel, str],
    ) -> list[dict]:
        """Dispatch a list of alerts, return all results."""
        all_results = []
        for alert in alerts:
            logger.info(f"\n── Firing alert: [{alert.priority.value.upper()}] {alert.title}")
            result = self.dispatch(alert, recipient_map)
            all_results.append({"alert_id": alert.id, "channels": result})
        return all_results
