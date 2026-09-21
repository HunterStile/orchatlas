"""One CLI for the combined runtime and optional legacy configuration exports."""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import (AtlasError, EFFORTS, HOSTS, bundled, new_config, read_json,
                     recipe_catalog, set_model, validate)
from .render import launch_commands, render
from .storage import (apply, checked_path, plan, read_bytes, save_manifest, status,
                      undo, undo_plan)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="orchatlas", description="Coordinate Codex and OpenCode together from one application.")
    root.add_argument("--version", action="version", version=f"OrchAtlas {__version__}")
    root.add_argument("--project", type=Path, default=Path.cwd(), help="project for the interactive terminal")
    commands = root.add_subparsers(dest="command")
    for name, help_text in (
        ("run", "Run a task: Codex plans/reviews, OpenCode implements in the background"),
        ("doctor", "Check both background clients and authentication without inference"),
        ("runs", "List saved runs in this project"),
        ("login", "Sign in through the official client; credentials stay with that client"),
        ("recipes", "List bundled or maintainer-supplied workflows"),
        ("models", "List documented model examples, not account availability"),
        ("init", "Create a project manifest without overwriting an existing one"),
        ("set", "Choose a model for one host.role"),
        ("use", "Select a recipe snapshot, preserving model choices"),
        ("validate", "Check manifest structure and adapter support offline"),
        ("preview", "Preview the exact generated files and removals"),
        ("apply", "Apply generated files with guarded updates and undo receipts"),
        ("status", "Inspect installed files for drift"),
        ("undo", "Preview the latest transaction's reversal; use --apply to restore"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--json", action="store_true", help="machine-readable result")
        if name not in ("recipes", "models", "login"):
            command.add_argument("--project", type=Path, default=argparse.SUPPRESS, help="existing project directory (default: current directory)")
        if name in ("recipes", "init", "use"):
            command.add_argument("--catalog", type=Path, help="local versioned recipe catalog; never downloaded automatically")
        if name in ("models", "init"):
            command.add_argument("--host", choices=(*HOSTS, "both"), default="both")
        if name == "init":
            command.add_argument("--recipe", help="recipe ID (default: catalog default; bundled: astra-flash)")
            command.add_argument("--set", dest="selections", action="append", default=[], metavar="HOST.ROLE=MODEL",
                                 help="repeat to override recipe model defaults")
        if name == "set":
            command.add_argument("role", help="host.role, for example codex.builder")
            command.add_argument("model", help="exact host model ID, or inherit")
            command.add_argument("--effort", choices=(*EFFORTS, "default"), default="default",
                                 help="explicit reasoning effort; default clears any previous effort")
        if name == "use":
            command.add_argument("recipe", help="recipe ID or ID@version")
            command.add_argument("--with-models", action="store_true", help="also adopt the recipe's model defaults; unspecified hosts inherit")
        if name == "preview":
            command.add_argument("--diff", action="store_true", help="include unified file diffs")
        if name == "undo":
            command.add_argument("--apply", action="store_true", help="perform the restoration")
        if name == "run":
            command.add_argument("task", nargs="?", help="implementation task, quoted as one argument")
            command.add_argument("--resume", metavar="RUN_ID", help="continue a saved run without resetting project files")
            command.add_argument("--note", help="additional user instructions for a resumed run")
            command.add_argument("--timeout", type=int, default=900, help="seconds allowed per model stage (default: 900)")
        if name == "login":
            command.add_argument("client", choices=("codex", "openrouter", "deepseek"))
    return root


def load_manifest(project: Path) -> dict:
    config = read_json(checked_path(project, "orchatlas.json"))
    validate(config)
    return config


def change_summary(changes: list, include_diff: bool = False) -> list[dict]:
    result = []
    for change in changes:
        item = {"action": change.action, "path": change.path}
        if include_diff:
            before = (change.before or b"").decode("utf-8").splitlines(keepends=True)
            after = (change.after or b"").decode("utf-8").splitlines(keepends=True)
            item["diff"] = "".join(difflib.unified_diff(before, after, fromfile="a/" + change.path, tofile="b/" + change.path))
        result.append(item)
    return result


def run(args: argparse.Namespace) -> dict:
    if args.command == "login":
        from .clients import executable
        if args.json:
            raise AtlasError("Login is interactive; omit --json and use the native client's prompts.")
        command = (executable("codex") + ["login"] if args.client == "codex" else
                   executable("opencode") + ["--pure", "auth", "login", "--provider", args.client])
        result = subprocess.run(command)
        if result.returncode:
            raise AtlasError("Native client login did not complete.")
        return {"status": "login-finished", "next": "Run orchatlas doctor in your project to verify the selected team."}
    if args.command == "recipes":
        return recipe_catalog(args.catalog)
    if args.command == "models":
        data = bundled("models.json")
        data["models"] = [m for m in data["models"] if args.host == "both" or m["host"] == args.host]
        data["note"] = "Examples only. Custom exact IDs are accepted; availability, pricing and quality are not verified."
        return data
    project = checked_path(args.project)
    if not project.is_dir():
        raise AtlasError("The project directory must already exist.")
    if args.command == "runs":
        from .runstore import list_runs
        return {"status": "saved-runs", "runs": list_runs(project)}
    if args.command in ("run", "doctor"):
        from . import runtime

        def event(kind, data):
            if args.json:
                print(json.dumps({"event": kind, **data}), file=sys.stderr, flush=True)
            elif kind == "stage":
                print(f"OrchAtlas | {data['stage']}", flush=True)
            elif kind == "session":
                print(f"  {data['role']}: {data['client']} / {data['model']}", flush=True)
            elif kind == "run":
                print(f"Run: {data['run_id']}", flush=True)

        def approve(request):
            details = json.dumps(request.get("patterns", []), ensure_ascii=True)
            answer = input(f"OpenCode requests {request['permission']}: {details}\nAllow once? [y/N] ")
            return answer.strip().lower() in ("y", "yes", "s", "si")

        if args.command == "doctor":
            return runtime.doctor(project, emit=event)
        if args.note and not args.resume:
            raise AtlasError("--note requires --resume; include initial instructions in the task.")
        return runtime.run(project, args.task, resume=args.resume, note=args.note, timeout=args.timeout,
                           emit=event, approve=approve if sys.stdin.isatty() and not args.json else None)
    if args.command == "init":
        hosts = HOSTS if args.host == "both" else (args.host,)
        config = new_config(args.recipe, hosts, recipe_catalog(args.catalog))
        for selection in args.selections:
            if "=" not in selection:
                raise AtlasError("--set requires HOST.ROLE=MODEL.")
            selector, model = selection.split("=", 1)
            set_model(config, selector, model)
        save_manifest(project, config)
        return {"status": "created", "path": "orchatlas.json", "recipe": config["recipe"]["id"],
                "hosts": list(config["hosts"]), "next": "Run orchatlas doctor, then orchatlas run for a combined task. Use preview/apply only for configuration exports."}
    if args.command == "set":
        path = checked_path(project, "orchatlas.json")
        before = read_bytes(path)
        config = load_manifest(project)
        set_model(config, args.role, args.model, args.effort)
        save_manifest(project, config, before)
        return {"status": "configured", "role": args.role, "model": args.model,
                "warnings": validate(config), "next": "New combined runs use these settings. Preview/apply updates optional host exports."}
    if args.command == "use":
        path = checked_path(project, "orchatlas.json")
        before = read_bytes(path)
        config = load_manifest(project)
        selected = new_config(args.recipe, tuple(config["hosts"]), recipe_catalog(args.catalog))
        config["recipe"] = selected["recipe"]
        config["catalog_version"] = selected["catalog_version"]
        if args.with_models:
            config["hosts"] = selected["hosts"]
        validate(config)
        save_manifest(project, config, before)
        return {"status": "configured", "recipe": config["recipe"]["id"] + "@" + config["recipe"]["version"],
                "next": ("Recipe model defaults selected." if args.with_models else "Model choices are preserved.")
                         + " New combined runs use this recipe; preview/apply updates optional host exports."}
    if args.command == "status":
        report = status(project)
        manifest = checked_path(project, "orchatlas.json")
        report["manifest_present"] = manifest.exists()
        if manifest.exists() and not report["modified_files"]:
            changes, _ = plan(project, render(load_manifest(project)))
            report["pending_changes"] = len(changes)
        return report
    if args.command == "undo":
        changes, _, transaction = undo_plan(project)
        if args.apply:
            undo(project)
        return {"status": "restored" if args.apply else "preview", "transaction": transaction,
                "changes": change_summary(changes),
                "note": "The editable manifest is preserved. Receipts remain ignored under .orchatlas/local/."}
    config = load_manifest(project)
    warnings = validate(config)
    if args.command == "validate":
        generated = render(config)
        return {"status": "static-valid", "runtime_verified": False, "files": len(generated),
                "recipe": config["recipe"]["id"] + "@" + config["recipe"]["version"], "warnings": warnings}
    outputs = render(config)
    changes, _ = plan(project, outputs)
    report = {"status": "preview", "changes": change_summary(changes, getattr(args, "diff", False)),
              "warnings": warnings, "launch": launch_commands(config), "runtime_verified": False}
    if args.command == "apply":
        transaction = apply(project, outputs)
        report["status"] = "applied" if transaction else "unchanged"
        report["transaction"] = transaction
        report["next"] = "Open .orchatlas/START.md for the host launch instructions."
    return report


def print_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if "recipes" in result:
        print(f"OrchAtlas recipes | catalog {result['catalog_version']}")
        if "default_recipe" in result:
            print(f"Default team: {result['default_recipe']}")
        for recipe in result["recipes"]:
            print(f"  {recipe['id']}@{recipe['version']}  {recipe['title']} [{recipe['evidence']}]")
            print(f"    {recipe['description']}")
        return
    if "models" in result:
        print(result["note"])
        for model in result["models"]:
            print(f"  {model['host']:8} {model['model']}")
        return
    print(f"OrchAtlas | {result.get('status', 'installed' if result.get('installed') else 'not installed')}")
    for client, check in result.get("checks", {}).items():
        if isinstance(check, dict):
            print(f"  {client}: {'ready' if check.get('ready') else 'blocked'}")
            if check.get("reason"):
                print("    " + check["reason"])
    for saved in result.get("runs", []):
        print(f"  {saved['id']}  {saved['status']}  {saved['stage']}")
    for key in ("run_id", "report", "reason", "summary"):
        if result.get(key):
            print(f"  {key}: {result[key]}")
    for change in result.get("changes", []):
        print(f"  {change['action'].upper():6} {change['path']}")
        if change.get("diff"):
            print(change["diff"], end="")
    if "changes" in result and not result["changes"]:
        print("  No generated file changes.")
    for key in ("path", "recipe", "role", "model", "transaction", "managed_files", "pending_changes", "modified_files"):
        if key in result:
            print(f"  {key}: {result[key]}")
    for warning in result.get("warnings", []):
        print("  Note: " + warning)
    for host, command in result.get("launch", {}).items():
        print(f"  Start {host} from the project: {command}")
    if "codex" in result.get("launch", {}):
        print("  Then request: $orchatlas Implement <your task>.")
    for key in ("next", "note"):
        if key in result:
            print(result[key])


def main(argv: list[str] | None = None) -> int:
    # Redirected Windows terminals otherwise encode model names and Italian text
    # with a legacy code page, breaking UTF-8 consumers and saved transcripts.
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    try:
        if args.command is None:
            try:
                from .interactive import start
            except ImportError:
                raise AtlasError("Install the interactive terminal dependencies: python -m pip install -e .") from None
            return start(args.project)
        result = run(args)
        print_result(result, args.json)
        return 130 if result.get("status") == "cancelled" else 2 if result.get("status") in ("blocked", "failed") else 0
    except (AtlasError, OSError) as exc:
        message = str(exc) if isinstance(exc, AtlasError) else f"Local filesystem operation failed ({type(exc).__name__})."
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": message}), file=sys.stderr)
        else:
            print("OrchAtlas: " + message, file=sys.stderr)
        return 2
