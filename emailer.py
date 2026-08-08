"""
emailer.py
Sends personalized emails with attachments via SMTP.

Configure real sending through environment variables:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS, FROM_EMAIL

If SMTP_HOST is not set, the app runs in DRY_RUN mode: emails are not
actually sent, but are logged to data/outbox/ as .eml-style text files so
the full workflow can be demoed and reviewed without live credentials.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

from documents import merge_fields

OUTBOX_DIR = os.path.join(os.path.dirname(__file__), "data", "outbox")
os.makedirs(OUTBOX_DIR, exist_ok=True)

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "hr@example.com")

DRY_RUN = not bool(SMTP_HOST)


def is_dry_run():
    return DRY_RUN


def send_email(candidate, subject_template, body_template, attachment_path=None):
    """
    Merges templates with candidate data and sends (or simulates sending) the email.
    Returns (success: bool, detail: str)
    """
    subject = merge_fields(subject_template, candidate)
    body = merge_fields(body_template, candidate)
    to_addr = candidate.get("email", "")

    if not to_addr or "@" not in to_addr:
        return False, f"Invalid recipient email: '{to_addr}'"

    if DRY_RUN:
        return _simulate_send(candidate, subject, body, attachment_path)

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_addr
        msg.set_content(body)

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                data = f.read()
            msg.add_attachment(
                data, maintype="application", subtype="pdf",
                filename=os.path.basename(attachment_path),
            )

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls(context=context)
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return True, f"Sent to {to_addr}"
    except Exception as e:
        return False, f"SMTP error: {e}"


def _simulate_send(candidate, subject, body, attachment_path):
    """Write the composed email to disk so the workflow can be reviewed/demoed."""
    safe_name = "".join(c if c.isalnum() else "_" for c in candidate["name"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{candidate['id']}_{safe_name}_{ts}.txt"
    filepath = os.path.join(OUTBOX_DIR, filename)

    with open(filepath, "w") as f:
        f.write(f"To: {candidate.get('email')}\n")
        f.write(f"From: {FROM_EMAIL}\n")
        f.write(f"Subject: {subject}\n")
        f.write(f"Attachment: {os.path.basename(attachment_path) if attachment_path else '(none)'}\n")
        f.write("-" * 60 + "\n\n")
        f.write(body)

    return True, f"[DRY RUN] Email composed and saved to outbox (no SMTP configured): {filename}"
