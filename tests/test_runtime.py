import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from orchatlas.clients import Codex, OpenCode, NativeClients
from orchatlas.config import AtlasError, new_config
from orchatlas.runstore import RunStore, changes, list_runs, snapshot
from orchatlas.runtime import doctor, run, runtime_roles
from orchatlas.storage import project_lock

FIXTURE = Path(__file__).with_name("fake_clients.py")


class FixtureClients(NativeClients):
    processes = []

    def __enter__(self):
        try:
            self.codex = Codex(self.project, self.timeout, self.emit, [sys.executable, "-u", str(FIXTURE), "codex"])
            self.processes.append(self.codex.process.process)
            self.opencode = OpenCode(self.project, self.roles["builder"], self.timeout, self.emit, self.approve,
                                     [sys.executable, "-u", str(FIXTURE), "opencode"],
                                     key_check=lambda key: {"valid": False, "reason": "OpenRouter key validation failed (HTTP 401). Use /login openrouter."}
                                     if os.environ.get("ORCHATLAS_TEST_SCENARIO") == "bad-stored-key" else {"valid": key == "synthetic-token"})
            self.processes.append(self.opencode.process.process)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        FixtureClients.processes = []
        self.addCleanup(self.assert_processes_stopped)

    def assert_processes_stopped(self):
        for process in FixtureClients.processes:
            self.assertIsNotNone(process.poll(), f"Leaked process {process.pid}")

    def execute(self, scenario="success", **kwargs):
        with patch.dict("os.environ", {"ORCHATLAS_TEST_SCENARIO": scenario}):
            return run(self.root, "Create a file; preserve existing work.", factory=FixtureClients, timeout=10, **kwargs)

    def methods(self):
        path = self.root / ".orchatlas/local/fake-requests.jsonl"
        return [json.loads(line)["method"] for line in path.read_text().splitlines()]

    def test_combined_run_writes_files_and_accepts_only_after_codex_review(self):
        existing = self.root / "existing.txt"
        existing.write_text("user work", encoding="utf-8")
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue(result["runtime_verified"])
        self.assertEqual(existing.read_text(), "user work")
        state = RunStore(self.root, result["run_id"]).load()
        self.assertEqual(state["changes"]["files"], [{"path": "generated.txt", "action": "create"}])
        self.assertNotEqual(state["sessions"]["planner"], state["sessions"]["reviewer"])
        self.assertEqual(self.methods().count("turn/start"), 2)
        self.assertTrue(Path(result["report"]).is_file())
        self.assertEqual(list_runs(self.root)[0]["status"], "completed")

    def test_doctor_never_starts_model_turns_or_implementation(self):
        result = doctor(self.root, factory=FixtureClients)
        self.assertEqual(result["status"], "ready")
        self.assertNotIn("turn/start", self.methods())
        self.assertNotIn("POST /session", self.methods())

    def test_subscription_and_provider_prerequisites_fail_before_inference(self):
        for scenario in ("api-key", "missing-deepseek"):
            with self.subTest(scenario=scenario):
                result = self.execute(scenario)
                self.assertEqual(result["status"], "blocked", result)
                self.assertFalse(result["runtime_verified"])
                self.assertNotIn("turn/start", self.methods())
                self.assertFalse((self.root / "generated.txt").exists())

    def test_corrections_reuse_worker_session_then_review_again(self):
        result = self.execute("revise")
        self.assertEqual(result["status"], "completed", result)
        state = RunStore(self.root, result["run_id"]).load()
        self.assertEqual(state["fix_round"], 1)
        self.assertEqual(self.methods().count("POST /session"), 1)
        self.assertEqual((self.root / "generated.txt").read_text(), "implementation 2\n")

    def test_failed_review_stops_at_actual_correction_limit(self):
        result = self.execute("never-accept")
        self.assertEqual(result["status"], "blocked", result)
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(self.methods().count("POST /session/ses_fixture/message"), 3)

    def test_worker_failure_preserves_files_and_never_reports_acceptance(self):
        result = self.execute("worker-error")
        self.assertEqual(result["status"], "failed", result)
        self.assertTrue((self.root / "generated.txt").exists())
        self.assertEqual(self.methods().count("turn/start"), 1)

    def test_provider_credential_rejection_is_actionable_and_redacted(self):
        result = self.execute("invalid-credential")
        self.assertEqual(result["status"], "blocked", result)
        self.assertIn("HTTP 401", result["reason"])
        self.assertIn("/login openrouter", result["reason"])
        self.assertEqual(self.methods().count("turn/start"), 1)
        for path in (self.root / ".orchatlas/local/runs" / result["run_id"]).iterdir():
            self.assertNotIn("synthetic-secret", path.read_text(encoding="utf-8"))

    def test_invalid_stored_openrouter_key_blocks_before_spending_model_quota(self):
        result = self.execute("bad-stored-key")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("/login openrouter", result["reason"])
        self.assertNotIn("turn/start", self.methods())

    def test_model_substitution_blocks_acceptance(self):
        result = self.execute("wrong-model")
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.methods().count("turn/start"), 1)

    def test_concurrent_edit_during_review_requires_another_review(self):
        result = self.execute("concurrent-edit")
        self.assertEqual(result["status"], "blocked", result)
        self.assertIn("changed during review", result["reason"])
        self.assertFalse(result["runtime_verified"])

    def test_snapshot_failure_is_saved_as_a_failed_run(self):
        with patch("orchatlas.runtime.snapshot", side_effect=AtlasError("Synthetic snapshot failure")):
            result = self.execute()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(list_runs(self.root)[0]["status"], "failed")
        self.assertFalse(FixtureClients.processes)

    def test_turn_timeout_stops_clients_and_keeps_a_checkpoint(self):
        with patch.dict("os.environ", {"ORCHATLAS_TEST_SCENARIO": "timeout"}):
            result = run(self.root, "Create a file.", factory=FixtureClients, timeout=1)
        self.assertEqual(result["status"], "failed", result)
        self.assertIn("timed out", result["reason"])
        self.assertFalse((self.root / "generated.txt").exists())

    def test_blocked_plan_never_dispatches_a_writer(self):
        result = self.execute("blocked-plan")
        self.assertEqual(result["status"], "blocked", result)
        self.assertIn("Which content", result["reason"])
        self.assertNotIn("POST /session", self.methods())

    def test_malformed_plan_cannot_dispatch_a_writer(self):
        result = self.execute("bad-json")
        self.assertEqual(result["status"], "failed", result)
        self.assertNotIn("POST /session", self.methods())

    def test_resume_retains_files_and_saved_team_after_provider_login(self):
        first = self.execute("missing-deepseek")
        (self.root / "user-note.txt").write_text("keep this", encoding="utf-8")
        with patch.dict("os.environ", {"ORCHATLAS_TEST_SCENARIO": "success"}):
            result = run(self.root, resume=first["run_id"], note="Continue now.", factory=FixtureClients, timeout=10)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["run_id"], first["run_id"])
        self.assertEqual((self.root / "user-note.txt").read_text(), "keep this")

    def test_cancel_keeps_checkpoint_and_resume_does_not_replan(self):
        def cancel(kind, data):
            if kind == "stage" and data["stage"] == "implementing":
                raise KeyboardInterrupt
        first = self.execute(emit=cancel)
        self.assertEqual(first["status"], "cancelled")
        self.assertEqual(first["stage"], "implementing")
        result = run(self.root, resume=first["run_id"], factory=FixtureClients, timeout=10)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(self.methods().count("turn/start"), 2)

    def test_permissions_are_forwarded_once_instead_of_auto_approved(self):
        requested = []
        result = self.execute("permission", approve=lambda request: requested.append(request) or True)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(len(requested), 1)
        self.assertEqual(requested[0]["permission"], "bash")

    def test_noninteractive_permission_request_blocks_and_cleans_up(self):
        result = self.execute("permission")
        self.assertEqual(result["status"], "blocked", result)
        self.assertFalse((self.root / "generated.txt").exists())

    def test_run_lock_blocks_a_second_writer(self):
        with project_lock(self.root):
            with self.assertRaisesRegex(AtlasError, "transaction"):
                self.execute()

    def test_snapshot_compares_to_preexisting_work_and_ignores_private_state(self):
        (self.root / "code.txt").write_text("user modification\n", encoding="utf-8")
        (self.root / ".env").write_text("SECRET=never-copy", encoding="utf-8")
        before = snapshot(self.root)
        (self.root / "code.txt").write_text("user modification\nnew line\n", encoding="utf-8")
        patch = changes(before, snapshot(self.root))
        self.assertNotIn(".env", before)
        self.assertIn("+new line", patch["diff"])
        self.assertNotIn("-user modification", patch["diff"])

    def test_inherited_or_routed_codex_model_is_not_a_subscription_team(self):
        with self.assertRaisesRegex(AtlasError, "explicit native"):
            runtime_roles(new_config("lean"))

    def test_invalid_resume_path_and_completed_run_are_refused(self):
        with self.assertRaises(AtlasError):
            run(self.root, resume="../elsewhere", factory=FixtureClients)
        first = self.execute()
        with self.assertRaisesRegex(AtlasError, "complete"):
            run(self.root, resume=first["run_id"], factory=FixtureClients)


if __name__ == "__main__":
    unittest.main()
