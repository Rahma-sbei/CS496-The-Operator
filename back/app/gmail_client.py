"""Thin wrapper over the Gmail API. This is the ONLY module that talks to Gmail."""
from __future__ import annotations

import base64
import hashlib
import html
import re
import threading
from email.message import EmailMessage
from email.utils import parseaddr

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import SCOPES, settings
from .errors import GmailAuthError, ToolError

_creds: Credentials | None = None
_creds_lock = threading.Lock()
_local = threading.local()  # googleapiclient services are not thread-safe: one per thread


def _credentials() -> Credentials:
    global _creds
    with _creds_lock:
        if _creds is None:
            if not settings.token_path.exists():
                raise GmailAuthError("Gmail is not authorised. Run: python -m sandbox.auth")
            _creds = Credentials.from_authorized_user_file(str(settings.token_path), SCOPES)
        if not _creds.valid:
            if not _creds.refresh_token:
                raise GmailAuthError("Gmail token has no refresh token. Run: python -m sandbox.auth")
            try:
                _creds.refresh(Request())
            except RefreshError as e:
                raise GmailAuthError(
                    "Gmail token expired or was revoked (Testing-mode tokens last 7 days). "
                    "Run: python -m sandbox.auth"
                ) from e
            settings.token_path.write_text(_creds.to_json())
        return _creds


def service():
    svc = getattr(_local, "svc", None)
    if svc is None:
        svc = build("gmail", "v1", credentials=_credentials(), cache_discovery=False)
        _local.svc = svc
    return svc


# ---------- helpers ----------

def _headers(payload: dict) -> dict:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _b64(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _extract_text(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data")
    if mime == "text/plain" and data:
        return _b64(data)
    for part in payload.get("parts", []) or []:
        found = _extract_text(part)
        if found:
            return found
    if mime == "text/html" and data:
        return _strip_html(_b64(data))
    return ""


def _meta(email_id: str, headers: list[str]) -> dict:
    return (
        service().users().messages()
        .get(userId="me", id=email_id, format="metadata", metadataHeaders=headers)
        .execute()
    )


# ---------- reads ----------

def account_email() -> str:
    return service().users().getProfile(userId="me").execute()["emailAddress"]


def get_summary(email_id: str) -> dict:
    m = _meta(email_id, ["From", "Subject", "Date"])
    h = _headers(m["payload"])
    return {
        "id": m["id"],
        "thread_id": m["threadId"],
        "from": h.get("from", ""),
        "subject": h.get("subject", "(no subject)"),
        "date": h.get("date", ""),
        "snippet": m.get("snippet", ""),
        "labels": m.get("labelIds", []),
    }


def list_messages(query: str, max_results: int) -> list[dict]:
    resp = service().users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    return [get_summary(m["id"]) for m in resp.get("messages", [])]


def get_message(email_id: str) -> dict:
    m = service().users().messages().get(userId="me", id=email_id, format="full").execute()
    h = _headers(m["payload"])
    return {
        "id": m["id"],
        "from": h.get("from", ""),
        "to": h.get("to", ""),
        "subject": h.get("subject", "(no subject)"),
        "date": h.get("date", ""),
        "body": _extract_text(m["payload"]) or "(empty body)",
    }


def reply_address(email_id: str) -> str:
    """Recipient of a reply. Derived from the ORIGINAL email, never chosen by the model."""
    h = _headers(_meta(email_id, ["From", "Reply-To"])["payload"])
    return parseaddr(h.get("reply-to") or h.get("from", ""))[1]


# ---------- writes ----------

def archive(email_id: str) -> None:
    service().users().messages().modify(
        userId="me", id=email_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()


def trash(email_id: str) -> None:
    service().users().messages().trash(userId="me", id=email_id).execute()


def _ensure_label(name: str) -> str:
    labels = service().users().labels().list(userId="me").execute().get("labels", [])
    for lab in labels:
        if lab["name"].lower() == name.lower():
            return lab["id"]
    created = service().users().labels().create(
        userId="me",
        body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    return created["id"]


def add_label(email_id: str, label_name: str) -> None:
    label_id = _ensure_label(label_name)
    service().users().messages().modify(
        userId="me", id=email_id, body={"addLabelIds": [label_id]}
    ).execute()


def _find_draft(thread_id: str, key: str) -> str | None:
    """Idempotency: a draft in this thread carrying the same X-Operator-Key already exists."""
    drafts = service().users().drafts().list(userId="me", maxResults=50).execute().get("drafts", [])
    for d in drafts:
        msg = d.get("message", {})
        if msg.get("threadId") != thread_id:
            continue
        meta = _meta(msg["id"], ["X-Operator-Key"])
        if _headers(meta["payload"]).get("x-operator-key") == key:
            return d["id"]
    return None


def _build_reply(email_id: str, body: str):
    """Build the reply message. The recipient comes from the ORIGINAL email, never from the model."""
    m = _meta(email_id, ["From", "Reply-To", "Subject", "Message-ID", "References"])
    h = _headers(m["payload"])
    to = parseaddr(h.get("reply-to") or h.get("from", ""))[1]
    if not to:
        raise ToolError("The original email has no sender address, so a reply cannot be created.")
    subject = h.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    key = hashlib.sha256(f"{email_id}\n{body}".encode()).hexdigest()[:16]
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    if h.get("message-id"):
        msg["In-Reply-To"] = h["message-id"]
        msg["References"] = (h.get("references", "") + " " + h["message-id"]).strip()
    msg["X-Operator-Key"] = key
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw, "threadId": m["threadId"]}, to, key


def create_draft_reply(email_id: str, body: str) -> dict:
    message, to, key = _build_reply(email_id, body)
    existing = _find_draft(message["threadId"], key)
    if existing:
        return {"draft_id": existing, "to": to, "created": False}
    d = service().users().drafts().create(userId="me", body={"message": message}).execute()
    return {"draft_id": d["id"], "to": to, "created": True}


def _find_sent(thread_id: str, key: str) -> bool:
    """Idempotency: a SENT message in this thread already carries the same X-Operator-Key."""
    thread = service().users().threads().get(
        userId="me", id=thread_id, format="metadata", metadataHeaders=["X-Operator-Key"]
    ).execute()
    return any(
        "SENT" in msg.get("labelIds", []) and _headers(msg["payload"]).get("x-operator-key") == key
        for msg in thread.get("messages", [])
    )


def send_reply(email_id: str, body: str) -> dict:
    message, to, key = _build_reply(email_id, body)
    if _find_sent(message["threadId"], key):
        return {"to": to, "sent": False}
    service().users().messages().send(userId="me", body=message).execute()
    return {"to": to, "sent": True}
