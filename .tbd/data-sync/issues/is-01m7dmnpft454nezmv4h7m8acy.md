---
type: is
id: is-01m7dmnpft454nezmv4h7m8acy
title: "Rendered Markdown: chrome always sans, documents serif unless the sans preference is on"
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-14T18:21:18.188Z
updated_at: 2026-11-14T18:21:23.996Z
started_at: 2026-11-14T18:21:23.995Z
---
The user (2026-11-14): "Let's make sure we have a clear system about when we use serif and sans-serif for rendered markdown. chrome and PR descriptions etc are always sans. but document rendering is by default serif, unless we have preferences settings set to sans serif, and then they are sans serif too. for documents, when we render them in rendered view, they should use document rendering, so be serif unless sans is enabled in preferences."

The rule has two contexts:
- Chrome Markdown (PR descriptions, PR and review comments, commit message bodies, issue and bead bodies, tooltips, any Markdown inside the app's own interface) is always sans, whatever the reading-font preference says.
- Document rendering (a Markdown file, or any document, in rendered view) is serif by default and sans only when the reading-font preference (`metabrowser.proseFont`, `data-prose-font` on <html>) is set to sans.

Main already has parts of this: `html[data-prose-font="sans"]` in static/styles.css bridges `--kpress-host-font-prose`, the github plugin's styles.css forces `--kpress-host-font-prose: var(--prose-sans-font)` for PR pages, and `.git-commit-body` uses `--prose-sans-font`.

Done when every surface that renders Markdown is inventoried with its context (chrome or document) and the face it uses today; each surface follows the rule through one named mechanism (one context marker or scope, not per-surface font overrides); the rule is stated once in the design-system docs and in the views/models/routes map where a surface is registered; a browserless or golden test pins the face each context resolves to under both preference values; and any surface that broke the rule is fixed. Spacing of headings is mb-orvr's, not this bead's.
