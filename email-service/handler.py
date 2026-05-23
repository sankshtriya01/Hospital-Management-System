"""
Serverless email handler — triggered via HTTP POST from the Django HMS app.

Supported event_type values:
  SIGNUP_WELCOME        — sent when a new user registers
  BOOKING_CONFIRMATION  — sent when a patient books an appointment

Expected JSON body (common fields):
  {
    "event_type": "SIGNUP_WELCOME" | "BOOKING_CONFIRMATION",
    "email": "recipient@example.com",
    ...event-specific fields...
  }
"""
import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ─── SMTP config (set via environment or .env) ───────────────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_NAME = os.environ.get("FROM_NAME", "HMS Hospital")
FROM_EMAIL = SMTP_USER


# ─── Template builders ────────────────────────────────────────────────────────

def _welcome_email(payload: dict) -> tuple[str, str]:
    name = payload.get("name", "User")
    role = payload.get("role", "")
    subject = f"Welcome to HMS, {name}!"
    body = f"""
<html><body style="font-family:sans-serif;max-width:500px;margin:0 auto;padding:24px;">
  <h2 style="color:#2563eb;">Welcome to HMS 🏥</h2>
  <p>Hi {name},</p>
  <p>Your account as a <strong>{role}</strong> has been created successfully.</p>
  {"<p>You can now set your availability slots so patients can book appointments.</p>" if role == "Doctor" else "<p>Browse available doctors and book your appointments from your dashboard.</p>"}
  <p style="margin-top:24px;color:#6b7280;font-size:13px;">
    This email was sent by Hospital Management System.<br>
    Please do not reply to this email.
  </p>
</body></html>
""".strip()
    return subject, body


def _booking_confirmation_email(payload: dict) -> tuple[str, str]:
    patient_name = payload.get("patient_name", "Patient")
    doctor_name = payload.get("doctor_name", "the doctor")
    date = payload.get("date", "")
    start_time = payload.get("start_time", "")
    end_time = payload.get("end_time", "")
    subject = f"Appointment Confirmed — {date} at {start_time}"
    body = f"""
<html><body style="font-family:sans-serif;max-width:500px;margin:0 auto;padding:24px;">
  <h2 style="color:#16a34a;">Appointment Confirmed ✅</h2>
  <p>Hi {patient_name},</p>
  <p>Your appointment has been booked successfully.</p>
  <table style="border-collapse:collapse;width:100%;margin:20px 0;">
    <tr><td style="padding:8px;color:#6b7280;font-size:13px;">Doctor</td><td style="padding:8px;font-weight:600;">{doctor_name}</td></tr>
    <tr><td style="padding:8px;color:#6b7280;font-size:13px;">Date</td><td style="padding:8px;font-weight:600;">{date}</td></tr>
    <tr><td style="padding:8px;color:#6b7280;font-size:13px;">Time</td><td style="padding:8px;font-weight:600;">{start_time} – {end_time}</td></tr>
  </table>
  <p>Please arrive 5 minutes early. If you need to cancel, contact the clinic directly.</p>
  <p style="margin-top:24px;color:#6b7280;font-size:13px;">
    Hospital Management System — automated notification.
  </p>
</body></html>
""".strip()
    return subject, body


EVENT_HANDLERS = {
    "SIGNUP_WELCOME": _welcome_email,
    "BOOKING_CONFIRMATION": _booking_confirmation_email,
}


# ─── SMTP sender ──────────────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, html_body: str) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        # Dev mode: just log the email
        logger.warning(
            "[DEV MODE — email not sent] To: %s | Subject: %s\n%s",
            to_email, subject, html_body,
        )
        print(f"\n{'='*60}")
        print(f"[DEV EMAIL] To: {to_email}")
        print(f"[DEV EMAIL] Subject: {subject}")
        print(f"[DEV EMAIL] Body preview: {html_body[:200]}...")
        print(f"{'='*60}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())

    logger.info("Email sent to %s: %s", to_email, subject)


# ─── Lambda / serverless-offline entry point ─────────────────────────────────

def send_email(event, context):
    """
    AWS Lambda handler (also works with serverless-offline locally).

    event["body"] is the raw JSON string from the HTTP POST body.
    """
    # Parse body
    try:
        if isinstance(event.get("body"), str):
            payload = json.loads(event["body"])
        else:
            payload = event.get("body") or {}
    except (json.JSONDecodeError, AttributeError) as exc:
        return _response(400, {"error": f"Invalid JSON: {exc}"})

    event_type = payload.get("event_type")
    to_email = payload.get("email") or payload.get("patient_email")

    if not event_type:
        return _response(400, {"error": "Missing event_type"})

    if not to_email:
        return _response(400, {"error": "Missing email address"})

    handler = EVENT_HANDLERS.get(event_type)
    if not handler:
        return _response(400, {"error": f"Unknown event_type: {event_type}. Valid: {list(EVENT_HANDLERS)}"})

    try:
        subject, html_body = handler(payload)
        _send_email(to_email, subject, html_body)
        return _response(200, {"status": "sent", "event_type": event_type, "to": to_email})
    except Exception as exc:
        logger.error("Failed to send %s email to %s: %s", event_type, to_email, exc)
        return _response(500, {"error": str(exc)})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
