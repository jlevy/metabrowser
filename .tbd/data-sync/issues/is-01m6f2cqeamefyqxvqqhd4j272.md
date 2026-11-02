---
type: is
id: is-01m6f2cqeamefyqxvqqhd4j272
title: A pin's patch container accepts a .. inner path where a folder answers 404
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-02T21:24:36.937Z
updated_at: 2026-11-02T21:24:36.937Z
---
Found 2026-11-02 by the security review of PR 274, outside that layer, on main. /api/file?path=<patch wire>/../../etc/passwd answers 200 kind diff with the inner path echoed, for a plain .patch too, where a folder answers 404. The path is virtual and nothing is read from the filesystem, so this is a parity gap, not a read. See content_routes.py near lines 1517-1519.
