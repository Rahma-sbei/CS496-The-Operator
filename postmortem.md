# Postmortem

Format: date, what happened, root cause, fix, what we learned.

## 2026-11-15: Google login blocked (error 403 access_denied)
- **What happened:** `python -m sandbox.auth` opened Google's login page and showed "Access blocked: gmail-operator has not completed the Google verification process".
- **Root cause:** The OAuth app is in Testing mode, and only accounts listed under Test users may log in. The test account was not on the list.
- **Fix:** Added the test account under Audience, Test users in Google Cloud Console, then ran the login again.
- **Lesson:** Testing mode only admits listed accounts, and its tokens expire after 7 days. Add the test user first, and re-run the login before the demo.

## 2026-11-15: Approval bar always visible in the side panel
- **What happened:** The Approve and Deny buttons and an empty Summary box showed even when nothing was waiting for a decision.
- **Root cause:** In `sidepanel.css`, `.gate` sets `display: grid`, which overrides the HTML `hidden` attribute. The tests did not catch it because they never run the extension.
- **Fix:** Added `[hidden] { display: none !important; }` at the top of `sidepanel.css`.
- **Lesson:** A checkpoint that looks always on teaches people to click without reading. The UI needs its own check, because the offline tests only cover the backend.

## 2026-11-15: OpenAI returned 429, credit_balance_exhausted
- **What happened:** Every run ended with "OpenAIRateLimitError: You have no credits remaining". The key was correct.
- **Root cause:** The shared class key has no credits left. We confirmed this with one direct request to the OpenAI API that skipped our code. Nothing in our code or `.env` was wrong.
- **Fix:** Asked the professor to check the balance and expiry of the key's project.
- **Lesson:** Test the key with one direct request before debugging the code. A shared budget is an outside dependency that can fail without warning. The agent handled it safely: the run ended with status `error`, the panel showed the message, and nothing was written to the mailbox.
