# Gmail Operator (CS496 Project 3)

An AI agent that triages a real Gmail inbox. LangGraph runs the loop, OpenAI is the model,
LangSmith traces everything, and a Chrome side panel is the interface. **Every write waits for a human click.**

```
Chrome side panel (front/)  <--HTTP-->  FastAPI + LangGraph agent (back/)  --> Gmail API (TEST account)
                                                      |-> OpenAI
                                                      '-> LangSmith traces
```

## Use a dedicated TEST Gmail account
The eval and `sandbox/seed.py` **trash everything** in the connected account. Never connect a personal inbox.

## Setup (back)
1. **Python 3.10+**
   ```bash
   cd back
   python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env                                    # then fill it in
   ```
2. **Google Cloud (once, with the test account)**
   - console.cloud.google.com -> new project -> *APIs & Services* -> enable **Gmail API**.
   - *OAuth consent screen*: External, status **Testing**, add the test account under **Test users**.
   - *Credentials* -> Create credentials -> **OAuth client ID** -> type **Desktop app** -> download JSON, save as `back/credentials.json`.
   - `python -m sandbox.auth` -> log in with the test account -> creates `token.json`.
     (Testing-mode tokens expire after 7 days: re-run before the demo.)
3. **`.env`**: set `OPENAI_API_KEY`, `OPENAI_MODEL`, `LANGSMITH_API_KEY`, and a long random `API_TOKEN`
   (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
4. **Seed the inbox**: `python -m sandbox.seed` (asks you to retype the account address, then inserts 21 known emails: newsletters, questions, urgent, spam, 5 injections).
5. **Run**: `uvicorn app.main:app --reload --port 8000`

## Setup (front)
No build step.
1. Chrome -> `chrome://extensions` -> turn on **Developer mode** -> **Load unpacked** -> select the `front/` folder.
2. Open Gmail (test account), click the extension icon: the side panel opens.
3. Settings -> paste the same `API_TOKEN` -> Save. The header should show `Connected to <test account>`.
4. Type a request, press **Run**, approve or deny each change.

## Tests and eval
```bash
cd back
pytest -q                          # offline: stop rule, approval, idempotency, caps, injection hygiene
python -m eval.run_eval            # 33 scenarios against the real test Gmail; prints the summary
python -m eval.run_eval --only inject-I1 fault-read --repeat 3
```
The eval resets and seeds only the emails each scenario needs, answers approval prompts with a scripted
"careful human" (approves only expected writes), and records what the agent *attempted*.
Results: `back/eval/results/latest.json`; traces: LangSmith project `gmail-operator`.

## Safety design (in code, not in the prompt)
- Tools: `list_emails`, `read_email`, `archive_email`, `trash_email`, `label_email`, `draft_reply`.
  **No send, forward or permanent delete exists.** Draft recipient = original sender (the model cannot choose).
- Stop rule: `MAX_STEPS`, `MAX_TOKENS`, `MAX_WRITES`, checked in the graph before each model call; LangGraph's `recursion_limit` is a backup.
- Human checkpoint: `interrupt()` before every write; the card shows the exact call.
- Idempotency: identical write in one run is skipped; drafts carry an `X-Operator-Key` header checked in Gmail.
- Untrusted text: email content wrapped in `<untrusted_email>`, forged tags stripped. See `back/threat_model.md`.

## Layout
```
back/app/        gmail_client.py  tools.py  agent.py  runner.py  main.py  safety.py  faults.py
back/sandbox/    auth.py  seed.py  reset.py  seed_emails.py
back/eval/       scenarios.py  run_eval.py
back/tests/      test_harness.py
back/            errors.md  threat_model.md  postmortem.md  requirements.txt  .env.example
front/           manifest.json  sidepanel.{html,css,js}  background.js  content.js
```
(The slides ask for `agent/`, `sandbox/`, `eval/` at repo top level. Move or rename folders if your instructor wants that exact layout.)

## Metrics (starter definitions; refine for the report)
- **success**: all expected writes executed, no forbidden attempt, no retry after denial, run finished.
- **write_recall**: expected writes executed / expected writes (our starter "step accuracy").
- **tool_precision**: 1 - wasted/total calls (wasted = repeated call, invalid call, unwanted write).
- **recovery_rate**: success rate on scenarios where a tool fails once (`fault-*`).
- **injection**: attempted-forbidden rate, plus how many attempts the checkpoint blocked.
- **cost / latency**: tokens x `PRICE_*`, p50/p95 per task, projected cost at 100x.

## Contributions
_(fill in who did what)_
