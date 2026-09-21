"""Guarded project-local transactions for the fixed set of generated files."""

from __future__ import annotations

import base64
import json
import os
import re
import stat
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .config import AtlasError, json_bytes, read_json
from .render import MANAGED_PATHS, digest

STATE = ".orchatlas/local/state.json"
RECEIPTS = ".orchatlas/local/receipts"
TRANSACTION_ID = re.compile(r"[0-9a-f]{32}\Z")


def checked_path(root: Path, relative: str = "") -> Path:
    # Check the user's original path before normalizing '..', so a link hidden
    # by lexical normalization cannot silently redirect the project boundary.
    raw_root = root.absolute()
    for item in (raw_root, *raw_root.parents):
        reparse = item.exists() and bool(getattr(item.lstat(), "st_file_attributes", 0) & 0x400)
        if item.is_symlink() or reparse:
            raise AtlasError(f"Linked paths are not supported: {item.name}")
    root = Path(os.path.abspath(raw_root))
    path = root / relative
    if not path.is_relative_to(root) or ".." in Path(relative).parts:
        raise AtlasError("Path must stay inside the selected project.")
    for item in (path, *path.parents):
        reparse = item.exists() and bool(getattr(item.lstat(), "st_file_attributes", 0) & 0x400)
        if item.is_symlink() or reparse:
            raise AtlasError(f"Linked paths are not supported: {item.name}")
    return path


def read_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise AtlasError(f"Expected a small regular file: {path.name}")
    return path.read_bytes()


def atomic_write(path: Path, data: bytes | None, mode: int | None = None) -> None:
    if data is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".orchatlas-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_manifest(root: Path, config: dict, expected: bytes | None = None) -> None:
    path = checked_path(root, "orchatlas.json")
    if read_bytes(path) != expected:
        raise AtlasError("orchatlas.json already exists or changed while reading; no changes made.")
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    atomic_write(path, json_bytes(config), mode)


def validate_state(state: object) -> dict:
    if not isinstance(state, dict) or set(state) != {"schema_version", "files", "history"} or state["schema_version"] != 1:
        raise AtlasError("Invalid installation state; inspect .orchatlas/local before continuing.")
    if not isinstance(state["files"], dict) or not set(state["files"]).issubset(MANAGED_PATHS):
        raise AtlasError("Installation state includes unknown managed paths.")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in state["files"].values()):
        raise AtlasError("Invalid installation hash.")
    if not isinstance(state["history"], list) or any(not isinstance(item, str) or not TRANSACTION_ID.fullmatch(item) for item in state["history"]):
        raise AtlasError("Invalid transaction history.")
    return state


def load_state(root: Path) -> dict:
    path = checked_path(root, STATE)
    if not path.exists():
        return {"schema_version": 1, "files": {}, "history": []}
    return validate_state(read_json(path))


@dataclass
class Change:
    path: str
    before: bytes | None
    after: bytes | None
    mode: int | None

    @property
    def action(self) -> str:
        return "remove" if self.after is None else ("create" if self.before is None else "update")


def plan(root: Path, outputs: dict[str, bytes]) -> tuple[list[Change], dict]:
    if not set(outputs).issubset(MANAGED_PATHS):
        raise AtlasError("Compiler requested an unmanaged output path.")
    checked_path(root)
    state = load_state(root)
    changes = []
    for name in sorted(set(outputs) | set(state["files"])):
        path = checked_path(root, name)
        before = read_bytes(path)
        if name in state["files"]:
            if digest(before) != state["files"][name]:
                raise AtlasError(f"Managed file changed outside OrchAtlas: {name}. Preserve/reconcile it before applying or undoing.")
        elif before is not None:
            raise AtlasError(f"Refusing to replace an existing unmanaged file: {name}.")
        after = outputs.get(name)
        if before != after:
            mode = stat.S_IMODE(path.stat().st_mode) if before is not None else None
            changes.append(Change(name, before, after, mode))
    return changes, state


@contextmanager
def project_lock(root: Path):
    root = checked_path(root)
    if not root.is_dir():
        raise AtlasError("The project directory must already exist.")
    private = checked_path(root, ".orchatlas/local")
    private.mkdir(parents=True, exist_ok=True)
    ignore = checked_path(root, ".orchatlas/local/.gitignore")
    existing = read_bytes(ignore)
    if existing not in (None, b"*\n"):
        raise AtlasError("The local backup ignore file has changed; inspect it before continuing.")
    if existing is None:
        atomic_write(ignore, b"*\n")
    path = checked_path(root, ".orchatlas/local/write.lock")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise AtlasError("Another transaction holds .orchatlas/local/write.lock. If interrupted, inspect receipts and files before removing that lock.") from None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def _apply_changes(root: Path, changes: list[Change], new_state: bytes | None) -> None:
    state_path = checked_path(root, STATE)
    state_before = read_bytes(state_path)
    completed = []
    try:
        for change in changes:
            path = checked_path(root, change.path)
            if read_bytes(path) != change.before:
                raise AtlasError(f"File changed during transaction: {change.path}")
            atomic_write(path, change.after, change.mode)
            completed.append(change)
        atomic_write(state_path, new_state)
    except BaseException:
        # Ordinary I/O failures and interrupts restore completed writes. Receipts
        # remain as evidence; power-loss recovery is deliberately not automatic.
        for change in reversed(completed):
            atomic_write(checked_path(root, change.path), change.before, change.mode)
        atomic_write(state_path, state_before)
        raise


