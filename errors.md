# Error taxonomy

For each class: what the agent does, and the test that shows it. "Offline" means the pytest suite in `back/tests` (fake model, fake Gmail); "Eval" means the live scenarios in `back/eval`. Eval results are filled in after the eval run.

| Class | What happens | Agent behaviour | Test | Result |
|---|---|---|---|---|
| Tool down / Gmail 5xx / rate limit | `execute()` returns "Gmail is temporarily unavailable... retry once" | Retries once, then explains | `test_injected_fault_fails_once_then_recovers`, eval `fault-*` | Offline: pass. Eval: pending |
| Bad arguments (malformed id, label outside allowlist) | Pydantic validation fails before anything runs | Reads the error, fixes the call | `test_invalid_arguments_are_rejected...`, `test_label_outside_allowlist...` | Offline: pass |
| Unknown / forbidden tool (`send_email`) | "unknown tool" error | Tells the user it cannot do that | `test_unknown_tool_like_send_email...`, eval `refuse-*` | Offline: pass. Eval: pending |
| Empty result | "No emails found for this query." | Reports, stops | eval `empty-inbox` | |
| Email not found (404) | "email not found... call list_emails" | Re-lists | `test_email_not_found_gives_a_readable_error` | Offline: pass |
| Wrong tool / wrong target | Approval card shows the exact call; scripted approver denies | Continues or explains | eval `attempts` with `forbidden=True` | |
| Loop (model never finishes) | Hard step cap, token cap | Forced stop with a message | `test_stop_rule_holds_when_model_loops_forever`, `test_token_budget...` | Offline: pass |
| Repeated write | Signature already in `done_writes` | "Already done", no second approval | `test_same_write_twice_executes_once_and_asks_once`, `test_same_send_twice_sends_once_and_asks_once` | Offline: pass |
| Too many writes | `max_writes` cap | "write limit reached" | `test_write_cap_per_run` | Offline: pass |
| Timeout / model API error | Run ends with status `error`, shown in the UI | User re-runs | `test_model_api_error_ends_the_run_with_error_status` | Offline: pass. Observed live 2026-11-15: OpenAI 429, run ended with status `error`, message shown in the panel, no write happened |
| User changes mind | Denial returned as normal text | Does not retry the denied call | eval `user-denies` | |
| Expired Google token (7 days in Testing mode) | `GmailAuthError` with the fix in the message | Tells the user | manual: delete `token.json`, call `/health` | |
