---
type: is
id: is-01m880q926wkkczw9vdg7d3grv
title: Offer the structured Table tab only on a list of records
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/805
    at: 2026-11-25T00:58:58.513Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7tv7gz4yk6tygqfexgtw0s2
hold: null
hold_until: null
created_at: 2026-11-25T00:12:08.123Z
updated_at: 2026-11-25T03:06:41.591Z
started_at: 2026-11-25T00:16:28.314Z
closed_at: 2026-11-25T03:06:41.587Z
close_reason: "Merged in #805 (de144e2fa): the structured Table view is offered only on a JSON or YAML file that starts as a list of records (structured/offer.py, a bounded prefix sniff), so a mapping, a scalar, or an empty list has no Table tab. File-kind views may declare offer on text kinds. Follow-up: mb-87vw (a record list past the parse limit)."
resolution: null
duplicate_of: null
---
A JSON or YAML file that is not a list of mappings shows a Table tab whose body says 'This document is not a list of records: its top level is a mapping, not a list.' The owner asked (2026-11-24) that the message never appear: offer the Table view only where it applies.
