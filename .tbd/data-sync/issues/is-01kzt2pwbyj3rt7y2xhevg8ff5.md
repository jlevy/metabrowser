---
type: is
id: is-01kzt2pwbyj3rt7y2xhevg8ff5
title: "Spec: bounded binary byte preview"
kind: epic
status: open
priority: 2
version: 10
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies: []
child_order_hints:
  - is-01m023aj0nsy3e8znz9bc0150f
  - is-01m023b2kyytw947ng94r6t5af
  - is-01m023bka4yd975g2b7xr5tap4
  - is-01m023c0gqd8ccpx9nr7rpbrp3
  - is-01m023ccrxgs5bpkjha8nev9c7
  - is-01m023cq7qajqd0y3x4r4378sv
  - is-01m024s03n1vxyhxqm7dz7p5tp
created_at: 2026-08-12T04:11:55.645Z
updated_at: 2026-08-15T07:27:36.574Z
---
Deliver the bounded binary byte preview described in
docs/project/specs/active/plan-2026-08-11-binary-byte-preview.md.

The built-in `binary` plugin declares no views today, so `_views_for_kind("binary")`
returns an empty list and the preview pane paints its static "No preview is available
for this binary file" branch in `static/app.js`. This epic gives that plugin one default
`bytes` view backed by a bounded chunked data hook.

Scope boundary: Metabrowser core is untouched apart from two test files. Everything
new lands under `src/metabrowser/builtin_plugins/binary/`.

Acceptance:
- `/api/file` reports a default `bytes` view for a binary file.
- Bytes render under the documented display contract with bounded reads, bounded DOM
  growth, disposal, and theme-aware plugin-owned styling.
- `make verify` passes.
