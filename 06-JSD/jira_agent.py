"""Jira Service Desk agent -- one question, one Jira, no framework.

    uv run --with openai,httpx jira_agent.py \
        "user reports jobs stuck in the queue with 'launch failed' on tasna"

Given a problem in plain words, the agent searches jira-tds.cscs.ch for
historical tickets that look like it, reads the comment threads on the ones it
picks, and proposes a course of action grounded in what was actually done.

The `openai` package is only an HTTP client for the CSCS inference endpoint.
The agent -- the tool list, the dispatch, the loop -- is the code below. The
model writes the JQL; this program decides whether to run it.
"""
import argparse
import json
import os
import pathlib
import re

import httpx
from openai import OpenAI

BASE_URL = "https://api.inference.cscs.ch/v1"
MODEL    = "moonshotai/Kimi-K2.7-Code"
JIRA     = "https://jira-tds.cscs.ch"
PAT_FILE = pathlib.Path.home() / ".jira-tds-pat"
KEY_FILE = pathlib.Path.home() / "agent-sandbox/secrets/cscs-api-key"

MAX_COMMENTS  = 12       # per issue, oldest first then the tail
MAX_CHARS     = 1200     # per comment or description body
MAX_TOOL_OUT  = 12000    # per tool result handed back to the model

# ---------------------------------------------------------------------------
# 1. The tools -- ordinary Python functions talking to Jira over REST.
# ---------------------------------------------------------------------------

jira = None              # an httpx.Client, built in main()


def _get(path, **params):
    r = jira.get(f"{JIRA}/rest/api/2/{path}", params=params)
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}: {r.text[:300]}"}
    return r.json()


def _clip(text, n=MAX_CHARS):
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    return text if len(text) <= n else text[:n] + f"… [+{len(text) - n} chars]"


def search_issues(jql, limit=15):
    """Source: Jira, as a search. The model writes the JQL."""
    if re.search(r"\b(delete|update|insert)\b", jql, re.I):
        return "REFUSED: this tool runs a read-only JQL search and nothing else."
    data = _get("search", jql=jql, maxResults=min(int(limit), 30),
                fields="summary,status,resolution,created,resolutiondate,updated,"
                       "issuetype,labels,components,priority,reporter,assignee")
    if "error" in data:                     # hand the error back; it will retry
        return f"JQL error: {data['error']}"
    out = []
    for i in data.get("issues", []):
        f = i["fields"]
        out.append({
            "key": i["key"],
            "summary": f["summary"],
            "type": (f.get("issuetype") or {}).get("name"),
            "status": (f.get("status") or {}).get("name"),
            "resolution": (f.get("resolution") or {}).get("name"),
            "created": (f.get("created") or "")[:10],
            "resolved": (f.get("resolutiondate") or "")[:10],
            "labels": f.get("labels") or [],
            "components": [c["name"] for c in f.get("components") or []],
            "assignee": (f.get("assignee") or {}).get("displayName"),
        })
    return json.dumps({"total_matching": data.get("total", 0),
                       "returned": len(out), "issues": out}, ensure_ascii=False)[:MAX_TOOL_OUT]


