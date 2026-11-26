---
type: is
id: is-01m8bfwz44tckg3hn0sh1r7nfr
title: "Linux confinement backend: Landlock and seccomp behind the isolation probe"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:06.500Z
updated_at: 2026-11-26T09:20:28.186Z
started_at: 2026-11-26T09:20:28.186Z
---
Phase 0 (plan: Isolation, The Enforcement Matrix). A Linux confinement backend behind the facility's probe: the host interpreter runs a standard-library launcher that sets no_new_privs, applies a Landlock ruleset (file reads, writes, creation, removal, and exec outside the grants; TCP from ABI 4; signal and abstract-socket scoping from ABI 6) and a seccomp filter that fails socket(2) with EPERM, then execs the child. The spike is explorations/plugin-worker-spike/confine_linux.py, with results in results/2026-11-26-linux-confine.json and -probes.json: on kernel 6.18 (Landlock ABI 7, x86-64) a child and a plugin worker were refused reads and writes outside their grants, TCP, UDP, and Unix sockets, and signalling the parent, while asyncio, inherited descriptors, and started tools kept working; the prefix added 18 ms to a trivial child and 30 ms to a worker's start. Production work: the launcher in metabrowser.isolation, fail closed when the kernel lacks Landlock or the architecture is unknown to the filter, a probe that starts a real child and checks one refusal, a test that shows each row of the matrix refused and allowed bare (as tests/test_pdf_preview_sandbox.py does on macOS), aarch64 run in CI or marked unverified, and previews of untrusted PDFs on Linux as the first user (render_child under the policy; today the route answers no_sandbox). Record the measured start cost beside the constant it sets.
