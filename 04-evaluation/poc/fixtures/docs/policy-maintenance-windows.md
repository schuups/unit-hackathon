# Policy: maintenance windows

**Scheduled maintenance** is the first Tuesday of each month, 06:00-14:00 CET.
The queue is drained from 04:00; jobs whose walltime would overrun the window
are held and start automatically afterwards.

**Unscheduled drains.** A node can be drained at any time for a hardware fault.
Drained nodes stay in the accounting database and keep their history, but the
scheduler stops placing work on them. `GET /nodes` on the telemetry service
reports the current state of every node, which is the authoritative answer to
"is this node taking work right now?".

Announcements go to the users of affected projects and to the status page.