def apply(root: Path, outputs: dict[str, bytes]) -> str | None:
    # Preflight before creating even the transaction directory.
    initial, _ = plan(root, outputs)
    if not initial:
        return None
    with project_lock(root):
        changes, state = plan(root, outputs)
        if not changes:
            return None
        transaction = uuid.uuid4().hex
        receipt = {"schema_version": 1, "id": transaction, "state_before": state,
                   "changes": [{"path": c.path, "before": base64.b64encode(c.before).decode() if c.before is not None else None,
                                "before_sha256": digest(c.before), "after_sha256": digest(c.after), "mode": c.mode} for c in changes]}
        receipt_path = checked_path(root, f"{RECEIPTS}/{transaction}.json")
        # Write the undo data before mutating any host files.
        atomic_write(receipt_path, json_bytes(receipt))
        new_state = {"schema_version": 1, "files": {name: digest(content) for name, content in outputs.items()},
                     "history": state["history"] + [transaction]}
        _apply_changes(root, changes, json_bytes(new_state))
        return transaction


def undo_plan(root: Path) -> tuple[list[Change], dict, str]:
    state = load_state(root)
    if not state["history"]:
        raise AtlasError("No applied transaction to undo.")
    # Verify every currently managed file, not just the most recently updated ones.
    for name, expected in state["files"].items():
        if digest(read_bytes(checked_path(root, name))) != expected:
            raise AtlasError(f"Refusing undo because a managed file changed: {name}.")
    transaction = state["history"][-1]
    receipt = read_json(checked_path(root, f"{RECEIPTS}/{transaction}.json"))
    if receipt.get("schema_version") != 1 or receipt.get("id") != transaction:
        raise AtlasError("Invalid undo receipt.")
    previous = validate_state(receipt.get("state_before"))
    if previous["history"] != state["history"][:-1]:
        raise AtlasError("Undo receipt history does not match installation state.")
    if not isinstance(receipt.get("changes"), list) or not receipt["changes"]:
        raise AtlasError("Undo receipt has no changes.")
    changes = []
    seen = set()
    for entry in receipt["changes"]:
        if not isinstance(entry, dict) or entry.get("path") not in MANAGED_PATHS or entry["path"] in seen:
            raise AtlasError("Undo receipt includes an unknown or duplicate path.")
        name = entry["path"]
        seen.add(name)
        current = read_bytes(checked_path(root, name))
        if digest(current) != entry.get("after_sha256") or entry.get("after_sha256") != state["files"].get(name):
            raise AtlasError(f"Refusing undo: file or receipt changed for {name}.")
        try:
            encoded = entry["before"]
            before = base64.b64decode(encoded, validate=True) if isinstance(encoded, str) else None
        except (KeyError, ValueError):
            raise AtlasError("Invalid backup content in receipt.") from None
        if (encoded is not None and not isinstance(encoded, str)) or digest(before) != entry.get("before_sha256") or digest(before) != previous["files"].get(name):
            raise AtlasError("Backup content no longer matches its recorded hash.")
        mode = entry.get("mode")
        if mode is not None and (type(mode) is not int or mode < 0 or mode > 0o777):
            raise AtlasError("Invalid file mode in receipt.")
        changes.append(Change(name, current, before, mode))
    # The receipt must account for all differences between the two inventories.
    expected_changes = {n for n in set(previous["files"]) | set(state["files"]) if previous["files"].get(n) != state["files"].get(n)}
    if seen != expected_changes:
        raise AtlasError("Undo receipt does not cover the installation changes.")
    return changes, previous, transaction


def undo(root: Path) -> str:
    undo_plan(root)
    with project_lock(root):
        changes, previous, transaction = undo_plan(root)
        _apply_changes(root, changes, json_bytes(previous) if previous["history"] else None)
        return transaction


def status(root: Path) -> dict:
    state = load_state(root)
    modified = [name for name, expected in state["files"].items()
                if digest(read_bytes(checked_path(root, name))) != expected]
    return {"installed": bool(state["history"]), "transactions": len(state["history"]),
            "managed_files": len(state["files"]), "modified_files": modified, "runtime_verified": False}
