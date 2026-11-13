---
type: is
id: is-01m7awmpdrtg05jbp6azj78jjh
title: Diff views carry no explanatory notes; the Rendered/Source toggle explains itself
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T16:42:50.679Z
updated_at: 2026-11-13T16:42:50.679Z
---
The user, 2026-11-13: remove superfluous notes like 'Source shows additional changes.' from the diff viewer. The Rendered/Source toggle should be clear on its own. Follow-up to mb-lw70 (#394), which removed 'Rendered diff unavailable. Showing source.' but kept this one. Sweep the diff views (core diff, rendered Markdown diff, PR files) for every similar meta-note about rendering, sources, or views, and remove them; keep only real errors the reader must act on.
