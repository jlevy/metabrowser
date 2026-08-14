---
type: is
id: is-01kzz039dpehjrvpg7nm2e47ft
title: Align logical extensions and metadata classification
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - classification
  - python
dependencies:
  - type: blocks
    target: is-01kzz03kns6hp4a0rzkqnbjdww
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:02:28.661Z
updated_at: 2026-08-14T02:26:42.572Z
closed_at: 2026-08-14T02:26:42.571Z
close_reason: Implemented ASCII-case-folded two-component logical extensions, leading-dot behavior, basename/exact/suffix classification precedence, and portable classification fields; walker/watcher and boundary tests pass.
---
Update fs_paths.derive_ext and the registry classifier to implement the exact two-component, ASCII-case, dotfile, eligibility, basename, exact-compound, longest-suffix, and priority contracts. Preserve logical and canonical extension plus kind, family, group, content family, source, confidence, and registry identity. Keep walker and watcher construction centralized through FsEntry.for_observed_file. Tests: every boundary example, uppercase suffixes, bare and suffixed dotfiles, .js.map/.ts.map/.tar.* precedence, basename evidence, unknown values, and walker/watcher parity. Acceptance: metadata classification is deterministic and breakdown placement follows No extension, family, then Remaining types precedence.
