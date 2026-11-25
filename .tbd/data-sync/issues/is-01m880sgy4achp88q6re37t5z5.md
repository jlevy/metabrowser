---
type: is
id: is-01m880sgy4achp88q6re37t5z5
title: Link the served root's whole address in the view header eyebrow
kind: task
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/803
    at: 2026-11-25T00:52:16.413Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T00:13:21.731Z
updated_at: 2026-11-25T00:52:28.308Z
started_at: 2026-11-25T00:20:32.029Z
closed_at: 2026-11-25T00:52:28.288Z
close_reason: "Merged in jlevy/metabrowser#803 (edb99dfd1): the served root's whole address is one link to the root, folders under it are their own links, and spaced slashes are text."
resolution: null
duplicate_of: null
---
The owner asked (2026-11-24): above a viewed file the eyebrow reads '~/wrk/github/metabrowser /' where only the spaced standalone / is a link to the served root and the address is dimmed text. Make it read '~/wrk/github/metabrowser/' with the whole address and its slash one link to the served root, dropping the spaced slash; the effect of clicking is the same.
