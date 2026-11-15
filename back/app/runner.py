"""Runs the graph in a background thread so the extension can poll for progress,
and turns graph state into a simple JSON shape for the UI."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from .agent import graph_config, initial_state
from .tools import WRITE_TOOLS


def build_trace(messages) -> list[dict]:
    trace: list[dict] = []
    for m in messages:
        if isinstance(m, AIMessage):
            if m.tool_calls:
                for c in m.tool_calls:
                    trace.append({"kind": "call", "tool": c["name"], "args": c["args"],
                                  "write": c["name"] in WRITE_TOOLS})
        elif isinstance(m, ToolMessage):
            text = str(m.content)
            status = "ok"
            if text.startswith("Human denied"):
                status = "denied"
            elif text.startswith("Error"):
                status = "error"
            trace.append({
                "kind": "result", "tool": m.name, "text": text[:1500], "status": status,
                "wrote": m.name in WRITE_TOOLS and status == "ok" and not text.startswith("Already done"),
            })
    return trace


@dataclass
class RunRecord:
    id: str
    request: str
    status: str = "running"  # running | awaiting_approval | done | error
    trace: list = field(default_factory=list)
    pending: Optional[dict] = None
    final: Optional[str] = None
    stop_reason: Optional[str] = None
    error: Optional[str] = None
    stats: dict = field(default_factory=dict)
    started: float = field(default_factory=time.time)

    def absorb(self, values: dict) -> None:
        self.trace = build_trace(values.get("messages", []))
        self.stats = {k: values.get(k, 0) for k in ("steps", "tokens", "writes")}

    def to_dict(self) -> dict:
        return {
            "run_id": self.id, "status": self.status, "trace": self.trace, "pending": self.pending,
            "final": self.final, "stop_reason": self.stop_reason, "error": self.error,
            "stats": self.stats, "elapsed_s": round(time.time() - self.started, 1),
        }


class RunManager:
    def __init__(self, graph):
        self.graph = graph
        self.runs: dict[str, RunRecord] = {}

    def start(self, request: str) -> RunRecord:
        rid = uuid.uuid4().hex[:12]
        rec = RunRecord(id=rid, request=request)
        self.runs[rid] = rec
        threading.Thread(target=self._drive, args=(rid, initial_state(request)), daemon=True).start()
        return rec

    def decide(self, rid: str, approved: bool) -> RunRecord:
        rec = self.runs[rid]  # KeyError -> 404 in the API
        if rec.status != "awaiting_approval":
            raise ValueError("This run is not waiting for a decision.")
        rec.status, rec.pending = "running", None
        threading.Thread(
            target=self._drive, args=(rid, Command(resume={"approved": approved})), daemon=True
        ).start()
        return rec

    def get(self, rid: str) -> RunRecord:
        return self.runs[rid]

    def _drive(self, rid: str, payload) -> None:
        rec = self.runs[rid]
        config = graph_config(rid, tags=["extension"], metadata={"request": rec.request[:200]})
        try:
            for chunk in self.graph.stream(payload, config, stream_mode="values"):
                if isinstance(chunk, dict) and "messages" in chunk:
                    rec.absorb(chunk)
            snap = self.graph.get_state(config)
            rec.absorb(snap.values)
            if snap.next:
                pending = [i for t in snap.tasks for i in t.interrupts]
                rec.pending = pending[0].value
                rec.status = "awaiting_approval"
            else:
                last = snap.values["messages"][-1]
                rec.final = str(last.content) or "(no answer)"
                rec.stop_reason = snap.values.get("stop_reason")
                rec.status = "done"
        except Exception as e:  # noqa: BLE001
            rec.status = "error"
            rec.error = f"{type(e).__name__}: {e}"
