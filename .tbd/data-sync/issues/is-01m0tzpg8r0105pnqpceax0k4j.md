---
type: is
id: is-01m0tzpg8r0105pnqpceax0k4j
title: "PR #76 review R9: service no longer needs highlightElement in the ambient declaration"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0tznss30senrnyn9x48gedp
created_at: 2026-08-24T22:54:13.784Z
updated_at: 2026-08-24T23:01:44.324Z
closed_at: 2026-08-24T23:01:44.324Z
close_reason: "Fixed: the ambient declaration sentence now says highlightElement already exists for the shell enhancer and only highlight and getLanguage need adding; the token service needs no element method."
resolution: null
duplicate_of: null
---
Leftover from the DOM-fragment design the R1 fix replaced. The token-data service calls hljs.highlight and hljs.getLanguage only; highlightElement belongs to the shell's existing highlightCode() enhancer and is already declared in static/types.d.ts:1542. The sentence sends the implementing agent to add a declaration that exists and implies the service uses it.
