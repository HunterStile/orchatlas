import json
import tomllib
import unittest

from orchatlas.config import new_config, set_model
from orchatlas.render import MANAGED_PATHS, digest, launch_commands, render


def frontmatter(data):
    # The generator's YAML values are JSON; parse that subset with stdlib.
    header = data.decode().split("---", 2)[1]
    return {key: json.loads(value) for line in header.strip().splitlines()
            for key, value in [line.split(":", 1)]}


class RenderTests(unittest.TestCase):
    def test_codex_pins_selected_models_and_disables_recursive_workers(self):
        config = new_config("reviewed", ("codex",))
        set_model(config, "codex.builder", "gpt-5.6-terra", "medium")
        outputs = render(config)
        builder = tomllib.loads(outputs[".codex/agents/orchatlas_builder.toml"].decode())
        self.assertEqual(builder["model"], "gpt-5.6-terra")
        self.assertEqual(builder["model_reasoning_effort"], "medium")
        self.assertFalse(builder["agents"]["enabled"])
        reviewer = tomllib.loads(outputs[".codex/agents/orchatlas_reviewer.toml"].decode())
        self.assertEqual(reviewer["sandbox_mode"], "read-only")
        self.assertNotIn("model", reviewer)
        self.assertFalse(any(name.startswith(".opencode") for name in outputs))

    def test_opencode_primary_and_children_have_distinct_permissions(self):
        config = new_config("reviewed", ("opencode",))
        set_model(config, "opencode.planner", "openai/gpt-5.2", "high")
        outputs = render(config)
        primary = frontmatter(outputs[".opencode/agents/orchatlas.md"])
        self.assertEqual(primary["mode"], "primary")
        self.assertEqual(primary["model"], "openai/gpt-5.2")
        self.assertEqual(primary["reasoningEffort"], "high")
        self.assertEqual(primary["permission"]["task"]["orchatlas-builder"], "allow")
        builder = frontmatter(outputs[".opencode/agents/orchatlas-builder.md"])
        self.assertEqual(builder["permission"]["task"], "deny")
        review = frontmatter(outputs[".opencode/agents/orchatlas-reviewer.md"])
        self.assertEqual(review["permission"]["*"], "deny")
        self.assertEqual(review["permission"]["read"]["*"], "allow")
        self.assertEqual(review["permission"]["read"]["*.env"], "ask")
        self.assertNotIn("bash", review["permission"])

    def test_lean_has_no_independent_reviewer(self):
        outputs = render(new_config())
        self.assertFalse(any("reviewer" in name for name in outputs))
        primary = frontmatter(outputs[".opencode/agents/orchatlas.md"])
        self.assertNotIn("orchatlas-reviewer", primary["permission"]["task"])

    def test_lock_captures_exact_manifest_and_output_hashes(self):
        config = new_config()
        first = render(config)
        self.assertEqual(first, render(config))
        lock = json.loads(first[".orchatlas/lock.json"])
        self.assertEqual(lock["manifest"], config)
        self.assertFalse(lock["runtime_verified"])
        for path, expected in lock["files"].items():
            self.assertEqual(digest(first[path]), expected)
        set_model(config, "codex.builder", "gpt-5.6")
        self.assertNotEqual(first[".orchatlas/lock.json"], render(config)[".orchatlas/lock.json"])

    def test_only_namespaced_project_files_are_generated(self):
        outputs = render(new_config("reviewed"))
        self.assertTrue(set(outputs).issubset(MANAGED_PATHS))
        for name in ("AGENTS.md", ".codex/config.toml", "opencode.json", "auth.json"):
            self.assertNotIn(name, outputs)

    def test_planner_settings_are_applied_at_codex_launch_not_to_a_fake_primary_role(self):
        config = new_config()
        set_model(config, "codex.planner", "gpt-5.6", "high")
        commands = launch_commands(config)
        self.assertIn("--model gpt-5.6", commands["codex"])
        self.assertIn('model_reasoning_effort="high"', commands["codex"])
        self.assertFalse(any("planner.toml" in name for name in render(config)))


if __name__ == "__main__":
    unittest.main()