def read_issue(key, comments=True):
    """Source: Jira, as one ticket -- the description and the conversation on it."""
    key = key.strip().upper()
    fields = "summary,description,status,resolution,created,resolutiondate," \
             "issuetype,labels,components,priority,reporter,assignee"
    if comments:
        fields += ",comment"
    data = _get(f"issue/{key}", fields=fields)
    if "error" in data:
        return f"Cannot read {key}: {data['error']}"
    f = data["fields"]
    lines = [f"{key}  {f['summary']}",
             f"url: {JIRA}/browse/{key}",
             f"type: {(f.get('issuetype') or {}).get('name')} | "
             f"status: {(f.get('status') or {}).get('name')} | "
             f"resolution: {(f.get('resolution') or {}).get('name')} | "
             f"created: {(f.get('created') or '')[:10]} | "
             f"resolved: {(f.get('resolutiondate') or '')[:10]}",
             f"labels: {f.get('labels') or []} | "
             f"components: {[c['name'] for c in f.get('components') or []]}",
             "",
             "## description", _clip(f.get("description"))]

    if comments:
        all_c = (f.get("comment") or {}).get("comments", [])
        total = (f.get("comment") or {}).get("total", len(all_c))
        shown = all_c if len(all_c) <= MAX_COMMENTS else \
            all_c[:MAX_COMMENTS // 2] + all_c[-(MAX_COMMENTS // 2):]
        lines += ["", f"## comments ({total} total, {len(shown)} shown)"]
        if len(shown) < total:
            lines.append("[middle of the thread elided]")
        for c in shown:
            who = (c.get("author") or {}).get("displayName", "?")
            lines.append(f"\n--- {who} · {c['created'][:16].replace('T', ' ')}")
            lines.append(_clip(c.get("body")))
    return "\n".join(lines)[:MAX_TOOL_OUT]


def list_projects():
    """Which Jira projects exist -- the key you need for `project = ...`."""
    data = _get("project")
    if isinstance(data, dict) and "error" in data:
        return f"Cannot list projects: {data['error']}"
    return json.dumps([{"key": p["key"], "name": p["name"]} for p in data], ensure_ascii=False)


TOOLS = [
    {"type": "function", "function": {
        "name": "search_issues",
        "description": "Run one read-only JQL query against the CSCS Jira and get a compact "
                       "list of matching issues (key, summary, status, resolution, dates, "
                       "labels, components). Use it to find historical tickets that resemble "
                       "the problem at hand. Search broadly first, then narrow.",
        "parameters": {"type": "object", "required": ["jql"], "properties": {
            "jql": {"type": "string", "description": "A JQL query, e.g. "
                    "'project = SD AND text ~ \"launch failed\" ORDER BY resolutiondate DESC'."},
            "limit": {"type": "integer", "description": "Max issues to return (default 15, max 30)."}}}}},
    {"type": "function", "function": {
        "name": "read_issue",
        "description": "Read one ticket in full: its description and the comment thread, which "
                       "is where the diagnosis and the fix actually live. Call it on every "
                       "candidate you intend to cite -- a summary alone is not evidence.",
        "parameters": {"type": "object", "required": ["key"], "properties": {
            "key": {"type": "string", "description": "Issue key, e.g. 'SD-60454'."},
            "comments": {"type": "boolean", "description": "Include the comment thread (default true)."}}}}},
    {"type": "function", "function": {
        "name": "list_projects",
        "description": "List every Jira project key and name, if you need one not in the system prompt.",
        "parameters": {"type": "object", "properties": {}}}},
]

DISPATCH = {"search_issues": search_issues, "read_issue": read_issue,
            "list_projects": list_projects}

# ---------------------------------------------------------------------------
# 2. What the model is told before it sees the question.
# ---------------------------------------------------------------------------

SYSTEM = """You are a CSCS Service Desk assistant working against the Jira at
{jira}. Today is {today}.

Someone brings you a problem. Your job is to find what the organisation already
knows about it -- in tickets that have been raised, discussed and closed before
-- and to turn that into a course of action. You do not guess at anything a
search can tell you.

The projects on this instance:

{projects}

{scope}

How to work:

  1. Search wide, then narrow. Start with the distinctive words of the problem
     (an error string, a command, a node or machine name, a filesystem) via
     `text ~ "..."`. If nothing lands, drop a term, try a synonym, or search
     `summary ~ ...` alone. Two or three searches are normal.
  2. Prefer tickets that were actually resolved -- `resolution IS NOT EMPTY`
     -- and recent ones over old ones, but say so when the best precedent is old.
  3. Open the promising ones with `read_issue`. The comment thread is where the
     real diagnosis, the workaround and the eventual fix are recorded; the
     summary is only a label. Read at least the two or three best candidates.
  4. If the threads disagree or the problem has recurred, say that.

JQL you will need: `project = SD`, `text ~ "phrase"` (searches summary,
description and comments), `summary ~ "..."`, `status = Resolved`,
`resolution IS NOT EMPTY`, `labels = ...`, `component = "..."`,
`created >= -180d`, `ORDER BY resolutiondate DESC`. Escape inner quotes as \\".
A `text ~` search with several words matches any of them, so a long phrase
returns noise -- keep it to the two or three words that are actually specific.

Answer in this shape, and keep it tight:

  **What this looks like** -- one or two sentences.
  **Precedents** -- 2 to 5 tickets, each as `KEY — summary` with one line on
  what happened there and how it ended. Give the {jira}/browse/KEY link.
  **Suggested course of action** -- concrete numbered steps, each traceable to
  a ticket you actually read, or marked as your own inference where it is not.
  **What to check / ask** -- the missing information that would change the answer.

Never invent a ticket key, a person or a fix. If the search comes up empty, say
so plainly and propose what to ask the user instead."""

# ---------------------------------------------------------------------------
# 3. Logging -- so the room can see the agent decide.
# ---------------------------------------------------------------------------
DIM, CYAN, YEL, GRN, BOLD, OFF = "\033[2m", "\033[36m", "\033[33m", "\033[32m", "\033[1m", "\033[0m"


def log_turn(n, usage):
    cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
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
    global jira
    cli = argparse.ArgumentParser(description="Ask the Jira Service Desk agent about a problem.")
    cli.add_argument("question", nargs="+", help="the problem, in plain words")
    cli.add_argument("--project", metavar="KEY", default="SD",
                     help="restrict the search to this project key, or 'any' (default: SD)")
    cli.add_argument("--model", default=MODEL, metavar="ID",
                     help=f"CSCS model id (default: {MODEL})")
    cli.add_argument("--max-turns", type=int, default=10, metavar="N",
                     help="stop after N round trips to the model (default: 10)")
    args = cli.parse_args()
    question = " ".join(args.question)

    pat = os.environ.get("JIRA_TDS_PAT") or PAT_FILE.read_text().strip()
    jira = httpx.Client(headers={"Authorization": f"Bearer {pat}",
                                 "Accept": "application/json"}, timeout=30)

    key = os.environ.get("CSCS_INFERENCE_API_KEY") or KEY_FILE.read_text().strip()
    client = OpenAI(base_url=BASE_URL, api_key=key)

    projects = list_projects()
    if projects.startswith("Cannot"):
        raise SystemExit(f"Jira is not reachable: {projects}")
    scope = (f"Unless the question clearly points elsewhere, search inside "
             f"`project = {args.project}` -- that is where the Service Desk history lives. "
             f"Widen only if it returns nothing useful.") if args.project.lower() != "any" else \
        "Search the whole instance; pick the projects that fit the question."

    messages = [{"role": "system", "content": SYSTEM.format(
                    jira=JIRA, today=__import__("datetime").date.today().isoformat(),
                    projects=projects, scope=scope)},
                {"role": "user", "content": question}]
    print(f"{BOLD}question ▸{OFF} {question}")
    calls = sent = received = turn = 0

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
            fn = DISPATCH.get(call.function.name)
            result = fn(**params) if fn else f"No such tool: {call.function.name}"
            log_call(call.function.name, params, result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            calls += 1
    else:
        print(f"\n{YEL}stopped after {args.max_turns} turns without a final answer.{OFF}")

    print(f"\n{DIM}{turn} turns · {calls} tool calls · "
          f"{sent:,} tokens sent · {received:,} received{OFF}")


if __name__ == "__main__":
    main()
