---
type: is
id: is-01m023ccrxgs5bpkjha8nev9c7
title: "Binary preview: plugin stylesheet and typography contract"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies:
  - type: blocks
    target: is-01m023cq7qajqd0y3x4r4378sv
parent_id: is-01kzt2pwbyj3rt7y2xhevg8ff5
created_at: 2026-08-15T06:57:36.029Z
updated_at: 2026-08-15T07:27:46.164Z
closed_at: 2026-08-15T07:27:10.259Z
close_reason: null
---
Plugin-owned styling that consumes host tokens and adds no new mono use site.

## `src/metabrowser/builtin_plugins/binary/styles.css` (new)

Auto-loaded: `server._build_plugin_style_block` emits a `<link>` for any
plugin's `styles.css` without a manifest entry.

- `:root` defines `--binary-special-text` in OKLCH, derived from the host
  `--muted` family so a transformed byte reads as de-emphasized structure
  rather than as status. `[data-theme="dark"]` overrides it. The shell resolves
  system preference onto that attribute, so no `prefers-color-scheme` block is
  needed.
- `.metabrowser-binary-host` — full-width wrapping surface:
  `white-space: pre-wrap; overflow-wrap: anywhere`, no prose measure, no
  horizontal scroll in the default layout.
- `.binary-byte-special` — the token plus `var(--weight-bold)`.
- No `font-family` and no font-size literal. The view renders inside
  `<pre class="code-block"><code>`, so monospace and `--mono-block-font-size`
  arrive from the existing, already-classified `.code-block code` rule.
- No color literal outside the token blocks, per the design system.
- No `user-select`: byte content is informational text and stays selectable.
- `Load more` uses `.btn` with `type="button"`; the loading placeholder uses the
  shared `.mb-delayed-loading` utility; oversize, empty, and error states use
  `.preview-empty`, with `role="alert"` on failures.

## `tests/test_chrome_typography.py`

Add `builtin_plugins/binary/styles.css` to `STYLE_FILES`. The design system says
the rule is enforced "across the host and plugin stylesheets", and the scanned
set currently covers only `static/styles.css` and `agent_log/styles.css`. The
plugin declares no monospace of its own, so no `MONO_ALLOWED_SELECTORS` entry is
added and the test proves it stays that way.
