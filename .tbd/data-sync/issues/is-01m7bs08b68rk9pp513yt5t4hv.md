---
type: is
id: is-01m7bs08b68rk9pp513yt5t4hv
title: Transitions recorder test can leak Chrome on a subprocess timeout
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-14T00:58:29.604Z
updated_at: 2026-11-14T00:58:29.604Z
---
Found while fixing mb-p34w (#415): tests/test_transitions_instrument.py runs Node with subprocess.run and a 50 s timeout; on timeout it kills Node only, which can leave headless Chrome and its profile running (the same issue #409 fixed for the Overview alignment test with a process group and parent-owned profile). Done when the transitions test stops the whole process group on any exit and removes its profile, with a forced-hang check.
