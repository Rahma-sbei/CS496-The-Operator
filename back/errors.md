# Error taxonomy

For each class: what the agent does, and the test that shows it. Fill the "Result" column from your eval run.

| Class | What happens | Agent behaviour | Test | Result |
|---|---|---|---|---|
| Tool down / Gmail 5xx / rate limit | `execute()` returns "Gmail is temporarily unavailable... retry once" | Retries once, then explains | `test_injected_fault_fails_once_then_recovers`, eval `fault-*` | |
| Bad arguments (malformed id, label outside allowlist) | Pydantic validation fails before anything runs | Reads the error, fixes the call | `test_invalid_arguments_are_rejected...`, `test_label_outside_allowlist...` | |
| Unknown / forbidden tool (`send_email`) | "unknown tool" error | Tells the user it cannot do that | `test_unknown_tool_like_send_email...`, eval `refuse-*` | |
| Empty result | "No emails found for this query." | Reports, stops | eval `empty-inbox` | |
| Email not found (404) | "email not found... call list_emails" | Re-lists | (add a test) | |
| Wrong tool / wrong target | Approval card shows the exact call; scripted approver denies | Continues or explains | eval `attempts` with `forbidden=True` | |
| Loop (model never finishes) | Hard step cap, token cap | Forced stop with a message | `test_stop_rule_holds_when_model_loops_forever`, `test_token_budget...` | |
| Repeated write | Signature already in `done_writes` | "Already done", no second approval | `test_same_write_twice_executes_once_and_asks_once` | |
| Too many writes | `max_writes` cap | "write limit reached" | `test_write_cap_per_run` | |
| Timeout / model API error | Run ends with status `error`, shown in the UI | User re-runs | (add a test with a failing fake LLM) | |
| User changes mind | Denial returned as normal text | Does not retry the denied call | eval `user-denies` | |
| Expired Google token (7 days in Testing mode) | `GmailAuthError` with the fix in the message | Tells the user | manual: delete `token.json`, call `/health` | |
