---
type: is
id: is-01m8bfwyrthng58j0rn5mjw2q5
title: "Core isolation facility: one way to start, limit, and confine a child process"
kind: task
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfwz44tckg3hn0sh1r7nfr
  - type: blocks
    target: is-01m8bfwztw84vfapjmyap7ta72
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:06.138Z
updated_at: 2026-11-26T09:20:37.473Z
started_at: 2026-11-26T09:20:28.178Z
---
Phase 0 (plan: Isolation, The Facility; Key Decisions 6 and 11). Extract one core package, src/metabrowser/isolation/, from builtin_plugins/pdf/preview_isolation.py, render_child.limit_resources, the supervision in sqlite_readers.py and markdown_projection_worker.py, and the stop registry in git/process.py and git/children.py. Two halves kept apart: containment (what a child may touch) and supervision (how it is started, watched, and ended); Git and gh take supervision alone. Shape: policy.py (Confinement with read, write, network none|internet, processes none|confined, programs; Limits with cpu, address space, a parent-side resident watch, file growth; Enforcement, which records what is actually enforced so --doctor, GET /api/plugins, and the consent print the same thing; decide(requirement, backend, confinement), which is isolation_for generalized to required|preferred|none and never downgrades silently), probe.py (one real probe per backend, replaceable in goldens), macos.py (a policy rendered as a profile), linux.py and _confine.py (mb-v2m7), child.py (spawn with subprocess: close_fds, pass_fds, process_group=0, cwd; a group led by a watchdog holding a lifeline; deadline, capped reads, reaping by pid), groups.py (the one stop registry). A structural test, in the shape of test_only_the_named_modules_start_git, fails when a module outside the facility starts a process. Defects it fixes: the SQLite readers inherit the server's whole environment and stay in its group with only RLIMIT_AS; render_child.py's comments say RLIMIT_NPROC stops a fork and RLIMIT_FSIZE stops every write, and neither holds, so Limits has no process count and a child that may start nothing is refused by the filter; four kinds of child have four stop paths. The PDF render child, the readers, the Markdown child, Git, and gh start through it; the readers and the Markdown child land with supervision alone and move to preferred as a second step. No behavior change for the PDF preview on macOS. Update arch-threat-model.md T7 and arch-plugin-system.md to name the facility.

## Notes

2026-11-26, third revision of the plan: folded in a second review of the isolation layer, threats, and protocol.
