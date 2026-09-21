import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchatlas.config import AtlasError, new_config, set_model
from orchatlas.render import render
from orchatlas import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = new_config("reviewed")
        self.outputs = render(self.config)

    def test_preview_is_read_only_and_apply_is_idempotent(self):
        changes, _ = storage.plan(self.root, self.outputs)
        self.assertEqual(len(changes), len(self.outputs))
        self.assertEqual(list(self.root.iterdir()), [])
        transaction = storage.apply(self.root, self.outputs)
        self.assertIsNotNone(transaction)
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertIsNone(storage.apply(self.root, self.outputs))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_unmanaged_collision_refuses_all_writes_even_if_content_matches(self):
        name = ".opencode/agents/orchatlas.md"
        path = self.root / name
        path.parent.mkdir(parents=True)
        path.write_bytes(self.outputs[name])
        with self.assertRaisesRegex(AtlasError, "unmanaged"):
            storage.apply(self.root, self.outputs)
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / ".orchatlas").exists())

    def test_preserves_host_configs_and_unrelated_agents(self):
        originals = {"AGENTS.md": b"project instructions\r\n", ".codex/config.toml": b'model = "other"\r\n',
                     "opencode.jsonc": b'{ // comment\n "model": "custom/model"\n}',
                     ".codex/agents/user.toml": b'name = "user"\n'}
        for name, content in originals.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        storage.apply(self.root, self.outputs)
        storage.undo(self.root)
        for name, content in originals.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_update_and_multiple_undos_restore_exact_previous_bytes(self):
        first = storage.apply(self.root, self.outputs)
        set_model(self.config, "codex.builder", "gpt-5.6", "high")
        next_outputs = render(self.config)
        second = storage.apply(self.root, next_outputs)
        self.assertNotEqual(first, second)
        self.assertEqual(storage.undo(self.root), second)
        for name, content in self.outputs.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertEqual(storage.undo(self.root), first)
        self.assertTrue(all(not (self.root / name).exists() for name in self.outputs))
        self.assertFalse(storage.status(self.root)["installed"])
        self.assertEqual((self.root / ".orchatlas/local/.gitignore").read_bytes(), b"*\n")

    def test_switching_workflow_removes_only_owned_obsolete_roles_and_undo_restores(self):
        storage.apply(self.root, self.outputs)
        lean = render(new_config("lean"))
        changes, _ = storage.plan(self.root, lean)
        self.assertEqual({c.path for c in changes if c.after is None},
                         {".codex/agents/orchatlas_reviewer.toml", ".opencode/agents/orchatlas-reviewer.md"})
        storage.apply(self.root, lean)
        self.assertFalse((self.root / ".codex/agents/orchatlas_reviewer.toml").exists())
        storage.undo(self.root)
        self.assertEqual((self.root / ".codex/agents/orchatlas_reviewer.toml").read_bytes(), self.outputs[".codex/agents/orchatlas_reviewer.toml"])

    def test_drift_blocks_update_and_undo_without_discarding_edits(self):
        storage.apply(self.root, self.outputs)
        name = ".codex/agents/orchatlas_builder.toml"
        (self.root / name).write_bytes(b"user change")
        with self.assertRaisesRegex(AtlasError, "changed"):
            storage.apply(self.root, render(new_config()))
        with self.assertRaisesRegex(AtlasError, "changed"):
            storage.undo(self.root)
        self.assertEqual((self.root / name).read_bytes(), b"user change")
        self.assertEqual(storage.status(self.root)["modified_files"], [name])

    def test_missing_managed_file_is_also_drift(self):
        storage.apply(self.root, self.outputs)
        (self.root / ".orchatlas/START.md").unlink()
        with self.assertRaises(AtlasError):
            storage.undo(self.root)

    def test_io_error_rolls_back_installation(self):
        actual = storage.atomic_write
        fail_at = sorted(self.outputs)[2]
        fired = False

        def failing(path, data, mode=None):
            nonlocal fired
            if path == self.root / fail_at and not fired:
                fired = True
                raise OSError("synthetic write error")
            return actual(path, data, mode)

        with patch.object(storage, "atomic_write", side_effect=failing):
            with self.assertRaises(OSError):
                storage.apply(self.root, self.outputs)
        self.assertTrue(fired)
        self.assertTrue(all(not (self.root / name).exists() for name in self.outputs))
        self.assertFalse(storage.status(self.root)["installed"])
        self.assertFalse((self.root / ".orchatlas/local/write.lock").exists())

    def test_state_write_error_restores_previous_installation(self):
        storage.apply(self.root, self.outputs)
        state_before = (self.root / storage.STATE).read_bytes()
        actual = storage.atomic_write
        fired = False

        def failing(path, data, mode=None):
            nonlocal fired
            if path == self.root / storage.STATE and not fired:
                fired = True
                raise OSError("synthetic state error")
            return actual(path, data, mode)

        with patch.object(storage, "atomic_write", side_effect=failing):
            with self.assertRaises(OSError):
                storage.apply(self.root, render(new_config()))
        self.assertEqual((self.root / storage.STATE).read_bytes(), state_before)
        for name, content in self.outputs.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_receipt_tampering_cannot_restore_outside_owned_paths(self):
        transaction = storage.apply(self.root, self.outputs)
        receipt_path = self.root / storage.RECEIPTS / (transaction + ".json")
        receipt = json.loads(receipt_path.read_text())
        receipt["changes"][0]["path"] = "../outside.txt"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(AtlasError, "unknown or duplicate"):
            storage.undo(self.root)
        self.assertTrue((self.root / ".orchatlas/lock.json").exists())

    def test_receipt_must_cover_every_change(self):
        transaction = storage.apply(self.root, self.outputs)
        receipt_path = self.root / storage.RECEIPTS / (transaction + ".json")
        receipt = json.loads(receipt_path.read_text())
        receipt["changes"].pop()
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(AtlasError, "cover"):
            storage.undo(self.root)

    def test_unknown_state_paths_are_rejected(self):
        path = self.root / storage.STATE
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 1, "files": {"../outside": "a" * 64}, "history": []}))
        with self.assertRaisesRegex(AtlasError, "unknown"):
            storage.plan(self.root, self.outputs)

    def test_concurrent_writer_lock_blocks_mutation(self):
        with storage.project_lock(self.root):
            with self.assertRaisesRegex(AtlasError, "transaction"):
                storage.apply(self.root, self.outputs)
        self.assertFalse((self.root / ".codex").exists())

    def test_manifest_writes_require_matching_previous_content(self):
        storage.save_manifest(self.root, self.config)
        with self.assertRaisesRegex(AtlasError, "already exists"):
            storage.save_manifest(self.root, self.config)
        before = (self.root / "orchatlas.json").read_bytes()
        (self.root / "orchatlas.json").write_bytes(b"user edit")
        with self.assertRaises(AtlasError):
            storage.save_manifest(self.root, self.config, before)

    def test_link_check_without_platform_specific_privileges(self):
        actual = Path.is_symlink
        destination = self.root / ".codex"
        with patch.object(Path, "is_symlink", lambda path: path == destination or actual(path)):
            with self.assertRaisesRegex(AtlasError, "Linked"):
                storage.plan(self.root, self.outputs)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_parent_relative_project_path_is_supported_without_resolving_links(self):
        (self.root / "nested").mkdir()
        self.assertEqual(storage.checked_path(self.root / "nested/.."), self.root)
        actual = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda p: p == self.root / "nested" or actual(p)):
            with self.assertRaisesRegex(AtlasError, "Linked"):
                storage.checked_path(self.root / "nested/..")


if __name__ == "__main__":
    unittest.main()
