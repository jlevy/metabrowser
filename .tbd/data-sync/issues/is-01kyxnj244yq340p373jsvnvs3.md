---
type: is
id: is-01kyxnj244yq340p373jsvnvs3
title: Audit and fix light/dark syntax palette contrast
kind: bug
status: in_progress
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-01T03:23:22.115Z
updated_at: 2026-08-01T03:39:38.356Z
---

## Notes

Root cause: the asynchronously loaded vendored light Highlight.js stylesheet won the cascade, while structured JSON/YAML syntax tokens lacked dark overrides. Added a shared semantic light/dark palette, higher-specificity mappings for every vendor color class, and WCAG contrast regression tests. make verify passes (743 pytest tests, 28 golden cases, full lint/type/audit/distribution gate).
