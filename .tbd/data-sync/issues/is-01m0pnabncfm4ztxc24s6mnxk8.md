---
type: is
id: is-01m0pnabncfm4ztxc24s6mnxk8
title: "GIT_DIR-from-hooks: asserted, never measured, and false here"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:52.363Z
updated_at: 2026-08-23T07:52:15.911Z
---
REOPENED, then closed as NOT REPRODUCIBLE. The mechanism this bead asserted does not exist in this environment, and the fix built on it has been reverted in #73.

MEASURED, which is what should have happened first. A probe hook that dumps its environment and then runs plain git from an unrelated directory:

    pre-commit    GIT_AUTHOR_DATE, GIT_AUTHOR_EMAIL, GIT_AUTHOR_NAME,
    pre-push      GIT_EDITOR, GIT_EXEC_PATH, GIT_INDEX_FILE, GIT_PREFIX
    post-commit   -- and NO GIT_DIR, NO GIT_WORK_TREE
    lefthook cmd  identical set

    `git rev-parse --show-toplevel` from /private/tmp inside the hook:
        "fatal: not a git repository"

Nothing is pinned. A subprocess started from a hook resolves git from its own cwd, which is the behaviour the code wanted all along. pre-push -- where this repository runs its test suite -- carries only GIT_EDITOR, GIT_EXEC_PATH and GIT_PREFIX, none of which redirect anything.

WHY THE BELIEF EXISTED. The comment in metabrowser.git.process asserts the same mechanism and predates this work. Older git versions DID export GIT_DIR to hooks; current git does not. So that comment is stale rationale attached to a harmless guard, not a wrong guard. It is left alone.

MY ERROR was to inherit that rationale, treat it as established, and build a shared module plus a make lint gate on top of it without ever running a hook to check. A one-minute probe would have settled it before any code was written.

WHAT REMAINS TRUE. A v1.0.0 tag and a stray commit really did appear on a real branch, and core.bare really was set. The CAUSE is not established and this bead should not pretend otherwise. Current state audited and clean:

    tags        no v1.x local or remote; highest is v0.6.0 at 440a2fe
    fsck        210 dangling objects, 0 errors
    core.bare   false in the shared config and in all 12 worktrees
    worktrees   all 12 resolve, HEAD sane, tree clean

If it recurs, capture the environment and the cwd AT THE MOMENT of the stray write rather than reasoning backwards from the damage -- that is what would actually identify it.

## Notes

FIXED in #73. metabrowser.git.env now owns REPO_PINNING_GIT_VARS and scrubbed_environ(), and devtools/check_git_subprocess.py fails make lint on any subprocess spawning git without an explicit env=.

What the consolidation found, which was more than expected: FIVE call sites had answered this question independently. The server spawner (correct), build_version (correct, but with its own blanket GIT_* prefix strip rather than the list), and three test helpers -- two of which imported the private _REPO_PINNING_GIT_VARS across module boundaries and hand-rolled the same dict comprehension. And devtools/lint.py had not answered it at all: it runs from a pre-commit hook, where GIT_DIR is exported, so `git ls-files` there would enumerate another repository's Markdown and lint that instead. Silently, since a wrong file list still produces a clean-looking run.

The check was verified to catch a reintroduction: a test file containing `subprocess.run(["git", "-C", path, "tag", "v9.9.9"])` -- the exact shape of the original incident -- is reported with file and line.

Exemptions are narrow and stated: `git --version` and `git rev-parse --local-env-vars` resolve no repository, and the second is how a caller discovers what to strip, so it cannot be scrubbed by an answer it does not have yet. A call site may also carry `# git-env-ok: <reason>`, which requires saying why.

Known limitation, recorded in the module docstring: passing `env=os.environ.copy()` satisfies the parser and not the intent. The check makes the decision visible at the call site; it cannot make it correct. And a vector built at runtime is not literal, so it is not classified as git.
