"""Local protocol fixtures: real subprocesses and loopback HTTP, never model requests."""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit

SCENARIO = os.environ.get("ORCHATLAS_TEST_SCENARIO", "success")
PROJECT = Path.cwd()


def record(method):
    path = PROJECT / ".orchatlas/local/fake-requests.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"method": method}) + "\n")


def codex():
    threads = {}
    reviews = 0
    for line in sys.stdin:
        message = json.loads(line)
        method = message["method"]
        record(method)
        if "id" not in message:
            continue
        params = message.get("params", {})
        result = {}
        notifications = []
        if method == "account/read":
            result = {"account": {"type": "apiKey" if SCENARIO == "api-key" else "chatgpt"}}
        elif method == "model/list":
            result = {"data": [{"model": "gpt-6-astra", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]}]}
        elif method == "thread/start":
            assert params["approvalPolicy"] == "never" and params["sandbox"] == "read-only"
            assert params["modelProvider"] == "openai"
            thread_id = "thread_" + str(len(threads))
            threads[thread_id] = "reviewer" if "You are the reviewer" in params["developerInstructions"] else "planner"
            result = {"thread": {"id": thread_id}, "model": params["model"], "modelProvider": "openai", "sandbox": {"type": "readOnly"}}
        elif method == "turn/start":
            role = threads[params["threadId"]]
            if SCENARIO == "timeout":
                time.sleep(15)
            if role == "planner":
                answer = {"status": "blocked" if SCENARIO == "blocked-plan" else "ready", "objective": "Create a file",
                          "instructions": "Write generated.txt and inspect its contents.", "acceptance_criteria": ["File exists"],
                          "verification_commands": ["Read generated.txt"], "blocker": "Which content?"}
            else:
                reviews += 1
                if SCENARIO == "concurrent-edit":
                    (PROJECT / "generated.txt").write_text("changed during review\n", encoding="utf-8")
                accepted = not (SCENARIO == "never-accept" or (SCENARIO == "revise" and reviews == 1))
                answer = {"accepted": accepted, "summary": "Reviewed actual file.",
                          "findings": [] if accepted else ["Correct the generated content."], "checks": ["Read generated.txt"]}
            if SCENARIO == "bad-json":
                answer = "not a structured result"
            turn = "turn_" + str(message["id"])
            result = {"turn": {"id": turn}}
            notifications = [
                {"method": "item/completed", "params": {"threadId": params["threadId"], "turnId": turn,
                 "item": {"type": "agentMessage", "text": json.dumps(answer), "phase": "final_answer"}}},
                {"method": "turn/completed", "params": {"threadId": params["threadId"], "turn": {"id": turn, "status": "completed"}}},
            ]
        print(json.dumps({"id": message["id"], "result": result}), flush=True)
        for notification in notifications:
            print(json.dumps(notification), flush=True)


def opencode():
    config = json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])
    provider, model = config["agent"]["orchatlas-worker"]["model"].split("/", 1)
    assert provider in ("openrouter", "deepseek")
    assert config["enabled_providers"] == [provider]
    assert config["agent"]["orchatlas-worker"]["permission"]["task"] == "deny"
    auth = "Basic " + base64.b64encode(("orchatlas:" + os.environ["OPENCODE_SERVER_PASSWORD"]).encode()).decode()
    progress = {"writes": 0, "pending": False, "approved": threading.Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

        def handle_request(self, method):
            if self.headers.get("Authorization") != auth:
                self.send_error(401)
                return
            path = urlsplit(self.path).path
            record(method + " " + path)
            size = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(size)) if size else None
            result = {}
            if path == "/global/health":
                result = {"healthy": True}
            elif path == "/provider":
                result = {"connected": [] if SCENARIO == "missing-deepseek" else [provider],
                          "all": [{"id": provider, "key": "synthetic-token", "models": {model: {}}}]}
            elif path == "/session":
                result = {"id": "ses_fixture"}
            elif path == "/session/ses_fixture":
                result = {"id": "ses_fixture"}
            elif path == "/session/ses_fixture/message" and method == "POST":
                assert body["agent"] == "orchatlas-worker"
                assert body["model"] == {"providerID": provider, "modelID": model}
                if SCENARIO == "permission":
                    progress["pending"] = True
                    progress["approved"].wait(timeout=8)
                    if not progress["approved"].is_set():
                        self.send_error(403)
                        return
                progress["writes"] += 1
                (PROJECT / "generated.txt").write_text(f"implementation {progress['writes']}\n", encoding="utf-8")
                info = {"providerID": provider, "modelID": "wrong-model" if SCENARIO == "wrong-model" else model,
                        "finish": "stop", "tokens": {"input": 12, "output": 3}, "cost": 0.001}
                if SCENARIO == "worker-error":
                    info["error"] = {"name": "synthetic_failure"}
                if SCENARIO == "invalid-credential":
                    info["error"] = {"name": "APIError", "data": {"statusCode": 401,
                        "message": "private diagnostic", "responseHeaders": {"Authorization": "synthetic-secret"},
                        "responseBody": "synthetic-secret"}}
                    info["finish"] = None
                result = {"info": info, "parts": [{"type": "text", "text": "Saved and read generated.txt."}]}
            elif path == "/permission":
                result = [{"id": "per_fixture", "sessionID": "ses_fixture", "permission": "bash", "patterns": ["python check.py"]}] if progress["pending"] else []
            elif path == "/permission/per_fixture/reply":
                if body["reply"] == "once":
                    progress["pending"] = False
                    progress["approved"].set()
                result = True
            elif path == "/question" or (path.endswith("/message") and method == "GET"):
                result = []
            elif path.endswith("/abort"):
                result = True
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                self.wfile.write(json.dumps(result).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"opencode server listening on http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    codex() if sys.argv[1] == "codex" else opencode()
