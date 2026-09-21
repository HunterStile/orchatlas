# Interactive terminal

Run `orchatlas` in an existing project, or `orchatlas --project PATH`. With no subcommand, the CLI opens a persistent terminal session. Existing one-shot commands remain available for automation.

## Commands

| Command | Behavior |
| --- | --- |
| `/help` | Display commands and keys |
| `/model` | Select a role, then a model from the client catalog |
| `/model orchestrator gpt-6-astra high` | Select an exact Codex model and optional supported effort |
| `/model worker openrouter/deepseek/deepseek-v4.1-flash` | Select a DeepSeek implementation model |
| `/model reviewer gpt-6-astra high` | Select the independent reviewer |
| `/models` | Refresh and list native model catalogs without inference |
| `/effort orchestrator high` | Set reasoning effort; `default` clears the override |
| `/status` | Show current project, team, conversation, timeout and last run |
| `/doctor` | Check authentication and model availability without inference |
| `/setup` | Detect existing Codex/ChatGPT and OpenCode/OpenRouter connections, validate the OpenRouter key online and offer native login for missing connections |
| `/login codex` or `/login openrouter` | Use the native client's login; secrets stay out of prompt history |
| `/new` | Start a fresh conversation without changing project files |
| `/sessions` | List saved conversations |
| `/session ID` | Open a conversation without starting a model turn |
| `/runs` | List task runs, including runs started with the older one-shot CLI |
| `/resume [RUN_ID]` | Continue the selected run, or choose an unfinished run |
| `/diff` | Compare current project files to the selected run's original snapshot |
| `/report` | Display the selected run's saved report |
| `/project "PATH WITH SPACES"` | Change project and start a separate conversation |
| `/timeout 900` | Set the per-stage model timeout for this terminal |
| `/clear` | Clear the screen while retaining context |
| `/exit` | Exit the application |

`planner` and `builder` are accepted aliases for `orchestrator` and `worker`. Model selection verifies exact IDs against the native catalog. The default implementation route is OpenRouter, with DeepSeek V4.1 Flash selected. Other OpenRouter model IDs can be chosen; legacy direct DeepSeek routes remain supported when explicitly configured. The existing manifest determines the team: changes apply to new runs, while continuation retains the run's original configuration. Catalog membership is not evidence of model quality or remaining account quota.

## Input and progress

Interactive startup checks both connections automatically and reuses existing logins. Codex must report ChatGPT authentication and the chosen model. OpenCode supplies its effective OpenRouter credential in memory; OrchAtlas validates it at `https://openrouter.ai/api/v1/key` without inference and retains only the result. The credential and account details are neither displayed nor saved. A valid key does not guarantee remaining account-wide credits or future model quota. Missing credentials open a setup choice; existing valid credentials never trigger another login. With piped input, startup checks are skipped; use `/setup` or `/doctor` explicitly.

Enter submits a task; Alt+Enter inserts a newline. Tab completes slash commands, roles and already-loaded models. Up/Down recall input, and Ctrl+R searches history. Ctrl+C clears the current prompt or stops an active run while keeping the shell open. Ctrl+D exits at an empty prompt. Task cancellation preserves files and resumable state.

During a run the terminal displays elapsed time, planning/implementation/review stages, chosen models and tool-status events. It does not display hidden reasoning or stream the structured model response as conversational text. Permission requests pause the progress display and ask for one-time approval.

Plain text after a completed task starts a new run with bounded context from up to six recent runs: user requests, follow-up notes, review summaries and changed-file names. This is saved conversation context, not an indefinitely shared native model thread. Plain text after an unfinished task becomes a follow-up note while resuming that task. Use `/new` when changing objectives.

Opening the app starts a fresh conversation and shows the latest unfinished run, if present; it does not automatically spend model quota. Use `/session` to reopen a previous conversation. `/resume` can also load a completed task as context for a new follow-up without rerunning it.

## Local records and installation

Input history and conversation records stay under ignored `.orchatlas/local/prompt-history` and `.orchatlas/local/sessions/`. They may contain private task content. Run records and reports retain the existing [runtime layout](RUNTIME.md). Use native login prompts for credentials rather than entering secrets as tasks.

On Windows, `scripts/install-local.ps1` installs the source checkout in editable mode for the current user and adds Python's user scripts directory to that user's PATH. It neither publishes a package nor changes the version. Restart the terminal application after installation so it inherits the new PATH. Keep the checkout at the same location; rerun the installer if it moves. To uninstall, run `python -m pip uninstall orchatlas`; the shared Python scripts PATH entry remains because other tools may use it.

The current scope is a terminal application coordinating one worker and independent review. Images, arbitrary native slash commands, detached execution, in-flight task steering and token-by-token model output are not supported.

Implementation references: [prompt-toolkit input and completion](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html), [Rich live displays](https://rich.readthedocs.io/en/stable/live.html).
