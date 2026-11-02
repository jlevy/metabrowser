---
type: is
id: is-01m6f9zf7pxwdfz4cx269spnfk
title: metab --api prints C1 control and bidi characters raw to the terminal
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-02T23:37:11.157Z
updated_at: 2026-11-02T23:37:11.157Z
---
Found 2026-11-02 by the security review of PR 279, pre-existing on main. api_cli._render near line 102 uses ensure_ascii=False, so C1 controls (U+009B CSI measured raw as c2 9b), DEL, and bidi overrides from untrusted content reach the terminal for every --api route; C0 and ESC are escaped. Whether a terminal acts on UTF-8 C1 controls varies. Related: mb-lzwc.
