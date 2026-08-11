---
type: is
id: is-01kxrgmxr607dw8d5ygsjt2bva
title: Reduce Markdown title spacing and refresh README screenshot
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-17T17:05:39.077Z
updated_at: 2026-07-17T17:28:27.458Z
closed_at: 2026-07-17T17:28:27.457Z
close_reason: "Completed in e4df7ac: preserved the owner's README voice, documented runtime and contributor prerequisites, retained the shared Node 24.18/npm 11.10 floor, scoped Markdown spacing fixes to the KPress host, regenerated the neutral-path screenshot after a settled render, added regression coverage, passed make verify with 705 tests, and passed GitHub Actions run 29600115127."
---
Measure and reduce the excessive top spacing above the first Markdown heading in the embedded KPress view, then regenerate and validate the public README screenshot.

## Notes

Measured the settled README render: the content wrapper, KPress article, and Diagnostics margin stacked to 60 px before the toggle, while the card and first H1 stacked to 73 px. Added MetaBrowser-host-scoped spacing overrides, a CSS contract regression test, and a refreshed 1280x720 neutral-path screenshot. Browser validation after a 10-second settle confirmed 44 px to Diagnostics and zero first-H1 top margin.
