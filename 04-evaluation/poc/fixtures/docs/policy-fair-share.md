# Policy: allocations, fair share and refunds

Each project is granted an allocation in **node hours** for the quarter. Usage
is charged as `nodes x elapsed hours`, whatever the job's exit state -- a job
that fails after twenty hours still costs twenty hours.

**Thresholds.**

- At **80%** of the allocation the PI is notified automatically.
- At **100%** new jobs are still accepted but drop to the lowest priority tier,
  and will only start when the machine is otherwise idle.
- Extensions are requested through the Service Desk and decided by the
  allocation committee, which meets fortnightly.

**Refunds.** Node hours lost to a confirmed hardware fault -- a thermally
throttled node, a failed DIMM, a fabric outage -- are credited back to the
project. Open a Service Desk ticket quoting the job ids and the node names.
Time lost to a user's own error is not refunded.
