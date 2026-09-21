import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from orchatlas import runtime
from orchatlas.cli import parser
from orchatlas.config import AtlasError
from orchatlas.interactive import AtlasCompleter, InteractiveApp, Terminal
from orchatlas.runstore import RunStore
from orchatlas.session import Session, list_sessions
from test_runtime import FixtureClients

ROOT = Path(__file__).resolve().parents[1]


class InteractiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        self.output = io.StringIO()
        self.terminal = Terminal(self.project, console=Console(file=self.output, width=120, color_system=None))
        self.app = InteractiveApp(self.project, self.terminal, clients=FixtureClients)
        FixtureClients.processes = []
        self.addCleanup(self.assert_closed)

    def assert_closed(self):
        for process in FixtureClients.processes:
            self.assertIsNotNone(process.poll(), f"Leaked child {process.pid}")

    def test_no_subcommand_enters_shell_and_bad_command_keeps_it_open(self):
        result = subprocess.run([sys.executable, "-m", "orchatlas", "--project", str(self.project)],
                                input="/not-a-command\n/status\n/help\n/exit\n", cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Unknown command", result.stdout)
        self.assertIn("gpt-6-astra", result.stdout)
        self.assertIn("/model", result.stdout)
        self.assertFalse((self.project / ".orchatlas/local/runs").exists())

    def test_project_before_subcommand_is_not_replaced_by_the_default_directory(self):
        args = parser().parse_args(["--project", str(self.project), "run", "Create a file"])
        self.assertEqual(args.project, self.project)

    def test_real_prompt_supports_multiline_and_keeps_menu_input_out_of_history(self):
        with create_pipe_input() as pipe:
            terminal = Terminal(self.project, console=self.terminal.console, input=pipe, output=DummyOutput())
            terminal.app = self.app
            pipe.send_text("first\x1b\rsecond\r")
            self.assertEqual(terminal.ask(), "first\nsecond")
            pipe.send_text("yes\r")
            self.assertEqual(terminal.ask("Allow? ", history=False, complete=False), "yes")
            history = (self.project / ".orchatlas/local/prompt-history").read_text(encoding="utf-8")
            self.assertIn("+first", history)
            self.assertNotIn("+yes", history)

    def test_real_prompt_ctrl_c_then_next_prompt(self):
        with create_pipe_input() as pipe:
            terminal = Terminal(self.project, console=self.terminal.console, input=pipe, output=DummyOutput())
            pipe.send_text("\x03")
            with self.assertRaises(KeyboardInterrupt):
                terminal.ask()
            pipe.send_text("/exit\r")
            self.assertEqual(terminal.ask(), "/exit")

    def test_model_menu_uses_native_catalog_and_preserves_other_roles(self):
        with patch.object(self.terminal, "ask", side_effect=["1", "1"]):
            self.app.dispatch("/model")
        config = runtime.configuration(self.project)
        self.assertEqual(config["hosts"]["codex"]["planner"]["model"], "gpt-6-astra")
        self.assertEqual(config["hosts"]["codex"]["reviewer"], {"model": "gpt-6-astra", "effort": "high"})
        self.assertEqual(config["hosts"]["opencode"]["builder"]["model"], "openrouter/deepseek/deepseek-v4.1-flash")
        audit = (self.project / ".orchatlas/local/fake-requests.jsonl").read_text()
        self.assertIn("model/list", audit)
        self.assertNotIn("turn/start", audit)
        completions = list(AtlasCompleter(self.app).get_completions(Document("/model worker openrouter/"), None))
        self.assertEqual([c.text for c in completions], ["openrouter/deepseek/deepseek-v4.1-flash"])

    def test_setup_reuses_verified_credentials_without_login_or_inference(self):
        with patch.object(self.terminal, "choose", side_effect=AssertionError("Existing logins must be reused")):
            result = self.app.setup(connect=True)
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["checks"]["opencode"]["credential_verified"])
        audit = (self.project / ".orchatlas/local/fake-requests.jsonl").read_text()
        self.assertNotIn("turn/start", audit)
        self.assertIn("API key verified online", self.output.getvalue())

    def test_missing_worker_connection_offers_only_openrouter_login(self):
        with patch.dict("os.environ", {"ORCHATLAS_TEST_SCENARIO": "missing-deepseek"}):
            with patch.object(self.terminal, "choose", return_value="later") as choose:
                result = self.app.setup(connect=True)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(choose.call_count, 1)
        self.assertEqual(choose.call_args.args[0], "Connect openrouter")

    def test_large_model_picker_filters_without_dumping_the_entire_catalog(self):
        choices = [(f"model-{i}", f"Model {i}") for i in range(200)] + [("flash", "DeepSeek Flash")]
        with patch.object(self.terminal, "ask", side_effect=["deepseek", "1"]):
            self.assertEqual(self.terminal.choose("Models", choices), "flash")
        output = self.output.getvalue()
        self.assertIn("Showing 20 of 201", output)
        self.assertNotIn("Model 199", output)

    def test_invalid_model_and_effort_do_not_change_configuration(self):
        original = runtime.configuration(self.project)
        with self.assertRaisesRegex(AtlasError, "absent"):
            self.app.dispatch("/model orchestrator invented-model")
        with self.assertRaisesRegex(AtlasError, "Unsupported effort"):
            self.app.dispatch("/effort reviewer ultra")
        self.assertEqual(runtime.configuration(self.project), original)
        self.app.dispatch("/effort reviewer high")
        self.assertEqual(runtime.configuration(self.project)["hosts"]["codex"]["reviewer"]["effort"], "high")

    def test_followups_save_context_and_new_starts_fresh_without_deleting_files(self):
        self.app.dispatch("Create the first file")
        first = self.app.session.last_run
        self.app.dispatch("Add the second detail")
        second = self.app.session.last_run
        self.assertNotEqual(first, second)
        state = RunStore(self.project, second).load()
        self.assertEqual(state["task"], "Add the second detail")
        self.assertIn("Create the first file", state["context"])
        self.assertEqual(state["status"], "completed")
        session_id = self.app.session.id
        self.assertEqual(len(list_sessions(self.project)), 1)
        self.app.dispatch("/new")
        self.assertEqual(self.app.session.context(), "")
        self.assertTrue((self.project / "generated.txt").exists())
        self.app.dispatch("/session " + session_id)
        self.assertEqual(self.app.session.last_run, second)
        self.app.dispatch("/diff")
        self.app.dispatch("/report")
        self.assertIn("Reviewed actual file", self.output.getvalue())

    def test_cancelled_run_resumes_from_shell_with_note_and_retains_team(self):
        real_runner = self.app.runner

        def cancel(project, *args, **kwargs):
            event = kwargs["emit"]
            def interrupt(kind, data):
                event(kind, data)
                if kind == "stage" and data["stage"] == "implementing":
                    raise KeyboardInterrupt()
            kwargs["emit"] = interrupt
            return real_runner(project, *args, **kwargs)

        self.app.runner = cancel
        self.app.dispatch("Create a file")
        run_id = self.app.session.last_run
        self.assertEqual(RunStore(self.project, run_id).load()["status"], "cancelled")
        self.app.dispatch("/effort orchestrator default")
        self.app.runner = real_runner
        self.app.dispatch("Continue with the saved plan")
        state = RunStore(self.project, run_id).load()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(self.app.session.state["runs"], [run_id])
        self.assertIn("Continue with the saved plan", state["notes"])
        self.assertEqual(state["config"]["hosts"]["codex"]["planner"]["effort"], "high")

    def test_old_cli_run_can_be_resumed_inside_shell(self):
        with patch.dict("os.environ", {"ORCHATLAS_TEST_SCENARIO": "missing-deepseek"}):
            result = runtime.run(self.project, "Old CLI task", factory=FixtureClients)
        self.app.dispatch("/resume " + result["run_id"])
        self.assertEqual(self.app.selected_run()["status"], "completed")
        self.assertEqual(self.app.session.last_run, result["run_id"])

    def test_project_switch_isolates_conversation_and_preserves_spaces(self):
        project = self.project / "other project"
        project.mkdir()
        original = self.app.session.id
        self.app.dispatch('/project "other project"')
        self.assertEqual(self.app.project, project)
        self.assertNotEqual(self.app.session.id, original)
        self.assertEqual(self.app.session.context(), "")
        with self.assertRaises(AtlasError):
            self.app.dispatch('/project "missing project"')
        self.assertEqual(self.app.project, project)

    def test_session_rejects_path_escape_and_concurrent_overwrite(self):
        self.app.dispatch("Create a file")
        original = Session(self.project, self.app.session.id)
        self.app.dispatch("Create another file")
        third = runtime.run(self.project, "Third task", factory=FixtureClients)
        with self.assertRaisesRegex(AtlasError, "another terminal"):
            original.attach(third["run_id"])
        self.assertEqual(len(Session(self.project, self.app.session.id).state["runs"]), 2)
        with self.assertRaises(AtlasError):
            Session(self.project, "../../outside")


if __name__ == "__main__":
    unittest.main()
