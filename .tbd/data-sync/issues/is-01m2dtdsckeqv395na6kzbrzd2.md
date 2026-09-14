---
type: is
id: is-01m2dtdsckeqv395na6kzbrzd2
title: Quiet-environment perf revalidation of the v0.10.0 candidate (walk under attached browser, /api/tree srv time, heap, first rows)
kind: task
status: in_progress
priority: 1
version: 9
labels:
  - performance
  - release-hardening
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-09-13T16:43:21.362Z
updated_at: 2026-09-14T23:54:11.215Z
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

Rough-cut run done, regression found; the quiet-machine rerun is still pending and must follow the mb-kicj fix.

exp-033 (PR #120, branch claude/release-v0.10.0-perf) compared the exact v0.9.1 wheel with the candidate 88606b56 on project-10 (tree-d44cf95e, 102,390 walker-visible files) and the 300k build_corpus (tree-b4ec96ce). It was a rough cut on a loaded host (1-minute load average 10-54 from unrelated jobs): 3 interleaved headed captures per side per corpus in the order C K K C C K, compare_builds --runs 3 per corpus, and one back-to-back rerun of each single-pair exceedance. The accept rule was a 1.3x ratio on back-to-back pairs; the README now records it as the rough-cut tolerance, with 1.1x (1.05x for fine claims) as the careful tolerance for quiet-machine measurements.

Result: rejected. Correctness passes on both corpora (zero ordered-row and tally differences, no refused records, complete catalogs, no errors). project-10 is much faster (browser first rows 144-269 ms vs 198-1,064 ms, walk about half, backend first row 11-14 ms vs about 1.1 s). On 300k the candidate regresses: walk pair ratios 1.20-1.91, backend index_done 1.13-1.49 (repeats at load 10), a candidate-only tally-overlap progress-latency miss (213-254 ms against the 200 ms compare_builds budget in 3 of 4 runs), and first_row_ms (1.52, rerun 1.94) and transient js_heap_mb (1.33-1.35) excesses. Root /api/tree srv time exceeds on both corpora; on project-10 it is the provider read moving into asyncio.to_thread (reader wait did not grow), on 300k about 20 ms reaches load_tree_ms.

Evidence to settle from the original list, as of exp-033 (loaded, so indicative only): walk with a browser attached is faster than v0.9.1 on project-10 and slower on 300k; /api/tree srv time 1-9 ms -> 12-68 ms; transient JS heap +25-35% with equal post-GC heap; backend RSS +1% (project-10) and +4% (300k); spawn-to-serving within 1.3x after reruns.

Remaining:
1. Fix mb-kicj, then rerun the comparison on the fixed commit with the same v0.9.1 wheel, corpora, and environments (kept in place on the benchmark host; script and pair-ratio tool are machine-local), same pair rule. Prefer a quiet machine; if it is quiet, use at least five interleaved runs per side and the careful 1.1x tolerance, and recalibrate the first_row_ms gate (mb-i2im) from it.
2. Harness items still open from the original list: 3 (strip PYTHON* env and verify find_spec origin), 5 (report.md annotations for labels compare would refuse), 6 (wheel attestation inside devtools/compare_builds.py; exp-033 attested both backend envs with attest_installed_wheel before running it), and 7 (A/A mode, mb-ot8o).

Procedure notes for the rerun: pin the measurement envs to a standard (GIL) CPython with --python, because uv discovery picks the checkout's free-threaded interpreter; create them outside every git work tree; open every series with an unrecorded serve plus run.py fingerprint; compare_builds only runs control-then-candidate within each pair.
