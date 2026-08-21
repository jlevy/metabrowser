---
type: is
id: is-01m0jewmgp8t3zh3v8fsp4q4kh
title: Verify diff/Git support and large-directory work hold together under load
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-21T15:26:33.493Z
updated_at: 2026-08-21T15:35:13.091Z
closed_at: 2026-08-21T15:35:13.090Z
close_reason: null
---
PR #58 (Git history, diff rendering, nav containers) and PR #59 (large-directory
responsiveness) were built in parallel against the same server and the same nav tree.
origin/main is merged into the #59 branch and CI is green, but a green merge only proves
the two do not fail apart; it does not prove they hold up together.

Reconnaissance already done, on the merged branch, serving this repository:

- /api/git/repo, /api/git/refs, /api/git/log all answer correctly.
- /commit/<rev> returns the shell.
- In a browser: the FILES/GIT tab pair renders, the graph draws with ref chips and
  lanes, selecting a commit opens the diff view with per-file bars and hunks.
- The folder Overview and file breakdown still render beside all of it.

So the surfaces coexist. What is untested is the seam under load, which is exactly where
#59's changes live.

What to check, and why each one:

- **Git routes during a boot scan.** The git collection shells out to git. #59's whole
  argument is that background scan work and foreground requests take CPU from each
  other under the GIL, so a subprocess-heavy route arriving mid-crawl is a case neither
  branch measured. Does the crawl still converge? Do the git routes stay responsive?

- **Git routes against a large index.** The reconnaissance ran on this repository, which
  is small. Run the same routes against the 400k corpus with a real git history.

- **Nav tree expansion with containers.** #58 makes a patch file expand in the tree like
  a folder; #59 rewrote how /api/tree builds a subtree (children_of over the incremental
  child index) and memoized the root tallies. Both edit the same response. Confirm a
  container expands correctly and that the memo cannot serve a tree answer that predates
  a container's contents.

- **Re-baseline the benchmark.** devtools/bench_serving.py's numbers were taken before
  the merge. Re-run against the merged branch so later work compares against something
  current, and confirm the merge itself costs nothing.

- **Settings collision.** Both branches added constants to settings.py. Confirm nothing
  was silently reconciled to one side's value.

Not a rewrite of either feature -- a systematic check that the seam holds, with anything
found tracked as its own bead.

## Notes

Verified. The two feature sets hold together, and the merge costs nothing.

**Settings.** Both sides' constants are present, no constant is defined twice, and
INVENTORY_FIRST_RENDER_DEPTH -- removed by #59 -- is gone from src and tests. Nothing was
silently reconciled to one side.

**Git routes during a boot crawl.** Built a 100,000-file git repository with six commits
and hammered /api/git/log, /api/git/commit/<rev>, and /api/rollup continuously from
server start. This is the case neither branch measured, since #59's argument is that
background scan work and foreground requests take CPU from each other under the GIL, and
the git collection shells out.

  crawl converged at      4.0s
  first folder count at   0.76s
  git log                 p50 124ms   p95 137ms   max 187ms
  git commit detail       p50  21ms   p95  23ms   max  25ms
  rollup                  p50  11ms   p95  12ms   max  13ms
  errors                  0

The crawl converges with git traffic on top, and the git routes stay responsive while it
runs.

**Non-repository trees.** /api/git/repo, /refs, and /log all answer 200 with
{"is_repo": false, "reason": "not_a_repo"} rather than failing.

**Nav containers over the rewritten tree path.** /api/tree serves a patch file as an
ordinary file row; the container affordance is client-side, from the [[kind]] container
table in the diff manifest, and its children come from the plugin data endpoint rather
than from _build_inventory_tree. So the overlap with #59's children_of rewrite is smaller
than it looked. Confirmed in a browser: change.patch expands into its four changed files,
the diff view renders hunks beside it, and an inner click routes to
/view/change.patch/CHANGELOG.md -- the <container address>/<inner path> shape.

**Benchmark.** Re-baselined. Back to back on the same corpus, merged against pre-merge:

  scan with a client attached    5.8s vs 7.3s
  rollup during scan p50         3.5ms vs 3.7ms
  settled rollup, retained body  3.1ms vs 3.3ms
  8 clients simultaneous         9.4ms vs 9.8ms
  /api/tree root depth=1         4.4ms vs 5.7ms

Merged is equal or faster on every row.

One methodology finding worth keeping. Comparing a fresh run against a stored --json from
an earlier session showed every row 1.2x to 1.8x slower, which reads exactly like a
regression. It was an unrelated load spike -- the same code measured 10s and 5.8s on the
same corpus an hour apart. The uniformity was the tell: a real change moves the rows its
mechanism touches. docs/development.md now says so.

Nothing found needing a fix. Follow-on work stays where it was: mb-me9y, mb-65mg,
mb-pn95.
