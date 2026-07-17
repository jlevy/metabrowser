---
type: is
id: is-01kxs1ycvj8kv2a9k0n4zwdk0n
title: "R1: Host middleware rejects non-default --host binds; wire CLI bind into allowlist + docs + actionable 421"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01kxs2bd3cgdpv7tka15ts9j99
parent_id: is-01kxs2b441234qwdrbz6zekv70
created_at: 2026-07-17T22:07:55.250Z
updated_at: 2026-07-17T22:15:28.573Z
closed_at: 2026-07-17T22:15:28.573Z
close_reason: Fixed and pushed; make verify green (723 tests incl. new host-validation CLI, selector round-trip, and copy-delegate behavioral suites).
---
server.py allowlist never learns the CLI --host value; wildcard binds need loopback readiness; document METABROWSER_ALLOWED_HOSTS; CLI regression tests.
