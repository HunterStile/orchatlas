# Changelog

## 0.2.0 — Interactive orchestration (2026-09-22)

- Open an interactive terminal with bare `orchatlas`: role/model selection, slash commands, persistent input history, multiline editing, progress, saved conversations and resumable tasks.
- Add a local editable Windows installer and user-PATH registration.
- Add a standalone runtime coordinating subscription-authenticated Codex planning/review and DeepSeek implementation through OpenRouter in a background OpenCode server.
- Detect existing ChatGPT and OpenRouter connections at interactive startup, verify the effective OpenRouter key without inference and offer login only when needed.
- Add `run`, `doctor`, `runs` and delegated `login`, with saved progress, continuation and model/permission checks.
- Retain per-client configuration exports as optional compatibility commands.
- Preserve published recipe snapshots and existing model choices; the combined runtime defaults to the OpenRouter route for new projects without a manifest.
- Keep acceptance strict: independent review must provide checks and have no unresolved implementation findings.

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

The v0.1.0 configuration exporter did not make model calls. Benchmark rankings and built-in remote publishing commands remain outside the product's scope.
