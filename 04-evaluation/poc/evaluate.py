"""Drive the comparison: run, judge, label, report.

    python3 evaluate.py setups                            what can be compared
    python3 evaluate.py doctor                            can each harness run?
    python3 evaluate.py compare oc-kimi oc-glm cc-kimi cc-glm --reps 3
    python3 evaluate.py label runs/<dir>                  put a human in the loop
    python3 evaluate.py report runs/<dir>                 re-render, free

The stages are separate commands on purpose. Trajectories are expensive and
scoring them is cheap, so splitting the two means you can re-judge, re-label and
re-report as often as you like against runs you have already paid for.
Everything lands in runs/<name>/ as JSON, so the evidence outlives the terminal
it was printed in.

No key? `python3 selftest.py` exercises every stage against a scripted stub
model. It proves the plumbing, not the models.
"""
import argparse
import datetime
import json
import pathlib
import random
import sys

import adapters
import judge as J
import report as R
from environment import TELEMETRY, check_fixtures
from harness import GRID, SETUPS, CSCSModel, Trajectory
from tasks import TASKS, TASKS_BY_ID

RUNS = pathlib.Path(__file__).parent / "runs"

# Judges, in preference order. evaluate.py drops any model that is itself under
# test: a model scoring its own output is the self-preference bias the panel
# exists to dilute, and it is the one bias removable for free.
JUDGE_POOL = [
    "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16",
    "swiss-ai/Apertus-v1.5-70B",
    "zai-org/GLM-5.2",
    "moonshotai/Kimi-K2.7-Code",
]


def pick_judges(setups, n=2, requested=None):
    if requested:
        return requested
    contestants = {s.model for s in setups}
    pool = [m for m in JUDGE_POOL if m not in contestants]
    if len(pool) < n:
        print(f"  ! only {len(pool)} judge(s) available that are not under test; "
              "self-preference bias is not fully mitigated.", file=sys.stderr)
    return pool[:n]


# ---------------------------------------------------------------------------

def cmd_setups(args):
    print("Setups available for comparison:\n")
    for s in SETUPS.values():
        print("  " + s.describe().replace("\n", "\n  ").rstrip() + "\n")
    print("The headline 2x2:\n")
    for (h, m), name in GRID["cells"].items():
        print(f"  {name:<10} {h:<12} {m}")
    print("\nTasks in the suite:\n")
    for t in TASKS:
        print(f"  {t['difficulty']:<11} {t['id']:<20} {t['prompt'][:58]}")
    print(f"\nFixtures: frozen telemetry ({TELEMETRY.name}), accounting.db and "
          f"docs/ from module 03, read-only.")


def cmd_doctor(args):
    """Check every harness can actually start, before anything is spent."""
    check_fixtures()
    print("  fixtures  ok")
    bad = 0
    for name, ad in adapters.ADAPTERS.items():
        why = ad.available()
        print(f"  {name:<12} {'ok' if why is None else 'UNUSABLE: ' + why}")
        bad += why is not None
    key = "set" if adapters.os.environ.get("CSCS_INFERENCE_API_KEY") else \
        ("key file" if (pathlib.Path.home() / "agent-sandbox/secrets/cscs-api-key").exists()
         else "MISSING")
    print(f"  api key      {key}")
    print(f"  mcp server   {'ok' if adapters.MCP_SERVER.exists() else 'MISSING'}")
    print(f"  oc config    {'ok' if adapters.OPENCODE_CONFIG.exists() else 'MISSING'}")
    return bad


