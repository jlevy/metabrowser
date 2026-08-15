---
type: is
id: is-01m023c0gqd8ccpx9nr7rpbrp3
title: "Binary preview: manifest view, registration, and file-envelope coverage"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies:
  - type: blocks
    target: is-01m023ccrxgs5bpkjha8nev9c7
parent_id: is-01kzt2pwbyj3rt7y2xhevg8ff5
created_at: 2026-08-15T06:57:23.479Z
updated_at: 2026-08-15T07:27:45.832Z
closed_at: 2026-08-15T07:27:10.256Z
close_reason: null
---
Wire the view into discovery so the shell stops painting its no-preview branch.

## `src/metabrowser/builtin_plugins/binary/manifest.toml`

Add one `[[view]]`: `kind = "binary"`, `id = "bytes"`, `label = "Bytes"`,
`default = true`, `container_class = "content-body metabrowser-binary-host"`,
`render_runtime = "client"`.

Declare neither `printable` nor `print_profile`. A bounded partial byte window
is not a complete print projection, so the shell's print button stays hidden.

Add one `[[data_hook]]`: `route = "chunk"`,
`sidekick = "metabrowser.builtin_plugins.binary.sidekick:chunk_handler"`,
`methods = ["GET"]`.

Add no `[[kind]]` block. The `binary` kind is assigned by the fallback in
`server._api_file_impl`, not by a manifest predicate; keep the existing comment
that says so and update it to describe the view that now exists.

## `src/metabrowser/builtin_plugins/binary/index.js`

Replace the placeholder IIFE with an ES module that imports `mountBytesView`
and calls `mb.registerView("binary", "bytes", { render })`. Reach only through
`window.metabrowser`; never touch `app.js` internals.

## `tests/test_api_file_plugin_views.py`

Add a case asserting `/api/file` reports a default `bytes` view for a binary
file, proving the shell's `data.type === "binary"` no-preview branch in
`static/app.js` is no longer reachable for it. `_views_for_kind` merges
`VIEW_REGISTRY["binary"]` (empty) with plugin manifest views, so the view
arrives purely from the manifest.

`tests/test_plugin_e2e_render.py` already fails when a declared `[[view]]` has
no matching `registerView`, so registration is covered by that existing
assertion; no new test is needed for it.
