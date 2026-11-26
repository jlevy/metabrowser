---
type: is
id: is-01m8bfwz44tckg3hn0sh1r7nfr
title: "Linux confinement backend: Landlock and seccomp behind the isolation probe"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:06.500Z
updated_at: 2026-11-26T09:20:37.479Z
started_at: 2026-11-26T09:20:28.186Z
---
Phase 0 (plan: Isolation, The Enforcement Matrix). A Linux confinement backend behind the facility's probe: the host interpreter runs a standard-library launcher that sets no_new_privs, applies a Landlock ruleset (file reads, writes, creation, removal, and exec outside the grants; TCP from ABI 4; signal and abstract-socket scoping from ABI 6) and a seccomp filter, then execs the child. The filter refuses socket(2), or with network internet admits only AF_INET and AF_INET6; refuses io_uring_setup(2), because IORING_OP_SOCKET makes a socket with no socket call and Landlock does not judge a connection to a Unix socket by path (the spike's first filter left this open, a second review found it, and confine_probe.py's column 'io_uring left open' shows a confined child reaching a Unix socket outside every grant); with processes none refuses fork and a clone without CLONE_THREAD and answers ENOSYS to clone3, so programs fail and threads start; and fails the keyring calls, bpf, and perf_event_open. Decide here whether the filter stays a list of refusals or becomes a list of what a Python worker may call: io_uring got past the first, and nothing shows it was the last door. Spike: explorations/plugin-worker-spike/confine_linux.py, with results/2026-11-26-linux-confine-2.json and -probes-2.json: on kernel 6.18 (Landlock ABI 7, x86-64) every row of the matrix as stated, a plugin worker confined, and the repository's unmodified PDF render child behind the prefix through the existing Sandbox seam (PNG identical, 131 ms against 94 ms). Production work: the launcher in metabrowser.isolation, fail closed when the kernel lacks Landlock or the architecture is unknown, a probe that requires a refused read and a refused socket, a test that reads NoNewPrivs and Seccomp from /proc, the matrix refused and allowed bare as tests/test_pdf_preview_sandbox.py does on macOS, aarch64 run in CI or marked unverified, and previews of untrusted PDFs on Linux as the first user.

## Notes

2026-11-26, third revision of the plan: folded in a second review of the isolation layer, threats, and protocol.
