"""Aggregation, uncertainty, and applying the decision rule.

Agents are nondeterministic, so a single run of a single task is an anecdote.
Everything here exists to stop an anecdote being read as a result:

  * repeats are averaged per task before setups are compared, so a task that
    happens to be run more often cannot dominate;
  * differences are reported with a bootstrap confidence interval, and a
    difference whose interval straddles zero is reported as no difference;
  * the pairwise verdicts get a sign test, because "8 wins out of 14" is not
    evidence of anything and should not be presented as though it were.

Pure standard library on purpose -- there is nothing here worth a dependency,
and the arithmetic is short enough to read.
"""
import math
import random
import statistics
from collections import defaultdict

from tasks import DECISION_RULE, KAPPA_GATE, MARGIN_POINTS, TASKS_BY_ID


def bootstrap_ci(values, reps=5000, alpha=0.05, seed=7):
    """Percentile bootstrap CI for the mean. Returns (lo, hi) or None."""
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(statistics.mean(rng.choices(values, k=n)) for _ in range(reps))
    return (means[int(alpha / 2 * reps)], means[int((1 - alpha / 2) * reps) - 1])


def sign_test(wins, losses):
    """Two-sided exact binomial p-value for wins vs losses, ties discarded."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def per_task_means(runs, key):
    """Collapse repeats: {task_id: mean of `key` over that task's runs}."""
    buckets = defaultdict(list)
    for r in runs:
        v = key(r)
        if v is not None:
            buckets[r["task"]].append(v)
    return {t: statistics.mean(vs) for t, vs in buckets.items() if vs}


def aggregate(setup_name, runs):
    """Everything that can be said about one setup, on its own."""
    n = len(runs)
    passed = [r for r in runs if r["check"]["passed"]]
    hard = [r for r in runs if r["check"]["hard_fail"]]
    errored = [r for r in runs if r.get("stopped") == "error"]

    judged = [r["judge"]["mean"] for r in runs
              if r.get("judge") and r["judge"].get("mean") is not None]
    sent = sum(r["tokens"]["sent"] for r in runs)
    recv = sum(r["tokens"]["received"] for r in runs)
    cached = sum(r["tokens"]["cached"] for r in runs)

    findings = defaultdict(int)
    for r in runs:
        for f in (r.get("judge") or {}).get("findings", []):
            if isinstance(f, dict) and f.get("code"):
                findings[f["code"]] += 1

    return {
        "setup": setup_name,
        "n": n,
        "n_pass": len(passed),
        "pass_rate": len(passed) / n if n else 0.0,
        "pass_by_task": per_task_means(runs, lambda r: 1.0 if r["check"]["passed"] else 0.0),
        "hard_fails": [h for r in hard for h in r["check"]["hard_fail"]],
        "n_errored": len(errored),
        "judge_mean": statistics.mean(judged) if judged else None,
        "judge_ci": bootstrap_ci(judged),
        "judge_by_task": per_task_means(
            runs, lambda r: (r.get("judge") or {}).get("mean")),
        "tokens_sent": sent, "tokens_received": recv, "tokens_cached": cached,
        "cache_rate": cached / sent if sent else 0.0,
        "tokens_per_run": (sent + recv) / n if n else 0,
        "tokens_per_correct": (sent + recv) / len(passed) if passed else None,
        "mean_turns": statistics.mean([r["turns"] for r in runs]) if n else 0,
        "mean_calls": statistics.mean([len(r["calls"]) for r in runs]) if n else 0,
        "mean_wall_s": statistics.mean([r["wall_s"] for r in runs]) if n else 0,
        "findings": dict(sorted(findings.items(), key=lambda kv: -kv[1])),
    }


def paired_delta(a_by_task, b_by_task, seed=7):
    """Per-task difference B-A, with a bootstrap CI over tasks."""
    shared = sorted(set(a_by_task) & set(b_by_task))
    deltas = [b_by_task[t] - a_by_task[t] for t in shared]
    if not deltas:
        return None
    return {"tasks": shared, "deltas": deltas,
            "mean": statistics.mean(deltas),
            "ci": bootstrap_ci(deltas, seed=seed)}


def decide(agg_a, agg_b, pairwise, kappa):
    """Apply tasks.DECISION_RULE. Returns (verdict, [explanation lines])."""
    a, b = agg_a["setup"], agg_b["setup"]
    lines = []

    # 1. Disqualification.
    dq = [s["setup"] for s in (agg_a, agg_b) if s["hard_fails"]]
    if dq:
        for s in (agg_a, agg_b):
            for h in s["hard_fails"]:
                lines.append(f"rule 1  DISQUALIFIED {s['setup']}: {h}")
        if len(dq) == 2:
            return "NEITHER", lines + ["rule 1  both setups disqualified; fix the "
                                       "harness before comparing anything."]
        survivor = b if dq[0] == a else a
        return survivor, lines + [f"rule 1  {survivor} wins by default. Verify the "
                                  "disqualification before you believe it."]
    lines.append("rule 1  no Catastrophic findings in either setup.")

    # 2. Deterministic pass rate -- the primary signal.
    det = paired_delta(agg_a["pass_by_task"], agg_b["pass_by_task"])
    det_winner = None
    if det and det["ci"]:
        lo, hi = det["ci"]
        sep = lo > 0 or hi < 0
        lines.append(
            f"rule 2  deterministic pass rate: {a} {agg_a['pass_rate']:.0%}, "
            f"{b} {agg_b['pass_rate']:.0%}  (delta {det['mean']:+.2f}, "
            f"95% CI [{lo:+.2f}, {hi:+.2f}]{'' if sep else ', straddles zero'})")
        if sep:
            det_winner = b if det["mean"] > 0 else a
    else:
        lines.append(f"rule 2  deterministic pass rate: {a} {agg_a['pass_rate']:.0%}, "
                     f"{b} {agg_b['pass_rate']:.0%}  (too few tasks for an interval)")

    # 3/4. The judge -- only if it has earned the right to speak.
    judge_winner = None
    if kappa is None:
        lines.append("rule 3  judge NOT CALIBRATED against human labels -> its scores "
                     "are reported but carry no weight. Run: evaluate.py label")
    elif kappa < KAPPA_GATE:
        lines.append(f"rule 3  judge calibration kappa={kappa:.2f} < {KAPPA_GATE:.2f} -> "
                     "quality comparison INCONCLUSIVE. Fix the rubric, not the verdict.")
    else:
        lines.append(f"rule 3  judge calibrated, kappa={kappa:.2f} >= {KAPPA_GATE:.2f}.")
        jd = paired_delta(agg_a["judge_by_task"], agg_b["judge_by_task"])
        if jd and jd["ci"] and agg_a["judge_mean"] is not None:
            lo, hi = jd["ci"]
            sep = lo > 0 or hi < 0
            big = abs(jd["mean"]) >= MARGIN_POINTS
            lines.append(
                f"rule 4  judge mean: {a} {agg_a['judge_mean']:.2f}, "
                f"{b} {agg_b['judge_mean']:.2f}  (delta {jd['mean']:+.2f}, "
                f"95% CI [{lo:+.2f}, {hi:+.2f}])")
            if sep and big:
                judge_winner = b if jd["mean"] > 0 else a
            else:
                lines.append(f"rule 4  margin below {MARGIN_POINTS} points or interval "
                             "straddles zero -> no winner on judged quality.")
        else:
            lines.append("rule 4  not enough judged runs to form an interval.")

    if pairwise and pairwise.get("n"):
        p = sign_test(pairwise["wins"][a], pairwise["wins"][b])
        lines.append(
            f"        pairwise, order-randomised: {a} {pairwise['wins'][a]} - "
            f"{pairwise['wins'][b]} {b}, {pairwise['ties']} ties  (sign test p={p:.3f}"
            f"{'' if p < 0.05 else ', not significant'})")

    # Reconcile.
    winners = {w for w in (det_winner, judge_winner) if w}
    if len(winners) == 1:
        w = winners.pop()
        agreed = det_winner and judge_winner
        lines.append(f"        signals {'agree' if agreed else 'give one winner'}: {w}")
        return w, lines
    if len(winners) == 2:
        lines.append(f"        SIGNALS DISAGREE: deterministic says {det_winner}, judge "
                     f"says {judge_winner}. Do not pick one because you like it. Read the "
                     "disagreeing trajectories; usually a check is wrong or the rubric is.")
        return "INCONCLUSIVE", lines

    # 5. Tie-break on cost.
    ca, cb = agg_a["tokens_per_correct"], agg_b["tokens_per_correct"]
    if ca and cb:
        cheap = a if ca <= cb else b
        ratio = max(ca, cb) / min(ca, cb)
        lines.append(f"rule 5  quality is a tie -> cost per correct answer: "
                     f"{a} {ca:,.0f} tok, {b} {cb:,.0f} tok ({ratio:.2f}x). "
                     f"Take {cheap}.")
        return cheap, lines
    lines.append("rule 5  quality is a tie and neither setup produced a correct answer "
                 "to divide cost by. Nothing to choose between them.")
    return "TIE", lines


# ---------------------------------------------------------------------------
# The 2x2: separating the harness from the model.
# ---------------------------------------------------------------------------

def factorial(aggs, metric="pass_by_task", seed=7):
    """Main effects and interaction for the harness x model grid.

    Four setups arranged as a grid answer three questions that four separate
    A/B tests would answer badly:

      main effect of HARNESS      averaged over both models, does swapping the
                                  harness move the score?
      main effect of MODEL        averaged over both harnesses, does swapping
                                  the model move it?
      INTERACTION                 is the better harness the same one whichever
                                  model you put in it? A large interaction is
                                  the interesting result: it means "which is
                                  better" has no answer on its own, and you
                                  must pick the pair.

    Each effect is a per-task mean difference with a bootstrap CI over tasks,
    so an effect whose interval straddles zero is reported as absent.
    """
    from harness import GRID, SHORT
    cells = {}
    for (h, m), name in GRID["cells"].items():
        if name in aggs and aggs[name][metric]:
            cells[(h, m)] = aggs[name][metric]
    if len(cells) < 4:
        return None

    h0, h1 = GRID["harness"]
    m0, m1 = GRID["model"]
    tasks = sorted(set.intersection(*(set(v) for v in cells.values())))
    if not tasks:
        return None

    def col(h, m):
        return [cells[(h, m)][t] for t in tasks]

    a, b = col(h0, m0), col(h0, m1)          # opencode  x {kimi, glm}
    c, d = col(h1, m0), col(h1, m1)          # claude    x {kimi, glm}

    harness_eff = [((c[i] + d[i]) - (a[i] + b[i])) / 2 for i in range(len(tasks))]
    model_eff = [((a[i] + c[i]) - (b[i] + d[i])) / 2 for i in range(len(tasks))]
    inter = [(c[i] - d[i]) - (a[i] - b[i]) for i in range(len(tasks))]

    def eff(deltas, label, positive, negative):
        m = statistics.mean(deltas)
        ci = bootstrap_ci(deltas, seed=seed)
        sep = bool(ci) and (ci[0] > 0 or ci[1] < 0)
        return {"label": label, "mean": m, "ci": ci, "separates": sep,
                "favours": (positive if m > 0 else negative) if sep else "neither"}

    return {"n_tasks": len(tasks),
            "cells": {f"{SHORT[h]} x {SHORT[m]}": statistics.mean(col(h, m))
                      for h in (h0, h1) for m in (m0, m1)},
            "harness": eff(harness_eff, f"{SHORT[h1]} - {SHORT[h0]}",
                           SHORT[h1], SHORT[h0]),
            "model": eff(model_eff, f"{SHORT[m0]} - {SHORT[m1]}", SHORT[m0], SHORT[m1]),
            "interaction": eff(inter, "does the winner depend on the pairing?",
                               "yes", "yes")}


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------

W = 15          # column width per setup


def _row(label, values, width=24):
    return f"  {label:<{width}}" + "".join(f"{v:>{W}}" for v in values)


def _fmt_ci(e):
    if not e["ci"]:
        return ""
    return f"  95% CI [{e['ci'][0]:+.2f}, {e['ci'][1]:+.2f}]"


def render(aggs, pairwise, kappa, kappa_n, meta, setups, fact=None, fact_judge=None):
    """`aggs` is a list of aggregate() dicts, in the order to display."""
    names = [a["setup"] for a in aggs]
    L = []
    add = L.append
    line = "=" * (26 + W * len(aggs))
    thin = "-" * (26 + W * len(aggs))

    add(line)
    add("  AGENTIC SETUP COMPARISON")
    add(line)
    add(f"  suite      {meta['n_tasks']} tasks x {meta['reps']} repetitions x "
        f"{len(aggs)} setups = {meta['n_tasks'] * meta['reps'] * len(aggs)} runs")
    add(f"  judges     {', '.join(meta['judges']) or '(none -- quality not judged)'}")
    add(f"  fixtures   frozen ({meta['fixture']}), tools identical across setups")
    add(f"  run at     {meta['when']}")
    add("")
    add("  THE SETUPS UNDER TEST")
    for d in setups:
        add("    " + d.replace("\n", "\n    ").rstrip())
    add("")
    add("  THE DECISION RULE  (written before the run, not after)")
    for l in DECISION_RULE.rstrip().split("\n"):
        add("    " + l)
    add("")

    add(thin)
    add(_row("", names))
    add(thin)
    add("  QUALITY")
    add(_row("deterministic pass", [f"{a['n_pass']}/{a['n']} ({a['pass_rate']:.0%})"
                                    for a in aggs]))
    add(_row("judge mean (0-3)", ["-" if a["judge_mean"] is None else f"{a['judge_mean']:.2f}"
                                  for a in aggs]))
    add(_row("  95% CI", ["" if not a["judge_ci"] else
                          f"[{a['judge_ci'][0]:.2f},{a['judge_ci'][1]:.2f}]" for a in aggs]))
    add(_row("hard fails", [str(len(a["hard_fails"])) for a in aggs]))
    add(_row("runs errored", [str(a["n_errored"]) for a in aggs]))
    add("")
    add("  COST  (see the caveat below the table)")
    add(_row("output tokens", [f"{a['tokens_received']:,}" for a in aggs]))
    add(_row("prompt tokens", [f"{a['tokens_sent']:,}" if a["tokens_sent"] else "n/a"
                               for a in aggs]))
    add(_row("mean wall time", [f"{a['mean_wall_s']:.1f}s" for a in aggs]))
    add(_row("output tok / correct", ["-" if not a["n_pass"] else
                                      f"{a['tokens_received'] / a['n_pass']:,.0f}"
                                      for a in aggs]))
    add(_row("wall s / correct", ["-" if not a["n_pass"] else
                                  f"{a['mean_wall_s'] * a['n'] / a['n_pass']:,.0f}"
                                  for a in aggs]))
    add("")
    add("  TRAJECTORY SHAPE")
    add(_row("mean turns", [f"{a['mean_turns']:.1f}" for a in aggs]))
    add(_row("mean tool calls", [f"{a['mean_calls']:.1f}" for a in aggs]))
    add("")

    add("  PER-TASK PASS RATE")
    for tid, t in TASKS_BY_ID.items():
        vals = [a["pass_by_task"].get(tid) for a in aggs]
        if all(v is None for v in vals):
            continue
        shown = ["  -  " if v is None else f"{v:.0%}".rjust(5) for v in vals]
        seen = [v for v in vals if v is not None]
        flag = "   <- discriminates" if seen and (max(seen) - min(seen)) >= 0.5 else ""
        add(f"    {t['difficulty']:<11} {tid:<20}" +
            "".join(v.rjust(W) for v in shown) + flag)
    add("")

    allf = sorted({c for a in aggs for c in a["findings"]})
    if allf:
        add("  CODEBOOK FINDINGS RAISED BY THE JUDGES")
        for code in allf:
            add(f"    {code:<24}" + "".join(f"{a['findings'].get(code, 0):>{W}}" for a in aggs))
        add("")

    add("  COST IS NOT FULLY COMPARABLE, AND HERE IS WHY")
    add("    The CSCS Anthropic-compatible endpoint reports input_tokens = 0 through")
    add("    both CLIs, so prompt tokens and cache hit rate are unavailable for them.")
    add("    Output tokens, turns, tool calls and wall time are sound everywhere and")
    add("    are what the cost rows above rank on. The in-process loop uses the")
    add("    OpenAI-compatible endpoint and does report prompt tokens, which is why")
    add("    its column is the only one with a number in that row -- do not read")
    add("    across it.")
    add("")

    if fact:
        add(line)
        add("  THE 2x2: IS IT THE HARNESS OR THE MODEL?")
        add(f"  deterministic pass rate, averaged over {fact['n_tasks']} tasks")
        add("")
        for cell, v in fact["cells"].items():
            add(f"    {cell:<32} {v:.0%}")
        add("")
        for key, title in (("harness", "effect of the HARNESS"),
                           ("model", "effect of the MODEL"),
                           ("interaction", "INTERACTION")):
            e = fact[key]
            verdict = (f"favours {e['favours']}" if e["separates"]
                       else "no detectable effect")
            add(f"    {title:<24} {e['mean']:+.2f}{_fmt_ci(e)}   -> {verdict}")
        add("")
        if fact["interaction"]["separates"]:
            add("    The interaction separates from zero: which harness is better DEPENDS")
            add("    on the model you put in it. Choose the pair, not the harness.")
        else:
            add("    No detectable interaction: the harness ranking, such as it is, does")
            add("    not depend on which of these two models you run.")
        add("")

    add("  JUDGE CALIBRATION")
    if kappa is None:
        add("    not measured -- no human labels on file. Until you label a sample, the")
        add("    judge's numbers above are decoration. Run: evaluate.py label <rundir>")
    else:
        from judge import kappa_label
        add(f"    Cohen's kappa vs human labels: {kappa:.2f} ({kappa_label(kappa)}) "
            f"on {kappa_n} labelled runs")
        add(f"    gate for using judged quality: {KAPPA_GATE:.2f}")
    add("")

    add(line)
    if len(aggs) < 2:
        add("  Only one setup has runs -- nothing to decide between yet.")
        add(line)
        return "\n".join(L), "INCOMPLETE"
    top = sorted(aggs, key=lambda a: (a["pass_rate"], a["judge_mean"] or 0), reverse=True)[:2]
    add("  HEAD TO HEAD: the two best on the primary signal")
    add(f"  {top[0]['setup']} vs {top[1]['setup']}")
    add("")
    # decide() reads pairwise["wins"] by setup name; a pairwise block judged for
    # a different pair must not be silently misread as this one's evidence.
    pw = pairwise if pairwise and set(pairwise.get("wins", {})) == {
        top[0]["setup"], top[1]["setup"]} else None
    if pairwise and pw is None:
        add(f"  (pairwise on file is for {' vs '.join(pairwise.get('pair', ['?']))}, "
            "not this pair -- ignored)")
    verdict, why = decide(top[0], top[1], pw, kappa)
    for l in why:
        add("  " + l)
    add("")
    add(f"  VERDICT: {verdict}")
    add(line)
    return "\n".join(L), verdict
