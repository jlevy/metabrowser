---
type: is
id: is-01m39amsczwb0ehaa4mgajhdw1
title: Untrusted Markdown in acquired sources can load outside stylesheets and images
kind: bug
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T09:06:17.629Z
updated_at: 2026-09-24T10:32:39.812Z
---
Found while fixing step 7's review (PR #233, fc752ad8). KPress sanitized output keeps <link href>, <img src>, id attributes, SVG <use>, and <input src>. markdown/rendered.js inserts it directly, and the main shell sends no Content-Security-Policy (only sandboxed /raw responses do). So a mirrored repository's README can load an outside stylesheet or tracking image, or clobber globals via id, even under the forced untrusted profile, which breaks the thin-mirror principle that acquired content is untrusted. Step 7 added builtin_plugins/github/pull_html.py (server) and neutralizeFragment (client) for PR text. Apply the same hardening to repository Markdown whenever the active-content capability is off (forced for every mirror), and consider a restrictive CSP on the shell for untrusted sources. Add hostile-README tests and a browser check. Pre-existing for local folders under --untrusted too.

## Notes

2026-09-24: the step 7 security review confirmed the exposure. A fork PR author controls the head's repository Markdown, and KPress sanitized output allows SVG url() attributes that load on render (P1), data-kpress-* hooks that load KPress JS and iframes, and app class names such as modal-overlay. This blocks landing: implement it as step 8 above #233 with the same strict allowlist step 7 adopts for PR comments, applied whenever active content is off, which is forced for every mirror. Add hostile-README tests and a real-browser network watch.
