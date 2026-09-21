"""Owned, background Codex and OpenCode processes. Credentials stay with the clients."""

from __future__ import annotations

import base64
import collections
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__
from .config import AtlasError


class RunBlocked(AtlasError):
    """A prerequisite or a human decision is needed; retain the run."""


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify_openrouter_key(key):
    """Validate the effective OpenCode credential without inference or secret persistence."""
    if not isinstance(key, str) or not key or any(ord(c) < 32 for c in key):
        return {"valid": False, "reason": "OpenRouter has no usable credential. Use /login openrouter."}
    request = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=10) as response:
            data = json.loads(response.read(100_001)).get("data")
        if not isinstance(data, dict):
            return {"valid": False, "reason": "OpenRouter returned an unexpected key-validation response."}
        if data.get("is_management_key") or data.get("is_provisioning_key"):
            return {"valid": False, "reason": "This OpenRouter key manages keys; use an inference API key with /login openrouter."}
        remaining = data.get("limit_remaining")
        if type(remaining) in (int, float) and remaining <= 0:
            return {"valid": False, "reason": "The OpenRouter API key has reached its configured spending limit."}
        return {"valid": True}
    except urllib.error.HTTPError as exc:
        hint = " Use /login openrouter to reconnect." if exc.code == 401 else " Retry /setup later."
        return {"valid": False, "reason": f"OpenRouter key validation failed (HTTP {exc.code})." + hint}
    except (OSError, ValueError, urllib.error.URLError):
        return {"valid": False, "reason": "Could not verify the OpenRouter key over the network. Retry /setup."}


def executable(name: str) -> list[str]:
    """Avoid PowerShell execution policy and batch interpolation on Windows."""
    path = shutil.which(name + ".exe") if os.name == "nt" else shutil.which(name)
    if path:
        return [path]
    shim = shutil.which(name + ".cmd") if os.name == "nt" else None
    if shim:
        npm = Path(shim).parent / "node_modules"
        if name == "opencode":
            binary = npm / "opencode-ai/bin/opencode.exe"
            if binary.is_file():
                return [str(binary)]
        if name == "codex":
            script = npm / "@openai/codex/bin/codex.js"
            node = shutil.which("node")
            if node and script.is_file():
                return [node, str(script)]
    raise RunBlocked(f"{name} is not installed or its executable cannot be resolved. Install the official client first.")


class BackgroundProcess:
    """One owned process tree, a bounded stdout queue, and deterministic cleanup."""

    def __init__(self, command: list[str], project: Path, env: dict | None = None):
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        self.process = subprocess.Popen(command, cwd=project, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, encoding="utf-8", errors="replace", bufsize=1, **options)
        self.lines = queue.Queue(maxsize=2048)
        self.closed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        while not self.closed.is_set():
            line = self.process.stdout.readline(2_000_001)
            if not line or len(line) > 2_000_000:
                line = None
            while not self.closed.is_set():
                try:
                    self.lines.put(line, timeout=0.2)
                    break
                except queue.Full:
                    continue
            if line is None:
                return

    def receive(self, timeout: float = 30) -> str:
        try:
            line = self.lines.get(timeout=max(0.001, timeout))
        except queue.Empty:
            raise AtlasError("Background client timed out.") from None
        if line is None:
            raise AtlasError("Background client closed its output or exceeded the message limit.")
        return line

    def send(self, payload: dict):
        try:
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise AtlasError("Background client is no longer accepting requests.") from None

    def close(self):
        if self.closed.is_set():
            return
        self.closed.set()
        if self.process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            else:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                self.process.kill()
                self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


