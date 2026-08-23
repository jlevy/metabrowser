"""The environment a ``git`` child process may safely inherit.

Git pins itself to a repository through the environment as well as through
``cwd``, and the environment wins. ``GIT_DIR`` overrides ``-C``; so does
``GIT_WORK_TREE``, ``GIT_INDEX_FILE`` and the rest of the list below. Git also
exports them into every hook it runs, so any process started from a hook
inherits a pin to whatever repository invoked the hook.

That combination has cost this project twice, and the second time is the reason
this module exists rather than a comment:

* A fixture ``git init`` run from a pre-push hook re-initialized the *served*
  repository as bare. That was fixed here, in the one module that spawns git
  for the server.
* Test fixtures for :mod:`metabrowser.build_version` then did the same thing
  from a new module that had never heard of the first fix, and wrote a
  ``v1.0.0`` tag and a stray commit onto a real branch. The next build read the
  tag and called itself version 1.0.0.

The knowledge existed both times. What did not exist was one place to import it
from and a check that fails when a new caller does not. Hence this module and
``devtools/check_git_subprocess.py``.

**Static, not queried.** ``git rev-parse --local-env-vars`` reports the same set
authoritatively, and the devtools that can afford a subprocess use it. This list
is a constant because its callers cannot: :mod:`metabrowser.build_version` runs
before ``--version`` prints and must not spawn an extra process to find out how
to spawn a process, and a scrub that fails open is worse than no scrub.
"""

from __future__ import annotations

import os

REPO_PINNING_GIT_VARS: tuple[str, ...] = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
    "GIT_CEILING_DIRECTORIES",
)
"""Variables that pin git to a repository, index, or object store.

Every one of these takes precedence over ``cwd`` and over ``-C``. Inherited
into a child, they silently redirect the command at another repository.
"""


def scrubbed_environ(base: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of *base* (default ``os.environ``) with the pinning variables gone.

    The result targets whichever repository the command resolves from ``cwd``
    or ``-C``, which is what every caller in this project actually wants.
    """
    env = dict(os.environ if base is None else base)
    for name in REPO_PINNING_GIT_VARS:
        env.pop(name, None)
    return env


__all__ = ["REPO_PINNING_GIT_VARS", "scrubbed_environ"]
