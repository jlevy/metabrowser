---
type: is
id: is-01m0pnabncfm4ztxc24s6mnxk8
title: GIT_DIR overrides -C, and git exports it to every hook
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:52.363Z
updated_at: 2026-08-23T07:11:39.423Z
---
WHAT HAPPENED, and it is the most serious error in this set. Test fixtures created a throwaway repository with `git -C <tmpdir> init/commit/tag`. Run from a pre-push hook, git had already exported `GIT_DIR` into the environment -- and `GIT_DIR` overrides `-C`. The fixture's commits and its `v1.0.0` tag were written to THIS repository. The next build then read that tag and called itself version 1.0.0.

CONTAINED. Nothing reached the remote. The tag was deleted and the branch reset. But the recovery had its own casualty: the `git reset --hard` discarded an uncommitted fix that had to be redone, which is the ordinary second failure of a hurried cleanup.

THE FIX THAT LANDED. Both `build_version._git` and the test helper strip every `GIT_*` variable before invoking git, and the reason is written at both call sites. Verified afterwards by running the suite with `GIT_DIR` deliberately set and confirming HEAD and the tag list were byte-identical before and after.

WHY IT STAYS OPEN AS A BEAD. The two known call sites are fixed; nothing prevents the third. Any new code that shells out to git in a test, a devtool or a hook inherits the same hazard, and the failure mode is writing to the developer's real repository. Worth a lint check -- `subprocess` invoking `git` without a scrubbed `env` -- since `make verify` can enforce what a paragraph of guidance cannot.

## Notes

FIXED in #73. metabrowser.git.env now owns REPO_PINNING_GIT_VARS and scrubbed_environ(), and devtools/check_git_subprocess.py fails make lint on any subprocess spawning git without an explicit env=.

What the consolidation found, which was more than expected: FIVE call sites had answered this question independently. The server spawner (correct), build_version (correct, but with its own blanket GIT_* prefix strip rather than the list), and three test helpers -- two of which imported the private _REPO_PINNING_GIT_VARS across module boundaries and hand-rolled the same dict comprehension. And devtools/lint.py had not answered it at all: it runs from a pre-commit hook, where GIT_DIR is exported, so `git ls-files` there would enumerate another repository's Markdown and lint that instead. Silently, since a wrong file list still produces a clean-looking run.

The check was verified to catch a reintroduction: a test file containing `subprocess.run(["git", "-C", path, "tag", "v9.9.9"])` -- the exact shape of the original incident -- is reported with file and line.

Exemptions are narrow and stated: `git --version` and `git rev-parse --local-env-vars` resolve no repository, and the second is how a caller discovers what to strip, so it cannot be scrubbed by an answer it does not have yet. A call site may also carry `# git-env-ok: <reason>`, which requires saying why.

Known limitation, recorded in the module docstring: passing `env=os.environ.copy()` satisfies the parser and not the intent. The check makes the decision visible at the call site; it cannot make it correct. And a vector built at runtime is not literal, so it is not classified as git.
