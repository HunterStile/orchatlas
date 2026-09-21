# OrchAtlas

**One task. Codex and OpenCode working together.**

OrchAtlas is a standalone local orchestrator. It starts **Codex in the background for GPT-6 Astra planning and review through your ChatGPT subscription**, and **OpenCode in the background for DeepSeek V4.1 Flash implementation through OpenRouter**. You submit a task to OrchAtlas; it manages the handoffs, saves progress and returns a reviewed result.

**v0.2.0 — interactive orchestration prerelease.** Open a terminal, choose your team with `/model`, and give OrchAtlas a task. The earlier configuration-export commands remain available. [Release notes and downloads](https://github.com/HunterStile/orchatlas/releases/tag/v0.2.0).

~~~mermaid
flowchart LR
    User[Your task] --> Atlas[OrchAtlas]
    Atlas --> Plan[Codex / Astra: plan]
    Plan --> Build[OpenCode / DeepSeek: implement and save]
    Build --> Review[Codex / Astra: review]
    Review -->|Corrections| Build
    Review -->|Accepted| Result[Saved files and report]
~~~

## Open the interactive terminal

Requirements: Python 3.11+, Codex CLI, OpenCode CLI, access to Astra through your ChatGPT account, and an OpenRouter API key connected in OpenCode. The terminal uses `prompt-toolkit` for editing/completion/history and `rich` for progress and display.

Install from source once. On Windows, the installer also adds Python's user commands directory to your user PATH:

~~~powershell
git clone https://github.com/HunterStile/orchatlas.git
cd orchatlas
.\scripts\install-local.ps1
~~~

Open a new terminal, enter your project directory and type:

~~~sh
orchatlas
~~~

Or choose an existing project explicitly: `orchatlas --project /path/to/project`. Other platforms can install with `python -m pip install -e .` in an activated virtual environment; `python -m orchatlas` opens the same interface. A wheel and source archive are also available in the [GitHub release](https://github.com/HunterStile/orchatlas/releases/tag/v0.2.0). Install a downloaded wheel with `python -m pip install ./orchatlas-0.2.0-py3-none-any.whl` in your Python environment. No package has been published to PyPI.

~~~text
atlas > /model
atlas > Crea una pagina web per gestire attività e verifica che funzioni
atlas > Aggiungi un filtro per le attività completate
atlas > /diff
~~~

Plain text starts a task or continues an unfinished task. Follow-up tasks carry bounded context from the conversation. `/model` offers role and model selection using the clients' current catalogs; `/model orchestrator gpt-6-astra high` selects directly. Choices are saved in the project manifest for new tasks. Resumed tasks retain their saved team.

Use `/help` for all commands: `/model`, `/models`, `/effort`, `/status`, `/doctor`, `/setup`, `/login`, `/new`, `/sessions`, `/session`, `/runs`, `/resume`, `/diff`, `/report`, `/project`, `/timeout`, `/clear`, `/exit`. Tab completes commands; Up/Down recall input; Ctrl+R searches history; Alt+Enter inserts a newline. Ctrl+C stops a task and returns to the prompt with files and checkpoints retained.

The terminal shows the active phase, elapsed time and tool-status events. This is an interactive CLI over the combined runtime; images, native-client slash-command passthrough and token-by-token model text are not implemented. [Interactive terminal guide](docs/INTERACTIVE.md).

## Authentication and one-shot commands

On interactive startup OrchAtlas detects the existing Codex ChatGPT login and asks OpenCode for its configured OpenRouter connection. It validates the effective key with OpenRouter's authenticated `/api/v1/key` endpoint without a model request. Existing valid logins are reused. Missing connections offer native login; `/setup` repeats detection. Secrets remain in the native credential store and are never written to project settings, prompt history or reports.

If a connection is missing, sign in once through the official clients:

~~~sh
python -m orchatlas login codex
python -m orchatlas login openrouter
~~~

The first command opens Codex's ChatGPT login. The second invokes OpenCode's OpenRouter login. Credentials remain in the respective client's store; OrchAtlas does not ask for an OpenAI API key or copy authentication tokens into project files.

Choose an existing project directory and check readiness:

~~~sh
python -m orchatlas doctor --project /path/to/project
~~~

Then give OrchAtlas a task:

~~~sh
python -m orchatlas run "Implement the feature in docs/spec.md and verify it" --project /path/to/project
~~~

For a new Windows demo project, from the OrchAtlas checkout:

~~~powershell
New-Item -ItemType Directory -Path demo
python -m orchatlas doctor --project demo
python -m orchatlas run "Create a small task-list web page and test its behavior" --project demo
~~~

There is no need to open a separate Codex/OpenCode terminal or run `init` and `apply` before a combined run. The processes run while OrchAtlas is active and are closed when the run ends or is interrupted. This is a foreground CLI supervising background clients, not a detached system service.

## The team

| Role | Execution client | Model | Authentication |
| --- | --- | --- | --- |
| Planner / orchestrator | Codex app-server | `gpt-6-astra` | ChatGPT subscription |
| Implementation worker | OpenCode local server | `openrouter/deepseek/deepseek-v4.1-flash` | OpenRouter API |
| Independent reviewer | Codex app-server, separate thread | `gpt-6-astra` | ChatGPT subscription |

Codex plans and reviews with a read-only filesystem sandbox. OpenCode owns implementation and saves changes in the selected project. A review can send corrections back to the same worker session, up to the recipe's correction limit. Exhausted corrections produce a blocked run, not a false success.

The combined runtime needs neither a DeepSeek router inside Codex nor an OpenAI provider connection inside OpenCode. It checks subscription authentication before Codex turns and stops if the configured model/provider changes. Account availability and quotas still apply. [Official OpenAI authentication](https://learn.chatgpt.com/docs/auth), [Codex app-server](https://learn.chatgpt.com/docs/app-server), [OpenCode server](https://opencode.ai/docs/server/).

The worker uses the exact OpenRouter model ID `deepseek/deepseek-v4.1-flash`, prefixed by `openrouter/` in OpenCode. [OpenRouter model](https://openrouter.ai/deepseek/deepseek-v4.1-flash).

## Progress and continuation

Files are saved directly in the target project. Private run state, the initial workspace snapshot, session IDs, events and `REPORT.md` are stored under `.orchatlas/local/runs/<run-id>/`, ignored by Git.

~~~sh
python -m orchatlas runs --project /path/to/project
python -m orchatlas run --resume RUN_ID --project /path/to/project
python -m orchatlas run --resume RUN_ID --note "Use SQLite for storage" --project /path/to/project
~~~

Ctrl+C stops the owned background processes and retains saved files and progress. Resume continues from the recorded phase without resetting your workspace. Completed runs cannot be resumed; start a new task for follow-up work. A killed process or power loss may leave a lock requiring inspection; see [runtime behavior and recovery](docs/RUNTIME.md).

The initial snapshot distinguishes pre-existing work from changes made during the run. Later manual edits are retained and included in review. Snapshots are review evidence, not an automatic rollback mechanism.

Existing client permission policies still apply. OpenCode permission requests are forwarded to an interactive OrchAtlas terminal for one-time approval. Without an interactive terminal, a request blocks the run rather than being silently approved. `--json` sends progress events to stderr and a final structured result to stdout.

## Choose models and maintain recipes

Without a manifest, the combined runtime uses Astra plus DeepSeek Flash via OpenRouter. The historical exporter recipe snapshots retain their original routes. `/model` saves the chosen runtime team directly; the older explicit configuration commands are also available:

~~~sh
python -m orchatlas init --project /path/to/project
python -m orchatlas set codex.planner gpt-6-astra --effort high --project /path/to/project
python -m orchatlas set codex.reviewer gpt-6-astra --effort high --project /path/to/project
python -m orchatlas set opencode.builder openrouter/deepseek/deepseek-v4.1-flash --project /path/to/project
~~~

For combined runs, those three settings determine the team. `codex.builder` and the OpenCode planner/reviewer fields belong to the optional per-client exports. Model changes take effect on new runs; resuming a run uses its saved team.

The [recipe catalog](orchatlas/data/recipes.json) controls model defaults and correction rounds. Its `default_recipe` selects the main team for new manifests. [Maintainer guidance](CONTRIBUTING.md) explains versioned snapshots and explicit adoption of model changes. Recipes remain **unbenchmarked**.

## Optional configuration exports

The earlier `preview`, `apply`, `status` and `undo` commands remain available for manually operating one client. They generate native agents and a shared skill; they do not start the combined runtime. [Configuration export documentation](docs/MVP.md).

`undo` reverses configuration exports only. It does not undo implementation changes made by a model.

## Validation and background

~~~sh
python -m unittest discover -s tests -v
~~~

[Validation evidence](docs/VALIDATION.md) separates protocol fixture tests, real client readiness checks and live model execution. A small live task completed planning, actual file writing through OpenRouter and independent review, including continuation from a saved run.

- [Runtime and recovery](docs/RUNTIME.md)
- [Team selection](docs/teams/astra-flash.md)
- [Architecture decision](docs/adr/0001-orchatlas-owns-the-combined-runtime.md)
- [Original repository analysis, Italian](docs/research/astra-flash-analysis.md)
- [Ecosystem research, Italian](docs/research/ecosystem.md)

Inspired by [Astra Flash Orchestrator](https://github.com/ethanplusai/astra-flash-orchestrator). Original implementation; upstream code is not bundled. Independent of OpenAI, OpenCode and DeepSeek. [MIT license](LICENSE).
