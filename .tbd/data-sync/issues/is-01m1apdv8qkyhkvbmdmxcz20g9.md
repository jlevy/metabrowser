---
type: is
id: is-01m1apdv8qkyhkvbmdmxcz20g9
title: "PR #89 F3: /api/kpress/render is GET+POST, so the POST decision's premise is half false"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1apd8ye0cvejxessb3ppzjy
created_at: 2026-08-31T01:20:03.862Z
updated_at: 2026-08-31T01:40:12.543Z
closed_at: 2026-08-31T01:40:12.543Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #89."
resolution: null
duplicate_of: null
---
The closed POST decision in plan-2026-08-21-cli-parity-and-golden-coverage.md says both kpress routes are POST-only. server.py registers render as methods=[GET, POST] and it renders on GET; only export is POST-only. Verified: cli-api-shell pins render through both forms.
