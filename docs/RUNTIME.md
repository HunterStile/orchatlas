# Combined runtime

Available in OrchAtlas v0.2.0. This prerelease coordinates installed Codex and OpenCode clients from one interactive terminal or one-shot command.

## Commands

Bare `orchatlas [--project PATH]` opens the [interactive terminal](INTERACTIVE.md). It supervises the same runtime described below; slash commands and saved conversations are an additional interface over it.

| Command | Behavior |
| --- | --- |
| `login codex` | Delegate to Codex's interactive ChatGPT login |
| `login openrouter` | Delegate to OpenCode's interactive OpenRouter login |
| `doctor --project PATH` | Start both clients, inspect authentication and catalogs, then stop them; no model turn |
| `run "TASK" --project PATH` | Plan in Codex, implement in OpenCode, independently review in Codex |
| `run --resume ID [--note TEXT] --project PATH` | Continue an unfinished run using its saved configuration |
| `runs --project PATH` | List saved run IDs, phases and status |

`run` accepts `--timeout SECONDS` (default 900 per model stage, from 1 to 86400). `--json` emits the final result to stdout and progress events to stderr. The CLI returns a nonzero status for blocked, failed or cancelled runs. Login requires an interactive terminal and does not accept JSON mode.

## Execution and authentication

`clients.py` owns the child processes. Codex app-server uses JSON messages over stdin/stdout. It is explicitly configured for OpenAI and ChatGPT login, with inherited OpenAI API keys/base URL removed from that child environment. `account/read` must report `chatgpt` before work proceeds; `model/list` must include the selected model and reasoning effort. Codex's returned thread settings must match the chosen provider/model and read-only sandbox. No credentials are read from files by OrchAtlas.

OpenCode starts a dedicated `--pure serve` process bound to `127.0.0.1` on a random port, protected by a random in-memory Basic-auth password. Provider login stays in OpenCode. Per-process configuration enables the selected worker provider (OpenRouter by default), chooses the same worker model for auxiliary model use, disables sharing and creates an implementation agent that cannot delegate. It inherits other client permission settings. OrchAtlas does not supply OpenAI credentials to OpenCode.

For OpenRouter, preflight takes the effective key returned by OpenCode's authenticated local provider endpoint and validates it against OpenRouter's fixed HTTPS `/api/v1/key` endpoint. Redirects are refused. Only validity and a redacted error are retained, with no key or raw account response in checkpoints. This check does not perform inference. Codex's ChatGPT authentication and model catalog are checked separately. The published exporter recipe catalog remains historical; the combined runtime's default worker is `openrouter/deepseek/deepseek-v4.1-flash`.

The worker's returned model/provider metadata is checked before review. Native authentication and metadata checks establish the selected route, not model quality, benchmark superiority or provider-weight immutability.

Each run normally uses one Codex planning thread, one continuing OpenCode implementation session, and a new Codex thread for each review. Codex issues an implementation bundle as structured output; the runtime dispatches it to OpenCode. A separate reviewer inspects current files and a bounded diff, then either accepts or returns findings. Only an accepted review with reported checks and no remaining findings completes the run.

## Persistence and scope

`runtime.py` owns phases and acceptance. `runstore.py` saves checkpoints and evidence under `.orchatlas/local/runs/<id>/`:

- `run.json`: task, team snapshot, phases, model/session identities, implementation and review results.
- `baseline.json`: hashes and bounded text from the original working tree.
- `events.jsonl`: stage and tool-status events; raw authentication responses are not logged.
- `REPORT.md`: human-readable result and next action.

These files can contain project source and task content. They stay local and ignored. Host clients retain their own native session records. No automatic commits, pushes or deployments are requested by the runtime.

The snapshot uses Git's tracked/untracked nonignored file list when available, otherwise a bounded directory walk. It excludes common generated directories, `.orchatlas` and `.env*` except `.env.example`, rejects linked paths, and limits source text retained for diffs. Large/binary files are reported for direct inspection. The snapshot does not isolate model tools or undo their changes. OpenCode's tools run under that client's permissions; a deny rule for external-directory access is not a general operating-system sandbox for shell commands.

## Interruption and failures

Ctrl+C closes the clients, records cancellation and keeps files. `run --resume ID` restarts the clients and continues the saved phase; an interrupted implementation reuses the native worker session. It tells the worker to inspect already-saved work before continuing. Resume may repeat the interrupted model turn and therefore is not exactly-once execution.

Product questions block the run with a message; resume with `--note` to provide the answer. Tool permission requests are forwarded for one-time approval when stdin is interactive. JSON/noninteractive mode blocks rather than approving them. Authentication errors, unavailable models, substituted providers, malformed structured results and exhausted correction rounds do not become successful runs.

The installer and runtime share `.orchatlas/local/write.lock` to prevent simultaneous OrchAtlas writers in one project. The lock does not exclude your editor or unrelated agents. After a hard kill or power loss, inspect the recorded run and ensure the old client processes are stopped before manually removing a stale lock. No automatic rollback or stale-lock recovery is provided. A run that exhausted its correction budget requires a follow-up task.

## References

- [Codex app-server](https://learn.chatgpt.com/docs/app-server)
- [OpenAI authentication](https://learn.chatgpt.com/docs/auth)
- [OpenCode server](https://opencode.ai/docs/server/)
- [OpenCode permissions](https://opencode.ai/docs/permissions/)
