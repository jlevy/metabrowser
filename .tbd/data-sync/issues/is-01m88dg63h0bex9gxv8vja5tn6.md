---
type: is
id: is-01m88dg63h0bex9gxv8vja5tn6
title: "Frontmatter follow-ups from the #816 review"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-25T03:55:27.215Z
updated_at: 2026-11-25T03:55:27.215Z
---
Low and nit findings from the review of #816 (frontmatter from the blob): (1) a pinned transclusion now carries the target file's frontmatter, as a folder's does, so show_frontmatter draws a Frontmatter disclosure inside the transcluded aside; say so in docs or decide transclusions show none; (2) InertRender.flight_key's docstring (markdown_projection_worker.py:380-383) still says frontmatter may come from the sent text; (3) the trusted render's frontmatter notice keeps KPress's role=alert while the page's inert one is role=status, which docs/design-system-messages.md calls a warning; make them agree; (4) add BOM and '...' closer shapes to tests/test_markdown_front_matter_boundary.py; (5) _without_kpress_toc now also removes the frontmatter notice; rename it.
