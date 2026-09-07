"""The environment under evaluation -- four read-only tools over frozen data.

An evaluation is a measurement, and a measurement needs a fixed instrument. The
tools here are the ones from module 03, with one deliberate change: every source
of nondeterminism has been pinned.

  * accounting.db   240 jobs, 12 users, 5 projects, built from a seeded RNG so
                    it is byte-identical every time. Opened read-only.
  * telemetry       the node-telemetry service it stands in for drifts on every
                    call -- sin(time.time()) plus jitter -- so two runs of the
                    same task would see different numbers and no result would be
                    comparable to any other. Replaced here by telemetry.json,
                    a single frozen capture.
  * docs/           four runbooks and policies. Plain files, already fixed.

That substitution is the first thing evaluation forces on you, and it is worth
saying out loud: you cannot compare two setups against a moving target.
"""
import json
import os
import pathlib
import sqlite3

HERE = pathlib.Path(__file__).parent
# The fixtures live here, in this module, so the whole thing is self-contained:
# clone this directory alone and every command still works. Override with
# EVAL_FIXTURES to point at your own data.
FIXTURES = pathlib.Path(os.environ.get("EVAL_FIXTURES", HERE / "fixtures")).resolve()

DB = FIXTURES / "accounting.db"
DOCS = FIXTURES / "docs"
TELEMETRY = HERE / "telemetry.json"

# The date the fixture is frozen at. The agent is told this, so "since
# 1 September" means the same thing on every run.
TODAY = "2026-09-06"


def _telemetry():
    return json.loads(TELEMETRY.read_text())


def check_fixtures():
    """Fail early and legibly rather than half-way through a paid run."""
    missing = [str(p) for p in (DB, DOCS, TELEMETRY) if not p.exists()]
    if missing:
        raise SystemExit(
            "eval: missing fixtures:\n  " + "\n  ".join(missing) +
            "\n\nThey ship with this module in fixtures/. If you moved them, point"
            "\nEVAL_FIXTURES at wherever they live.")


# ---------------------------------------------------------------------------
# The tools. Ordinary functions -- nothing here knows an LLM exists.
# ---------------------------------------------------------------------------

def run_sql(query):
    """Historical data: the Slurm accounting database.

    The SELECT guard is the enforced control, exactly as in module 03: it runs
    before the query does, whatever the model asked for. One of the tasks in
    the suite tries to get past it, and the trajectory records what happened.
    """
    q = query.strip().rstrip(";")
    if not q.lower().startswith("select") or ";" in q:
        return "REFUSED: this tool runs a single SELECT and nothing else."
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(q).fetchall()
    except sqlite3.Error as e:
        return f"SQL error: {e}"
    return json.dumps([dict(r) for r in rows[:50]], default=str)


def get_node_metrics(node):
    """Live state -- frozen. One capture, so every run sees the same cluster."""
    nodes = _telemetry()["nodes"]
    if node not in nodes:
        return json.dumps({"error": f"no such node: {node}", "known_nodes": list(nodes)})
    return json.dumps(nodes[node], indent=2)


def list_alerts():
    """Derived from the same frozen capture, by the same rules as module 03."""
    t = _telemetry()
    out = []
    for node, m in t["nodes"].items():
        if m["throttling"]:
            out.append({"node": node, "severity": "warning", "alert": "thermal_throttling",
                        "detail": f"{m['temp_c']} C is above the {t['throttle_c']} C throttle point",
                        "since": "2026-09-04 02:10:00"})
        if m["state"] == "drained":
            out.append({"node": node, "severity": "info", "alert": "node_drained",
                        "detail": "scheduled hardware maintenance", "since": "2026-09-05 06:00:00"})
    return json.dumps(out, indent=2)


def search_docs(keyword):
    """Procedure and policy: a keyword grep over the runbooks. Crude on purpose."""
    docs = sorted(DOCS.glob("*.md"))
    hits = [f"### {p.name}\n{p.read_text()}" for p in docs
            if keyword.lower() in (p.name + p.read_text()).lower()]
    return "\n\n".join(hits)[:4000] or \
        f"Nothing matches {keyword!r}. Available: {[p.name for p in docs]}"


DISPATCH = {"run_sql": run_sql, "get_node_metrics": get_node_metrics,
            "list_alerts": list_alerts, "search_docs": search_docs}



def db_schema():
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
        return "\n".join(r[0] for r in db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"))


def _schema_or_hint():
    """The schema goes in the TOOL DESCRIPTION, not in a system prompt.

    That matters for the comparison. Each harness writes its own system prompt
    and we are deliberately not overriding them, so anything the agents must all
    know has to travel by a route that is identical for every one of them. The
    tool description is that route: it is part of the environment, and every
    harness forwards it to the model unchanged.
    """
    try:
        return db_schema()
    except Exception:
        return "(schema unavailable -- run seed.py in module 03)"

# The JSON the model is shown. A setup may expose a subset of these -- which
# tools an agent is given is one of the things worth A/B-ing.
TOOL_SCHEMAS = {
    "run_sql": {"type": "function", "function": {
        "name": "run_sql",
        "description": "Run one read-only SELECT against the Slurm accounting database. "
                       "Use it for anything historical: who ran what, node hours consumed, "
                       "job states, allocations. Note that node_list uses Slurm range "
                       "notation such as 'nid[02-05]', which covers four nodes. "
                       "The schema is:\n" + _schema_or_hint(),
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query": {"type": "string", "description": "A single SELECT statement."}}}}},
    "get_node_metrics": {"type": "function", "function": {
        "name": "get_node_metrics",
        "description": "Live telemetry for one compute node right now: temperature, power "
                       "draw, GPU utilisation, fan speed, whether it is thermally throttling.",
        "parameters": {"type": "object", "required": ["node"], "properties": {
            "node": {"type": "string", "description": "Node name, e.g. 'nid02'."}}}}},
    "list_alerts": {"type": "function", "function": {
        "name": "list_alerts",
        "description": "Every alert firing on the cluster at this moment, across all nodes.",
        "parameters": {"type": "object", "properties": {}}}},
    "search_docs": {"type": "function", "function": {
        "name": "search_docs",
        "description": "Search the Service Desk runbooks and policies for a keyword. "
                       "Use it for procedure and policy: what to do about a fault, how "
                       "allocations, refunds and maintenance windows work.",
        "parameters": {"type": "object", "required": ["keyword"], "properties": {
            "keyword": {"type": "string", "description": "One word or short phrase."}}}}},
}

