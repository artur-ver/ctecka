import imaplib
import email
import os
import sys

EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.zoner.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))

if not EMAIL_FROM or not EMAIL_PASSWORD:
    print("Set EMAIL_FROM and EMAIL_PASSWORD env vars.")
    sys.exit(2)

mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_FROM, EMAIL_PASSWORD)
mail.select("inbox")

status, data = mail.search(None, "ALL")
mail_ids = data[0].split()
if not mail_ids:
    print("Inbox is empty.")
    mail.logout()
    sys.exit(0)
latest_email_id = mail_ids[-1]

status, data = mail.fetch(latest_email_id, "(RFC822)")
raw_email = data[0][1]
msg = email.message_from_bytes(raw_email)

subject = msg["subject"]
from_ = msg["from"]
if msg.is_multipart():
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            body = part.get_payload(decode=True).decode()
            break
else:
    body = msg.get_payload(decode=True).decode()

print("From:", from_)
print("Subject:", subject)
print("Body:", body)
mail.logout()
