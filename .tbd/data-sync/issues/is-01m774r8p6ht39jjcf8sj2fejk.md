---
type: is
id: is-01m774r8p6ht39jjcf8sj2fejk
title: One prepare unit per subject with an addressable render GET and prediction
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
  - type: blocks
    target: is-01m774r9n7z8bymhs94yjq67sw
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:38.565Z
updated_at: 2026-11-15T07:01:08.787Z
---
Shared prepare promise per subject covering envelope, render, and assets; render GET by path, content identity, and options; driven by keyboard focus and next row, pointer-down, hover; Commits and Pulls warmed after first view. Measured as cold-neighbor painted-ready and subject request counts.

## Notes

Input from jlevy/metabrowser#369 review B (B4, deferred here): the PR page's first visit is serial (record, then Markdown, then on a document's first PR page inert-html and five KPress stylesheets), about 20 ms per first visit plus about 50 ms once per document for assets. A prepare unit per subject should start the Markdown render and those assets with the record; moving inert-html and KPress stylesheets to another loading tier needs a measurement first, and a render per hover peek has its own cost to measure.

2026-11-14: H94 absorbed H75 (mb-97ex, closed as a duplicate), so this round also carries H75's PR and Git navigation dwell sweep, which mb-97ex said is still needed: preparation hit rate and the exact selected-subject request count, with painted readiness at 0, 100, 200 and 450 ms dwell and on keyboard selection. The dwell journey comes with recorder revision 6 (mb-tpol). Per the architecture review, H94 runs after H112 (mb-wki1), filling its hosts.