def cmd_run(args):
    check_fixtures()
    setups = [SETUPS[n] for n in args.setups]
    tasks = [t for t in TASKS if not args.tasks or t["id"] in args.tasks]
    total = len(tasks) * args.reps * len(setups)

    for s in setups:
        why = adapters.get(s).available()
        if why:
            raise SystemExit(f"eval: setup {s.name} cannot run -- {why}")

    outdir = RUNS / (args.out or f"{datetime.date.today()}-" + "-vs-".join(args.setups))
    print(f"  setups: {', '.join(args.setups)}")
    print(f"  {len(tasks)} tasks x {args.reps} reps x {len(setups)} setups = {total} runs")
    print(f"  -> {outdir}\n")
    if args.dry_run:
        print("  --dry-run: nothing was sent.")
        print(f"    agents   {total} runs, each 1-6 model calls")
        print(f"    judges   {total} absolute + {len(tasks)} pairwise, x "
              f"{len(pick_judges(setups, requested=args.judges))} judges")
        return None

    outdir.mkdir(parents=True, exist_ok=True)
    runs = []
    for setup in setups:
        ad = adapters.get(setup)
        for task in tasks:
            for rep in range(args.reps):
                tr = ad.run(setup, task, rep, timeout=args.timeout)
                check = J.deterministic(task, tr)
                mark = "HARD" if check["hard_fail"] else ("ok  " if check["passed"] else "FAIL")
                why = "; ".join(check["failures"] + check["hard_fail"])[:70]
                print(f"  {mark}  {setup.name:<10} {task['id']:<20} rep{rep} "
                      f"{tr.turns}t {len(tr.calls)}c {tr.wall_s:>6.1f}s "
                      f"{tr.tokens['received']:>5}out" + (f"  <- {why}" if why else ""))
                runs.append({**tr.to_dict(), "check": check})
                _save(outdir, runs, _meta(args, setups, tasks))   # crash-safe

    _save(outdir, runs, _meta(args, setups, tasks))
    print(f"\n  wrote {outdir}/trajectories.json ({len(runs)} runs)")
    print(f"  next: python3 evaluate.py judge runs/{outdir.name}")
    return outdir


def _meta(args, setups, tasks):
    return {"setups": [s.name for s in setups], "reps": args.reps,
            "n_tasks": len(tasks),
            "when": datetime.datetime.now().isoformat(timespec="seconds"),
            "fixture": TELEMETRY.name, "judges": [], "stub": False}


def cmd_judge(args, model=None):
    outdir = pathlib.Path(args.rundir)
    runs, meta = _load(outdir)
    setups = [SETUPS[n] for n in meta["setups"]]
    judges = pick_judges(setups, requested=args.judges)
    if not judges:
        raise SystemExit("eval: no judge models left. Pass --judges m1 m2")
    model = model or CSCSModel()
    rng = random.Random(args.seed)
    print(f"  judges: {', '.join(judges)}\n")

    for i, r in enumerate(runs, 1):
        if r.get("judge") and not args.rejudge:
            continue
        tr = Trajectory.from_dict(r)
        r["judge"] = J.jury(model, judges, TASKS_BY_ID[r["task"]], tr)
        m = r["judge"]["mean"]
        print(f"  [{i:>3}/{len(runs)}] {r['setup']:<10} {r['task']:<20} rep{r['rep']} "
              f"judge {'-' if m is None else f'{m:.2f}'} "
              f"(spread {r['judge']['spread']:.2f})")

    votes = [v for r in runs for v in (r.get("judge") or {}).get("votes", [])]
    if votes:
        ok = sum(v["parsed"] for v in votes)
        print(f"\n  judge replies parsed: {ok}/{len(votes)} ({ok / len(votes):.0%})")
        if ok / len(votes) < 0.9:
            print("  ! a tenth or more of the judge replies did not parse. Those runs")
            print("    carry no judged score. Check judge.ABSOLUTE_PROMPT and max_tokens")
            print("    before reading the quality columns.")

    # Pairwise is the bias-controlled signal, and it is quadratic in setups, so
    # it is spent only where it changes a decision: between the two best on the
    # primary signal.
    rate = {n: sum(r["check"]["passed"] for r in runs if r["setup"] == n) for n in meta["setups"]}
    top = sorted(meta["setups"], key=lambda n: -rate[n])[:2]
    a, b = top
    print(f"\n  pairwise: {a} vs {b} (the two best on deterministic pass rate)")
    pairwise = {"wins": {a: 0, b: 0}, "ties": 0, "n": 0, "pair": [a, b], "detail": []}
    by = {(r["setup"], r["task"], r["rep"]): r for r in runs}
    for tid in dict.fromkeys(r["task"] for r in runs):
        ra, rb = by.get((a, tid, 0)), by.get((b, tid, 0))
        if not (ra and rb):
            continue
        votes = [J.judge_pairwise(model, m, TASKS_BY_ID[tid], Trajectory.from_dict(ra),
                                  Trajectory.from_dict(rb), rng) for m in judges]
        tally = {a: 0, b: 0, "tie": 0}
        for v in votes:
            tally[v["winner"]] += 1
        winner = "tie" if tally[a] == tally[b] else max(tally, key=tally.get)
        pairwise["n"] += 1
        if winner == "tie":
            pairwise["ties"] += 1
        else:
            pairwise["wins"][winner] += 1
        pairwise["detail"].append({"task": tid, "winner": winner, "votes": votes})
        print(f"    {tid:<20} -> {winner}")

    meta["judges"] = judges
    meta["judge_tokens"] = getattr(model, "judge_tokens", {})
    _save(outdir, runs, meta, pairwise)
    print(f"\n  judged. next: python3 evaluate.py label runs/{outdir.name}  (then: report)")


