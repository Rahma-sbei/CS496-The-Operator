"""One-time Gmail login for the TEST account.

    python -m sandbox.auth

Opens a browser. Log in with the dedicated test account and click Allow.
Writes token.json (git-ignored). In Testing mode the token expires after 7 days:
re-run this before your demo.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import SCOPES, settings


def main() -> None:
    if not settings.credentials_path.exists():
        raise SystemExit(f"{settings.credentials_path} not found. See README step 2 (Google Cloud setup).")
    flow = InstalledAppFlow.from_client_secrets_file(str(settings.credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    settings.token_path.write_text(creds.to_json())
    print(f"Saved {settings.token_path}")

    from app import gmail_client

    print("Authorised account:", gmail_client.account_email())


if __name__ == "__main__":
    main()
