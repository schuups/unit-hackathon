# Runbook: node running hot / thermal throttling

**Symptom.** Jobs on a node take far longer than the same job took last week,
and often hit their walltime and end in `TIMEOUT` rather than failing outright.
Users report "the cluster is slow" without an error message.

**Cause.** Above **85 C** the GPUs clock down to protect themselves. Throughput
drops by 30-50% but nothing crashes, so nothing shows up in the job's own logs.
The usual reason is a blocked air intake, a failed fan, or a rack-level cooling
fault affecting one or two nodes.

**Diagnosis.**

1. Pull the live telemetry for the node: temperature, power draw, `throttling`.
2. Check the accounting database for jobs that landed on that node in the last
   few days. A cluster of `TIMEOUT` states on one node, while the same users'
   jobs complete normally elsewhere, confirms it.

**Action.**

- Drain the node so no new work lands on it: `scontrol update NodeName=<node> State=DRAIN Reason="thermal"`.
- Raise a hardware ticket with the facilities team; include the temperature
  history and the affected job ids.
- Tell the affected users to resubmit. Time lost to a throttled node is
  refunded against the project allocation -- see the fair-share policy.
