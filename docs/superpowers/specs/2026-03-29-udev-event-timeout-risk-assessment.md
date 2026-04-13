# Risk Assessment: `event_timeout=7200` in udev.conf

## Executive Summary

Setting `event_timeout=7200` (2 hours) in a Docker container is **moderately risky** but workable with mitigations. The primary danger is not worker exhaustion (which is unlikely) but rather **unkillable D-state processes** that survive even SIGKILL, blocking the worker slot permanently.

---

## 1. What Happens When a Worker Hangs (D-state / NFS mount)

When `event_timeout` fires, `on_event_timeout()` calls `kill_and_sigcont(worker->pid, SIGKILL)` and sets `worker->state = WORKER_KILLED`.

**Critical problem with D-state**: A process in uninterruptible sleep (D-state) — e.g., waiting on a stalled NFS mount or a CD/DVD read — **cannot be killed by any signal, including SIGKILL**. The kernel simply does not deliver signals to processes in D-state. The SIGKILL remains pending until the process exits D-state (if ever).

With `event_timeout=7200`, the worker sits there for 2 hours before udevd even *attempts* the kill. If the process is in D-state, the kill fails silently and the worker remains in `WORKER_KILLED` state — but the PID still exists in the workers hashmap, consuming a slot.

**After timeout fires**: udevd sets state to `WORKER_KILLED` and sends SIGTERM (as follow-up in `on_sigchld` when it sees `WORKER_KILLING`). The event is freed and the device is "unblocked" from udevd's perspective. But the zombie/D-state worker PID lingers in the hashmap until it actually exits.

## 2. Concurrent Workers (children_max)

**Default calculation** (from `manager_set_default_children_max()`):

```
cpu_limit = cpu_count * 2 + 16
mem_limit = MAX(physical_memory / 128MB, 10)
children_max = MIN(cpu_limit, mem_limit, 2048)
```

For a typical Docker container with 4 CPUs and 8GB RAM:
- `cpu_limit = 4*2 + 16 = 24`
- `mem_limit = 8192/128 = 64`
- `children_max = 24`

**Yes, other disc insertions can still be detected.** Each device event gets its own worker. With 24+ worker slots, even if 2-3 are occupied by long-running rip events, there are plenty of slots for new device events.

**However**: Events for the **same device path** (or parent/child paths) are serialized via `event_is_blocked()`. The function uses `devpath_conflict()` to check if two device paths are equivalent or have a parent/child relationship. A blocked event stays in `EVENT_QUEUED` state until the earlier event for that device completes.

So: A new disc in `/dev/sr0` cannot be processed while a prior `/dev/sr0` event is still running — but `/dev/sr1` events proceed independently.

## 3. Workers Exhausted — What Happens to New Events

When `hashmap_size(manager->workers) >= manager->children_max`, `event_run()` returns 0 ("no free worker"). The event stays in `EVENT_QUEUED` state. The event loop's `on_post()` callback periodically calls `event_queue_start()` to retry dispatching queued events whenever a worker becomes idle.

Events are **not dropped** — they queue indefinitely. But if all worker slots are consumed by hung processes, no new events process until workers free up.

**Realistic risk for ARM**: Very low. You have at most 2-4 optical drives. Each generates a handful of events per disc insertion. You would need 24+ simultaneous hung events to exhaust workers.

## 4. Resource Exhaustion Risk

Each worker is a forked child process. Resource costs per long-lived worker:

| Resource | Cost | Risk |
|----------|------|------|
| PID | 1 per worker | Negligible — 2048 max, container PID limit typically 32768 |
| File descriptors | ~10-20 per worker (netlink, inotify, pipes) | Low — well within container ulimits |
| Memory | Fork COW pages, rules structures | Low — workers share most pages with parent |
| /proc entries | 1 per PID | Negligible |

**Verdict**: No meaningful resource exhaustion risk from 2-4 workers running for 2 hours.

## 5. Container Stop with Pending 7200s Event

When `docker stop` is issued:

1. Docker sends SIGTERM to PID 1 (`my_init` in phusion/baseimage)
2. `my_init` propagates SIGTERM to child processes (including runit services)
3. The runit service for udevd receives SIGTERM
4. `manager_exit()` is called, which calls `manager_kill_workers(true)` — this sends SIGKILL to all workers
5. Docker waits for the stop timeout (default 10s), then sends SIGKILL to PID 1

