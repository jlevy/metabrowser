---
type: is
id: is-01m7kbqszvgyye5ezs0pyj29c6
title: "PR #485 B1: The identity's import trusts /usr/bin/security and leaves the key extractable, so an unlocked release keychain lets any process export it without a prompt"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T23:40:36.730Z
updated_at: 2026-11-16T23:48:26.199Z
started_at: 2026-11-16T23:40:37.620Z
closed_at: 2026-11-16T23:48:26.198Z
close_reason: "Fixed in 9e7d362be: O1 imports with security import FILE -k KEYCHAIN -x, without -A, -T or -f pkcs12; the offline .p12 is required; removing /usr/bin/security from the key's access list is optional; O1's verification and testing row require security export -k KEYCHAIN -t identities -f pkcs12 -P x -o /dev/null to fail with the keychain unlocked; CI gets its own Developer ID Application certificate in O4, so O4 and O9 never export from the release keychain; Background and Who Can Sign say what the import trusts and that this rests on Apple's source (keychain_import.c read), confirmed at O1, not by this PR."
resolution: null
duplicate_of: null
---
High. PLAN:317-321, :332-334, :501-507 (O1), :530 (O4), :563-565 (O9). Per Apple's open-source Security code, security import with neither -A nor -T gives the key the default access, trusting the importing tool for sign and export, and marks it extractable unless -x. Fix: import with -x and without -f pkcs12; optionally remove security from the key's access list; make the offline .p12 required or give CI its own certificate; add a verification that security export fails with the keychain unlocked; correct the import statement. Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
