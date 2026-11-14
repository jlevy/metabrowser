---
type: is
id: is-01m7dm8kg73d4tyaed1t0ethta
title: Pulls says 'Run gh auth login' although gh is signed in (app-launched server)
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-14T18:14:09.153Z
updated_at: 2026-11-14T18:41:37.919Z
closed_at: 2026-11-14T18:41:37.918Z
close_reason: "Not a bug: an artifact of the end-to-end run's scratch HOME. The window the user saw was the E2E copy's 'notes' window, whose server ran with HOME set to a scratch directory. metab resolved /opt/homebrew/bin/gh 2.83.2 (gh.py:197, shutil.which); under the scratch HOME, 'gh auth status --active --hostname github.com --json hosts' prints 'You are not logged into any GitHub hosts' because gh finds the account through $HOME/.config/gh/hosts.yml, so parse_account returned nothing and the page showed the sign-in message (gh.py:114). With the same binary under the real HOME, gh reports login jlevy, active, tokenSource keyring; a GUI-launched copy with HOME=the real home read Pulls as reader gh:jlevy, state current. Evidence: app-e2e-check worktree attic/e2e/evidence/mb-mc85-gui-real-home.txt and mb-mc85-gh-scratch-vs-real.txt."
resolution: null
duplicate_of: null
---
The user (2026-11-14, forwarded from another session) saw in a Metabrowser app window's Pulls tab: "jlevy/metabrowser — Run gh auth login --hostname github.com to connect." gh 2.98.0 at ~/.local/bin/gh is authenticated with stored credentials (no GH_TOKEN). Possibly the release-variant window from the end-to-end run (mb-hwxu), launched from a DMG with fresh settings; possibly a real fresh-install bug: a GUI-launched app's server lacks ~/.local/bin (or /opt/homebrew/bin) on PATH, or cannot read gh's credential store, and the panel reports "auth login" instead of "gh not found".

Done when the cause is shown with evidence (the server's PATH, which gh ran, the exact command and its error); if real, the app's server finds gh the way the user's shell does (or the panel says gh was not found and how to fix it), with a test.
