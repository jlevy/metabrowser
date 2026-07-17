---
type: is
id: is-01kxs1ycvj8kv2a9k0n4zwdk0n
title: "R1: Host middleware rejects non-default --host binds; wire CLI bind into allowlist + docs + actionable 421"
kind: bug
status: open
priority: 1
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01kxs2bd3cgdpv7tka15ts9j99
created_at: 2026-07-17T22:07:55.250Z
updated_at: 2026-07-17T22:15:03.178Z
---
server.py allowlist never learns the CLI --host value; wildcard binds need loopback readiness; document METABROWSER_ALLOWED_HOSTS; CLI regression tests.
