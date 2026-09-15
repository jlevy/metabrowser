---
type: is
id: is-01m09s72hhtrzyr71j0dhwwwfj
title: "Diff boundary: Git refs, hosted-review metadata, and plugin views"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/architecture/arch-hosted-review-model.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T06:33:51.408Z
updated_at: 2026-09-15T00:01:49.910Z
closed_at: 2026-09-15T00:01:49.908Z
close_reason: Architecture boundary is now explicit in arch-hosted-review-model.md and the v0.11 provider plan; implementation is tracked by mb-63ym, mb-jlon, mb-p4sw, mb-wx32, and mb-r19i.
resolution: null
duplicate_of: null
---
Resolved by arch-hosted-review-model.md. The repository service owns bounded acquisition of selected Git refs and revision materialization. Provider adapters own hosted collaboration acquisition and map GitHub payloads into provider-neutral Hosted Review Format records. The hosted-review plugin owns PR documents, review/check presentation, and repository-scoped nav collections. File Diff Format remains the only diff rendering contract. Common views contain no provider branches.
