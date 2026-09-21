# Main team: Astra + DeepSeek V4.1 Flash

Maintainer selection as of 2026-09-21. Recipe: `astra-flash@0.1.0`; catalog: `2026.09.21.2`. This is a chosen starting team, not a benchmark winner.

| Role | Responsibility | Codex model | OpenCode model |
| --- | --- | --- | --- |
| Planner / orchestrator | Define the task, assign work, coordinate corrections and accept the result | `gpt-6-astra` | `openai/gpt-6-astra` |
| Builder | Implement and save files in the project; run relevant checks and handle corrections | `deepseek/deepseek-v4.1-flash` | `deepseek/deepseek-flash` |
| Reviewer | Inspect the patch and evidence in a separate read-only agent | `gpt-6-astra` | `openai/gpt-6-astra` |

Astra owns orchestration and review; Flash is the single implementation writer. The builder returns changed paths, check results and outstanding issues. Saving workspace changes is part of implementation; commits, pushes and deployments follow the user's authorization. No silent substitution with another model is allowed.

## Exact model names

OpenAI documents Astra as `gpt-6-astra`; the recipe selects `high` reasoning for planning and review. [Official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).

DeepSeek's official API name is `deepseek-flash`, serving V4.1 Flash as of this date. This is a mutable upstream alias: freezing an OrchAtlas recipe freezes the requested ID, not provider weights. [DeepSeek changelog](https://api-docs.deepseek.com/updates/).

OpenCode agent models use `provider/model-id`. The recipe selects the direct OpenAI and DeepSeek providers; account credentials and model availability must be established in OpenCode. This is distinct from OpenCode Go, whose model IDs and subscription are different. DeepSeek effort is left to that provider because the MVP only translates explicit OpenCode effort for `openai/`. [OpenCode agent models](https://opencode.ai/docs/agents/#model).

## Codex routing prerequisite

`deepseek/deepseek-v4.1-flash` is a **Codex Router catalog slug**, mapped to the upstream `deepseek-flash` API model. It is not a native OpenAI model ID. The recipe sets this worker's effort to `high`. [Router mapping and effort levels at the inspected commit](https://github.com/duolahypercho/codex-router/blob/9c0db45676238d032757370ec4010b66b6759dd8/test/deepseek-v4-1-flash.test.mjs).

Use a separately configured [Codex Router](https://github.com/duolahypercho/codex-router) that preserves the native Astra route and exposes this DeepSeek route to child agents. Provider credentials, compatible client/catalog configuration and an actual delegation test are prerequisites. The inspected registry does not certify this route for v2 subagents by default. OrchAtlas does not install the router, change global Codex settings or mark a route as verified.

Changing Codex's entire session provider to DeepSeek would also change the orchestrator; that does not realize this mixed team. If the required route is unavailable, the workflow reports the missing prerequisite instead of falling back to Astra for implementation.

## Select or update

New projects use this recipe by default:

```sh
orchatlas init --project /path/to/project
orchatlas preview --project /path/to/project
orchatlas apply --project /path/to/project
```

To switch an existing project and adopt the model choices:

```sh
orchatlas use astra-flash@0.1.0 --with-models --project /path/to/project
orchatlas preview --project /path/to/project
orchatlas apply --project /path/to/project
```

Follow the generated `.orchatlas/START.md` to start a fresh host session. Static generation and tests do not establish provider authentication or live delegation; `runtime_verified` remains false.
