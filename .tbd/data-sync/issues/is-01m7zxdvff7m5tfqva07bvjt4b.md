---
type: is
id: is-01m7zxdvff7m5tfqva07bvjt4b
title: Handle exhausted inventory-version retries in HTTP and SSE
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-21T20:40:38.125Z
updated_at: 2026-11-21T20:40:38.125Z
---
Main can raise VersionUnavailableError after pin retries in tree, grouped tree, and catalog reads. Assess typed retryable HTTP and SSE resync behavior at the existing public consumers, with CLI/browser parity, independently of FDU provider recovery. Research source: draft #520. Keep out of 0.1.0 unless reproduced in the candidate.
