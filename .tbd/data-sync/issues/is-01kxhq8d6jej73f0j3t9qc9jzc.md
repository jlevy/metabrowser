---
type: is
id: is-01kxhq8d6jej73f0j3t9qc9jzc
title: "PR #1 review A7b: remove cold-start inventory busy scan"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:27.921Z
updated_at: 2026-07-15T01:46:27.921Z
---
Review A7b (Low). src/metabrowser/server.py: avoid repeated O(N) inventory copies/scans during api_tree cold-start grace.
