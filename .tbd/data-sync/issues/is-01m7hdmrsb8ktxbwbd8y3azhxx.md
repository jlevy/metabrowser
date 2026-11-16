---
type: is
id: is-01m7hdmrsb8ktxbwbd8y3azhxx
title: "PR #463 A9: a shared changed-file part builder for the Diff summary and Pulls files trees"
kind: task
status: open
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T05:35:25.482Z
updated_at: 2026-11-16T06:17:01.149Z
---
Deferred from PR #463 Review A (A9, Low suggestion): https://github.com/jlevy/metabrowser/pull/463#pullrequestreview-5915439143. diff/diff-summary.js partsOf/statsOf and github/pull-files-view.js partsOf/statsOf each build the same four parts with the shell's .changed-file-row classes: the name, the chevron's slot (.changed-file-toggle), the change letter (.tree-container-badge.file-change-status), and the stats (.changed-file-stats). A part builder beside the model both already receive (host.tree, static/changed-files-tree.js) would put the class set's markup in one place, as its CSS is (static/styles.css, Changed-file rows). It takes the plugin's h, the chevron, and an extra name class such as mb-refreshing-text (the Pulls tree's names breathe). The source pin in tests/test_design_vocabulary.py (test_both_trees_of_changed_files_use_the_shells_rows) then becomes one check. Waits on: #470 and #472, which rework diff-summary.js's mount above #463; build it on the stack's final shape, after the stack lands.