**D-state problem again**: If a worker is in D-state (e.g., hung NFS mount), SIGKILL cannot kill it. The container's PID 1 cannot exit because it has living child processes. Docker's final SIGKILL to PID 1 also fails if the kernel task is in D-state. This leads to the container being **unkillable** — even `docker rm -f` fails.

This is the **exact issue** noted in your MEMORY.md under "D-state mount hangs block container stop."

**The event_timeout value does not help here** — the D-state process is unkillable regardless of whether the timeout is 180s or 7200s.

## 6. Known Issues with Large event_timeout Values

There are no systemd bug reports specifically about large `event_timeout` values. The implementation is a simple timer — the value is stored as `usec_t` (64-bit), so even `7200` works fine mechanically.

**Practical concerns**:

- **Delayed error detection**: If a udev rule handler genuinely hangs (bug, not intended long operation), you wait 2 hours before udevd notices and kills it. With the default 180s, you find out in 3 minutes.
- **Stale device state**: While a worker is processing an event for a device, subsequent events for that same device path queue behind it (via `event_is_blocked()`). A 2-hour window means the device's udev state could be stale for up to 2 hours.
- **Log noise**: At `udev_warn_timeout()` (approximately 2/3 of `timeout_usec`), udevd logs a warning. With 7200s, this warning comes at ~80 minutes — very late for debugging.

## 7. Recommendation: 7200s vs 1800s vs Alternative

### The real question: Why does udevd need a long timeout at all?

The `event_timeout` controls how long udevd waits for a **RUN{program}** or rule processing to complete. If your udev rule launches MakeMKV or a rip script as a `RUN{}` program, then yes — you need the timeout to exceed the longest possible rip.

**But this is an anti-pattern.** The udev(7) manpage explicitly warns:

> *"This can only be used for very short-running foreground tasks. Running an event process for a long period of time may block all further events for this or a dependent device."*

### Recommended architecture

Instead of a long `event_timeout`, your udev rule should:
1. **Detect the disc insertion** (fast — milliseconds)
2. **Launch the rip process in the background** (e.g., `systemd-run`, `nohup`, or signal your ARM daemon)
3. **Return immediately** from the RUN{} handler

This way `event_timeout` can stay at the default 180s (or even lower), and the actual rip runs outside udevd's supervision entirely.

### If you must use a long timeout

| Timeout | Pros | Cons |
|---------|------|------|
| 7200s (2hr) | Covers longest Blu-ray rips | Very late error detection, long device event blocking |
| 1800s (30min) | Covers most DVDs, shorter Blu-rays | May kill long Blu-ray rips prematurely |
| 900s (15min) | Reasonable for detection + handoff | Too short if rip runs inline |
| 180s (default) | Fast failure detection | Only works if rip is backgrounded |

**If the rip process runs inline in the udev handler**: Use `event_timeout=7200` but increase `children_max` to at least `number_of_drives * 2 + 10` to ensure other events can proceed.

**If the rip process is backgrounded** (recommended): Keep `event_timeout=180` (default). The udev handler returns in seconds.

---

## Summary of Risks

| Risk | Severity | Likelihood | Notes |
|------|----------|------------|-------|
| Worker slot consumed for 2hr | Low | High (by design) | Only blocks same-device events |
| All workers exhausted | Medium | Very Low | Need 24+ simultaneous hangs |
| D-state worker unkillable | High | Medium | NFS/mount hangs cause this regardless of timeout |
| Container unkillable | High | Medium | D-state propagates to `docker stop` failure |
| Delayed error detection | Medium | Medium | Genuine bugs hide for 2 hours |
| Resource exhaustion | Low | Very Low | Workers are lightweight |
| Event queue overflow | Low | Very Low | Events queue, not dropped |

**Bottom line**: The `event_timeout=7200` setting is safe for worker/resource management but masks the real problem — long-running processes should not run inside udev event handlers. The D-state container-stop issue exists independently of the timeout value and requires a separate fix (mount timeouts, avoiding `mount` on non-filesystem discs).
