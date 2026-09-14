---
type: is
id: is-01m2ehe8r599htpy8dpf62a54k
title: First directory tree paint waits for a full-repository .gitignore prewalk
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels:
  - performance
  - first-paint
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-09-13T23:25:34.340Z
updated_at: 2026-09-14T01:29:19.320Z
closed_at: 2026-09-14T01:29:19.319Z
close_reason: "Fixed on claude/fast-first-tree-paint (commit 2e9e2066). HierarchicalGitIgnore replaces the whole-repository pre-walk. Validation on /Users/levy/wrk/aisw/trading (146,677 files), built wheel 0.9.2.dev150+2e9e2066 vs installed main 0.9.2.dev149+723f4213, interleaved: first root rows 0.70-1.64 s after launch vs 3.7-6.4 s; real-browser cold load painted the tree 245 ms after navigation with 57 inlined rows vs about 9.5 s with none; full index 25.4-25.6 s vs 39.6-45.7 s with identical file and entry counts; verdicts match git check-ignore except four directories whose own .gitignore is * or /* (unchanged from before). Contract tests fail on the old design."
resolution: null
duplicate_of: null
---
First directory tree paint waits for a full-repository .gitignore prewalk.

Evidence (installed 0.9.2.dev149+723f4213 and v0.9.1, cold start against /Users/levy/wrk/aisw/trading, 146k files, 10,298 tracked):
- HTTP ready in 1.2-3.0 s; first root rows (inlined shell rows and /api/tree) at 9.8-34.3 s, each time 1-2 s after `build_gitignore_check took N s` (8.7-32.2 s depending on load). A root scandir of the same 88 entries takes 0.2-0.6 ms.
- Interleaved runs: new build 14.6 s and 9.8 s; v0.9.1 11.9 s and 16.7 s. Not a regression: the prewalk has gated the walk since v0.1.0 (8f96f22b).
- Profile: load_gitignore os.walks 40,832 directories (38,374 under runs/) and 83,479 file names to find 25 nested .gitignore files, before the indexing walk (which is BFS and would yield root children first) is allowed to start. It always walks from the git root, even when the served root is a small subdirectory.
- The release comparison missed it: exp-032 used the synthetic build_corpus (1,105 dirs, no nested .gitignore), where backend first row was about 0.5 s and browser first row about 100-160 ms.

Design defect: python_inventory._run_walker awaits build_gitignore_check_for(root), which calls load_gitignore, a second whole-tree traversal, before walk_tree. Nested patterns are also prefixed as `rel_dir/pattern`, which is not git semantics (a nested `*.log` stops matching deeper files; negations break).

Fix: evaluate .gitignore hierarchically and lazily. Find the git root, load each directory's .gitignore the first time a path inside it is checked, evaluate levels from the git root to the path's parent with last-match semantics, and treat contents of an ignored directory as ignored. The indexing walk then starts immediately and root rows land after one scandir. Validate against `git check-ignore` on real repositories.
