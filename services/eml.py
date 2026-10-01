"""Outlook draft emails. Access displayed each email in Outlook for the user to check and send;
the portal gives a .eml file marked as unsent, which Outlook opens as an editable draft."""
from email.message import EmailMessage
from email.policy import SMTP


def _addresses(s):
    """Access/Outlook lists use ';' — e-mail headers need ',' or only the first address is read."""
    return ", ".join(a.strip() for a in (s or "").replace(";", ",").split(",") if a.strip())


def build_eml(to, cc, subject, html, attachments=None):
    msg = EmailMessage(policy=SMTP)
    msg["X-Unsent"] = "1"            # Outlook: open as a new draft with a Send button
    msg["To"] = _addresses(to)
    if cc:
        msg["Cc"] = _addresses(cc)
    msg["Subject"] = subject
    msg.set_content("This message is in HTML format.")
    msg.add_alternative(f"<html><body style=\"font-family:Calibri,Arial,sans-serif;font-size:11pt\">{html}</body></html>",
                        subtype="html")
    for name, data, mime in attachments or []:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return msg.as_bytes()
