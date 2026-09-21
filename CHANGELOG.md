# Changelog

## 0.1.1 — Astra / DeepSeek main team

- Make `astra-flash@0.1.0` the default: GPT-6 Astra plans and reviews; DeepSeek V4.1 Flash implements.
- Add explicit host-specific IDs and document the Codex Router prerequisite and mutable DeepSeek API alias.
- Let maintainers choose `default_recipe` in their catalog without changing the CLI.
- Preserve existing manifests and model choices until explicit adoption.

## 0.1.0 — Local configuration MVP

- Add a dependency-free Python CLI for Codex and OpenCode.
- Select models and reasoning effort per host and role.
- Snapshot lean/reviewed recipes and support local versioned catalogs.
- Generate native agents, a shared skill, launch instructions and a hash manifest.
- Preview, apply, detect drift and undo project-local changes with guarded receipts.
- Add lifecycle/rollback tests and report host-loading evidence separately from inference.

No benchmark rankings, automated model calls or built-in remote publishing commands are included.
