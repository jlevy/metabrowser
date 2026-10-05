---
type: is
id: is-01m456f4va45tae7y1mj72aa3p
title: Isolate configuration in the HOME-override source-status golden
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
created_at: 2026-10-05T04:52:02.529Z
updated_at: 2026-10-05T05:05:54.710Z
---
Review with Tryscript 0.3.0 and no inherited config override exposed cli-api-source status naming case: HOME and cache both point at fixture home, so default configuration becomes nested in cache and is correctly refused. Add explicit sibling METABROWSER_CONFIG_DIR in this command, retain expected output, and replay the full golden suite without relying on caller configuration.
