import copy
import json
import tempfile
import unittest
from pathlib import Path

from orchatlas.config import (AtlasError, new_config, read_json, recipe_catalog,
                             set_model, validate)


class ConfigTests(unittest.TestCase):
    def test_starter_supports_both_hosts_and_discloses_inheritance(self):
        config = new_config("lean")
        self.assertEqual(set(config["hosts"]), {"codex", "opencode"})
        self.assertEqual(sum("not pinned" in warning for warning in validate(config)), 6)

    def test_recipe_snapshot_is_independent_of_catalog_edits(self):
        catalog = recipe_catalog()
        config = new_config("lean", catalog=catalog)
        catalog["recipes"][0]["max_fix_rounds"] = 5
        self.assertEqual(config["recipe"]["max_fix_rounds"], 1)

    def test_exact_recipe_version_resolves_ambiguity(self):
        catalog = recipe_catalog()
        newer = copy.deepcopy(catalog["recipes"][0])
        newer["version"] = "0.2.0"
        catalog["recipes"].append(newer)
        with self.assertRaisesRegex(AtlasError, "ambiguous"):
            new_config("lean", catalog=catalog)
        self.assertEqual(new_config("lean@0.2.0", catalog=catalog)["recipe"]["version"], "0.2.0")

    def test_unknown_fields_and_invalid_structures_are_rejected(self):
        cases = [
            lambda c: c.update(schema_version=True),
            lambda c: c.update(typo=True),
            lambda c: c.update(hosts={}),
            lambda c: c["hosts"]["codex"].pop("builder"),
            lambda c: c["hosts"]["codex"]["builder"].update(reasonning="high"),
            lambda c: c["recipe"].update(max_fix_rounds=True),
            lambda c: c["recipe"].update(evidence="verified"),
            lambda c: c.update(recipe=None),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                config = new_config()
                mutate(config)
                with self.assertRaises(AtlasError):
                    validate(config)

    def test_model_ids_cannot_inject_shell_or_config_content(self):
        for value in ('x;whoami', '$(whoami)', 'x\nmodel=bad', 'https://example.test', '-x', '../bad', 'a//b', 'a/'):
            with self.subTest(value=value), self.assertRaises(AtlasError):
                set_model(new_config(), "codex.builder", value)

    def test_opencode_requires_provider_and_preserves_nested_ids(self):
        with self.assertRaisesRegex(AtlasError, "provider/model"):
            set_model(new_config(), "opencode.builder", "model")
        config = new_config()
        set_model(config, "opencode.builder", "openrouter/vendor/model")
        self.assertEqual(config["hosts"]["opencode"]["builder"]["model"], "openrouter/vendor/model")

    def test_unsupported_effort_mapping_is_rejected(self):
        with self.assertRaisesRegex(AtlasError, "openai/"):
            set_model(new_config(), "opencode.builder", "anthropic/claude-sonnet-4-5-20250929", "high")
        with self.assertRaisesRegex(AtlasError, "explicit model"):
            set_model(new_config(), "codex.builder", "inherit", "high")

    def test_changing_model_clears_previous_effort(self):
        config = new_config()
        set_model(config, "codex.builder", "gpt-5.6", "high")
        set_model(config, "codex.builder", "custom/model")
        self.assertNotIn("effort", config["hosts"]["codex"]["builder"])

    def test_invalid_choice_preserves_in_memory_configuration(self):
        config = new_config()
        before = copy.deepcopy(config)
        with self.assertRaises(AtlasError):
            set_model(config, "opencode.builder", "missing-provider")
        self.assertEqual(config, before)

    def test_custom_models_are_explicitly_unverified(self):
        config = new_config()
        set_model(config, "codex.builder", "provider/new-model")
        self.assertTrue(any("custom model provider/new-model" in w for w in validate(config)))

    def test_local_model_tags_are_preserved(self):
        config = new_config()
        set_model(config, "opencode.builder", "ollama/llama3.2:3b")
        self.assertEqual(config["hosts"]["opencode"]["builder"]["model"], "ollama/llama3.2:3b")

    def test_duplicate_json_keys_and_invalid_catalog_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"schema_version": 1, "schema_version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(AtlasError, "Duplicate"):
                read_json(path)
            catalog = recipe_catalog()
            catalog["recipes"].append(copy.deepcopy(catalog["recipes"][0]))
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(AtlasError, "Duplicate"):
                recipe_catalog(path)

    def test_recipe_can_pin_models_for_each_host(self):
        catalog = recipe_catalog()
        team = new_config()["hosts"]
        team["codex"]["builder"] = {"model": "gpt-5.6-terra", "effort": "medium"}
        team["opencode"]["builder"] = {"model": "openai/gpt-5.2", "effort": "high"}
        catalog["recipes"][0]["models"] = team
        config = new_config("lean", catalog=catalog)
        self.assertEqual(config["hosts"], team)
        team["codex"]["builder"]["model"] = "changed"
        self.assertEqual(config["hosts"]["codex"]["builder"]["model"], "gpt-5.6-terra")

    def test_invalid_preset_does_not_hide_in_recipe_snapshot(self):
        config = new_config()
        config["recipe"]["models"] = {"opencode": {role: {"model": "bad"} for role in ("planner", "builder", "reviewer")}}
        with self.assertRaisesRegex(AtlasError, "provider/model"):
            validate(config)

    def test_catalog_default_is_exact_and_legacy_catalog_keeps_lean(self):
        catalog = recipe_catalog()
        self.assertEqual(new_config(catalog=catalog)["recipe"]["id"], "astra-flash")
        catalog.pop("default_recipe")
        self.assertEqual(new_config(catalog=catalog)["recipe"]["id"], "lean")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            for default in (None, "astra-flash", "astra-flash@missing"):
                catalog["default_recipe"] = default
                path.write_text(json.dumps(catalog), encoding="utf-8")
                with self.subTest(default=default), self.assertRaisesRegex(AtlasError, "default_recipe"):
                    recipe_catalog(path)


if __name__ == "__main__":
    unittest.main()
