import json
import subprocess
import sys
import tomllib
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orchatlas project ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()

    def cli(self, command, *args, expected=0):
        result = subprocess.run([sys.executable, "-m", "orchatlas", command, "--project", str(self.project),
                                 "--json", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def test_complete_dual_host_lifecycle_with_model_choices(self):
        self.cli("init", "--recipe", "reviewed", "--set", "codex.builder=gpt-5.6-terra")
        self.cli("set", "opencode.builder", "openai/gpt-5.2", "--effort", "medium")
        self.assertEqual(self.cli("validate")["status"], "static-valid")
        before = list(self.project.iterdir())
        preview = self.cli("preview", "--diff")
        self.assertEqual(list(self.project.iterdir()), before)
        self.assertTrue(preview["changes"])
        self.assertEqual(self.cli("apply")["status"], "applied")
        self.assertEqual(self.cli("apply")["status"], "unchanged")
        self.assertEqual(self.cli("status")["pending_changes"], 0)
        self.cli("use", "lean@0.1.0")
        config = json.loads((self.project / "orchatlas.json").read_text())
        self.assertEqual(config["hosts"]["codex"]["builder"]["model"], "gpt-5.6-terra")
        self.assertGreater(self.cli("status")["pending_changes"], 0)
        self.cli("apply")
        self.assertEqual(self.cli("undo")["status"], "preview")
        self.assertFalse((self.project / ".codex/agents/orchatlas_reviewer.toml").exists())
        self.cli("undo", "--apply")
        self.assertTrue((self.project / ".codex/agents/orchatlas_reviewer.toml").exists())
        self.cli("undo", "--apply")
        self.assertFalse(self.cli("status")["installed"])
        self.assertTrue((self.project / "orchatlas.json").exists())

    def test_init_is_non_destructive_and_errors_are_machine_readable(self):
        self.cli("init")
        original = (self.project / "orchatlas.json").read_bytes()
        self.assertEqual(self.cli("init", expected=2)["status"], "error")
        self.assertEqual((self.project / "orchatlas.json").read_bytes(), original)

    def test_invalid_model_does_not_change_manifest(self):
        self.cli("init")
        original = (self.project / "orchatlas.json").read_bytes()
        self.cli("set", "opencode.builder", "unknown-without-provider", expected=2)
        self.assertEqual((self.project / "orchatlas.json").read_bytes(), original)

    def test_single_host_does_not_create_other_host_files(self):
        self.cli("init", "--host", "opencode")
        self.cli("apply")
        self.assertFalse((self.project / ".codex").exists())
        self.assertTrue((self.project / ".opencode/agents/orchatlas.md").exists())

    def test_invalid_init_override_creates_nothing(self):
        self.cli("init", "--set", "codex.builder", expected=2)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_custom_catalog_is_snapshotted_without_network_updates(self):
        catalog = {"schema_version": 1, "catalog_version": "local.1", "recipes": [{
            "id": "my-team", "version": "1.0.0", "title": "My team", "description": "A local recipe.",
            "review": "independent", "max_fix_rounds": 3, "evidence": "unbenchmarked"}]}
        path = self.project / "recipes.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        self.cli("init", "--catalog", str(path), "--recipe", "my-team@1.0.0")
        path.unlink()
        self.assertEqual(self.cli("validate")["recipe"], "my-team@1.0.0")

    def test_recipe_model_defaults_require_explicit_adoption_on_update(self):
        self.cli("init", "--recipe", "lean")
        catalog = str(ROOT / "examples/recipes.json")
        self.cli("use", "my-team@1.0.0", "--catalog", catalog)
        config = json.loads((self.project / "orchatlas.json").read_text())
        self.assertEqual(config["hosts"]["codex"]["builder"]["model"], "inherit")
        self.cli("use", "my-team@1.0.0", "--catalog", catalog, "--with-models")
        config = json.loads((self.project / "orchatlas.json").read_text())
        self.assertEqual(config["hosts"]["codex"]["builder"]["model"], "gpt-5.6-terra")
        self.assertEqual(config["hosts"]["opencode"]["builder"]["model"], "anthropic/claude-sonnet-4-5-20250929")

    def test_main_team_uses_astra_for_planning_review_and_flash_for_writing(self):
        self.assertEqual(self.cli("init")["recipe"], "astra-flash")
        preview = self.cli("preview")
        self.assertFalse(preview["runtime_verified"])
        self.assertIn("--model gpt-6-astra", preview["launch"]["codex"])
        self.assertTrue(any("provider/router" in warning for warning in preview["warnings"]))
        self.cli("apply")
        for role, model in (("builder", "deepseek/deepseek-v4.1-flash"), ("reviewer", "gpt-6-astra")):
            agent = tomllib.loads((self.project / f".codex/agents/orchatlas_{role}.toml").read_text())
            self.assertEqual(agent["model"], model)
            self.assertEqual(agent["model_reasoning_effort"], "high")
        for name, model in (("orchatlas", "openai/gpt-6-astra"),
                            ("orchatlas-builder", "deepseek/deepseek-flash"),
                            ("orchatlas-reviewer", "openai/gpt-6-astra")):
            text = (self.project / f".opencode/agents/{name}.md").read_text()
            header = text.split("---", 2)[1]
            fields = {key: json.loads(value) for line in header.strip().splitlines()
                      for key, value in [line.split(":", 1)]}
            self.assertEqual(fields["model"], model)
        self.assertEqual(self.cli("status")["pending_changes"], 0)

    def test_catalog_default_can_change_without_migrating_existing_projects(self):
        self.cli("init", "--recipe", "lean")
        self.cli("set", "codex.builder", "custom/worker")
        self.cli("use", "astra-flash@0.1.0")
        path = self.project / "orchatlas.json"
        self.assertEqual(json.loads(path.read_text())["hosts"]["codex"]["builder"]["model"], "custom/worker")
        self.cli("use", "astra-flash@0.1.0", "--with-models")
        config = json.loads(path.read_text())
        self.assertEqual(config["hosts"]["codex"]["builder"]["model"], "deepseek/deepseek-v4.1-flash")


if __name__ == "__main__":
    unittest.main()
