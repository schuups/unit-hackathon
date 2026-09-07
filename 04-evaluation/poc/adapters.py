"""Driving a real coding agent from outside, and reading its trajectory back.

Three harnesses, one interface. Each takes a Setup and a task and returns the
same `Trajectory` object, so everything downstream -- checks, judges, statistics,
the decision rule -- is written once and does not know or care which agent
produced the run.

What makes the comparison fair is that all three are handed **the same four
tools**, from `environment.py`, over the MCP server in `mcp_server.py`, against
the same frozen fixtures. Their own toolsets are switched off. Compare OpenCode
and Claude Code as they ship and you are mostly comparing two different tool
lists, which is a question nobody asked.

What is deliberately NOT equalised is each harness's own system prompt. That
prompt is not a confound, it *is* the product: a large part of what you buy when
you choose Claude Code over OpenCode is the several thousand words it puts in
front of the model before your question. Overriding it would erase the thing
being measured. What the two share instead is `tasks.PREAMBLE`, appended to
every question for every setup, carrying the date and nothing else.

Two things found by running it, both recorded in the report rather than hidden:

  * The CSCS Anthropic-compatible endpoint reports `input_tokens: 0` through
    both CLIs. Output tokens, turns, tool calls and wall time are all sound;
    prompt tokens and cache hit rate are simply not available on that path. The
    in-process baseline talks to the OpenAI-compatible endpoint and does get
    them, which is why its numbers are not directly comparable and are labelled.
  * This build of Claude Code has no --max-turns, so the ceiling is enforced
    with a wall-clock timeout instead.
"""
import json
import os
import pathlib
import shutil
import subprocess
import time

import harness
from harness import Trajectory

HERE = pathlib.Path(__file__).parent
MCP_SERVER = HERE / "mcp_server.py"
OPENCODE_CONFIG = HERE / "opencode.json"
TOOL_NAMES = ("run_sql", "get_node_metrics", "list_alerts", "search_docs")

BASE_URL_OPENAI = "https://api.inference.cscs.ch/v1"
BASE_URL_ANTHROPIC = "https://api.inference.cscs.ch"


def api_key():
    key = os.environ.get("CSCS_INFERENCE_API_KEY")
    if not key:
        f = pathlib.Path.home() / "agent-sandbox/secrets/cscs-api-key"
        if f.exists():
            key = f.read_text().strip()
    if not key:
        raise SystemExit("eval: no CSCS_INFERENCE_API_KEY and no key file. See 01-sandboxing.")
    return key


def workspace():
    """A clean directory to run the agents in.

    Not the repository: both CLIs read CLAUDE.md / AGENTS.md from the working
    directory, and an instruction file lying around would be an uncontrolled
    variable that reaches one harness and not the other.
    """
    ws = HERE / "runs" / ".workspace"
    ws.mkdir(parents=True, exist_ok=True)
    for junk in ("CLAUDE.md", "AGENTS.md", ".cursorrules"):
        (ws / junk).unlink(missing_ok=True)
    return ws


