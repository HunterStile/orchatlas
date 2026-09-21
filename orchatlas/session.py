"""Project-local conversations link resumable runs and supply bounded follow-up context."""

from __future__ import annotations

import json
from pathlib import Path
import re
import time
import uuid

from .config import AtlasError, json_bytes, read_json
from .runstore import RunStore
from .storage import atomic_write, checked_path, read_bytes

SESSIONS = ".orchatlas/local/sessions"
ID = re.compile(r"[0-9a-f]{32}\Z")


class Session:
    def __init__(self, project: Path, session_id: str | None = None):
        self.project = checked_path(project)
        self.id = session_id or uuid.uuid4().hex
        if not ID.fullmatch(self.id):
            raise AtlasError("Session ID must contain 32 hexadecimal characters.")
        self.path = checked_path(self.project, f"{SESSIONS}/{self.id}.json")
        self.expected = read_bytes(self.path)
        if session_id:
            self.state = read_json(self.path)
            if (self.state.get("schema_version") != 1 or self.state.get("id") != self.id
                    or self.state.get("project") != str(self.project)
                    or not isinstance(self.state.get("runs"), list)
                    or any(not isinstance(item, str) or not ID.fullmatch(item) for item in self.state["runs"])):
                raise AtlasError("Invalid conversation checkpoint.")
        else:
            self.state = {"schema_version": 1, "id": self.id, "project": str(self.project),
                          "title": "New conversation", "runs": [], "updated_at": time.time()}

    @property
    def last_run(self):
        return self.state["runs"][-1] if self.state["runs"] else None

    def attach(self, run_id: str):
        run = RunStore(self.project, run_id).load()
        if run_id in self.state["runs"]:
            if run_id != self.last_run:
                raise AtlasError("This run is earlier in the conversation. Use /new before resuming it separately.")
            return
        if len(self.state["runs"]) >= 1000:
            raise AtlasError("Conversation is full. Use /new to start another.")
        if not self.state["runs"]:
            self.state["title"] = run["task"][:100]
        self.state["runs"].append(run_id)
        self.state["updated_at"] = time.time()
        if read_bytes(self.path) != self.expected:
            self.state["runs"].pop()
            raise AtlasError("This conversation changed in another terminal. Reopen it with /session or use /new.")
        data = json_bytes(self.state)
        atomic_write(self.path, data, 0o600)
        self.expected = data

    def context(self):
        # Fixed-size excerpts avoid recursively carrying previous prompts forever.
        entries = []
        for run_id in self.state["runs"][-6:]:
            run = RunStore(self.project, run_id).load()
            review = (run.get("review") or {}).get("result", {})
            entries.append({"user": run["task"][:2500], "follow_up": "\n".join(run["notes"])[-1500:],
                            "status": run["status"], "result": review.get("summary", "")[:1500],
                            "files": [f["path"] for f in run.get("changes", {}).get("files", [])][:20]})
        text = json.dumps(entries, ensure_ascii=False)
        while len(text) > 32_000 and entries:
            entries.pop(0)
            text = json.dumps(entries, ensure_ascii=False)
        return text if entries else ""


def list_sessions(project: Path):
    directory = checked_path(project, SESSIONS)
    if not directory.exists():
        return []
    result = []
    for path in directory.glob("*.json"):
        if ID.fullmatch(path.stem):
            state = Session(project, path.stem).state
            result.append({key: state[key] for key in ("id", "title", "runs", "updated_at")})
    return sorted(result, key=lambda s: s["updated_at"], reverse=True)
