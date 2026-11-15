"""Reset and seed the TEST mailbox.

    python -m sandbox.seed                 # reset, then insert all 21 emails
    python -m sandbox.seed --keys N1 Q1    # reset, then insert only these
    python -m sandbox.reset                # reset only (empty inbox)

SAFETY: this trashes EVERYTHING in the connected account. Only use a dedicated test account.
(With the narrow gmail.modify scope we cannot permanently delete, so reset = move to Trash
and delete drafts. Trashed mail is purged by Google after 30 days.)
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from app import gmail_client

from .seed_emails import BY_KEY, SEED_EMAILS


def reset_mailbox() -> int:
    svc = gmail_client.service()

    # 1. drafts (permanently deleted)
    token = None
    while True:
        resp = svc.users().drafts().list(userId="me", pageToken=token, maxResults=100).execute()
        for d in resp.get("drafts", []):
            svc.users().drafts().delete(userId="me", id=d["id"]).execute()
        token = resp.get("nextPageToken")
        if not token:
            break

    # 2. every remaining message -> Trash
    ids: list[str] = []
    token = None
    while True:
        resp = svc.users().messages().list(userId="me", pageToken=token, maxResults=500).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        token = resp.get("nextPageToken")
        if not token:
            break
    for i in range(0, len(ids), 1000):
        svc.users().messages().batchModify(
            userId="me",
            body={"ids": ids[i:i + 1000], "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX", "UNREAD"]},
        ).execute()
    return len(ids)


def _insert(email: dict, account: str) -> str:
    msg = EmailMessage()
    msg["From"] = email["sender"]
    msg["To"] = account
    msg["Subject"] = email["subject"]
    msg["Date"] = format_datetime(datetime.now(timezone.utc) - timedelta(hours=email["hours_ago"]))
    msg["Message-ID"] = make_msgid(domain="seed.example")
    msg["X-Seed-Key"] = email["key"]
    msg.set_content(email["body"])
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    resp = gmail_client.service().users().messages().insert(
        userId="me", internalDateSource="dateHeader",
        body={"raw": raw, "labelIds": ["INBOX", "UNREAD"]},
    ).execute()
    return resp["id"]


def seed_keys(keys: list[str] | None = None, reset: bool = True) -> dict[str, str]:
    """Reset (optional), insert the given seed emails, return {seed_key: gmail_id}."""
    if reset:
        reset_mailbox()
    account = gmail_client.account_email()
    wanted = [BY_KEY[k] for k in keys] if keys is not None else SEED_EMAILS
    # oldest first so the inbox order matches the dates
    wanted = sorted(wanted, key=lambda e: -e["hours_ago"])
    return {e["key"]: _insert(e, account) for e in wanted}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--keys", nargs="*", help="only seed these keys (default: all)")
    args = p.parse_args()
    account = gmail_client.account_email()
    print(f"Connected account: {account}")
    if input("This will TRASH everything in that account. Type the address to confirm: ").strip() != account:
        raise SystemExit("Aborted.")
    mapping = seed_keys(args.keys)
    print(f"Seeded {len(mapping)} emails.")


if __name__ == "__main__":
    main()