def _strip(name):
    """`mcp__servicedesk__run_sql` / `servicedesk_run_sql` -> `run_sql`."""
    for prefix in ("mcp__servicedesk__", "servicedesk_", "servicedesk__"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


class Adapter:
    """Interface. `available()` is checked once before anything is spent."""
    name = "?"

    def available(self):
        raise NotImplementedError

    def run(self, setup, task, rep, timeout):
        raise NotImplementedError

    @staticmethod
    def _blank(setup, task, rep):
        return Trajectory(setup=setup.name, task=task["id"], rep=rep, model=setup.model)


# ---------------------------------------------------------------------------

class OpenCodeAdapter(Adapter):
    name = "opencode"

    def available(self):
        if not shutil.which("opencode"):
            return "the `opencode` binary is not on PATH"
        if not OPENCODE_CONFIG.exists():
            return f"{OPENCODE_CONFIG.name} is missing"
        return None

    def command(self, setup, prompt):
        # --pure: no user plugins. Without it opencode waits on stdin and hangs.
        return ["opencode", "run", "--pure", "--format", "json",
                "-m", f"cscs/{setup.model}"] + \
               (["--variant", setup.reasoning_effort] if setup.reasoning_effort else []) + \
               [prompt]

    def env(self):
        e = dict(os.environ)
        e["CSCS_INFERENCE_API_KEY"] = api_key()
        e["OPENCODE_CONFIG"] = str(OPENCODE_CONFIG)
        return e

    def run(self, setup, task, rep, timeout=240):
        tr = self._blank(setup, task, rep)
        prompt = task["prompt_full"]
        t0 = time.time()
        try:
            p = subprocess.run(self.command(setup, prompt), env=self.env(),
                               cwd=workspace(), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            tr.stopped, tr.error = "error", f"timed out after {timeout}s"
            tr.wall_s = round(time.time() - t0, 2)
            return tr
        tr.wall_s = round(time.time() - t0, 2)

        steps = 0
        for line in p.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind, part = ev.get("type"), ev.get("part") or {}

            if kind == "step_start":
                steps += 1
            elif kind == "tool_use":
                state = part.get("state") or {}
                result = state.get("output") or ""
                name = _strip(part.get("tool", "?"))
                tr.calls.append({
                    "turn": max(1, steps), "name": name,
                    "args": state.get("input") or {}, "result": result,
                    "result_chars": len(result),
                    "guard_refused": result.startswith("REFUSED"),
                })
            elif kind == "text":
                tr.answer = (part.get("text") or "").strip()
            elif kind == "step_finish":
                tok = part.get("tokens") or {}
                tr.tokens["sent"] += tok.get("input") or 0
                tr.tokens["received"] += tok.get("output") or 0
                tr.tokens["cached"] += (tok.get("cache") or {}).get("read") or 0

        tr.turns = max(steps, 1)
        if tr.answer:
            tr.stopped = "answered"
        else:
            tr.stopped = "error"
            tr.error = (p.stderr or p.stdout or "no output")[-400:]
        return tr


# ---------------------------------------------------------------------------

class ClaudeCodeAdapter(Adapter):
    name = "claude-code"

    def available(self):
        if not shutil.which("claude"):
            return "the `claude` binary is not on PATH"
        return None

    def mcp_config(self):
        return json.dumps({"mcpServers": {"servicedesk": {
            "command": "python3", "args": [str(MCP_SERVER)]}}})

    def command(self, setup, prompt):
        return ["claude", "-p", prompt, "--model", setup.model,
                "--output-format", "stream-json", "--verbose",
                "--strict-mcp-config", "--mcp-config", self.mcp_config(),
                "--allowed-tools", *[f"mcp__servicedesk__{t}" for t in TOOL_NAMES],
                # Anything not on that list is refused rather than queued for a
                # human, so the harness's own toolset cannot quietly join in.
                "--permission-prompts", "none",
                "--settings", json.dumps({"disableAllHooks": True})]

    def env(self):
        e = dict(os.environ)
        e.pop("ANTHROPIC_API_KEY", None)          # must not outrank the CSCS token
        e["ANTHROPIC_BASE_URL"] = BASE_URL_ANTHROPIC
        e["ANTHROPIC_AUTH_TOKEN"] = api_key()
        e["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        return e

    def run(self, setup, task, rep, timeout=300):
        tr = self._blank(setup, task, rep)
        t0 = time.time()
        try:
            p = subprocess.run(self.command(setup, task["prompt_full"]), env=self.env(),
                               cwd=workspace(), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            tr.stopped, tr.error = "error", f"timed out after {timeout}s"
            tr.wall_s = round(time.time() - t0, 2)
            return tr
        tr.wall_s = round(time.time() - t0, 2)

        pending, turn = {}, 0
        for line in p.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = ev.get("type")
            blocks = (ev.get("message") or {}).get("content") or []

            if kind == "assistant":
                turn += 1
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        pending[b.get("id")] = {
                            "turn": turn, "name": _strip(b.get("name", "?")),
                            "args": b.get("input") or {}, "result": "",
                            "result_chars": 0, "guard_refused": False}
                    elif b.get("type") == "text" and (b.get("text") or "").strip():
                        tr.answer = b["text"].strip()
            elif kind == "user":
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        call = pending.pop(b.get("tool_use_id"), None)
                        if call is None:
                            continue
                        content = b.get("content")
                        text = ("".join(c.get("text", "") for c in content
                                        if isinstance(c, dict))
                                if isinstance(content, list) else str(content or ""))
                        call.update(result=text, result_chars=len(text),
                                    guard_refused=text.startswith("REFUSED"))
                        tr.calls.append(call)
            elif kind == "result":
                u = ev.get("usage") or {}
                tr.tokens["sent"] += u.get("input_tokens") or 0
                tr.tokens["received"] += u.get("output_tokens") or 0
                tr.tokens["cached"] += u.get("cache_read_input_tokens") or 0
                tr.turns = ev.get("num_turns") or turn
                if ev.get("is_error"):
                    tr.error = str(ev.get("result"))[:400]
                if not tr.answer and isinstance(ev.get("result"), str):
                    tr.answer = ev["result"].strip()

        tr.calls.extend(pending.values())              # calls with no result came back empty
        tr.turns = tr.turns or turn or 1
        if tr.answer and not tr.error:
            tr.stopped = "answered"
        else:
            tr.stopped = "error"
            tr.error = tr.error or (p.stderr or "no answer")[-400:]
        return tr


# ---------------------------------------------------------------------------

class InProcessAdapter(Adapter):
    """The module-03 loop: ~25 lines of Python, no harness at all.

    Kept in the comparison as the floor. If a product harness cannot beat the
    loop you could write yourself in an afternoon, that is worth knowing before
    you standardise on it. It talks to the OpenAI-compatible endpoint, so unlike
    the two CLIs it does report prompt tokens.
    """
    name = "in-process"

    def __init__(self):
        self._client = None

    def available(self):
        try:
            import openai                       # noqa: F401
        except ImportError:
            return "the `openai` package is not importable (use: uv run --with openai,httpx)"
        return None

    def run(self, setup, task, rep, timeout=240):
        if self._client is None:
            self._client = harness.CSCSModel()
        return harness.run(setup, task, self._client, rep)


ADAPTERS = {a.name: a for a in
            (OpenCodeAdapter(), ClaudeCodeAdapter(), InProcessAdapter())}


def get(setup):
    return ADAPTERS[setup.harness]
