"""CSCS Service Desk agent -- one question, three data sources, no framework.

    python3 metrics_service.py &                    # the telemetry service
    uv run --with openai,httpx ask.py "job 4831 failed on nid02, what happened?"

The `openai` package is used only as an HTTP client for the CSCS inference
endpoint. Everything an agent actually is -- the tool list, the dispatch, the
execution, the loop -- is the code below. The model never touches this machine:
it asks, and this program decides whether to comply.
"""
import argparse
import json
import os
import pathlib
import sqlite3

import httpx
from openai import OpenAI

BASE_URL = "https://api.inference.cscs.ch/v1"
MODEL    = "moonshotai/Kimi-K2.7-Code"
METRICS  = "http://127.0.0.1:8088"
HERE     = pathlib.Path(__file__).parent
DB       = HERE / "accounting.db"
DOCS     = HERE / "docs"
TODAY    = "2026-09-06"

# ---------------------------------------------------------------------------
# 1. The tools -- ordinary Python functions. Nothing here knows about an LLM.
# ---------------------------------------------------------------------------

def run_sql(query):
    """Source 1: the accounting database (SQLite)."""
    q = query.strip().rstrip(";")
    if not q.lower().startswith("select") or ";" in q:
        return "REFUSED: this tool runs a single SELECT and nothing else."
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(q).fetchall()
    except sqlite3.Error as e:                  # hand the error back; it will retry
        return f"SQL error: {e}"
    return json.dumps([dict(r) for r in rows[:50]], default=str)


def get_node_metrics(node):
    """Source 2: the telemetry service (HTTP)."""
    return httpx.get(f"{METRICS}/metrics/{node}", timeout=5).text


def list_alerts():
    """Source 2 again -- one source, two tools."""
    return httpx.get(f"{METRICS}/alerts", timeout=5).text


def search_docs(keyword):
    """Source 3: the runbooks and policies on disk."""
    hits = [f"### {p.name}\n{p.read_text()}" for p in sorted(DOCS.glob("*.md"))
            if keyword.lower() in (p.name + p.read_text()).lower()]
    return "\n\n".join(hits)[:4000] or \
        f"Nothing matches {keyword!r}. Available: {[p.name for p in sorted(DOCS.glob('*.md'))]}"


TOOLS = [
    {"type": "function", "function": {
        "name": "run_sql",
        "description": "Run one read-only SELECT against the Slurm accounting database "
                       "(tables: projects, users, jobs). Use it for anything historical: "
                       "who ran what, node hours consumed, job states, allocations.",
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query": {"type": "string", "description": "A single SELECT statement."}}}}},
    {"type": "function", "function": {
        "name": "get_node_metrics",
        "description": "Live telemetry for one compute node right now: temperature, power "
                       "draw, GPU utilisation, fan speed, whether it is thermally throttling.",
        "parameters": {"type": "object", "required": ["node"], "properties": {
            "node": {"type": "string", "description": "Node name, e.g. 'nid02'."}}}}},
    {"type": "function", "function": {
        "name": "list_alerts",
        "description": "Every alert firing on the cluster at this moment, across all nodes.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "search_docs",
        "description": "Search the Service Desk runbooks and policies for a keyword. "
                       "Use it for procedure and policy: what to do about a fault, how "
                       "allocations, refunds and maintenance windows work.",
        "parameters": {"type": "object", "required": ["keyword"], "properties": {
            "keyword": {"type": "string", "description": "One word or short phrase."}}}}},
]

DISPATCH = {"run_sql": run_sql, "get_node_metrics": get_node_metrics,
            "list_alerts": list_alerts, "search_docs": search_docs}

# ---------------------------------------------------------------------------
# 2. What the model is told before it sees the question.
# ---------------------------------------------------------------------------

def schema():
    with sqlite3.connect(DB) as db:
        return "\n".join(r[0] for r in db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"))

SYSTEM = f"""You are the CSCS Service Desk assistant. Today is {TODAY}.

You have three sources and must decide which to use for each question -- one,
several, or none. Do not guess at anything a tool can tell you.

  * the accounting database, via run_sql. Its schema is:

{{schema}}

  * live node telemetry, via get_node_metrics and list_alerts. Nodes are
    nid01..nid08.
  * the runbooks and policies, via search_docs.

Answer in a few sentences. Give the numbers you actually retrieved, and say
which source each part of the answer came from."""

# ---------------------------------------------------------------------------
# 3. Logging -- so the room can see the agent decide.
# ---------------------------------------------------------------------------
DIM, CYAN, YEL, GRN, BOLD, OFF = "\033[2m", "\033[36m", "\033[33m", "\033[32m", "\033[1m", "\033[0m"

def log_turn(n, usage):
    cached = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0
    head = f"── turn {n} "
    print(f"\n{DIM}{head}{'─' * (58 - len(head))} "
          f"{usage.prompt_tokens:,} tokens sent ({cached:,} cached){OFF}")

def log_call(name, params, result):
    shown = ", ".join(f"{k}={v!r}" for k, v in params.items())
    shown = shown if len(shown) <= 170 else shown[:170] + "…"
    print(f"  {CYAN}⚙ {name}({shown}){OFF}")
    first = result.replace("\n", " ")[:110]
    print(f"    {DIM}← {len(result):,} chars: {first}…{OFF}")

# ---------------------------------------------------------------------------
# 4. The loop. This is the whole agent.
# ---------------------------------------------------------------------------

def main():
    cli = argparse.ArgumentParser(description="Ask the CSCS Service Desk agent one question.")
    cli.add_argument("question", nargs="+", help="the question, in plain words")
    cli.add_argument("--model", default=MODEL, metavar="ID",
                     help=f"CSCS model id (default: {MODEL})")
    cli.add_argument("--max-turns", type=int, default=6, metavar="N",
                     help="stop after N round trips to the model (default: 6)")
    args = cli.parse_args()
    question = " ".join(args.question)

    key = os.environ.get("CSCS_INFERENCE_API_KEY") or \
        (pathlib.Path.home() / "agent-sandbox/secrets/cscs-api-key").read_text().strip()
    client = OpenAI(base_url=BASE_URL, api_key=key)

    messages = [{"role": "system", "content": SYSTEM.format(schema=schema())},
                {"role": "user", "content": question}]
    print(f"{BOLD}question ▸{OFF} {question}")
    calls = sent = received = 0

    for turn in range(1, args.max_turns + 1):
        reply = client.chat.completions.create(model=args.model, messages=messages, tools=TOOLS)
        message = reply.choices[0].message
        log_turn(turn, reply.usage)
        sent += reply.usage.prompt_tokens
        received += reply.usage.completion_tokens
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:                       # nothing more to look up
            print(f"\n{BOLD}{GRN}answer ▸{OFF} {message.content.strip()}")
            break
        if message.content:
            print(f"  {DIM}{message.content.strip()[:150]}{OFF}")

        for call in message.tool_calls:                  # THE AGENT executes, not the model
            params = json.loads(call.function.arguments or "{}")
            result = DISPATCH[call.function.name](**params)
            log_call(call.function.name, params, result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            calls += 1

    print(f"\n{DIM}{turn} turns · {calls} tool calls · "
          f"{sent:,} tokens sent · {received:,} received{OFF}")


if __name__ == "__main__":
    main()
