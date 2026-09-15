---
type: is
id: is-01m2dtdsckeqv395na6kzbrzd2
title: Quiet-environment perf revalidation of the v0.10.0 candidate (walk under attached browser, /api/tree srv time, heap, first rows)
kind: task
status: open
priority: 1
version: 11
labels:
  - performance
  - release-hardening
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-09-13T16:43:21.362Z
updated_at: 2026-09-15T00:53:34.130Z
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

exp-034 is done and the candidate is REJECTED on the 300k corpus; project-10 passes.

Quiet host (4 vCPU Intel Xeon 2.80GHz, Linux 6.18.44, load average below 1.1 throughout), five interleaved pairs per corpus for both halves, one environment alternating only the wheel, headed Chromium 141 under Xvfb at 1600x1040, CPython 3.13.12 standard build.

run.py compare verdicts: project-10 PASS (every hard responsiveness budget passed), 300k FAIL (first_row_ms 392, 359 and 364 ms against the 350 ms gate).

project-10 (118,860 walker-visible files): first rows 1,238 -> 230 ms, walk 39,203 -> 15,507 ms, backend index_done 39.2 -> 9.3 s, FCP 1,140 -> 188 ms, LCP 1,516 -> 244 ms, RSS 1.00x. Regressions there: tree_fetch_srv_ms 1 -> 39 ms (mb-3s45), transient js_heap_mb 8 -> 24 MB with equal post-GC heap (mb-kccm).

300k: walk 18,715 -> 31,295 ms (mb-kicj), first rows 293 -> 359 ms crossing the gate, tree_fetch_srv_ms 6 -> 22 ms, LCP 180 -> 416 ms, long tasks 0 -> 98 ms, backend index_done 15.35 -> 19.18 s.

Correctness is clean on both corpora: compare_builds valid on both, zero ordered-row and zero tally differences, every catalog complete, no refused record, one tree-region repaint per run.

Evidence: explorations/performance-loop/experiments/exp-034-*.md, results/runs.jsonl labels exp-034-p10-* and exp-034-300k-*, machine-local reports under .bench/release-comparisons/v0.9.1-to-v0.10.0/.
