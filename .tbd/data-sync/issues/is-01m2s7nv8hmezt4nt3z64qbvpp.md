---
type: is
id: is-01m2s7nv8hmezt4nt3z64qbvpp
title: Golden-pin file:// acquire, reuse, and staging sweep without a live Git floor
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
  - stack:pr147
dependencies:
  - type: blocks
    target: is-01m2s7p36wwz4jjvvyv4x70mq7
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:06:35.665Z
updated_at: 2026-09-18T03:11:45.573Z
started_at: 2026-09-18T03:06:44.122Z
---
Portable pytest golden for Cache 1B-a acquire evidence. ubuntu-latest and this VM report Git 2.43.0, below the acquisition floor (2.43.7 / patched tracks); distro-patched Git remains refuse, so a live `metab file:// --no-serve` tryscript cannot run in current CI.

Follow tests/test_cli_golden.py: invoke the production CLI in-process, monkeypatch only require_acquisition_git (same as tests/test_cache_acquire.py), and pin logical identity. Origin recipe: isolated Git configs, pinned author/date, --initial-branch=main, no allowFilter so strategy is always full.

Pin: strategy, publication, transport, object_format, default_remote_ref, revision OID, home/layout state, staging_entries after sweep.
Elide: slug, source/store ids, file:// URL, timestamps, git_version, package created_by/written_by.
Do not add <HOME>/<MTIME> to normalize.py until a transcript emits those values (cache routes never report paths; --no-serve does not print the home).

Also pin leftover lock-free staging swept by --no-serve (open_cache startup sweep), and portable fail-closed https/ssh cases in cli-errors.tryscript.md.

No serving. Live cli-cache-acquire.tryscript.md waits on a CI Git 2.50.1 pin. Do not close until review.

## Notes

PR https://github.com/jlevy/metabrowser/pull/147 on cursor/v011-cache-acquire-golden-bd04 HEAD f2032694, stacked on #146. Pytest in-process goldens: acquire+reuse (cli-cache-acquire.txt) and lock-free staging sweep (cli-cache-recover.txt). Monkeypatch only require_acquisition_git. Origin recipe pins revision 8f05aafe23bbeade03ef581868a59e3c944ac5c4, strategy full, branch topic (remote-tracking spelling public hygiene accepts). Fail-closed https/ssh added to cli-errors.tryscript.md. Live tryscripts wait on mb-oueh (CI Git 2.50.1). Do not close until review.
