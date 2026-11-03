---
type: is
id: is-01m6ghtfstncw2xgewnwzvjr6y
title: Investigate the preexisting ResizeObserver notification on a named PR file jump
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T11:13:30.932Z
updated_at: 2026-11-03T11:13:30.932Z
---
Matched real-Chrome probes on handoff renderer 9b624b3a and reviewed integration 64afc0d9 both emit one ResizeObserver loop completed with undelivered notifications ErrorEvent during scrollToFile for a named file. Conversation-to-Files alone does not emit it. Root height changes 965 to 953 around the existing jump/spacer/hold-place path. No visible layout break, drift, overflow, console warning, or unhandled application exception was observed. Preserve anchoring and measure any proposed change; do not suppress observer diagnostics or change anchoring without a matched control. This is a Low diagnostic follow-up, not a newly introduced final integration regression. Matched evidence is in the final real-browser QA report and action captures.
