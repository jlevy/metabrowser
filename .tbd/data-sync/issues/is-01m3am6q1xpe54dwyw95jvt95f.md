---
type: is
id: is-01m3am6q1xpe54dwyw95jvt95f
title: No way to open a changed file at base or head from a commit or PR diff
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T21:12:36.668Z
updated_at: 2026-09-24T21:12:36.668Z
---
Found during the v0.12 alpha acceptance (mb-gnr9) on the integrated stack (PR #241; installed wheel 0.11.1.dev400+250a10c4).

Alpha matrix rows M03 ("open base/head files from a diff") and M08 ("Open an unchanged and changed Markdown file at both PR base and head") expect to reach a changed file at either side of a comparison from the diff itself. On the integrated stack, neither a commit's diff (`/commit/<oid>`) nor a pull request's Files changed (`/pull/<n>/files`) offers that: each file bar has only "Copy path". Review comments do link to the file at the served head and line, and the header's "Browse code" opens the head pin.

The content is correct when reached another way: the comparison records the base and head blob OIDs, and `metab https://github.com/<o>/<r>/blob/<merge-base>/<path> --show <path>` and the PR URL's head pin show the base and head files (verified on jlevy/metabrowser#3: README.md is 5681 bytes at merge base 5dfb02e7 and 7454 at head 93edfdeb). Opening the base in a browser means another `metab` run or a pin switch through `POST /api/source/pin` with the commit ID, since the ref selector lists branches and tags only.

Acceptance test: a file bar in the diff view offers "View file" at the new side (and at the old side for a modified, renamed, or deleted entry). On a served mirror the old side switches the pin to the comparison's left commit, or opens it read-only without a switch. Cover it with a browserless session over the production diff-view module and a golden transcript, per the parity rules.

Owning PR: #233 (PR view) for Files changed; the commit diff view predates the v0.12 stack. The thin-mirror plan's capability map does not list this action, so it may be a plan decision rather than a defect; if so, amend the alpha matrix rows instead.
