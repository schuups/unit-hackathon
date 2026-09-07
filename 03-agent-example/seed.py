"""Build accounting.db -- a miniature Slurm accounting database.

Stands in for the kind of in-house database every unit has: who ran what,
on how many nodes, for how long, and against which allocation.

Deterministic: same numbers on every run, so the demo tells the same story
twice. Run it once:   python3 seed.py
"""
import pathlib
import random
import sqlite3
from datetime import datetime, timedelta

DB = pathlib.Path(__file__).parent / "accounting.db"
random.seed(7)

# project_id, name, PI, allocation for the quarter (node hours)
PROJECTS = [
    ("s1023", "Climate Downscaling CH2100", "Prof. H. Bernet",   4000),
    ("s1044", "Cardiac Flow Simulation",    "Dr. A. Lombardi",   1500),
    ("s1101", "Lattice QCD Production",     "Prof. K. Vogel",    6000),
    ("s1187", "Genome Assembly Pipeline",   "Dr. S. Amrein",     1200),
    ("s1250", "Swiss AI Pretraining",       "Prof. N. Baumann",  3000),
]

# username, full name, unit, project
USERS = [
    ("hbernet",   "Hanna Bernet",     "Atmospheric Physics", "s1023"),
    ("mrossi",    "Marco Rossi",      "Atmospheric Physics", "s1023"),
    ("tkeller",   "Timo Keller",      "Atmospheric Physics", "s1023"),
    ("alombardi", "Anna Lombardi",    "Biomedical Eng.",     "s1044"),
    ("pfrei",     "Pia Frei",         "Biomedical Eng.",     "s1044"),
    ("kvogel",    "Karl Vogel",       "Theoretical Physics", "s1101"),
    ("akaufmann", "Andrin Kaufmann",  "Theoretical Physics", "s1101"),
    ("rmoser",    "Rahel Moser",      "Theoretical Physics", "s1101"),
    ("samrein",   "Simon Amrein",     "Genomics",            "s1187"),
    ("nbaumann",  "Nadia Baumann",    "AI Group",            "s1250"),
    ("lweber",    "Livia Weber",      "AI Group",            "s1250"),
    ("dsteiner",  "David Steiner",    "AI Group",            "s1250"),
]

NODES = [f"nid{i:02d}" for i in range(1, 9)]
PARTITIONS = ["normal", "gpu", "debug", "prepost"]
PART_W     = [     45,    35,      12,         8]
STATES = ["COMPLETED", "FAILED", "TIMEOUT", "OUT_OF_MEMORY", "CANCELLED"]
STATE_W = [        74,        11,        7,               5,           3]

# The AI group burns the most; the genomics project the least.
USER_W = [3 if u[3] == "s1250" else 2 if u[3] == "s1101" else 1 for u in USERS]

START, END = datetime(2026, 7, 1, 6), datetime(2026, 9, 3, 23)


def node_list(n):
    """A Slurm-style node list: 'nid04' or 'nid[03-06]'."""
    first = random.randint(1, len(NODES) - n + 1)
    if n == 1:
        return f"nid{first:02d}"
    return f"nid[{first:02d}-{first + n - 1:02d}]"


rows = []
for _ in range(231):
    user, _name, _unit, project = random.choices(USERS, USER_W)[0]
    part = random.choices(PARTITIONS, PART_W)[0]
    nodes = 1 if part in ("debug", "prepost") else random.choices([1, 2, 4, 8], [40, 30, 20, 10])[0]
    hours = round(random.uniform(0.1, 0.6) if part == "debug" else random.uniform(0.5, 24.0), 2)
    state = random.choices(STATES, STATE_W)[0]
    submit = START + timedelta(seconds=random.randint(0, int((END - START).total_seconds())))
    start = submit + timedelta(minutes=random.randint(1, 240))
    rows.append([user, project, part, nodes, node_list(nodes), state,
                 0 if state == "COMPLETED" else random.choice([1, 2, 9, 137]),
                 submit, start, start + timedelta(hours=hours), round(nodes * hours, 2)])

rows.sort(key=lambda r: r[7])                      # job ids are handed out in time order
rows = [[4600 + i] + r for i, r in enumerate(rows)]

# The story: nid02 has been running hot for three days, and jobs that land on
# it burn their whole walltime and time out. Job 4831 is the one the demo asks
# about; 4833 and 4835 are the pattern the agent can find in the same table.
def story(jid, user, project, part, nodes, nl, state, code, submit, hours):
    s = datetime.fromisoformat(submit)
    return [jid, user, project, part, nodes, nl, state, code,
            s, s + timedelta(minutes=4), s + timedelta(minutes=4, hours=hours),
            round(nodes * hours, 2)]

rows += [
    story(4831, "mrossi",    "s1023", "gpu",     4, "nid[02-05]", "TIMEOUT",   0, "2026-09-05 08:12:00", 24.0),
    story(4832, "akaufmann", "s1101", "normal",  2, "nid[06-07]", "COMPLETED", 0, "2026-09-05 09:40:00",  6.5),
    story(4833, "lweber",    "s1250", "gpu",     2, "nid[02-03]", "TIMEOUT",   0, "2026-09-05 14:05:00", 12.0),
    story(4834, "samrein",   "s1187", "prepost", 1, "nid08",      "COMPLETED", 0, "2026-09-05 18:22:00",  1.2),
    story(4835, "mrossi",    "s1023", "gpu",     4, "nid[02-05]", "TIMEOUT",   0, "2026-09-06 07:03:00", 24.0),
    story(4836, "pfrei",     "s1044", "normal",  1, "nid07",      "COMPLETED", 0, "2026-09-06 08:15:00",  3.0),
    story(4837, "dsteiner",  "s1250", "gpu",     8, "nid[01-08]", "FAILED",    1, "2026-09-06 09:30:00",  0.4),
    story(4838, "kvogel",    "s1101", "normal",  4, "nid[04-07]", "COMPLETED", 0, "2026-09-06 10:02:00",  5.5),
    story(4839, "tkeller",   "s1023", "debug",   1, "nid01",      "COMPLETED", 0, "2026-09-06 11:48:00",  0.3),
]

DB.unlink(missing_ok=True)
db = sqlite3.connect(DB)
db.executescript("""
CREATE TABLE projects (
    project_id            TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    pi                    TEXT NOT NULL,
    allocation_node_hours REAL NOT NULL   -- granted for the current quarter
);
CREATE TABLE users (
    username   TEXT PRIMARY KEY,
    full_name  TEXT NOT NULL,
    unit       TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id)
);
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
);
""")
db.executemany("INSERT INTO projects VALUES (?,?,?,?)", PROJECTS)
db.executemany("INSERT INTO users VALUES (?,?,?,?)", USERS)
db.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               [r[:8] + [d.strftime("%Y-%m-%d %H:%M:%S") for d in r[8:11]] + r[11:] for r in rows])
db.commit()

print(f"wrote {DB.name}: {len(rows)} jobs, {len(USERS)} users, {len(PROJECTS)} projects")
for pid, name, used, alloc in db.execute("""
        SELECT p.project_id, p.name, ROUND(SUM(j.node_hours),1), p.allocation_node_hours
        FROM projects p JOIN jobs j USING (project_id) GROUP BY 1 ORDER BY 3 DESC"""):
    print(f"  {pid}  {name:<28} {used:>8.1f} / {alloc:>7.0f} node hours  ({100*used/alloc:.0f}%)")
