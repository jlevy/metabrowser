---
type: is
id: is-01m0pnabncfm4ztxc24s6mnxk8
title: GIT_DIR overrides -C, and git exports it to every hook
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:52.363Z
updated_at: 2026-08-23T06:35:52.363Z
---
WHAT HAPPENED, and it is the most serious error in this set. Test fixtures created a throwaway repository with `git -C <tmpdir> init/commit/tag`. Run from a pre-push hook, git had already exported `GIT_DIR` into the environment -- and `GIT_DIR` overrides `-C`. The fixture's commits and its `v1.0.0` tag were written to THIS repository. The next build then read that tag and called itself version 1.0.0.

CONTAINED. Nothing reached the remote. The tag was deleted and the branch reset. But the recovery had its own casualty: the `git reset --hard` discarded an uncommitted fix that had to be redone, which is the ordinary second failure of a hurried cleanup.

THE FIX THAT LANDED. Both `build_version._git` and the test helper strip every `GIT_*` variable before invoking git, and the reason is written at both call sites. Verified afterwards by running the suite with `GIT_DIR` deliberately set and confirming HEAD and the tag list were byte-identical before and after.

WHY IT STAYS OPEN AS A BEAD. The two known call sites are fixed; nothing prevents the third. Any new code that shells out to git in a test, a devtool or a hook inherits the same hazard, and the failure mode is writing to the developer's real repository. Worth a lint check -- `subprocess` invoking `git` without a scrubbed `env` -- since `make verify` can enforce what a paragraph of guidance cannot.
