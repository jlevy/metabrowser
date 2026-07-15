---
type: is
id: is-01kxhvy508zsg3zxbj2m5wptzd
title: Remove built-in LMDB support from the standalone core
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T03:08:14.727Z
updated_at: 2026-07-15T03:18:23.278Z
closed_at: 2026-07-15T03:18:23.277Z
close_reason: "Removed specialized database support and its two native dependencies from the core package; updated public docs/spec and wheel assertions; local make verify and the full PR #1 CI matrix pass."
---
Remove the mandatory lmdb dependency, core reader, built-in LMDB plugin, browser types, tests, packaging assertions, and public documentation. Update the v0.1.0 plan so specialized binary formats are external plugins while gzip and zlib remain first-class core compression support. Run the full release gate and update PR #1.

## Notes

Removed the specialized reader and built-in plugin end to end, including both now-unused native dependencies, source, browser types, tests, manifests, distribution assertions, and public docs. Updated the v0.1 spec; mb-fls3 tracks bounded zlib support and blocks mb-xkcx publication. Local make verify passes with 604 tests and 64 audited Python packages.
