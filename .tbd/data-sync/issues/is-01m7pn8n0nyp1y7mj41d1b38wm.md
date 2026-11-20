---
type: is
id: is-01m7pn8n0nyp1y7mj41d1b38wm
title: "Open modes: shared local-open resolver (walk-up, --exact-root, root in Serving line)"
kind: task
status: open
priority: 2
version: 5
labels: []
dependencies: []
parent_id: is-01m7wyrvxk2xx44pqtqmy5cq5g
created_at: 2026-11-18T06:24:49.172Z
updated_at: 2026-11-20T17:08:41.259Z
---
Implement the one resolver arch-open-modes.md (#558) specifies: walk up to the nearest repository root with the owner's Q2(b) guards (not for an ignored path, not up to the home folder, not beyond loopback, serving only), --exact-root opt-out, the resolved root printed in the Serving line. #540's _resolve_local becomes this resolver; #539 and #546 route through it. Goldens and parity rows.

## Notes

2026-11-18, from PR #558 (docs only; review A, A17 and A18). What this change must also do in the documents, since #558 kept every sentence that is true on main and only pointed at the design:

Requirements added to arch-open-modes.md by review A, which the resolver implements:
- A root is taken only when <root>/.git, followed if it is a file, is what `git rev-parse --absolute-git-dir` answers (refuses a planted core.worktree; keeps a subfolder, a nested repository, a linked worktree, a submodule).
- The resolver's Git policy: `-c core.fsmonitor=false` and optional locks off. Plain `git check-ignore -q` ran a configured core.fsmonitor program and, with core.fsmonitor=true, started fsmonitor--daemon and wrote under .git (Git 2.50.1).
- The ignored-path guard tests the path the reader named (a file's own path), and any answer but exit 1 opens the path named (0 ignored, 128 failure).
- Fixture cases (with mb-ajxe): each guard, each Edge Cases row, the planted core.worktree, an ignored file in a tracked folder, and a hostile core.fsmonitor that would leave a marker, with an unchanged Git directory asserted across resolution.
- Measure the cost on metab's open path and on the app's file-open path (every file opened asks for its repository's root, a file an open window already holds included).
- Hand check 10 in docs/project/qa/qa-macos-app-hand-checks.md (a root above the folder picked, in Documents, Desktop, Downloads) becomes runnable with this change.

Guide wording to change with the code (replacement text is the design review's, in #558's vocabulary):
- docs/command-line.md, What ROOT Names: "A path inside a Git repository opens that repository's root, at the folder or file named. Any other folder opens as itself, and a file opens its folder. `--exact-root` serves the folder named and nothing above it. The data modes always read `ROOT` exactly." Remove the "planned in Open Modes" paragraph #558 added there.
- docs/command-line.md, the Serving line: "prints `Serving <root> at <address>`, where the root can be above the path you named".
- docs/browsing-files.md, first paragraph, and skills/metabrowser/SKILL.md, the --path bullet: "`metab PATH` opens the repository that holds PATH, at PATH, or the folder itself when it is in no repository; a file outside a repository opens its folder with the file selected."
- docs/browsing-history.md, The Commits Tab: "A folder inside a repository opens its repository, so it has the tab; only a folder served with `--exact-root` does not." Remove the first half of the "Branches of a local repository" line in What It Does Not Do Yet.
- docs/reviewing-pull-requests.md, the open list: "any path inside one"; "opens its repository in folder mode: the working tree as it is on disk, local changes included".
- docs/macos-app.md, Opening Folders and Files (with #546 and mb-m4mg): the owner's menu, Open Folder…, Open URL…, Open Recent; "A folder or file inside a repository opens the repository at that folder or file; outside one, a folder opens as itself and a file opens its folder." Remove the Known Limitations line #558 added.
- "Designed, not built" pointers to turn into present tense: arch-git.md (the exact-root gate paragraph), arch-mirror-acquisition-and-refresh.md (Transports and Credentials, first sentence), arch-macos-app.md (Open, Files, Planned), and in arch-open-modes.md the "Not built" note under Resolving a Target to a Root and this bead's row in Implementation Status.
- Code docstrings: root_identity.py (module), cli/main.py (_names_existing_path, the ROOT help), cli/serve.py (run_serve), git/repo.py (module).

2026-11-18, review B on #558 (eaf9a1940) adds to the above: the resolver's Git policy also sets GIT_NO_LAZY_FETCH=1. In a --filter=blob:none --sparse clone, check-ignore -q on a path under a folder outside the sparse checkout fetched that folder's .gitignore blob (packs 2 to 3, Git 2.50.1); with the variable it fetches nothing and exits 1, so an ignore file neither on disk nor in the object store is not consulted and such a path opens the repository's root. The fixture needs a sparse partial-clone case. The first guard also requires a root that can be read.

2026-11-18, from PR #546 (recent targets, mb-40k4), the hook this resolver replaces. #546 does not build the resolver; it records the root metab serves today and routes both callers through one function:
- `resolve_local_open(path) -> LocalOpen(root, place)` in src/metabrowser/cli/common.py. Today: a folder opens as itself and a file opens its folder, links resolved; `place` is the file named, None when the path is the root. `run_serve` (cli/serve.py) serves `opened.root` and turns `place` into its `--path`; `recent_cli.add_recent` and `_folder_spellings` (--recent-forget) ask the same function. Replace this function's body with the resolver (walk-up and the guards) and serving, `--recent-add`, and the recent list follow with no other change.
- `place` becomes the path the reader named under a repository root (a folder or a file); `run_serve` then needs `place` as a folder to be a `--path` too (today only a file reaches it, and the combine-with---path error says "is a file").
- The list records `place` as the entry's optional `target` (recorded_path spelling; must lie inside the root, else it is dropped and the root still recorded), and `root` as the key. The store needs no change for walk-up.
- `--exact-root` is not on `--recent-add` (its mode takes no options); decide whether it should be when the resolver adds the flag.
- Goldens to update with the resolver: tests/golden/cli-recent.tryscript.md (a file's root and target), plus those listed above.