class Codex:
    def __init__(self, project: Path, timeout: float, emit, command=None):
        self.project, self.timeout, self.emit = project, timeout, emit
        env = dict(os.environ)
        # Subscription-only: do not allow an inherited API key/base URL to change billing.
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL"):
            env.pop(key, None)
        self.process = BackgroundProcess((command or executable("codex")) + [
            "app-server", "--listen", "stdio://", "-c", 'model_provider="openai"',
            "-c", 'forced_login_method="chatgpt"', "-c", "agents.enabled=false"], project, env)
        self.counter = 0
        self.pending = collections.deque()
        try:
            self.request("initialize", {"clientInfo": {"name": "orchatlas", "title": "OrchAtlas", "version": __version__}})
            self.process.send({"method": "initialized"})
        except BaseException:
            self.close()
            raise

    def _message(self, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() >= deadline:
                raise AtlasError("Codex request timed out.")
            line = self.process.receive(deadline - time.monotonic())
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if "method" in message and "id" in message:
                self.process.send({"id": message["id"], "error": {
                    "code": -32601, "message": "Interactive requests are unavailable in the read-only OrchAtlas stage."}})
                raise RunBlocked("Codex requested an interactive action during a read-only planning/review stage.")
            return message

    def request(self, method, params, timeout=30):
        self.counter += 1
        request_id = self.counter
        self.process.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            message = self._message(deadline - time.monotonic())
            if message.get("id") == request_id:
                if "error" in message:
                    raise AtlasError(f"Codex rejected {method} (RPC {message['error'].get('code', 'error')}).")
                return message.get("result", {})
            self.pending.append(message)

    def check(self, settings: list[dict]) -> dict:
        account = self.request("account/read", {"refreshToken": False}).get("account") or {}
        result = {"authentication": account.get("type", "none"), "plan": account.get("planType"), "models": [], "ready": False}
        if account.get("type") != "chatgpt":
            result["reason"] = "Sign in with your subscription using codex login. OpenAI API-key billing is not used by this runtime."
            return result
        models = {item["model"]: item for item in self.catalog()}
        missing = [s["model"] for s in settings if s["model"] not in models]
        unsupported = [s for s in settings if s["model"] in models and s.get("effort") and
                       s["effort"] not in {e["reasoningEffort"] for e in models[s["model"]].get("supportedReasoningEfforts", [])}]
        result["models"] = sorted({s["model"] for s in settings if s["model"] in models})
        result["ready"] = not missing and not unsupported
        if missing:
            result["reason"] = "Requested Codex model missing from your catalog: " + ", ".join(missing)
        elif unsupported:
            result["reason"] = "Requested reasoning effort is unavailable for a selected Codex model."
        return result

    def catalog(self):
        models = {}
        cursor = None
        for _ in range(100):
            page = self.request("model/list", {"includeHidden": True, "limit": 100, "cursor": cursor})
            models.update({item["model"]: item for item in page.get("data", [])})
            cursor = page.get("nextCursor")
            if not cursor:
                break
        return list(models.values())

    def structured(self, role: str, settings: dict, prompt: str, schema: dict) -> dict:
        account = self.request("account/read", {"refreshToken": False}).get("account") or {}
        if account.get("type") != "chatgpt":
            raise RunBlocked("Codex is no longer signed in with ChatGPT. No API-key fallback was attempted.")
        started = self.request("thread/start", {
            "model": settings["model"], "modelProvider": "openai", "cwd": str(self.project),
            "sandbox": "read-only", "approvalPolicy": "never",
            "config": {"agents.enabled": False, "web_search": "disabled"},
            "developerInstructions": (
                f"You are the {role} in an OrchAtlas run. OrchAtlas coordinates an external OpenCode implementation worker. "
                "Do not delegate or implement. Inspect this project with read-only tools. Preserve all existing changes. "
                "Follow project guidance, but do not start any older OrchAtlas skill's delegation workflow. "
                "Return the requested structured result; do not claim checks ran without evidence. "
                "A user task authorizes work on this project, not publication or production operations."),
        })
        if started.get("model") != settings["model"] or started.get("modelProvider") != "openai":
            raise RunBlocked("Codex resolved a different model/provider from the requested team. Stopping without fallback.")
        if started.get("sandbox", {}).get("type") != "readOnly":
            raise RunBlocked("Codex did not confirm a read-only planning/review sandbox.")
        thread_id = started["thread"]["id"]
        self.emit("session", {"client": "codex", "role": role, "id": thread_id, "model": started["model"]})
        params = {"threadId": thread_id, "input": [{"type": "text", "text": prompt}], "outputSchema": schema}
        if settings.get("effort"):
            params["effort"] = settings["effort"]
        deadline = time.monotonic() + self.timeout
        turn_id = self.request("turn/start", params, timeout=self.timeout)["turn"]["id"]
        answer = None
        while True:
            if time.monotonic() >= deadline:
                raise AtlasError("Codex " + role + " turn timed out.")
            message = self.pending.popleft() if self.pending else self._message(deadline - time.monotonic())
            params = message.get("params", {})
            if params.get("threadId") != thread_id:
                continue
            method = message.get("method")
            if method == "item/completed" and params.get("turnId") == turn_id:
                item = params.get("item", {})
                if item.get("type") == "agentMessage":
                    answer = item.get("text")
                elif item.get("type") == "commandExecution":
                    self.emit("tool", {"client": "codex", "role": role, "tool": "command", "status": item.get("status")})
            if method == "turn/completed" and params.get("turn", {}).get("id") == turn_id:
                if params["turn"].get("status") != "completed":
                    raise AtlasError("Codex did not complete the " + role + " turn. Check the native Codex session for details.")
                break
        try:
            result = json.loads(answer)
        except (TypeError, json.JSONDecodeError):
            raise AtlasError("Codex returned no valid structured " + role + " result.") from None
        return {"result": result, "session_id": thread_id, "model": started["model"], "provider": "openai", "auth": "chatgpt"}

    def close(self):
        self.process.close()


class OpenCode:
    def __init__(self, project: Path, settings: dict, timeout: float, emit, approve=None, command=None, key_check=None):
        self.project, self.settings, self.timeout = project, settings, timeout
        self.emit, self.approve = emit, approve
        self.key_check = key_check or verify_openrouter_key
        self.url = None
        password = secrets.token_urlsafe(32)
        self.auth = "Basic " + base64.b64encode(("orchatlas:" + password).encode()).decode()
        env = dict(os.environ)
        env.update({"OPENCODE_SERVER_PASSWORD": password, "OPENCODE_SERVER_USERNAME": "orchatlas",
                    "OPENCODE_DISABLE_AUTOUPDATE": "true"})
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps({
            "$schema": "https://opencode.ai/config.json", "share": "disabled",
            "enabled_providers": [settings["model"].split("/", 1)[0]], "small_model": settings["model"],
            "agent": {"orchatlas-worker": {
                "mode": "primary", "model": settings["model"],
                "description": "Execute the implementation bundle assigned by OrchAtlas.",
                "prompt": (
                    "You are the implementation worker in OrchAtlas. Codex handles planning and review. "
                    "Do not invoke other agents or an older OrchAtlas skill. Implement and save the requested files "
                    "in this project, preserve prior work, run relevant checks, and report changed paths and evidence. "
                    "Do not commit, push, deploy, change credentials, or alter .orchatlas unless explicitly authorized. "
                    "When given corrections, inspect current files and continue; never reset the workspace."),
                "permission": {"task": "deny", "external_directory": "deny"},
            }},
        })
        self.process = BackgroundProcess((command or executable("opencode")) + [
            "--pure", "serve", "--hostname", "127.0.0.1", "--port", "0"], project, env)
        # Loopback traffic must not be sent through a user's outbound proxy.
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline = time.monotonic() + 30
            while self.url is None:
                line = self.process.receive(deadline - time.monotonic())
                found = re.search(r"http://127\.0\.0\.1:(\d+)", line)
                if found:
                    self.url = found.group(0)
            self.request("GET", "/global/health")
        except BaseException:
            self.close()
            raise

    def request(self, method, path, data=None, timeout=30):
        query = urllib.parse.urlencode({"directory": str(self.project)})
        url = self.url + path + ("&" if "?" in path else "?") + query
        payload = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(url, data=payload, method=method,
                                         headers={"Authorization": self.auth, "Content-Type": "application/json"})
        try:
            with self.http.open(request, timeout=timeout) as response:
                raw = response.read(16_000_001)
                if len(raw) > 16_000_000:
                    raise AtlasError("OpenCode response exceeded the size limit.")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raise AtlasError(f"OpenCode rejected {method} {path} (HTTP {exc.code}).") from None
        except (OSError, ValueError, urllib.error.URLError):
            raise AtlasError(f"OpenCode connection failed for {method} {path}.") from None

    def check(self) -> dict:
        data = self.request("GET", "/provider")
        provider, model = self.settings["model"].split("/", 1)
        connected = provider in data.get("connected", [])
        entry = next((p for p in data.get("all", []) if p.get("id") == provider), {})
        available = model in entry.get("models", {})
        result = {"provider": provider, "model": model, "connected": connected, "model_available": available,
                  "ready": connected and available, "credential_verified": False}
        if not connected:
            result["reason"] = f"Connect {provider} in OpenCode with orchatlas login {provider}, or supply {provider.upper()}_API_KEY to its environment."
        elif not available:
            result["reason"] = f"The requested model is missing from OpenCode's {provider} catalog."
        if connected and provider == "openrouter":
            credential = self.key_check(entry.get("key"))
            result["credential_verified"] = credential["valid"]
            if not credential["valid"]:
                result.update(ready=False, reason=credential["reason"])
        return result

    def implement(self, prompt: str, session_id: str | None = None) -> dict:
        if session_id:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
                raise AtlasError("Invalid saved OpenCode session ID.")
            self.request("GET", "/session/" + session_id)
        else:
            session_id = self.request("POST", "/session", {"title": "OrchAtlas implementation"})["id"]
        self.emit("session", {"client": "opencode", "role": "builder", "id": session_id, "model": self.settings["model"]})
        provider, model = self.settings["model"].split("/", 1)
        result_queue = queue.Queue()

        def send():
            try:
                result_queue.put(self.request("POST", f"/session/{session_id}/message", {
                    "agent": "orchatlas-worker", "model": {"providerID": provider, "modelID": model},
                    "parts": [{"type": "text", "text": prompt}],
                }, timeout=self.timeout + 10))
            except Exception as exc:
                result_queue.put(exc)

        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        deadline = time.monotonic() + self.timeout
        seen = set()
        try:
            while True:
                try:
                    response = result_queue.get(timeout=min(1, max(0.001, deadline - time.monotonic())))
                    break
                except queue.Empty:
                    if time.monotonic() >= deadline:
                        raise AtlasError("OpenCode implementation timed out; saved files are retained.")
                for permission in self.request("GET", "/permission", timeout=5):
                    if permission.get("sessionID") != session_id:
                        continue
                    if self.approve is None:
                        raise RunBlocked("OpenCode needs permission: " + permission.get("permission", "tool") + ". Resume from an interactive terminal.")
                    allowed = self.approve({"client": "opencode", "permission": permission.get("permission"),
                                            "patterns": permission.get("patterns", [])})
                    self.request("POST", "/permission/" + permission["id"] + "/reply", {"reply": "once" if allowed else "reject"})
                    if not allowed:
                        raise RunBlocked("An OpenCode permission request was declined. Saved files are retained.")
                for question in self.request("GET", "/question", timeout=5):
                    if question.get("sessionID") == session_id:
                        questions = " ".join(q.get("question", "") for q in question.get("questions", []))
                        raise RunBlocked("The implementation worker asks: " + questions + " Resume this run with --note containing your answer.")
                for message in self.request("GET", f"/session/{session_id}/message?limit=10", timeout=5):
                    for part in message.get("parts", []):
                        if part.get("type") == "tool":
                            key = (part.get("id"), part.get("state", {}).get("status"))
                            if key not in seen:
                                seen.add(key)
                                self.emit("tool", {"client": "opencode", "role": "builder", "tool": part.get("tool"), "status": key[1]})
            if isinstance(response, Exception):
                raise response
            info = response.get("info", {})
            error = info.get("error") or {}
            status_code = (error.get("data") or {}).get("statusCode")
            if status_code == 401:
                raise RunBlocked(f"{provider} rejected the configured API credential (HTTP 401). "
                                 f"Use /login {provider} (or orchatlas login {provider}), then resume this run. "
                                 f"Also check any {provider.upper()}_API_KEY supplied to OpenCode.")
            if info.get("error") or info.get("finish") not in ("stop", "end_turn"):
                status_hint = f" (HTTP {status_code})" if type(status_code) is int and 100 <= status_code <= 599 else ""
                raise AtlasError("OpenCode did not complete the implementation" + status_hint + ". Inspect its native session for details.")
            if info.get("providerID") != provider or info.get("modelID") != model:
                raise RunBlocked("OpenCode returned a different model/provider; the run cannot be accepted.")
            text = "\n".join(p.get("text", "") for p in response.get("parts", []) if p.get("type") == "text")
            if not text.strip():
                raise AtlasError("OpenCode returned no implementation report.")
            return {"text": text, "session_id": session_id, "provider": provider, "model": model,
                    "tokens": info.get("tokens"), "cost": info.get("cost")}
        except BaseException:
            try:
                self.request("POST", f"/session/{session_id}/abort", timeout=3)
            except AtlasError:
                pass
            self.close()
            raise
        finally:
            thread.join(timeout=2)

    def close(self):
        self.process.close()


class NativeClients:
    """One combined team; subscription Codex plus a separately authenticated worker provider."""

    def __init__(self, project, roles, timeout, emit, approve=None):
        self.codex = self.opencode = None
        self.roles, self.project, self.timeout, self.emit, self.approve = roles, project, timeout, emit, approve

    def __enter__(self):
        try:
            self.codex = Codex(self.project, self.timeout, self.emit)
            self.opencode = OpenCode(self.project, self.roles["builder"], self.timeout, self.emit, self.approve)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        try:
            if self.opencode:
                self.opencode.close()
        finally:
            if self.codex:
                self.codex.close()

    def check(self):
        codex = self.codex.check([self.roles["planner"], self.roles["reviewer"]])
        opencode = self.opencode.check()
        return {"ready": codex["ready"] and opencode["ready"], "codex": codex, "opencode": opencode,
                "inference_tested": False}

    def plan(self, prompt, schema):
        return self.codex.structured("planner", self.roles["planner"], prompt, schema)

    def catalog(self):
        codex = [{"id": m["model"], "name": m.get("displayName", m["model"]),
                  "efforts": [e["reasoningEffort"] for e in m.get("supportedReasoningEfforts", [])]}
                 for m in self.codex.catalog()]
        providers = self.opencode.request("GET", "/provider")
        provider = self.roles["builder"]["model"].split("/", 1)[0]
        selected = next((p for p in providers.get("all", []) if p.get("id") == provider), {})
        return {"codex": codex, "opencode": [{"id": provider + "/" + key, "name": value.get("name", key),
                    "connected": provider in providers.get("connected", [])}
                    for key, value in selected.get("models", {}).items()]}

    def implement(self, prompt, session_id=None):
        return self.opencode.implement(prompt, session_id)

    def review(self, prompt, schema):
        return self.codex.structured("reviewer", self.roles["reviewer"], prompt, schema)
