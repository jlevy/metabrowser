---
type: is
id: is-01m8bfwztw84vfapjmyap7ta72
title: "Plugin worker client on the isolation facility: protocol, deadlines, lifeline, build stamp"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: claude-code@vm
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
updated_at: 2026-11-26T09:20:28.188Z
started_at: 2026-11-26T09:20:28.188Z
---
Phase 1 (plan: Process Model, Protocol; Key Decisions 8 and 9). The worker client, built on metabrowser.isolation, split from mb-3q4e. Start: [confinement prefix] <interpreter> -I -X pycache_prefix=<cache home> <runtime>/worker.py, in /, leading its own process group; request pipe on descriptor 3 and reply pipe on 4, close-on-exec in the worker; descriptor 0 /dev/null, descriptor 1 stderr to the server log; SIGINT ignored; an allowlisted environment with a private TMPDIR. Protocol: one JSON header line of at most 64 KiB then body_len bytes; id for host requests, wid for worker requests; hello carries the host's build stamp and a worker from another build answers wrong_build and exits; hello's answer carries sys.path for the ownership check; a header or body past its bound, or a malformed frame, ends that worker and never the host's reader; large replies in chunks other frames may pass. Deadlines fail the call with the degraded plugin_error envelope and do not end the worker; the worker ends only at a hard limit, at a cap of handlers past their deadlines, or when the event-loop heartbeat goes unanswered; ending it kills its process group and fails its other calls. A client disconnect cancels an async handler and abandons a synchronous one. Calls in flight are capped and one more answers busy. The lifeline exits from the reader thread. Start failures three times in a minute mark the worker failed; a hook that hit the hard limit is refused for a cool-off instead. Idle exit except with open streams; fingerprint checks at most once per measured interval. Every constant from a measurement of the three plugins. Golden protocol session and the fault tests in the plan's Testing Strategy; the probes in explorations/plugin-worker-spike/probes.py reproduce the failures this replaces (lifeline held by a blocking async hook for 7.5 s, a kill that left a subprocess and an unanswered call, a forked child ending the host reader).
