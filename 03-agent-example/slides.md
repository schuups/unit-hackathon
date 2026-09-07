---
marp: true
theme: default
paginate: true
size: 16:9
header: 'SW1 Unit Hackathon on Agentic possibilities'
footer: '7th September 2026, CSCS LCP'
style: |
  :root {
    --ink: #16202b;
    --muted: #5b6b7c;
    --accent: #0f6f8c;
    --warn: #b4451f;
    --rule: #d8e0e6;
    --code-bg: #f2f5f7;
  }
  section {
    font-family: "Helvetica Neue", Inter, system-ui, sans-serif;
    font-size: 25px;
    color: var(--ink);
    background: #ffffff;
    padding: 60px 70px 70px 70px;
    line-height: 1.45;
  }
  section h1 { font-size: 46px; color: var(--ink); margin: 0 0 .4em 0; letter-spacing: -.5px; }
  section h2 { font-size: 34px; color: var(--accent); margin: 0 0 .5em 0; letter-spacing: -.3px; }
  section h3 { font-size: 27px; color: var(--muted); font-weight: 600; }
  section code {
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    background: var(--code-bg); padding: .08em .3em; border-radius: 4px; font-size: .92em;
  }
  section pre {
    background: var(--code-bg); border-left: 4px solid var(--accent);
    padding: 16px 20px; border-radius: 6px; font-size: 19px; line-height: 1.35;
  }
  section pre code { background: none; padding: 0; font-size: inherit; }
  section blockquote {
    border-left: 4px solid var(--warn); margin-left: 0; padding-left: 20px;
    color: var(--ink); font-style: normal;
  }
  section strong { color: var(--accent); }
  section em { color: var(--muted); font-style: italic; }
  header, footer { color: #9aa8b4; font-size: 15px; }
  section::after { color: #9aa8b4; font-size: 15px; }

  /* title + section dividers */
  section.lead, section.section {
    background: #16202b; color: #f4f7f9; justify-content: center;
  }
  section.lead h1, section.section h1 { color: #ffffff; font-size: 56px; }
  section.lead h2, section.section h2 { color: #7fc8dd; font-size: 30px; font-weight: 500; }
  section.lead strong, section.section strong { color: #7fc8dd; }
  section.lead em, section.section em { color: #a9bccb; }
  section.lead .note, section.section .note { color: #93a5b3; }
  section.lead blockquote, section.section blockquote { border-left-color: #7fc8dd; }
  section.lead code, section.section code { background: #24313f; color: #cfe6ef; }
  section.section::after, section.lead::after { color: #52616f; }

  /* two-column layout */
  section.split { display: grid; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
  .cols.wide-left { grid-template-columns: 1.35fr 1fr; }

  /* small helper classes */
  .big { font-size: 34px; line-height: 1.35; }
  .note { color: var(--muted); font-size: 21px; }
  .tag {
    display: inline-block; background: var(--warn); color: #fff; font-size: 15px;
    padding: 2px 10px; border-radius: 12px; letter-spacing: .4px; vertical-align: middle;
  }
  .tag.ok { background: var(--accent); }
  /* three-column grid + framed cards */
  .cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 26px; }
  .card { border-top: 3px solid var(--accent); padding-top: 9px; font-size: 21px; }
  .card.warn { border-top-color: var(--warn); }
  .card h4 { margin: 0 0 .25em 0; font-size: 22px; color: var(--accent); font-weight: 700; }
  .card.warn h4 { color: var(--warn); }

  /* one-line lead-in under a heading */
  .lede { font-size: 23px; color: var(--muted); margin: -.35em 0 .85em 0; line-height: 1.35; }

  /* figures built from plain elements — no raw SVG, so they survive any renderer */
  .fig { margin: 12px 0 14px 0; }
  .axis { font-size: 14px; color: var(--muted); margin: 0 0 6px 92px; }
  .brow { display: grid; grid-template-columns: 80px 1fr; align-items: center;
          gap: 12px; margin-bottom: 8px; }
  .blab { font-size: 16px; color: var(--muted); text-align: right; }
  .bar { display: flex; height: 24px; }
  .bar .hist { background: #8fb9cc; }
  .bar .new { background: var(--warn); width: 4%; }
  .w0 { width: 0; } .w26 { width: 26%; } .w54 { width: 54%; } .w86 { width: 86%; }
  .legend { font-size: 14px; color: var(--muted); margin: 8px 0 0 92px; }
  .legend.ind { margin: -2px 0 12px 92px; }
  .sw { display: inline-block; width: 11px; height: 11px; margin-right: 6px; }
  .sw.h { background: #8fb9cc; } .sw.n { background: var(--warn); }

  .ttft { width: 34%; border-bottom: 1px solid #9aa8b4; text-align: center;
          font-size: 14px; color: var(--muted); padding-bottom: 3px; margin-bottom: 5px; }
  .tl { display: flex; height: 48px; font-size: 16px; }
  .tl.slim { height: 30px; font-size: 14px; }
  .tl-pre { flex: 0 0 34%; background: var(--accent); color: #fff;
            display: flex; align-items: center; justify-content: center; letter-spacing: .5px; }
  .tl-pre.cold { flex: 0 0 52%; }
  .tl-pre.warm { flex: 0 0 5%; }
  .tl-dec { flex: 1; color: #2f6b55; display: flex; align-items: center;
            justify-content: center; letter-spacing: .5px;
            background: repeating-linear-gradient(90deg, #7fbfa3 0 14px, #ffffff 14px 22px); }
  .chip { background: #ffffff; color: #2f6b55; padding: 3px 10px; letter-spacing: .5px; }
  .tlcap { display: flex; font-size: 14px; color: var(--muted); margin-top: 5px; }
  .tlcap .c1 { flex: 0 0 34%; text-align: center; }
  .tlcap .c2 { flex: 1; text-align: center; }

  /* email mock-up */
  .mail { border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; font-size: 19px; }
  .mail-hdr { background: #eef3f6; padding: 7px 13px; border-bottom: 1px solid var(--rule);
              color: var(--muted); font-size: 15px;
              font-family: ui-monospace, Menlo, monospace; }
  .mail-body { padding: 11px 13px; line-height: 1.4; }
  .ghost { color: #fefefe; }
  .reveal { display: block; margin: 8px 0; background: #fdeeea; color: var(--warn);
            border-left: 3px solid var(--warn); padding: 8px 11px;
            font-family: ui-monospace, Menlo, monospace; font-size: 16px; line-height: 1.4; }
  .caption { font-size: 17px; color: var(--muted); margin-top: 7px; }

  section.tight li { margin-bottom: .15em; }
  section.tight { font-size: 23px; }

  /* prompt -> which sources it should reach for */
  .rows { display: grid; gap: 9px; margin-top: 4px; }
  .row { display: grid; grid-template-columns: 1.75fr 1fr; gap: 20px;
         align-items: baseline; border-bottom: 1px solid var(--rule); padding-bottom: 7px; }
  .row .k { font-family: ui-monospace, Menlo, monospace; font-size: 17px; }
  .row .v { font-size: 16px; color: var(--muted); text-align: right; }

  /* file list */
  .files { font-family: ui-monospace, Menlo, monospace; font-size: 18px; line-height: 1.6; }
  .files b { color: var(--accent); font-weight: 600; }
  .files span { color: var(--muted); font-family: "Helvetica Neue", sans-serif; font-size: 17px; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

# Build a specialized agent

## A Service Desk assistant over three in-house systems
### Stefano Schuppli

<br>

<span class="note">138 lines of Python, no framework. A SQLite accounting database, a live metrics service and a folder of runbooks — and a model that works out for itself which of them each question needs.</span>

<!--
Stand-alone deck: assumes nothing from any other talk. Two slides of scenario,
four of code, then everything else happens at the terminal. Keep it moving.
-->

---

## The scenario — a Service Desk assistant

<p class="lede">One question from a user. The answer is spread across three systems, and none of them knows about the other two.</p>

> *"Job 4831 failed on nid02 — what happened and what should I do?"*

To answer that, somebody normally opens three windows:

- the **accounting database** — what state did the job end in, what did it cost
- the **monitoring** — is that node healthy *right now*
- the **runbook** — what is the procedure when it is not

<span class="note">That shape — history, live state, procedure — is most of what a service desk does. It is why this makes a good first agent.</span>

---

## What it can reach

<p class="lede">Three sources, and deliberately three different kinds of integration.</p>

<div class="cols3">
<div class="card">

#### accounting.db
SQLite · `run_sql`

240 jobs, 12 users, 5 projects.

**What happened.**

</div>
<div class="card">

#### telemetry
HTTP :8088 · `get_node_metrics` `list_alerts`

Temperature, power, alerts.

**What is happening now.**

</div>
<div class="card">

#### docs/
files · `search_docs`

Four runbooks and policies.

**What to do about it.**

</div>
</div>

<br>

<span class="note">A database driver, an HTTP call and a file read — because that is what you actually have in-house. Four tools over three sources: one source can expose several.</span>

---

<!-- _class: tight -->

## 1 — The database

<p class="lede">A miniature Slurm accounting database, standing in for whatever your unit really queries.</p>

```sql
CREATE TABLE jobs (
    job_id INTEGER PRIMARY KEY, username TEXT, project_id TEXT,
    partition   TEXT,      -- normal | gpu | debug | prepost
    nodes INTEGER, node_list TEXT,   -- 'nid02' or 'nid[02-05]'
    state       TEXT,      -- COMPLETED | FAILED | TIMEOUT | OUT_OF_MEMORY
    exit_code INTEGER, submit_time TEXT, start_time TEXT, end_time TEXT,
    node_hours  REAL);     -- nodes x elapsed hours
```

…plus `projects` (allocation in node hours, PI) and `users`.

> The schema is read back out of `sqlite_master` at start-up and pasted into
> the system prompt. **The model writes every query itself** — there is not one
> SQL statement written in advance anywhere in the application.

---

## 2 — The metrics service

<p class="lede">A separate process, so the agent has to reach it over HTTP exactly as it would reach the real monitoring API.</p>

<div class="cols">
<div>

```
GET /nodes           all eight nodes
GET /metrics/<node>  temperature, power,
                     GPU util, throttling
GET /alerts          what is firing now
```

</div>
<div>

```json
{ "node": "nid02",
  "temp_c": 88.5,
  "power_w": 581,
  "throttling": true }
```

</div>
</div>

<span class="note">Values drift on every call — <code>curl</code> it twice and they change. <strong>nid02 has been above the 85 °C throttle point for three days</strong>, and that single fault is what the whole demo hangs on.</span>

---

## 3 — The runbooks

<p class="lede">Prose, not data. The part that says what to <em>do</em>.</p>

<div class="files">
<b>runbook-thermal-throttling.md</b> &nbsp; <span>hot node → 30-50% slower → TIMEOUT</span><br>
<b>runbook-out-of-memory.md</b> &nbsp; <span>exit 137, and when it is the node's fault</span><br>
<b>policy-fair-share.md</b> &nbsp; <span>allocations, the 80% warning, refunds</span><br>
<b>policy-maintenance-windows.md</b> &nbsp; <span>drains, scheduled and not</span>
</div>

<br>

<span class="note"><code>search_docs</code> is a keyword grep in one line of Python. Crude on purpose — and it misses often enough that you get to watch the agent read the failure and try a better word.</span>

---

## `ask.py` — 138 lines, four blocks

<p class="lede">That is the whole application. There is no framework underneath it.</p>

<div class="cols">
<div class="card">

#### 1 — The tools
Four ordinary Python functions. Nothing in them knows that an LLM exists.

</div>
<div class="card">

#### 2 — The tool list
The JSON schema the model is shown. Sent on every request.

</div>
</div>
<div class="cols">
<div class="card">

#### 3 — The system prompt
Who it is, today's date, and the database schema.

</div>
<div class="card">

#### 4 — The loop
send → read → execute → append → repeat.

</div>
</div>

<span class="note">The <code>openai</code> package is used <strong>only as an HTTP client</strong>. The agent is the code around it: the model reasons, this program acts.</span>

---

## The tool list — what the model is actually shown

<p class="lede">Appended to every request, alongside the question. You never write it by hand and you never see it — here it is, for one tool.</p>

```json
{"type": "function", "function": {
  "name": "run_sql",
  "description": "Run one read-only SELECT against the Slurm accounting
                  database (tables: projects, users, jobs). Use it for
                  anything historical: who ran what, node hours consumed,
                  job states, allocations.",
  "parameters": {"type": "object", "required": ["query"], "properties": {
      "query": {"type": "string", "description": "A single SELECT statement."}}}}}
```

<span class="note">Four of these. <strong>This is the entire extension mechanism:</strong> to point the agent at your systems, write a function and describe it here. The description is prompt engineering — it is how the model decides when to reach for it.</span>

---

<!-- _class: tight -->

## The loop

<p class="lede">Twenty lines. This is what makes it an agent rather than a chat window.</p>

```python
for turn in range(1, args.max_turns + 1):
    reply = client.chat.completions.create(model=args.model,
                                           messages=messages, tools=TOOLS)
    message = reply.choices[0].message
    messages.append(message.model_dump(exclude_none=True))

    if not message.tool_calls:                 # nothing left to look up
        print(message.content); break

    for call in message.tool_calls:            # THE AGENT executes, not the model
        params = json.loads(call.function.arguments)
        result = DISPATCH[call.function.name](**params)
        messages.append({"role": "tool", "tool_call_id": call.id,
                         "content": result})
```

> The model never touches the database. It names a function and some arguments;
> `DISPATCH` decides whether that happens.

---

## Start it

<p class="lede">No virtualenv and no install step — <code>uv</code> fetches the two dependencies for the one command.</p>

```bash
python3 seed.py               # once: builds accounting.db, 240 jobs, deterministic
python3 metrics_service.py    # second terminal — leave it running

uv run --with openai,httpx ask.py "which project is closest to its allocation?"
```

<div class="cols">
<div>

**Key** — `$CSCS_INFERENCE_API_KEY`, or
`~/agent-sandbox/secrets/cscs-api-key`,
created at `ui.inference.cscs.ch`.

</div>
<div>

**Model** — `moonshotai/Kimi-K2.7-Code`
on `api.inference.cscs.ch`.
`--model` to try another.

</div>
</div>

---

## What you see while it runs

<p class="lede">The log is half the point: every tool call, its arguments, and the context growing underneath.</p>

```
── turn 1 ──────────────────────────── 628 tokens sent (0 cached)
  ⚙ run_sql(query='SELECT * FROM jobs WHERE job_id = 4831')
    ← 288 chars: [{"job_id": 4831, "username": "mrossi", "state": "TIME…
  ⚙ get_node_metrics(node='nid02')
    ← 201 chars: {"node": "nid02", "temp_c": 88.5, "throttling": true, …
  ⚙ search_docs(keyword='TIMEOUT')
    ← 1,261 chars: ### runbook-thermal-throttling.md # Runbook: node runn…

── turn 2 ──────────────────────────── 1,527 tokens sent (576 cached)
```

> **628 → 1 527 → 2 134 tokens sent.** The model keeps no memory between calls,
> so every turn re-sends the whole conversation. That growth *is* the running
> cost of an agent. The `cached` figure beside it is the endpoint's prompt cache
> taking the sting out of it.

---

<!-- _class: tight -->

## Prompts to try <span class="tag">YOUR TURN</span>

<p class="lede">Same binary every time. Nothing in the code branches on the question.</p>

<div class="rows">
<div class="row"><div class="k">"which project is closest to using up its allocation?"</div><div class="v">run_sql alone</div></div>
<div class="row"><div class="k">"what is our policy on refunding node hours lost to a hardware fault?"</div><div class="v">search_docs alone</div></div>
<div class="row"><div class="k">"is anything wrong with the cluster right now?"</div><div class="v">list_alerts alone</div></div>
<div class="row"><div class="k">"which nodes have had the most TIMEOUT jobs since 1 September?"</div><div class="v">run_sql, one GROUP BY it wrote itself</div></div>
<div class="row"><div class="k">"job 4831 failed on nid02 — what happened and what should I do?"</div><div class="v"><strong>all three sources</strong></div></div>
</div>

<span class="note">The last one is the one to sit with: four tool calls in the first turn, then one answer — the job burned its walltime because nid02 is throttling, here is the runbook, and the 96 node hours are refundable.</span>

<!--
The path varies run to run — the shape is stable, the exact SQL is not. Narrate
the shape, not the steps. Good harder one if there is time: "have other jobs on
nid02 timed out recently?" — the nid[02-05] range notation is awkward in SQL
and you get to watch it iterate for four or five turns.
-->

---

## The rule that is actually enforced

<p class="lede">Ask it to drop a table and it declines politely. That politeness is not a control.</p>

```python
def run_sql(query):
    q = query.strip().rstrip(";")
    if not q.lower().startswith("select") or ";" in q:
        return "REFUSED: this tool runs a single SELECT and nothing else."
```

<div class="cols">
<div class="card warn">

#### The model's refusal
Prose weighed against everything else in the context. Usually holds. Never checked.

</div>
<div class="card">

#### The three lines above
Run before the query does, on every call, whatever the model asked for.

</div>
</div>

<span class="note">The database is also opened <code>mode=ro</code>. A rule written in prose is a suggestion; a rule written in code is a control.</span>

---

<!-- _class: tight -->

## Take it apart <span class="tag">YOUR TURN</span>

<div class="cols">
<div>

**Try**

- add a fifth tool against a system *you* own
- delete `search_docs` and watch the answers get vaguer but no less confident
- `--model zai-org/GLM-5.2` — a different model reaches for different sources
- remove the `SELECT` guard, then re-run the injection

</div>
<div>

**What it deliberately is not**

- no memory between runs — every question is a fresh context
- no permission prompts: every tool is allowed, because every tool is small
- a keyword grep, not retrieval
- one user, one machine, no auth

</div>
</div>

---

<!-- _class: lead -->

# Over to you

<br>

**A tool is a function. The tool list is its documentation.**

<br>

<span class="note">Everything else in this application is code you already know how to write.</span>
