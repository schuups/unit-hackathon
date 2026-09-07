# Jira Service Desk agent

Given a problem in plain words, this agent searches **jira-tds.cscs.ch** for
historical tickets that resemble it, reads the comment threads on the ones it
picks, and proposes a course of action grounded in what was actually done.

One file, `jira_agent.py`, same shape as `03-agent-example/ask.py`: three tools,
a dispatch table and a twenty-line loop. The model writes the JQL; the agent
decides whether to run it.

| Tool | What it reaches | Answers |
|---|---|---|
| `search_issues(jql, limit)` | `/rest/api/2/search`, read-only | which tickets look like this |
| `read_issue(key, comments)` | `/rest/api/2/issue/KEY` | what was actually diagnosed and done — the comment thread |
| `list_projects()` | `/rest/api/2/project` | the project keys (also injected into the system prompt at startup) |

## Run it

```bash
uv run --with openai,httpx jira_agent.py \
  "a user reports their jobs get stuck in the queue with 'launch failed' and they have to scancel them manually"
```

Credentials, both read at startup, no arguments needed:

* Jira PAT — `$JIRA_TDS_PAT`, else `~/.jira-tds-pat` (Bearer auth, Jira Server 10.3).
* CSCS inference key — `$CSCS_INFERENCE_API_KEY`, else `~/agent-sandbox/secrets/cscs-api-key`.

Model `moonshotai/Kimi-K2.7-Code` on `https://api.inference.cscs.ch/v1`.

Flags: `--project KEY` (default `SD`, the CSCS Service Desk; `any` searches the
whole instance), `--model ID`, `--max-turns N` (default 10).

## What a run looks like

The example above: 6 turns, 8 tool calls. The model searched
`text ~ "launch failed"` (665 hits), narrowed with `scancel`, then
`launch_failed_requeued_held`, then `resolution IS NOT EMPTY`, opened
**SD-60454**, **SD-28792** and **SD-51358**, and came back with the pattern that
only exists in the comments — the held state is released with
`scontrol release <JOBID>`, and the root cause is node-side (a failed
`node_prolog`, a node back in service too early, a `slurmctld` restart after a
version mismatch) rather than user error.

Nothing in `jira_agent.py` branches on the question. Which searches get run, and
in what order, is decided by the model on every run.

## Notes for the demo

* `text ~ "several words"` matches *any* of them, so long phrases return noise —
  the system prompt tells the model to keep queries to the two or three specific
  words. Watch it narrow across turns; that is the agentic part.
* Output is capped where Jira is unbounded: 12 comments per issue (head + tail),
  1200 chars per body, 12000 chars per tool result. Comment threads are the one
  place this agent can blow its context.
* `search_issues` refuses anything that is not a query, and every endpoint it
  touches is a GET — the PAT's write permissions are never exercised.
* The search runs as **you**: the agent only sees tickets your account can see.
