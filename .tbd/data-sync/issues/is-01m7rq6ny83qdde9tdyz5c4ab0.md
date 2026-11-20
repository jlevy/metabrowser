---
type: is
id: is-01m7rq6ny83qdde9tdyz5c4ab0
title: Pass diagrams=mermaid to KPress once a release draws svg fences as code
kind: task
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/597
    at: 2026-11-20T17:05:50.386Z
labels:
  - blocked-upstream
  - linear
dependencies: []
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
hold: null
hold_until: null
created_at: 2026-11-19T01:37:10.598Z
updated_at: 2026-11-20T18:01:22.583Z
closed_at: 2026-11-19T07:21:13.402Z
close_reason: 'Done in #597 with jlevy/kpress#80: KPressRenderRequest.diagrams exists on the KPress branch; kpress_adapter passes diagrams="mermaid"; cli-api-untrusted-markdown pins the svg fence as code, trusted and inert.'
resolution: null
duplicate_of: null
extensions:
  linear:
    id: d564ad49-237b-4a26-b608-57b29bc576c7
    linked_at: 2026-11-20T18:01:22.581Z
---
KPress 0.3.8 draws a svg fence as inline SVG in every diagrams mode but off; GitHub shows it as code, and Metabrowser's inert render drops it entirely (svg is DROPPED_WITH_CONTENT). Blocked on a KPress release where diagrams=mermaid draws only Mermaid; then pass it from kpress_adapter and pin a svg fence rendering as code, trusted and inert.
