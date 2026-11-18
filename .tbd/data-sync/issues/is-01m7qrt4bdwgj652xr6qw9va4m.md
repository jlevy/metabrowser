---
type: is
id: is-01m7qrt4bdwgj652xr6qw9va4m
title: "macOS app: Open URL… offers 'borrow from the checkout' and 'open the checkout instead' when a checkout of the URL's repository is known"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T16:46:02.092Z
updated_at: 2026-11-18T16:46:02.092Z
---
Follows mb-m4mg, whose first release (File > Open URL…, stacked on #539) opens a supported GitHub URL in the repository's mirror, always, and offers no checkout: neither the app nor metab can yet tell that a checkout of a URL's repository is known, so per the owner's direction that part was not built.

The design is in docs/project/architecture/arch-open-modes.md, The File Menu: when a checkout of the repository is known, Open URL… also offers "borrow from the checkout" (the mirror opened with `metab URL --checkout PATH`, an overlay store that downloads none of the objects the checkout has) and "open the checkout instead" (that folder, in folder mode). "A checkout is known when an open folder window is one; recent folders join when an entry records its repository."

What is missing, checked on #539's head 79b147537 and #546:
- An open folder window does not know which repository it is a checkout of: `GET /api/identity` answers short_name, full_name, kind, kind_label, title (FolderIdentity.swift), and `metab FOLDER --present --dry-run --format json` answers kind folder with no repository identity.
- Recent folder entries do not record their repository (plan-2026-11-10-native-macos-app.md Phase 4 on #546: "Record a checkout's repository with a folder entry").
- The `--present --dry-run` plan for a URL names no checkout.

Needed first: one resolver in metab (not the app) that answers, for a folder the reader opened, the repository identity of its remotes, compared through the GitHub plugin's grammar as the --checkout check in cache/lender.py does, so a planted .git cannot name a repository (plan-2026-11-02-pr-review-mirror-and-checkout.md, Finding the Checkout). Then the app matches an Open URL… plan's root against its open folder windows (and recent entries once they record it) and offers the two choices; the CLI parity is `metab URL --checkout PATH` and the resolver's dry-run field, each with a golden.
