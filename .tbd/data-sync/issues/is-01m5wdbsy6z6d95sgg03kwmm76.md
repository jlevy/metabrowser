---
type: is
id: is-01m5wdbsy6z6d95sgg03kwmm76
title: "Coordinate the 0.12.0 release: tag and publish from main"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-26T15:30:46.852Z
updated_at: 2026-10-26T15:32:55.531Z
---
Coordinate tagging and publishing 0.12.0 from main. This replaces mb-n2ro, which coordinated the LANDING and is closed: the stack merged at 0b016e4b (PR #268, 2026-10-04) with CI 9 of 9 green. PyPI is 0.11.0 and there is no v0.12.0 tag.

Decided by the user on 2026-10-26: NO 0.11.1 patch release. main carries three breaking changes (Plugin SDK 0.6 to 0.7, the cache and configuration XDG split, the stronger meaning of --untrusted and --no-active-content), so it cannot ship as a patch, and a cherry-pick of the plain-folder fixes off v0.11.0 would be real work to deliver fixes that 0.12.0 ships anyway. Version is 0.12.0; later QA findings become 0.12.x.

The release is gated on the user's stated bar: everything additive on what exists, with what is missing tracked in the plans and beads.

ORDER OF WORK

1. Security and gate mechanics. DONE on branch claude/v012-release-prep: tryscript 0.3.0 reached the vulnerable zod 3.25.76 and `make audit` failed on GHSA-mrhx-c7xc-m3w5, so `make verify` failed on main even though CI was green three weeks earlier. Bumped to tryscript 0.3.1 (first-party exemption, reviewed in SUPPLY-CHAIN-SECURITY.md); lock delta is exactly two packages and zod 4.6.6 clears the ordinary cool-off on its own. The non-security upgrades were deliberately reverted and are mb-1jq3.

2. Re-run the landing gate on the release head (mb-2g6f). All three differentials were taken at 14fcdb85 and #268 landed above them with a breaking storage change, so none covers what would be tagged. The browser differential was never read even at the old head. Harnesses survive in the sibling folder metabrowser-landing-gate-evidence: data/run.sh (about 90 minutes, run detached), audit/run.sh, browser/run.sh (about 45 minutes, node 24, Chrome, ports 8851-8858). Corpora are gitignored and rebuild from data/build_corpora.py and browser/make_corpus.mjs. Accept rule unchanged: zero unexplained differences.

3. Release rehearsal step 3 on a quiet machine (mb-cf6y). exp-039 was never recorded; the experiments end at exp-038, which did not clear the candidate because wall-clock gates failed for BOTH builds under load. Needs 5 headed pairs and 5 compare_builds pairs with no agents running. The host was at load 11.5 on 2026-10-26, so this cannot share the machine with other work.

4. Full QA runbook on an installed wheel from the release commit, plus the human-only matrix (the two open P1 children of mb-425f): Chrome, Safari and Firefox; a readable and an unreadable private repository; an external Plugin SDK 0.7 plugin; and real-browser bfcache acceptance, which is the only part of mb-tdmd still open.

5. Documents up to date (mb-bdwl) and the owner's sign-off on the behavior-change record, which must first gain the #268 storage split.

6. Then the standard checklist in docs/publishing.md, steps 6 to 10: `gh release create v0.12.0`, watch publish.yml, verify PyPI metadata, uvx smoke, and the public Agent Skill check.

WHAT IS VERIFIED ADDITIVE (hand-checked on main, 2026-10-26)

The GitHub features are inert without GitHub, and degrade rather than fail without credentials. On a plain folder /api/plugin/github/pull answers state absent with reason no_pull_request at 200, and pull-markdown answers 409 no_pull_request. With NEITHER git NOR gh on PATH and an empty environment, --show and --api /api/tree on a plain folder both work and exit 0, and isolated --cache-dir and --config-dir are left uncreated, so a plain folder leaves no footprint. --doctor reports 11 plugins OK and exits 0 with no git and no gh. A GitHub URL with no git refuses with a typed message, exit 1, no traceback and no cache created. A pull-request URL with git but no gh clones, pins the default branch, exits 0 and names gh_missing as the reason.

WHAT IS NOT ADDITIVE, and needs the owner's decision

The GitHub work is additive; these are separate and each is intended and documented:

- Plugin SDK 0.6 to 0.7 is a HARD GATE, confirmed by hand: a third-party manifest declaring 0.6 is refused at load and --doctor exits 1 naming the fix; at 0.7 it passes. Any external plugin must be updated. Hand-written data-mb-copy controls and hand-built Load more buttons also go silently inert without the page's owner mark.
- The cache and configuration XDG split: METABROWSER_HOME and the old home layout are no longer read. Existing files are left untouched, so nothing is destroyed, but a user who set METABROWSER_HOME must move to --cache-dir / --config-dir. This landed in #268, AFTER the behavior-change record was written, so it is not yet on the sign-off list.
- --untrusted and --no-active-content now render Markdown inert and apply a Content-Security-Policy on a folder, where v0.11.0 only dropped allow-scripts from the /raw sandbox.
- Smaller CLI changes: `metab ""` is refused; a scheme:// argument is always a source; a failed server start exits 1 where v0.11.0 exited 0; source views gained a line gutter; --doctor is about 250 ms slower, 1.78x by design.

The full list with how each was checked is docs/project/reviews/review-2026-10-01-v012-changes-to-existing-behavior.md.

PRACTICAL CONSTRAINT: on 2026-10-26 the data volume was 94 percent full, 403 GiB used of 460 GiB with 26 GiB free (read /System/Volumes/Data, not /, which is the sealed system volume and reports misleadingly). Worktrees are NOT the cause: 40 of the 49 worktree records are stale pointers to directories that no longer exist, so `git worktree prune` cleans records and reclaims nothing, and every metabrowser checkout together is under 2 GiB. The differentials need rebuilt corpora plus two installed builds, which 26 GiB should carry; the 300,000-file flat-stress pass from exp-036 is what disk blocked before, so check free space before attempting that one specifically.
