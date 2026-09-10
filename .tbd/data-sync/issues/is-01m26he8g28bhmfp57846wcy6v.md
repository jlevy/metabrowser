---
type: is
id: is-01m26he8g28bhmfp57846wcy6v
title: Make image preview a manifest-owned view with CLI/golden parity
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m269p2k74jayrjt4vjad15y2
created_at: 2026-09-10T20:51:38.625Z
updated_at: 2026-09-10T22:20:07.476Z
closed_at: 2026-09-10T22:20:07.476Z
close_reason: "Implemented and verified the release-hardening slice: Recent now filters and clusters the complete server-selected model with bounded convergence repair; functional UI parity is enforced through CLI/golden evidence over exact production JavaScript; Markdown TOC composition restores same-document scrollspy and KPress disclosure; image preview is manifest-owned. make verify passes, including 1,968 tests, 104 golden scenarios, audits, and isolated wheel smoke."
resolution: null
duplicate_of: null
---
Release-blocking parity gap found during the functional UI audit. api_file emits kind=image with views=[] and app.js imperatively renders /raw, so the visible image surface is absent from the kind/view architecture map, metab --show golden, and production-renderer sessions. Move the behavior behind a built-in image plugin view, emit the declared view from /api/file, remove the app.js type special case, pin the envelope via cli-show, execute the exact renderer in a browserless session, and reserve a narrow exemption only for real decode/paint/layout behavior.
