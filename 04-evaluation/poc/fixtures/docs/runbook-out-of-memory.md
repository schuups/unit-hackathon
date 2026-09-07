# Runbook: job killed OUT_OF_MEMORY

**Symptom.** The job ends in state `OUT_OF_MEMORY`, usually with exit code 137
(128 + SIGKILL). The user sees the job disappear with no output.

**Cause.** The process exceeded the memory the scheduler reserved for it. Most
often the job asked for the default per-node memory and then scaled up its
problem size, or a rank leaked over a long run.

**Action.**

- Ask for more memory explicitly with `--mem=` or use the `largemem` reservation.
- If the job is MPI, check the rank count per node; oversubscribing multiplies
  the memory footprint.
- Repeated `OUT_OF_MEMORY` on the *same node* while other nodes are fine points
  at faulty DIMMs, not at the job. Drain the node and raise a hardware ticket.
