---
type: is
id: is-01m456f4va45tae7y1mj72aa3p
title: Isolate configuration in the HOME-override source-status golden
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
created_at: 2026-10-05T04:52:02.529Z
updated_at: 2026-10-05T05:29:24.029Z
closed_at: 2026-10-05T05:29:24.029Z
close_reason: "Fixed in PR268 commit f67606b7. Full make verify passed: 4006 pytest tests, 8 live-test skips, 278 goldens, clean npm/Python audits and distribution checks. All nine GitHub checks passed in run 37267339978; review posted on PR268."
resolution: null
duplicate_of: null
---
Review with Tryscript 0.3.0 and no inherited config override exposed cli-api-source status naming case: HOME and cache both point at fixture home, so default configuration becomes nested in cache and is correctly refused. Add explicit sibling METABROWSER_CONFIG_DIR in this command, retain expected output, and replay the full golden suite without relying on caller configuration.
