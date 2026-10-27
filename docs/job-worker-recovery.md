# Worker browser recovery

The worker's `/tmp` is an `emptyDir`: it survives a container restart within
the same Pod. A killed Xvfb can therefore leave `.X99-lock` and its Unix socket
behind, preventing the next browser from starting.

On startup, after acquiring the exclusive worker-data lock, the worker removes
only its own stale X11 files. It refuses cleanup if a display responds, a lock
owner is alive, or the files are unowned. Browser cookies, resume, configuration
and approval markers stay on the existing persistent volume.

Child stderr/stdout now go to container logs. A child monitor reports exited
critical services and reaps their status. `/health` checks the child processes,
Chromium's debugging endpoint and the job panel. Kubernetes allows 120 seconds
for startup, marks an unhealthy worker unready, and restarts it after sustained
liveness failure (six ten-second checks). Startup is not a request to replay an
interrupted application cycle; the scheduler retains its existing no-overlap
and no-second-run behavior.

Validate recovery on an isolated Pod with empty test data, no owner credentials,
no Service, and an ingress/egress-deny NetworkPolicy. Kill Xvfb, observe readiness
failure and a container restart, and verify health recovers with the same Pod
UID (so temporary storage was retained). Also kill PID 1 to reproduce the
abrupt-container-restart path. Never fault-inject into an active production run.

Historical failed Jobs are not evidence of a current worker outage. Preserve
their status and logs before cleaning up completed failed Jobs after recovery.
The original exit 137 needs kernel/container evidence for attribution; it is
not automatically proof of an out-of-memory event.
