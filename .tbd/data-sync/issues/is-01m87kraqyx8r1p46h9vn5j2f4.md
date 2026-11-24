---
type: is
id: is-01m87kraqyx8r1p46h9vn5j2f4
title: Document the security policy and accepted risks for every surface, from the threat model
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m87kjamkxy7hpkk0dyj5f737
created_at: 2026-11-24T20:25:31.130Z
updated_at: 2026-11-24T22:14:41.428Z
closed_at: 2026-11-24T22:14:41.426Z
close_reason: "SECURITY.md and arch docs, PR #797"
resolution: null
duplicate_of: null
---
From the threat model: state each security policy (the trusted and untrusted shell policies, /raw's sandbox and nosniff, frame and object policy, the sanitizer, API origin proof, trust switches, the app's open-file type policy and quarantine) with the threat it answers and the residual risk it accepts, in the user-facing SECURITY.md and the architecture documents. Includes PDFs: the native viewer embedded on the file page under object-src <origin>/raw, server-side PDFium rendering of untrusted PDFs for previews, and the app opening files in their default app. Name the evidence for each, and a check where make verify can enforce one.
