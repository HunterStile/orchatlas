# OrchAtlas

[![Tests](https://github.com/HunterStile/orchatlas/actions/workflows/tests.yml/badge.svg)](https://github.com/HunterStile/orchatlas/actions/workflows/tests.yml)

**Choose your models. Version your orchestration.**

Versioned orchestration recipes for **Codex and OpenCode**. Choose the models for planning, building and reviewing, then generate the native agents and workflow for your project.

**v0.1.1 — local configuration MVP.** The CLI works offline and uses Python 3.11+ with no runtime dependencies. It does not send prompts, store API keys or run its own agent loop. All starter recipes are **unbenchmarked**; no model combination is presented as a measured winner.

The current main team is **GPT-6 Astra for orchestration and review, with DeepSeek V4.1 Flash for implementation**. Astra defines and accepts the task; a Flash builder writes the files, tests and corrections; a separate Astra reviewer checks the patch. [Exact IDs and provider prerequisites](docs/teams/astra-flash.md).

## Try it

Clone the repository, then try the CLI without installing dependencies:

```sh
git clone https://github.com/HunterStile/orchatlas.git
cd orchatlas
python -m orchatlas recipes
python -m orchatlas models
mkdir ../orchatlas-demo
python -m orchatlas init --project ../orchatlas-demo
python -m orchatlas preview --project ../orchatlas-demo
python -m orchatlas apply --project ../orchatlas-demo
```

Both hosts and `astra-flash@0.1.0` are selected by default. Use `--host codex` or `--host opencode` at initialization for only one. The main team requires OpenAI and DeepSeek access; **Codex additionally requires a configured external route such as Codex Router**. OrchAtlas does not install or authenticate these providers. For inherited host models, explicitly choose `--recipe lean` or `--recipe reviewed`.

To use the CLI outside this checkout, install the local package:

```sh
python -m pip install .
orchatlas --help
```

The installed `orchatlas` and `python -m orchatlas` expose the same interface. There is no published PyPI package or remote installer in this release.

Versioned wheels are available from [GitHub releases](https://github.com/HunterStile/orchatlas/releases). Download a wheel and install its local path with `python -m pip install path/to/orchatlas-0.1.1-py3-none-any.whl`.

## Choose your models

Use exact IDs available to your host/account. These are syntax examples, not benchmark recommendations:

```sh
orchatlas set codex.planner gpt-5.6 --effort high --project ../orchatlas-demo
orchatlas set codex.builder gpt-5.6-terra --effort medium --project ../orchatlas-demo
orchatlas set opencode.builder openai/gpt-5.2 --effort medium --project ../orchatlas-demo
orchatlas preview --project ../orchatlas-demo --diff
orchatlas apply --project ../orchatlas-demo
```

Choose `inherit` to return a role to the host default. Changing a model clears its previous effort unless you explicitly supply a new one. Codex effort is emitted as `model_reasoning_effort`; OpenCode effort maps to `reasoningEffort` only for `openai/` in this MVP. Other provider-specific reasoning options are not translated.

Custom model IDs are accepted with an unverified warning. `models` lists documentation examples, not the live account catalog. External Codex routes require a separately configured provider/router and appropriate subagent support. Model discovery is not proof that inference or tool use works.

## Start the workflow

Change into the target project. The generated `.orchatlas/START.md` contains commands reflecting the selected planner model.

For Codex, start a fresh session using the generated command, then request:

```text
$orchatlas Implement the feature described in docs/spec.md.
```

For OpenCode:

```sh
opencode --agent orchatlas
```

Describe your task to the primary agent. Both hosts run their own native agent loop. Codex and OpenCode are alternative hosts for a project, not two processes launched together by OrchAtlas.

## Starter workflows

| Recipe | Flow | Review ownership |
| --- | --- | --- |
| `astra-flash@0.1.0` **(default)** | Astra plan → Flash implementation → Astra review → Astra acceptance | Separate Astra reviewer; Astra coordinator accepts |
| `lean@0.1.0` | Plan → one builder → acceptance | Coordinator |
| `reviewed@0.1.0` | Plan → one builder → separate reviewer → acceptance | Reviewer supplies findings; coordinator accepts |

One writer is active at a time. A workflow defines correction rounds and evidence to return; those instructions are not a hard runtime budget or scheduler.

Existing projects keep their current snapshot and model choices. To adopt the main team explicitly:

```sh
orchatlas use astra-flash@0.1.0 --with-models --project ../orchatlas-demo
orchatlas preview --project ../orchatlas-demo
orchatlas apply --project ../orchatlas-demo
```

Switch recipes while retaining model choices:

```sh
orchatlas use lean@0.1.0 --project ../orchatlas-demo
orchatlas preview --project ../orchatlas-demo
orchatlas apply --project ../orchatlas-demo
```

## Files and reversibility

`orchatlas.json` is the editable source. Its recipe snapshot prevents silent changes after catalog updates. `.orchatlas/lock.json` records the compiler version, manifest and generated-file hashes.

| Destination | Content |
| --- | --- |
| `.agents/skills/orchatlas/SKILL.md` | Shared skill, discovered by both hosts |
| `.codex/agents/orchatlas_*.toml` | Codex builder and optional reviewer |
| `.opencode/agents/orchatlas*.md` | OpenCode primary, builder and optional reviewer |
| `.orchatlas/START.md` | Project-specific launch instructions |
| `.orchatlas/local/` | Ignored state, transaction lock and undo receipts |

Existing `AGENTS.md`, `.codex/config.toml`, `opencode.json[c]`, credentials and unrelated agents remain untouched. Existing unowned files at generated destinations cause an error. Modified or deleted managed files also block updates and undo, preserving later edits.

```sh
orchatlas status --project ../orchatlas-demo
orchatlas undo --project ../orchatlas-demo
orchatlas undo --project ../orchatlas-demo --apply
```

Undo reverses one applied transaction, newest first. It preserves `orchatlas.json`, unrelated files and receipts. A removed host or reviewer removes only unchanged, previously managed generated files during the next apply.

Writes are atomic **per file** and ordinary failures roll back completed writes. This is not a crash-proof filesystem transaction; see [recovery and limits](docs/MVP.md#recovery-and-limits). Backups remain ignored after uninstalling generated files.

## Maintain your catalog

Edit the human-readable [recipe catalog](orchatlas/data/recipes.json) and [model examples](orchatlas/data/models.json). The catalog's optional `default_recipe` selects the exact `id@version` used by `init` when no recipe is specified. Distribute a separate recipe catalog without changing the CLI:

```sh
orchatlas recipes --catalog ./my-recipes.json
orchatlas use my-team@1.0.0 --catalog ./my-recipes.json --project ../orchatlas-demo
```

The new recipe is copied into the manifest; application remains a separate step. By default `use` preserves model choices. Add `--with-models` to also adopt the maintainer's model defaults. `init` uses those defaults automatically for a new project. [Example catalog with models for both hosts](examples/recipes.json). Historical versions can coexist; select `id@version` when an ID is ambiguous. See [maintainer guidance](CONTRIBUTING.md).

## Validation

```sh
python -m unittest discover -s tests -v
```

Tests cover both adapters, model/effort validation, deterministic output, recipe pinning, collisions, drift, rollback and stacked undo. [Validation evidence](docs/VALIDATION.md) distinguishes unit/CLI tests, actual host configuration loading and live inference.

Codex artifacts follow the [official OpenAI documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents). OpenCode artifacts follow its [agent configuration](https://opencode.ai/docs/agents/) and [skill discovery](https://opencode.ai/docs/skills/). Host configuration and policies can override generated settings; a valid file does not imply account access or routing compatibility.

## Background

- [MVP scope and limits](docs/MVP.md)
- [Original repository analysis, Italian](docs/research/astra-flash-analysis.md)
- [Ecosystem research, Italian](docs/research/ecosystem.md)
- [Product blueprint, Italian](docs/blueprint.md)
- [Launch plan, Italian](docs/launch-plan.md)

Inspired by [Astra Flash Orchestrator](https://github.com/ethanplusai/astra-flash-orchestrator). This MVP is an original implementation; upstream code is not bundled. Independent of OpenAI, OpenCode, DeepSeek and Codex Router. Licensed under [MIT](LICENSE).
