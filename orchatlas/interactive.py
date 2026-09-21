"""Interactive OrchAtlas terminal; one persistent conversation over the combined runtime."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from . import __version__, runtime
from .clients import NativeClients, executable
from .config import AtlasError, EFFORTS, set_model
from .runstore import RunStore, changes, list_runs, snapshot
from .session import Session, list_sessions
from .storage import checked_path, project_lock, read_bytes, save_manifest

COMMANDS = {
    "/help": "Show commands and keyboard shortcuts",
    "/model": "Choose orchestrator, worker or reviewer model",
    "/models": "Refresh the live client model catalogs",
    "/effort": "Set orchestrator/reviewer reasoning effort",
    "/status": "Show project, team and current run",
    "/doctor": "Check clients and authentication without inference",
    "/setup": "Detect existing Codex login and verify the OpenRouter key",
    "/login": "Sign in: /login codex or /login openrouter",
    "/new": "Start a fresh conversation, preserving project files",
    "/sessions": "List saved conversations",
    "/session": "Open a saved conversation: /session ID",
    "/runs": "List resumable task runs, including older CLI runs",
    "/resume": "Continue a run: /resume [RUN_ID]",
    "/diff": "Show current file changes for the selected run",
    "/report": "Show the last saved result and report path",
    "/project": "Show or change project: /project PATH",
    "/timeout": "Set seconds per model stage: /timeout 900",
    "/clear": "Clear the terminal display, keeping conversation context",
    "/exit": "Close OrchAtlas",
}
ROLES = {"orchestrator": "codex.planner", "worker": "opencode.builder", "reviewer": "codex.reviewer"}
ALIASES = {"planner": "orchestrator", "builder": "worker"}


def clean(value):
    value = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", value)


class AtlasCompleter(Completer):
    def __init__(self, app):
        self.app = app

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        if not text.startswith("/"):
            return
        prefix = text.rsplit(" ", 1)[-1]
        choices = COMMANDS if len(words) <= 1 and " " not in text else {}
        if words and words[0] in ("/model", "/effort"):
            position = len(words) - (0 if text.endswith(" ") else 1)
            if position == 1:
                choices = ROLES
            elif position == 2 and len(words) > 1:
                role = ALIASES.get(words[1], words[1])
                if words[0] == "/effort":
                    choices = (*EFFORTS, "default")
                else:
                    host = "opencode" if role == "worker" else "codex"
                    choices = [m["id"] for m in self.app.catalog.get(host, [])]
        elif words and words[0] == "/login" and len(words) <= 2:
            choices = ("codex", "openrouter")
        for choice in choices:
            if choice.startswith(prefix):
                yield Completion(choice, start_position=-len(prefix), display_meta=COMMANDS.get(choice, ""))


class Terminal:
    def __init__(self, project, *, console=None, input=None, output=None):
        self.console = console or Console(highlight=False)
        self.input, self.output = input, output
        self.session = None
        self.app = None
        self.live = None
        self.stage = "starting clients"
        self.started = 0
        self.spinner = Spinner("dots")
        self.set_project(project)

    def set_project(self, project):
        self.project = project
        self.session = None

    def write(self, text="", style=None):
        self.console.print(Text(clean(text), style=style or ""))

    def table(self, columns, rows):
        table = Table(box=None, padding=(0, 2), header_style="bold cyan")
        for column in columns:
            table.add_column(column)
        for row in rows:
            table.add_row(*(Text(clean(cell)) for cell in row))
        self.console.print(table)

    def ask(self, message="atlas > ", *, history=True, complete=True):
        if self.input is None and not sys.stdin.isatty():
            return input(message)
        if self.session is None:
            bindings = KeyBindings()

            @bindings.add("escape", "enter")
            def newline(event):
                event.current_buffer.insert_text("\n")

            history_path = checked_path(self.project, ".orchatlas/local/prompt-history")
            self.session = PromptSession(
                history=FileHistory(str(history_path)),
                auto_suggest=AutoSuggestFromHistory(), key_bindings=bindings,
                style=Style.from_dict({"prompt": "bold ansicyan", "bottom-toolbar": "bg:#202637 #bbc4d4"}),
                input=self.input, output=self.output, complete_while_typing=True)
        prompt = self.session if history else PromptSession(history=InMemoryHistory(), input=self.input, output=self.output)
        return prompt.prompt(
            [("class:prompt", message)],
            completer=AtlasCompleter(self.app) if complete and self.app else None,
            bottom_toolbar=(lambda: self.app.toolbar()) if self.app else "",
        )

    def choose(self, title, choices):
        self.write(title, "bold")
        filtered = choices
        while True:
            shown = filtered[:20]
            self.table(("#", "Choice"), [(i + 1, label) for i, (_, label) in enumerate(shown)])
            if len(filtered) > len(shown):
                self.write(f"Showing {len(shown)} of {len(filtered)}. Type a name to search.", "dim")
            answer = self.ask("Number or search (Enter cancels) > ", history=False, complete=False).strip()
            if not answer:
                return None
            if answer.isdigit():
                if not 1 <= int(answer) <= len(shown):
                    raise AtlasError("Choose one of the listed numbers.")
                return shown[int(answer) - 1][0]
            exact = next((key for key, _ in choices if key == answer), None)
            if exact is not None:
                return exact
            filtered = [(key, label) for key, label in choices if answer.casefold() in label.casefold()]
            if not filtered:
                self.write("No matching choices. Search again or press Enter to cancel.", "yellow")

    def _activity(self):
        elapsed = int(time.monotonic() - self.started)
        self.spinner.update(text=Text(f" {clean(self.stage)}  |  {elapsed}s  |  Ctrl+C stops this task", style="cyan"))
        return self.spinner

    @contextmanager
    def working(self, label):
        self.stage, self.started, self.spinner = label, time.monotonic(), Spinner("dots")
        with Live(console=self.console, get_renderable=self._activity, transient=True,
                  refresh_per_second=4, redirect_stdout=False, redirect_stderr=False) as live:
            self.live = live
            try:
                yield
            finally:
                self.live = None

    def event(self, kind, data):
        if kind == "stage":
            self.stage = data["stage"]
            self.write(f"  {self.stage}", "cyan")
        elif kind == "session":
            self.write(f"  {data['role']} · {data['model']}", "dim")
        elif kind == "tool":
            self.write(f"    {data['client']} · {data['tool']} · {data.get('status', '')}", "dim")
        elif kind == "run":
            self.write("  Run " + data["run_id"], "dim")

    def approve(self, request):
        if self.live:
            self.live.stop()
        try:
            self.write("OpenCode requests " + request["permission"] + ": " + json.dumps(request.get("patterns", [])))
            return self.ask("Allow once? [y/N] > ", history=False, complete=False).strip().lower() in ("y", "yes", "s", "si")
        finally:
            if self.live:
                self.live.start()


class InteractiveApp:
    """The same dispatch path serves the terminal, scripted input and integration tests."""

    def __init__(self, project: Path, terminal=None, *, runner=runtime.run, clients=NativeClients):
        self.project = checked_path(project)
        if not self.project.is_dir():
            raise AtlasError("The project directory must already exist.")
        with project_lock(self.project):
            pass  # Ensure that local history and conversations are ignored by Git.
        self.terminal = terminal or Terminal(self.project)
        self.terminal.app = self
        self.runner, self.clients = runner, clients
        self.session = Session(self.project)
        self.catalog = {}
        self.timeout = 900
        self.team = runtime.runtime_roles(runtime.configuration(self.project))

    def toolbar(self):
        return f" {self.project.name} | {self.team['planner']['model']} → {self.team['builder']['model']} | /help  Tab  Alt+Enter newline "

    def banner(self):
        self.terminal.console.print(Panel(Text(
            f"OrchAtlas  {__version__} · interactive orchestration\n\n"
            f"{self.project}\n"
            f"Orchestrator  {self.team['planner']['model']}  ·  Codex / ChatGPT\n"
            f"Worker        {self.team['builder']['model']}  ·  OpenCode\n"
            f"Reviewer      {self.team['reviewer']['model']}  ·  Codex / ChatGPT\n\n"
            "Describe your task. /model selects the team. /help lists commands.\n"
            "Enter sends · Alt+Enter adds a line · Tab completes · Ctrl+C stops a task",
        ), border_style="cyan", expand=False))
        saved = list_runs(self.project)
        if saved and saved[0]["status"] != "completed":
            self.terminal.write(f"Unfinished run: {saved[0]['id']} ({saved[0]['status']}). Use /resume {saved[0]['id']}", "yellow")

    def selected_run(self):
        if not self.session.last_run:
            raise AtlasError("No run selected. Use /runs and /resume ID, or describe a task.")
        return RunStore(self.project, self.session.last_run).load()

    def result(self, result):
        status = result["status"]
        self.terminal.write(status.upper(), "green" if status == "completed" else "yellow")
        for key in ("summary", "reason", "report"):
            if result.get(key):
                self.terminal.write(result[key])
        if status != "completed":
            self.terminal.write("Use /resume to continue, write a follow-up, or /new for a different task.", "dim")

    def execute(self, text=None, resume=None):
        context = self.session.context() if not resume else ""

        def event(kind, data):
            if kind == "run":
                self.session.attach(data["run_id"])
            self.terminal.event(kind, data)

        with self.terminal.working("starting Codex and OpenCode"):
            result = self.runner(self.project, text if not resume else None, resume=resume,
                                 note=text if resume else None, context=context, timeout=self.timeout,
                                 emit=event, approve=self.terminal.approve, factory=self.clients)
        self.result(result)
        return result

    def submit(self, text):
        last = self.selected_run() if self.session.last_run else None
        return self.execute(text, last["id"] if last and last["status"] != "completed" else None)

    def refresh_models(self):
        self.team = runtime.runtime_roles(runtime.configuration(self.project))
        with self.terminal.working("reading client model catalogs; no inference"):
            with self.clients(self.project, self.team, self.timeout, self.terminal.event) as clients:
                self.catalog = clients.catalog()
        return self.catalog

    def setup(self, *, connect=False):
        with self.terminal.working("detecting Codex login and checking OpenRouter credentials"):
            report = runtime.doctor(self.project, emit=self.terminal.event, factory=self.clients)
        checks = report["checks"]
        codex, worker = checks["codex"], checks["opencode"]
        if codex["ready"]:
            self.terminal.write("Codex: existing ChatGPT login detected" + (f" ({codex['plan']})" if codex.get("plan") else "") + "; selected models available.", "green")
        else:
            self.terminal.write("Codex: " + codex.get("reason", "not ready"), "yellow")
        if worker["ready"]:
            self.terminal.write(f"OpenCode: {worker['provider']} connected" +
                                ("; API key verified online." if worker.get("credential_verified") else "; credential present."), "green")
        else:
            self.terminal.write("OpenCode: " + worker.get("reason", "not ready"), "yellow")
        self.terminal.write(report["note"], "dim")
        if connect:
            missing = []
            if codex.get("authentication") != "chatgpt":
                missing.append("codex")
            if not worker.get("connected") or "HTTP 401" in worker.get("reason", ""):
                missing.append(worker["provider"])
            for client in missing:
                choice = self.terminal.choose(f"Connect {client}", [("login", "Open native login"), ("later", "Continue without login")])
                if choice == "login":
                    self.dispatch("/login " + client)
        return report

    def model(self, argument):
        words = argument.split()
        role = ALIASES.get(words[0], words[0]) if words else None
        if role is None:
            role = self.terminal.choose("Choose a role", [(r, f"{r}  ({selector})") for r, selector in ROLES.items()])
        if not role:
            return
        if role not in ROLES or len(words) > 3:
            raise AtlasError("Usage: /model [orchestrator|worker|reviewer] [MODEL_ID] [EFFORT]")
        host = ROLES[role].split(".")[0]
        models = self.refresh_models()[host]
        model = words[1] if len(words) > 1 else self.terminal.choose(
            f"Models from {host}", [(m["id"], f"{m['id']}  ·  {m['name']}") for m in models])
        if not model:
            return
        match = next((m for m in models if m["id"] == model), None)
        if match is None:
            raise AtlasError("That exact model ID is absent from the client's current catalog.")
        effort = words[2] if len(words) > 2 else None
        if effort and (host != "codex" or effort not in match.get("efforts", [])):
            raise AtlasError("That reasoning effort is not supported by the selected model.")
        self.update_model(role, model, effort)

    def update_model(self, role, model, effort=None):
        with project_lock(self.project):
            path = checked_path(self.project, "orchatlas.json")
            expected = read_bytes(path)
            config = runtime.configuration(self.project)
            if role == "reviewer" and config["recipe"]["review"] != "independent":
                raise AtlasError("This recipe shares the planner model for review. Select an independent-review recipe first.")
            set_model(config, ROLES[role], model, effort)
            runtime.runtime_roles(config)
            save_manifest(self.project, config, expected)
        self.team = runtime.runtime_roles(config)
        self.terminal.write(f"{role}: {model}" + (f" · effort {effort}" if effort else ""), "green")
        self.terminal.write("Saved for new tasks. Resuming an existing run keeps its original team.", "dim")

    def dispatch(self, line):
        line = line.strip()
        if not line:
            return True
        if not line.startswith("/"):
            self.submit(line)
            return True
        command, _, arg = line.partition(" ")
        arg = arg.strip()
        if command in ("/exit", "/quit"):
            return False
        if command == "/help":
            self.terminal.table(("Command", "Action"), COMMANDS.items())
            self.terminal.write("Enter sends; Alt+Enter inserts a newline; Up/Down recall history; Ctrl+R searches history.\n"
                                "Ctrl+C stops the active task and keeps the shell open; Ctrl+D exits at an empty prompt.")
        elif command == "/model":
            self.model(arg)
        elif command == "/models":
            catalog = self.refresh_models()
            self.terminal.table(("Client", "Model ID", "Name", "Efforts"),
                [(host, m["id"], m["name"], ", ".join(m.get("efforts", []))) for host, models in catalog.items() for m in models])
        elif command == "/effort":
            words = arg.split()
            if len(words) != 2 or ALIASES.get(words[0], words[0]) not in ("orchestrator", "reviewer"):
                raise AtlasError("Usage: /effort orchestrator|reviewer high|medium|...|default")
            role, effort = ALIASES.get(words[0], words[0]), words[1]
            catalog = self.refresh_models()["codex"]
            model = self.team["planner" if role == "orchestrator" else "reviewer"]["model"]
            item = next((m for m in catalog if m["id"] == model), {})
            if effort != "default" and effort not in item.get("efforts", []):
                raise AtlasError("Unsupported effort for the selected model.")
            self.update_model(role, model, None if effort == "default" else effort)
        elif command == "/status":
            self.team = runtime.runtime_roles(runtime.configuration(self.project))
            self.terminal.write(f"Project: {self.project}\nConversation: {self.session.id}\nTimeout: {self.timeout}s per stage")
            self.terminal.table(("Role", "Model", "Effort"),
                                [(role, settings["model"], settings.get("effort", "default")) for role, settings in self.team.items()])
            if self.session.last_run:
                state = self.selected_run()
                self.terminal.write(f"Run: {state['id']} · {state['status']} · {state['stage']}")
                self.terminal.write(state.get("reason", ""))
        elif command in ("/doctor", "/setup"):
            self.setup(connect=command == "/setup")
        elif command == "/login":
            if arg not in ("codex", "openrouter", "deepseek"):
                raise AtlasError("Usage: /login codex or /login openrouter")
            cmd = executable("codex") + ["login"] if arg == "codex" else executable("opencode") + ["--pure", "auth", "login", "--provider", arg]
            if subprocess.run(cmd).returncode:
                raise AtlasError("Login did not complete. Use /doctor to inspect readiness.")
            self.setup()
        elif command == "/new":
            self.session = Session(self.project)
            self.terminal.write("New conversation. Project files retained; previous tasks remain in /sessions and /runs.")
        elif command == "/sessions":
            self.terminal.table(("Session ID", "Tasks", "Title"),
                [(s["id"], len(s["runs"]), s["title"]) for s in list_sessions(self.project)])
            self.terminal.write("/session ID opens the conversation without starting a model turn.", "dim")
        elif command == "/session":
            self.session = Session(self.project, arg)
            self.terminal.write("Opened: " + self.session.state["title"])
            if self.session.last_run:
                state = self.selected_run()
                self.terminal.write(f"Last run: {state['id']} · {state['status']}")
        elif command == "/runs":
            self.terminal.table(("Run ID", "Status", "Stage"),
                [(r["id"], r["status"], r["stage"]) for r in list_runs(self.project)])
        elif command == "/resume":
            run_id = arg or self.session.last_run
            if not run_id:
                runs = [r for r in list_runs(self.project) if r["status"] != "completed"]
                run_id = self.terminal.choose("Choose an unfinished run", [(r["id"], f"{r['id']} · {r['status']}") for r in runs]) if runs else None
            if not run_id:
                self.terminal.write("No run selected. Describe a new task.")
                return True
            state = RunStore(self.project, run_id).load()
            if self.session.last_run != run_id:
                self.session = Session(self.project)
                self.session.attach(run_id)
            if state["status"] == "completed":
                self.terminal.write("Loaded completed task as conversation context. Write a follow-up to start a new run.")
            else:
                self.execute(resume=run_id)
        elif command == "/diff":
            state = self.selected_run()
            diff = changes(RunStore(self.project, state["id"]).baseline(), snapshot(self.project))
            self.terminal.table(("Action", "File"), [(f["action"], f["path"]) for f in diff["files"]])
            self.terminal.write(diff["diff"] or "No text changes.")
        elif command == "/report":
            state = self.selected_run()
            report = checked_path(self.project, f".orchatlas/local/runs/{state['id']}/REPORT.md")
            if not report.exists():
                raise AtlasError("No report yet. The run checkpoint is available through /status.")
            self.terminal.write(report.read_text(encoding="utf-8"))
            self.terminal.write(report, "dim")
        elif command == "/project":
            if arg:
                path = Path(arg.strip('"').strip("'"))
                project = checked_path(path if path.is_absolute() else self.project / path)
                if not project.is_dir():
                    raise AtlasError("The project directory must already exist.")
                team = runtime.runtime_roles(runtime.configuration(project))
                with project_lock(project):
                    pass
                self.project, self.team, self.catalog = project, team, {}
                self.session = Session(project)
                self.terminal.set_project(project)
            self.terminal.write(self.project)
        elif command == "/timeout":
            if not arg.isdigit() or not 1 <= int(arg) <= 86400:
                raise AtlasError("Usage: /timeout SECONDS (1 to 86400)")
            self.timeout = int(arg)
            self.terminal.write(f"Timeout: {self.timeout}s per model stage")
        elif command == "/clear":
            self.terminal.console.clear()
        else:
            raise AtlasError("Unknown command. Use /help or press Tab after /.")
        return True

    def loop(self):
        self.banner()
        if sys.stdin.isatty() or self.terminal.input is not None:
            try:
                self.setup(connect=True)
            except (AtlasError, OSError, KeyboardInterrupt) as exc:
                self.terminal.write(str(exc) if isinstance(exc, AtlasError) else "Connection checks interrupted or unavailable. Use /setup to retry.", "yellow")
        while True:
            try:
                if not self.dispatch(self.terminal.ask()):
                    break
            except EOFError:
                break
            except KeyboardInterrupt:
                self.terminal.write("Interrupted. Saved runs remain available with /resume.", "yellow")
            except (AtlasError, OSError) as exc:
                self.terminal.write(str(exc) if isinstance(exc, AtlasError) else "Local operation failed. Project files are retained.", "red")
        self.terminal.write("Session saved. See you next time.", "dim")
        return 0


def start(project: Path):
    return InteractiveApp(project).loop()
