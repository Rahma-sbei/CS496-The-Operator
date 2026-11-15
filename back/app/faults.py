"""Fault injection for the eval: make a tool fail once, then work again."""
import threading

from .errors import ToolError

_armed: set[str] = set()
_lock = threading.Lock()


def arm(*tool_names: str) -> None:
    with _lock:
        _armed.update(tool_names)


def clear() -> None:
    with _lock:
        _armed.clear()


def maybe_fail(tool_name: str) -> None:
    with _lock:
        if tool_name in _armed:
            _armed.discard(tool_name)
            raise ToolError("Gmail is temporarily unavailable (simulated fault). Retry this call once.")
