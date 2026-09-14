---
type: is
id: is-01m2dtdsckeqv395na6kzbrzd2
title: Quiet-environment perf revalidation of v0.9.2 candidate (walk under attached browser, /api/tree srv time, heap)
kind: task
status: open
priority: 1
version: 4
labels:
  - performance
  - release-hardening
dependencies: []
created_at: 2026-09-13T16:43:21.362Z
updated_at: 2026-09-14T03:20:18.883Z
---
Quiet-machine performance revalidation of the release candidate, required before tagging.

Measure the FINAL release commit (not 863dcd9c): release review after exp-032 changed shipped browser and server sources (catalog removal/compaction, Markdown literal masking and in-document navigation, resync handling, KPress request validation).

Evidence to settle (exp-032 was captured while other agents loaded the machine):
- Walk completion with a headed browser attached: 16.6-18.1 s candidate vs 12.7-13.0 s v0.9.1 in the final series, yet 11.0-12.3 s vs 11.1-11.8 s in the paired series on identical shipped sources; backend-only index_done overlaps. Related standing item: mb-kicj (walk slower than main).
- Repeatable small wrong-way results to confirm or attribute: root /api/tree server time 3->14 ms, transient JS heap 45->56 MB, backend RSS +10 MiB, backend spawn-to-serving 0.679->0.787 s (likely the serve-time KPress prewarm).

Harness fixes to make first (from the release-lane review; harness-only, not shipped):
1. run.py _WALK_LINE requires provider=/contract=; v0.9.1 logs 'inventory walker complete: status=... elapsed=...ms'. Accept the legacy line when the pre-contract declaration is in effect, add walk_elapsed_ms to compare METRICS, and record spawn time plus the spawn-to-profile-start offset.
2. _corpus_fingerprint walks all ~301k entries immediately before the measured walk (host kern.maxvnodes 263,168 < corpus), perturbing the vnode cache. Fingerprint at record time only.
3. Scrub PYTHON* variables from the server environment and verify find_spec('metabrowser').origin is inside the attested install.
4. probe-server samples carry no nonce; include and check it. Take a file lock around the nonce re-check and append.
5. report.md should annotate labels compare would refuse (e.g. -paired control n=6, duplicate nonce 0b0a097f); share one pure identity-check function between compare and report.
6. devtools/compare_builds.py has no wheel attestation; reuse attest_installed_wheel.
7. Add an explicit A/A mode (compare refuses two labels with one build) for the noise floor (see mb-ot8o).
8. External wheel provenance always records dirty=False; record null unless verified.
9. README control-build recipes use uv sync (editable, refused by attestation) and a never-built dist/metabrowser.whl; document installing the exact wheel into one fresh venv and alternating with --no-deps.

Method: >=5 interleaved runs per side, one environment alternating only the wheel, headed Chrome, 300k corpus, quiet machine (no other agents, no stray metab servers).

## Notes

Also run the first-rows release metric from mb-i2im on the repository-shaped project-10 corpus during this rerun: cold backend first_row (compare_builds) and browser first_row_ms for control and candidate, then promote first_row_ms to a hard gate at the measured value. The candidate must include commit 2e9e2066 (gitignore pre-walk removed); before it, first rows on a real repository waited 9-34 s.


Harness fixes 1, 2, 4, 5, and 9 plus the README exact-wheel recipes are on branch claude/perf-harness-evidence (HARNESS_VERSION 22). Items 3 (strip PYTHON* env and verify find_spec origin), 6 (shared pure identity check for compare and report), 7 (wheel attestation in devtools/compare_builds.py), and 8 (A/A mode, mb-ot8o) remain. The quiet-machine rerun itself has not been done.
