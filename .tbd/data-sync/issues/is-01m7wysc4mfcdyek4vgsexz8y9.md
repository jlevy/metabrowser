---
type: is
id: is-01m7wysc4mfcdyek4vgsexz8y9
title: Agent operations views for Claude Code and Codex
kind: epic
status: in_progress
priority: 2
version: 15
spec_path: docs/project/specs/active/plan-2026-11-19-agent-operations-views.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/619
    at: 2026-11-20T19:14:54.488Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/623
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/636
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/639
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/640
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/648
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/654
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/655
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/663
    at: 2026-11-20T19:14:54.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/683
    at: 2026-11-21T19:01:25.522Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7v6zvf1g0xxpt03124y9etx
  - is-01m7ey9rh2d248vz5qe8yteasa
  - is-01m7vr3zn31cz93jckrtmgw7hh
  - is-01m7vkyp4r0rtmjjee8bq16frf
  - is-01m7twcn3tvnassmqymn7aask8
  - is-01m7zk4qfyb6ep79p81gwdj87q
  - is-01m7zktgz6zp5s6ny6dkmxm5m7
created_at: 2026-11-20T17:06:40.914Z
updated_at: 2026-11-21T19:01:25.550Z
duplicate_of: null
extensions:
  linear:
    id: 99cce315-e87d-462e-9e07-3cb1b8e5f249
    linked_at: 2026-11-20T19:16:50.543Z
---
Operational visibility into \~/.claude and \~/.codex as the built-in agents plugin. Plan: docs/project/specs/active/plan-2026-11-19-agent-operations-views.md. Phase 1 (recognize current Claude Code transcripts and Codex rollouts, #636) and Phase 2 (SDK additions, the provider layer, the plugin, the catalog and routes, the home, session list and Session view; #639, #640, #648, #654, #655) are merged.

What remains: Phases 3 to 6 (timeline and live events, usage and tokens, events, tools and latency, agent-specific depth and trust) have no beads yet; agent-log chart hues per record kind (mb-lkja); and agent-log detection that still lists agent names beside the registry (mb-0mq1).
