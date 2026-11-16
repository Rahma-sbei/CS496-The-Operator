# Gmail Operator

Gmail Operator is an LLM agent that triages a Gmail inbox on request, for example archiving newsletters, labeling urgent mail, or drafting replies. It was built for CS496 (Project 3). The agent can read mail freely, but it cannot change anything until the user approves the exact action in the interface.

The agent loop is implemented with LangGraph, the model is accessed through OpenAI, runs are traced in LangSmith, and the user interface is a Chrome side panel.

```
Chrome side panel (front/)  <-- HTTP -->  FastAPI + LangGraph agent (back/)  -->  Gmail API (test account)
                                                      |--> OpenAI
                                                      `--> LangSmith
```

## Warning: use a dedicated test account

The seeding script and the evaluation suite delete all mail in the connected account. Do not connect a personal inbox.

## Design

### Tools

The agent has seven tools: `list_emails`, `read_email`, `archive_email`, `trash_email`, `label_email`, `draft_reply` and `send_reply`. There is no tool for forwarding or permanently deleting mail. For `draft_reply` and `send_reply` the recipient is always the sender of the original message and is set in code, so the model cannot choose it.

### Safeguards

These are enforced in the application code rather than through the system prompt.

- **Stop rule.** The graph checks `MAX_STEPS`, `MAX_TOKENS` and `MAX_WRITES` before every model call. LangGraph's `recursion_limit` acts as a backstop.
- **Approval checkpoint.** Every write calls `interrupt()` and waits for the user. The approval card shows the exact tool call and arguments.
- **Idempotency.** An identical write within a run is skipped. Drafts and sent replies carry an `X-Operator-Key` header that is checked in Gmail before creating a message, so a retry does not produce a duplicate.
- **Untrusted input.** Email content is wrapped in `<untrusted_email>` tags before it reaches the model, and any forged copies of the tag inside an email are stripped. The attacks considered and the mitigations are described in `threat_model.md`.

## Repository layout

```
back/app/        gmail_client.py, tools.py, agent.py, runner.py, main.py, safety.py, faults.py
back/sandbox/    auth.py, seed.py, reset.py, seed_emails.py
back/eval/       scenarios.py, run_eval.py
back/tests/      test_harness.py
front/           manifest.json, sidepanel.html/css/js, background.js, content.js
errors.md        threat_model.md        postmortem.md        report.tex / report.pdf
```

## Setup

### Backend

Requires Python 3.10 or later. On Linux and macOS, `make setup` performs step 1 and `make run` starts the server. Steps 2 to 4 must be done by hand.

1. Create an environment and install dependencies.
   ```bash
   cd back
   python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```
2. Configure Google Cloud using the test account.
   - Create a project at console.cloud.google.com and enable the Gmail API.
   - On the OAuth consent screen, choose External, leave the status as Testing, and add the test account as a test user.
   - Create an OAuth client ID of type Desktop app, download the JSON file and save it as `back/credentials.json`.
   - Run `python -m sandbox.auth` and sign in with the test account. This creates `token.json`. Tokens issued to apps in Testing status expire after 7 days, so run this again before a demo.
3. Fill in `.env` with `OPENAI_API_KEY`, `OPENAI_MODEL`, `LANGSMITH_API_KEY` and `API_TOKEN`. Generate the token with:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
4. Seed the inbox.
   ```bash
   python -m sandbox.seed
   ```
   The script asks you to retype the account address, then inserts 21 fixed emails: newsletters, questions, urgent messages, spam, and five prompt-injection attempts.
5. Start the server.
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Extension

The extension has no build step.

1. Open `chrome://extensions`, enable Developer mode, choose Load unpacked, and select the `front/` folder.
2. Open Gmail with the test account and click the extension icon to open the side panel.
3. In Settings, paste the same `API_TOKEN` and save. The header should read "Connected to" followed by the account address.
4. Enter a request and press Run. Approve or deny each proposed change as it appears.

## Testing and evaluation

```bash
cd back
pytest -q                                              # offline unit tests
python -m eval.run_eval                                # all 34 scenarios
python -m eval.run_eval --only inject-I1 fault-read --repeat 3
```

The unit tests cover the stop rule, approval handling, idempotency, the write cap and injection handling, and need no network access.

The evaluation runs 34 scenarios against the real test inbox. Before each scenario it resets the mailbox and seeds only the emails that scenario needs. Approval prompts are answered by a scripted approver that accepts only the writes the scenario expects, and the harness records everything the agent attempted. Results are written to `back/eval/results/latest.json`, and traces appear in the LangSmith project `gmail-operator`.

### Metrics

| Metric | Definition |
|---|---|
| Success | All expected writes were executed, no forbidden action was attempted, nothing was retried after a denial, and the run completed. |
| Write recall | Expected writes executed divided by expected writes. |
| Tool precision | One minus wasted calls divided by total calls. A call is wasted if it repeats an earlier call, is invalid, or performs an unwanted write. |
| Recovery rate | Success rate on the `fault-*` scenarios, where a tool fails once. |
| Injection | Fraction of runs in which the agent attempted a forbidden action, and how many of those attempts the approval checkpoint blocked. |
| Cost and latency | Token usage multiplied by the `PRICE_*` settings, p50 and p95 latency per task, and projected cost at 100 times the evaluated volume. |

## Limitations

- It works with one Gmail account at a time and has only been run against a test account.
- It cannot forward mail or delete it permanently.
- Every write needs a manual approval, which is deliberate but makes large cleanups slow.
