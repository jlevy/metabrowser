---
type: is
id: is-01m7jk8ngsg04g1ebkeqgf38aq
title: "Keymap: C opens Commits (H freed), Conversation moves to O, agent-log Charts to R, with a PLUGIN_SDK_VERSION bump — awaiting owner decision"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T16:32:54.806Z
updated_at: 2026-11-16T16:32:54.806Z
---
Owner, 2026-11-16: "Also, can you check if there's a reason we don't assign C to be the keyboard shortcut for commits? If there are no conflicts, that is better than our current assignment." Conflicts found: C is the pull request page's Conversation tab (pull-page.js PULL_TABS) and the agent-log Charts view (agent_log/manifest.toml key c); reserving C refuses third-party manifests using c (plugin contract break, needs PLUGIN_SDK_VERSION bump). Proposed mapping sent to the owner; build as one small layer on their go-ahead.