def cmd_recheck(args):
    """Recompute the deterministic checks over stored trajectories.

    The checks are pure functions of a trajectory, so fixing a check -- or
    adding one -- costs nothing and needs no model. Print what moved, because a
    check change that silently reclassifies runs is how an evaluation stops
    being an evaluation.
    """
    outdir = pathlib.Path(args.rundir)
    runs, meta = _load(outdir)
    moved = 0
    for r in runs:
        before = r["check"]["passed"]
        r["check"] = J.deterministic(TASKS_BY_ID[r["task"]], Trajectory.from_dict(r))
        if before != r["check"]["passed"]:
            moved += 1
            print(f"  {'FAIL->ok' if r['check']['passed'] else 'ok->FAIL'}  "
                  f"{r['setup']:<10} {r['task']:<20} rep{r['rep']}"
                  + ("" if r["check"]["passed"] else
                     "  <- " + "; ".join(r["check"]["failures"])[:70]))
    _save(outdir, runs, meta)
    print(f"\n  rechecked {len(runs)} runs, {moved} changed verdict.")
    return moved


def cmd_label(args):
    """Score a sample yourself, so the judge can be checked against you.

    This is the step people skip, and skipping it is what turns an evaluation
    into a machine that agrees with itself. It takes about ten minutes.
    """
    outdir = pathlib.Path(args.rundir)
    runs, meta = _load(outdir)
    labelfile = outdir / "labels.json"
    labels = json.loads(labelfile.read_text()) if labelfile.exists() else {}

    rng = random.Random(args.seed)
    sample = rng.sample(runs, min(args.n, len(runs)))
    todo = [r for r in sample if _key(r) not in labels]
    if not todo:
        print(f"  all {len(sample)} sampled runs already labelled.")
        return _kappa_report(runs, labels)

    print(f"\n  Labelling {len(todo)} trajectories on GOAL ATTAINMENT only.")
    print("  The setup name is hidden -- you are scoring the work, not the brand.\n")
    print(J.RUBRIC.split("TRAJECTORY_QUALITY")[0].rstrip())
    print("\n  Enter 0-3, 's' to skip, 'q' to stop and save.\n")

    for i, r in enumerate(todo, 1):
        tr = Trajectory.from_dict(r)
        print("=" * 78)
        print(f"  [{i}/{len(todo)}]  task: {r['task']}")
        print(f"  question: {TASKS_BY_ID[r['task']]['prompt']}")
        print("=" * 78)
        print(tr.transcript(limit=600))
        print("-" * 78)
        while True:
            got = input("  your goal-attainment score [0-3/s/q] > ").strip().lower()
            if got == "q":
                labelfile.write_text(json.dumps(labels, indent=2))
                print(f"  saved {len(labels)} labels to {labelfile}")
                return _kappa_report(runs, labels)
            if got == "s":
                break
            if got in ("0", "1", "2", "3"):
                labels[_key(r)] = int(got)
                break
            print("  0, 1, 2, 3, s or q.")
    labelfile.write_text(json.dumps(labels, indent=2))
    print(f"\n  saved {len(labels)} labels to {labelfile}")
    _kappa_report(runs, labels)


def _human_vs_judge(runs, labels):
    human, machine = [], []
    for r in runs:
        dims = (r.get("judge") or {}).get("dims") or {}
        k = _key(r)
        if k in labels and dims.get("goal_attainment") is not None:
            human.append(labels[k])
            machine.append(dims["goal_attainment"])
    return human, machine


def _kappa_report(runs, labels):
    human, machine = _human_vs_judge(runs, labels)
    if not human:
        print("  no overlap between labels and judged runs yet -- run `judge` first.")
        return None
    k = J.cohens_kappa(human, machine)
    exact = sum(a == b for a, b in zip(human, machine)) / len(human)
    print(f"\n  human vs judge on {len(human)} runs: exact agreement {exact:.0%}, "
          f"Cohen's kappa {k:.2f} ({J.kappa_label(k)})")
    if k < 0.60:
        print("  Below the gate. The fix is the rubric, not the verdict: read the runs")
        print("  you and the judge scored differently and sharpen the anchor that failed")
        print("  to separate them.")
    return k


