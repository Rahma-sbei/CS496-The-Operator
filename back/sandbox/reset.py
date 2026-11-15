"""python -m sandbox.reset   (empties the TEST mailbox; see seed.py for the safety note)"""
from app import gmail_client

from .seed import reset_mailbox


def main() -> None:
    account = gmail_client.account_email()
    if input(f"Trash EVERYTHING in {account}? Type the address to confirm: ").strip() != account:
        raise SystemExit("Aborted.")
    print(f"Moved {reset_mailbox()} messages to Trash and deleted all drafts.")


if __name__ == "__main__":
    main()
