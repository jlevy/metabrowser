---
type: is
id: is-01m8bfwztw84vfapjmyap7ta72
title: "Plugin worker client on the isolation facility: protocol, deadlines, lifeline, build stamp"
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvywxsmc0m4481ypk3zbq
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:07.228Z
updated_at: 2026-11-26T09:20:37.481Z
started_at: 2026-11-26T09:20:28.188Z
---
Phase 1 (plan: Process Model, Protocol; Key Decisions 8 and 9). The worker client, built on metabrowser.isolation. Start with subprocess (close_fds, pass_fds, process_group=0, cwd=/): [confinement prefix] <watchdog> <interpreter> -I -X pycache_prefix=<its cache> <runtime>/worker.py <request fd> <reply fd>; the pipes' numbers are arguments, not fixed descriptors. A watchdog leads the group: a small trusted program holding a lifeline from the server that kills its own process group when the lifeline ends or the worker exits, because a lifeline inside the worker cannot promise its end (a hook in native code holding the interpreter lock kept a worker 2 s past its pipe closing; a worker that exits leaves the programs it started; probes.py lifecycle and watchdog). The reader's exit at end of file is the fast path. The server learns a worker is gone by waiting on its pid, never from end of file on the reply pipe. SIGINT is not ignored, since an ignored signal is inherited by a plugin's programs. Descriptor 0 /dev/null, 1 moved to 2, 2 a pipe the host drains under a cap. One worker per server, environment, and grant set. An import guard fails import metabrowser with a sentence naming metabrowser_sdk. Protocol: u32 header length, u32 body length, a JSON header, a body, as the Markdown child frames; header at most 64 KiB, request body 1 MiB, response bound measured; the reply pipe is untrusted, so a frame past a bound, a header that does not parse, or an id the host did not issue ends the worker's group and never raises in the host's reader. Handshake hello {build, root, subject, cache_dir, scratch} answered ready or wrong_build, under a start deadline. Every handler runs off the reader thread and off the dispatching loop. cancel cancels a coroutine and expires a synchronous handler's Budget. Two-level deadlines as the SQLite readers have: at the deadline the call fails with the degraded plugin_error envelope; at deadline plus grace the group is killed, a GET in flight not past its own deadline is sent once more, and the refusal is kept for that plugin, hook, and query for a time. Calls in flight capped, a short queue, then busy; host writes never block. Streams do not pin a worker: stream.open and stream.lines, the host keeps cursors, a new worker replays up to the cursor. The host watches resident size and recycles or kills. Generation is the environment's fingerprint plus each plugin directory's asset stamp, compared on an interval off the event loop. The chart memo stays in the worker. Three failed starts then a cool-off; a hard-deadline kill counts against the hook. Every constant from a measurement of the three plugins. Golden protocol session and the fault tests in the plan's Testing Strategy.

## Notes

2026-11-26, third revision of the plan: folded in a second review of the isolation layer, threats, and protocol.