def cmd_report(args):
    outdir = pathlib.Path(args.rundir)
    runs, meta = _load(outdir)
    pairwise = _read(outdir / "pairwise.json")
    labels = _read(outdir / "labels.json") or {}

    human, machine = _human_vs_judge(runs, labels)
    kappa = J.cohens_kappa(human, machine) if human else None

    aggs = [R.aggregate(n, [r for r in runs if r["setup"] == n]) for n in meta["setups"]]
    aggs = [a for a in aggs if a["n"]]
    fact = R.factorial({a["setup"]: a for a in aggs})
    text, verdict = R.render(aggs, pairwise, kappa, len(human), meta,
                             [SETUPS[a["setup"]].describe() for a in aggs], fact)
    print(text)
    if meta.get("stub"):
        print("\n  NOTE: scripted stub model (selftest). The numbers demonstrate the")
        print("  pipeline, not any real model's ability.")
    (outdir / "report.txt").write_text(text + "\n")
    jt = meta.get("judge_tokens") or {}
    if jt.get("received"):
        print(f"\n  judging itself cost {jt.get('sent', 0):,} sent + "
              f"{jt['received']:,} received tokens.")
    print(f"\n  written to {outdir / 'report.txt'}")
    return verdict


def cmd_compare(args):
    outdir = cmd_run(args)
    if outdir is None:
        return
    args.rundir, args.rejudge = str(outdir), False
    cmd_judge(args)
    cmd_report(args)
    print("\n  The judge is not calibrated yet. Before acting on the quality numbers:")
    print(f"    python3 evaluate.py label runs/{outdir.name}")


# ---------------------------------------------------------------------------

def _key(r):
    return f"{r['setup']}|{r['task']}|{r['rep']}"


def _read(p):
    return json.loads(p.read_text()) if p.exists() else None


def _save(outdir, runs, meta, pairwise=None):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "trajectories.json").write_text(
        json.dumps({"meta": meta, "runs": runs}, indent=2, default=str))
    if pairwise is not None:
        (outdir / "pairwise.json").write_text(json.dumps(pairwise, indent=2, default=str))


def _load(outdir):
    data = _read(pathlib.Path(outdir) / "trajectories.json")
    if data is None:
        raise SystemExit(f"eval: no trajectories.json in {outdir}")
    return data["runs"], data["meta"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setups", help="list setups, the grid, and the tasks").set_defaults(fn=cmd_setups)
    sub.add_parser("doctor", help="check each harness can start").set_defaults(fn=cmd_doctor)

    def add_run_args(sp):
        sp.add_argument("setups", nargs="+", help="two or more setup names")
        sp.add_argument("--reps", type=int, default=3,
                        help="repetitions per task per setup (default 3)")
        sp.add_argument("--tasks", nargs="*", default=None, help="subset of task ids")
        sp.add_argument("--out", default=None, help="run directory name")
        sp.add_argument("--timeout", type=int, default=300, help="seconds per run")
        sp.add_argument("--dry-run", action="store_true", help="print the plan, send nothing")
        sp.add_argument("--judges", nargs="*", default=None)
        sp.add_argument("--seed", type=int, default=7)

    add_run_args(sub.add_parser("run", help="produce trajectories"))
    sub.choices["run"].set_defaults(fn=cmd_run)
    add_run_args(sub.add_parser("compare", help="run + judge + report"))
    sub.choices["compare"].set_defaults(fn=cmd_compare)

    sp = sub.add_parser("judge", help="score trajectories with the jury")
    sp.add_argument("rundir"); sp.add_argument("--judges", nargs="*", default=None)
    sp.add_argument("--rejudge", action="store_true", help="re-score already-judged runs")
    sp.add_argument("--seed", type=int, default=7); sp.set_defaults(fn=cmd_judge)

    sp = sub.add_parser("label", help="score a sample yourself; report kappa")
    sp.add_argument("rundir"); sp.add_argument("-n", type=int, default=12)
    sp.add_argument("--seed", type=int, default=7); sp.set_defaults(fn=cmd_label)

    sp = sub.add_parser("recheck", help="recompute deterministic checks (free)")
    sp.add_argument("rundir"); sp.set_defaults(fn=cmd_recheck)

    sp = sub.add_parser("report", help="render the comparison and the verdict")
    sp.add_argument("rundir"); sp.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    for name in getattr(args, "setups", []) or []:
        if name not in SETUPS:
            raise SystemExit(f"eval: unknown setup {name!r}. Known: {', '.join(SETUPS)}")
    return args.fn(args)


if __name__ == "__main__":
    main()
