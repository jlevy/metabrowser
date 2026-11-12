---
type: is
id: is-01m78aepp2j77wr6a4bpm4tvgt
title: "PR #375 A6: --doctor blames the built-in plugin when an override takes its key"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:31.105Z
updated_at: 2026-11-12T17:22:21.079Z
started_at: 2026-11-12T16:46:42.459Z
closed_at: 2026-11-12T17:22:21.078Z
close_reason: "Fixed in 8a813fbd: ViewKeyProblem.holder, describe(holder_plugin), docstring and docs/plugins.md; override repro test. Disposition: https://github.com/jlevy/metabrowser/pull/375#issuecomment-6830783051"
resolution: null
duplicate_of: null
---
Low. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). cli/plugins.py:280-286 names only the losing view's owner, and keymap.py:135 keeps only the holder's view id; the docstring at cli/plugins.py:268 says the problem names the plugin whose view is served. Repro: plugin steal overrides markdown/rendered with key s. Fix: add holder to ViewKeyProblem, name the holder's plugin, correct the docstring, document in docs/plugins.md.
