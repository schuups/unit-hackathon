# Build your own agent — a CSCS Service Desk assistant

A working agent in **one readable file**. No framework, no orchestration
library: `ask.py` is the whole thing, and the loop at the bottom of it is
twenty lines.

The point it makes is the one from Part 1: *the model requests, the agent
executes.* Here you can see both halves at once — the model picks which data
sources to consult and writes the SQL, and this program decides whether to
comply.

## What it can reach

Three sources, deliberately of three different kinds, because that is what an
in-house agent actually faces:

| Source | Tool | Answers |
|---|---|---|
| `accounting.db` — SQLite, Slurm-shaped: `projects`, `users`, `jobs` | `run_sql` | what *happened* |
| a telemetry service on `localhost:8088` | `get_node_metrics`, `list_alerts` | what is happening *now* |
| `docs/` — four runbooks and policies | `search_docs` | what to *do about it* |

Nothing in `ask.py` branches on the question. Which sources get used, and in
what order, is decided by the model on every run.

## The database the agent writes SQL against

`seed.py` builds `accounting.db`: **240 jobs** by **12 users**
across **5 projects**, spanning 1 July to 6 September 2026.
Three tables, Slurm-shaped:

```sql
CREATE TABLE jobs (
    job_id      INTEGER PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES users(username),
    project_id  TEXT NOT NULL REFERENCES projects(project_id),
    partition   TEXT NOT NULL,           -- normal | gpu | debug | prepost
    nodes       INTEGER NOT NULL,
    node_list   TEXT NOT NULL,           -- e.g. 'nid02' or 'nid[02-05]'
    state       TEXT NOT NULL,           -- COMPLETED | FAILED | TIMEOUT | OUT_OF_MEMORY | CANCELLED
    exit_code   INTEGER NOT NULL,
    submit_time TEXT NOT NULL,           -- 'YYYY-MM-DD HH:MM:SS'
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    node_hours  REAL NOT NULL            -- nodes x elapsed hours
)

CREATE TABLE projects (
    project_id            TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    pi                    TEXT NOT NULL,
    allocation_node_hours REAL NOT NULL   -- granted for the current quarter
)

CREATE TABLE users (
    username   TEXT PRIMARY KEY,
    full_name  TEXT NOT NULL,
    unit       TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id)
)
```

Two rows, so you know what the values look like:

| job_id | username | project_id | partition | nodes | node_list | state | exit_code | start_time | node_hours |
|---|---|---|---|---|---|---|---|---|---|
| `4831` | `mrossi` | `s1023` | `gpu` | `4` | `nid[02-05]` | `TIMEOUT` | `0` | `2026-09-05 08:16:00` | `96.0` |
| `4838` | `kvogel` | `s1101` | `normal` | `4` | `nid[04-07]` | `COMPLETED` | `0` | `2026-09-06 10:06:00` | `22.0` |

Job **4831** is the one the demo asks about, and the two rows above are the
contrast: a four-node GPU job on `nid[02-05]` that burned its full 24 hours and
ended in `TIMEOUT`, next to a normal job that completed. Jobs 4833 and 4835 also
timed out on nid02 in the same three days — a pattern the agent can find on its
own with a `GROUP BY`.

**This exact text is what the model is shown.** `ask.py` reads it back out of
`sqlite_master` at startup and drops it into the system prompt, so the schema
the model writes against can never drift from the schema on disk.

## Run it

```bash
python3 seed.py                       # once: builds accounting.db (240 jobs, deterministic)
python3 metrics_service.py            # leave running in a second terminal
uv run --with openai,httpx ask.py "job 4831 failed on nid02 - what happened and what should I do?"
```

No virtualenv and no install step: `uv` fetches `openai` and `httpx` for the
one command. The API key is read from `$CSCS_INFERENCE_API_KEY`, or from
`~/agent-sandbox/secrets/cscs-api-key` if that is not set (see `01-sandboxing/`
for how to get one).

Model: `moonshotai/Kimi-K2.7-Code` on `https://api.inference.cscs.ch/v1`.
`ask.py --help` lists the two flags worth knowing: `--model ID` to try another
CSCS model, and `--max-turns N` to cap the round trips.

## The demo, in order

**1 — one source.** The database on its own:

```
ask.py "which project is closest to using up its allocation, and how much has it burned?"
```

One `run_sql` call, and the SQL is worth reading out: nobody wrote that query,
and the schema it is written against was pulled from `sqlite_master` at
startup.

**2 — a different source.** Same binary, no database this time:

```
ask.py "what is our policy on refunding node hours lost to a hardware fault?"
```

**3 — all three at once.** The one to spend time on:

```
ask.py "job 4831 failed on nid02 - what happened and what should I do?"
```

It issues four tool calls in the first turn — accounting, telemetry, alerts,
docs — then assembles one answer: the job hit its walltime because nid02 is
throttling at ~89 °C, here is the runbook, and the 96 node hours are
refundable. Three systems, one question, no glue code written by you.

Two things to point at while it runs:

- **The failed lookup.** `search_docs` often misses on its first guess and the
  model reads the error and tries a better keyword. That recovery is the loop
  doing its job, not a bug.
- **The token counter.** `628 → 1,231 → 1,645 tokens sent`. That is Part 1's
  "every turn re-sends everything", happening in front of them. The `cached`
  figure next to it is the endpoint's prompt cache working.

## The part that is enforced

`run_sql` accepts a single `SELECT` and nothing else, and opens the database
read-only. Ask the agent to drop a table and it will usually decline on its
own — but *that* is politeness, not a control. The control is one line of
Python, and you can show it without the model in the way:

```bash
uv run --with openai,httpx python -c "import ask
print(ask.run_sql('DROP TABLE jobs'))
print(ask.run_sql('SELECT * FROM jobs; DROP TABLE jobs'))"
```

```
REFUSED: this tool runs a single SELECT and nothing else.
REFUSED: this tool runs a single SELECT and nothing else.
```

Whatever the model asks for, that check runs first. This is the difference
between a rule written in prose and a rule written in code.

## Where to take it next

Every tool is an ordinary Python function. To point this at your own systems,
replace the four in section 1 of `ask.py` and describe them in `TOOLS` — the
schema block is what the model actually sees, and it is sent on every request.
That is the entire extension mechanism.

Worth trying:

- Add a fifth tool against a system you own.
- Take `search_docs` away and watch the answers get vaguer but no less
  confident.
- Run the same question with `--model zai-org/GLM-5.2` and compare which
  sources each model reaches for.
- Delete the `SELECT` guard and re-run the injection. Then put it back.
