---
type: is
id: is-01m774r8p6ht39jjcf8sj2fejk
title: One prepare unit per subject with an addressable render GET and prediction
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:38.565Z
updated_at: 2026-11-12T15:31:32.818Z
---
Shared prepare promise per subject covering envelope, render, and assets; render GET by path, content identity, and options; driven by keyboard focus and next row, pointer-down, hover; Commits and Pulls warmed after first view. Measured as cold-neighbor painted-ready and subject request counts.

## Notes

Input from jlevy/metabrowser#369 review B (B4, deferred here): the PR page's first visit is serial (record, then Markdown, then on a document's first PR page inert-html and five KPress stylesheets), about 20 ms per first visit plus about 50 ms once per document for assets. A prepare unit per subject should start the Markdown render and those assets with the record; moving inert-html and KPress stylesheets to another loading tier needs a measurement first, and a render per hover peek has its own cost to measure.
