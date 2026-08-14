---
type: is
id: is-01kzz47hh2hcdx2ckc7rx284kp
title: "PR #35 review R7: select-dir does not guard data-path like select does"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:42.338Z
updated_at: 2026-08-14T03:32:03.677Z
closed_at: 2026-08-14T03:32:03.677Z
close_reason: "Fixed in 78ee53e: select-dir now guards row.dataset.path like the select branch."
---
activateTreeRow in app.js guards row.dataset.path on the select branch but not on select-dir, so a pathless folder row would clear the whole selection and request the root.
