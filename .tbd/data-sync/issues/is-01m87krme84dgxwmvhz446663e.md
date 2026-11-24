---
type: is
id: is-01m87krme84dgxwmvhz446663e
title: Embed the PDF viewer on the file page for every source
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md
labels: []
dependencies: []
parent_id: is-01m87bky1pb8rhr10p26bsp6w6
created_at: 2026-11-24T20:25:41.053Z
updated_at: 2026-11-24T20:25:41.053Z
---
Untrusted shell policy admits object-src <origin>/raw only, so a pin's and an --untrusted folder's file page shows the browser's viewer inline. Only the file page embeds. Justified against the threat model (mb-31vb). Evidence: cli-ui-pdf-surfaces shows viewer on every surface with its policy-admits invariant; a policy test pins the directive; the Chrome test checks the viewer loads untrusted with no violation and a non-/raw embed stays blocked.
