"""Every tool call is logged: input, output, time. (LangSmith also traces them.)"""
import json
import threading
import time

from .config import settings

_lock = threading.Lock()


def log_tool_call(run_id: str, tool: str, args: dict, result: str, approved, duration_ms: int) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_id": run_id,
        "tool": tool,
        "args": args,
        "approved": approved,  # None for reads
        "result": result[:1000],
        "duration_ms": duration_ms,
    }
    with _lock, open(settings.log_dir / "tool_calls.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
