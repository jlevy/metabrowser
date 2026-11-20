---
type: is
id: is-01m7tnaxethq70h5dxyhfdzz8r
title: Draw Mermaid in pull-request text beside a trusted checkout, laid out in a frame whose policy loads nothing
kind: task
status: closed
priority: 2
version: 10
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/616
    at: 2026-11-20T17:05:41.355Z
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-19T19:43:01.079Z
updated_at: 2026-11-20T19:16:01.394Z
started_at: 2026-11-19T19:43:02.773Z
closed_at: 2026-11-20T03:05:28.181Z
close_reason: Merged in jlevy/metabrowser#616 (738758e38) after review B and a WebKit check in the app's WKWebView. Inert documents' in-page layout follows up as mb-htyq.
resolution: null
duplicate_of: null
extensions: {}
---
PR-text diagrams draw only on pinned-revision pages, whose untrusted CSP bounds what Mermaid loads while it lays a diagram out. Without a page CSP, KPress image placement still loads URLs from themeCSS (init directive and front matter), a fontFamily directive, state classDef, block-beta style, and the image shape (measured in headless Chrome). Lay PR-text diagrams out in a same-origin srcdoc frame whose meta CSP is default-src 'none', img-src data:, script-src the frame entry and Mermaid's directory, so nothing loads under either profile, and draw them on every page.

## Notes

PR https://github.com/jlevy/metabrowser/pull/616 (branch claude/pr-text-diagrams-frame). Measurement and design in the PR body.
