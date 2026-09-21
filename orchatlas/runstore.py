"""Private run checkpoints and working-tree evidence, without resetting user files."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from .config import AtlasError, json_bytes, read_json
from .storage import atomic_write, checked_path

RUNS = ".orchatlas/local/runs"
SKIP_DIRS = {".git", ".orchatlas", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}


def snapshot(project: Path) -> dict:
    """Capture hashes and bounded text for diffs against the actual initial workspace."""
    result = {}
    text_budget = 12_000_000
    try:
        listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                                cwd=project, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        listed = None
    if listed is not None and listed.returncode == 0:
        candidates = [project / os.fsdecode(name) for name in listed.stdout.split(b"\0") if name]
    else:
        candidates = []
        for parent, dirs, names in os.walk(project, followlinks=False):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (Path(parent) / d).is_symlink()]
            candidates.extend(Path(parent) / name for name in names)
            if len(candidates) > 20_000:
                raise AtlasError("Project is too large for the initial snapshot. Use a Git project with generated directories ignored.")
    if len(candidates) > 20_000:
        raise AtlasError("Project snapshot exceeds 20,000 files.")
    for candidate in sorted(set(candidates)):
        relative = candidate.relative_to(project)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if candidate.name.startswith(".env") and candidate.name != ".env.example":
            continue
        path = checked_path(project, str(relative))
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > 20_000_000:
            raise AtlasError(f"Snapshot file is too large: {relative}. Ignore generated/binary assets in Git first.")
        content = path.read_bytes()
        text = None
        if len(content) <= 300_000 and len(content) <= text_budget and b"\0" not in content:
            try:
                text = content.decode("utf-8")
                text_budget -= len(content)
            except UnicodeError:
                pass
        result[relative.as_posix()] = {"sha256": hashlib.sha256(content).hexdigest(), "text": text}
    return result


def changes(before: dict, after: dict) -> dict:
    files, diffs, remaining = [], [], 80_000
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old and new and old["sha256"] == new["sha256"]:
            continue
        files.append({"path": name, "action": "create" if old is None else "delete" if new is None else "modify"})
        left, right = (old or {}).get("text", ""), (new or {}).get("text", "")
        if left is None or right is None:
            diffs.append(f"{name}: binary or large file; inspect the current file directly.\n")
            continue
        patch = "".join(difflib.unified_diff(left.splitlines(True), right.splitlines(True),
                                            fromfile="before/" + name, tofile="after/" + name))
        if len(patch) > remaining:
            diffs.append(patch[:remaining] + "\n[Diff truncated; inspect remaining files directly.]\n")
            remaining = 0
        else:
            diffs.append(patch)
            remaining -= len(patch)
    return {"files": files, "diff": "\n".join(diffs), "truncated": remaining == 0}


class RunStore:
    def __init__(self, project: Path, run_id: str):
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise AtlasError("Run ID must contain 32 hexadecimal characters.")
        self.project, self.run_id = project, run_id
        self.directory = checked_path(project, RUNS + "/" + run_id)

    @classmethod
    def create(cls, project: Path, task: str, config: dict, *, context: str = ""):
        store = cls(project, uuid.uuid4().hex)
        store.directory.mkdir(parents=True)
        store.save({"schema_version": 1, "id": store.run_id, "project": str(project), "task": task,
                    "config": config, "context": context, "status": "created", "stage": "planning", "fix_round": 0,
                    "plan": None, "worker": None, "review": None, "sessions": {}, "notes": [],
                    "created_at": time.time(), "runtime_verified": False})
        return store

    def load(self):
        path = checked_path(self.project, RUNS + "/" + self.run_id + "/run.json")
        state = read_json(path)
        if state.get("schema_version") != 1 or state.get("id") != self.run_id or state.get("project") != str(self.project):
            raise AtlasError("Run checkpoint does not match this project.")
        if state.get("stage") not in ("planning", "implementing", "reviewing", "complete"):
            raise AtlasError("Run checkpoint has an invalid stage.")
        return state

    def save(self, state):
        state["updated_at"] = time.time()
        atomic_write(checked_path(self.project, RUNS + "/" + self.run_id + "/run.json"), json_bytes(state), 0o600)

    def baseline(self, value=None):
        path = checked_path(self.project, RUNS + "/" + self.run_id + "/baseline.json")
        if value is not None:
            atomic_write(path, json_bytes(value), 0o600)
        else:
            # The baseline intentionally has a larger bound than small manifests.
            if not path.is_file() or path.stat().st_size > 100_000_000:
                raise AtlasError("Missing or oversized run baseline.")
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                raise AtlasError("Invalid run baseline.") from None

    def event(self, kind, data):
        path = checked_path(self.project, RUNS + "/" + self.run_id + "/events.jsonl")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": time.time(), "event": kind, **data}, ensure_ascii=False) + "\n")

    def report(self, state):
        lines = ["# OrchAtlas run", "", f"Status: {state['status']}", f"Run: {self.run_id}",
                 "", "## Task", "", state["task"], "", "## Team", "",
                 "Codex / ChatGPT: planner and reviewer. OpenCode: " + state["config"]["hosts"]["opencode"]["builder"]["model"] + " for implementation.", ""]
        if state.get("reason"):
            lines += ["## Next action", "", state["reason"], ""]
        if state.get("worker"):
            lines += ["## Implementation", "", state["worker"]["text"], ""]
        if state.get("review"):
            review = state["review"]["result"]
            lines += ["## Review", "", review["summary"], "", *["- " + f for f in review["findings"]], ""]
        if state.get("changes"):
            lines += ["## Changed files", "", *[f"- {f['action']}: {f['path']}" for f in state["changes"]["files"]], ""]
        path = checked_path(self.project, RUNS + "/" + self.run_id + "/REPORT.md")
        atomic_write(path, "\n".join(lines).encode("utf-8"), 0o600)
        return str(path)


def list_runs(project):
    directory = checked_path(project, RUNS)
    if not directory.exists():
        return []
    result = []
    for path in sorted(directory.iterdir()):
        if re.fullmatch(r"[0-9a-f]{32}", path.name):
            state = RunStore(project, path.name).load()
            result.append({key: state[key] for key in ("id", "status", "stage", "updated_at")})
    return sorted(result, key=lambda item: item["updated_at"], reverse=True)
