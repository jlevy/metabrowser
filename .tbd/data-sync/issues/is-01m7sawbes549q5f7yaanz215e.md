---
type: is
id: is-01m7sawbes549q5f7yaanz215e
title: Return the KPress pin to an exact release once jlevy/kpress#80 ships
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m7hhr43k5rc7ytbxg1vx031s
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-19T07:21:03.704Z
updated_at: 2026-11-23T00:15:43.807Z
started_at: 2026-11-23T00:15:43.784Z
---
jlevy/metabrowser#597 builds KPress from branch claude/diagrams-mermaid-mode via [tool.uv.sources] (pyproject.toml), with kpress>=0.3.9.dev0. Once jlevy/kpress#80 merges and KPress releases it: set kpress==<release>, remove [tool.uv.sources], relock, replace the SUPPLY-CHAIN-SECURITY.md branch row with the release row, and regenerate the goldens that record KPress's version stamp (cli-api-shell). publish.yml refuses a Metabrowser release until this is done.
