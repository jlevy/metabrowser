"""What a pytest session leaves in the system temporary directory, what this suite removes
of it, and the stale sessions the next one prunes.

pytest gives each session a numbered directory, ``pytest-<N>``, under ``pytest-of-<user>``
in the system temporary directory (``PYTEST_DEBUG_TEMPROOT`` moves it), and each test a
directory in that; under pytest-xdist each worker's tests are in ``popen-gw<N>`` there.
pytest keeps them all (``tmp_path_retention_policy = "all"`` in ``pyproject.toml``), and
``tests/conftest.py`` removes what no one reads:

- A test's ``tmp_path`` is emptied after its teardown report, unless the test failed or
  errored in its setup, its call, or its teardown (``empty``). The directory itself is
  kept, so that no later test is handed its path.
- A passing session's whole directory is removed as the session ends, unless
  ``--basetemp`` named it (``end_session``).

So what stays is the ``tmp_path`` of a test that failed or errored, beside the directories
the session's own fixtures made (the largest measured, ``drawn-from-disk``, 2.9 MiB), until
pytest prunes the session among those older than the newest ``tmp_path_retention_count``
(pytest's default, which this suite keeps). The directory is shared by every project the
user tests, so the newest are any project's. pytest's own ``"failed"`` policy is not used
because it removes a test's directory in the fixture's teardown, by the call's outcome
alone: a test whose setup errored after its ``tmp_path`` was made, or whose teardown
failed after its call passed, would lose the directory that shows why.

On 2026-11-24 it filled the disk with 7.2 GiB. Of the 4.4 GiB measured there later that
day, 3.5 GiB was this suite's, and one full run under pytest-xdist had left 1.8 GiB in
136,922 files. Half of that was four tests that each push and fetch one large object, of
64 MiB in ``tests/test_refresh_signals.py`` (256 MiB each, three of them) and 48 MiB in
``tests/test_cache_update.py`` (192 MiB), and the rest the other 9,389 tests'
directories, about 100 KiB and 14 files each, which no later run reads. Those two
modules, with ``tests/test_check_app_contract.py`` and
``tests/test_api_logical_fields.py``, run passing under two workers, left 1.0 GiB in
14,643 files before this cleanup and nothing after.

pytest prunes an older session's directory only when it can take that directory's
``.lock``, which the session writes with its process id and removes as it ends. A session
that never ends there, killed by a signal, by an agent's command bound, or by
pytest-timeout's thread method (which calls ``os._exit``), leaves its lock behind, and
pytest then keeps the directory until the lock is older than its ``LOCK_TIMEOUT``
(``_pytest/pathlib.py``), days later. On 2026-11-24, 57 session directories there held a
lock: 54 of a process that had gone, the oldest two days old, and three of a running
session. ``release_dead_locks`` removes those locks just before pytest prunes
(``pytest_sessionfinish`` in ``tests/conftest.py``), so pytest's own rule, the newest
sessions kept and the rest removed, applies to a killed session too.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
from pathlib import Path

# pytest's own names: ``make_numbered_dir_with_cleanup(prefix="pytest-")`` for a
# session, ``garbage-<uuid>`` for one whose removal began, and ``get_lock_path``.
_SESSION = re.compile(r"pytest-\d+")
_GARBAGE = "garbage-"
LOCK_NAME = ".lock"


def empty(path: Path) -> None:
    """Remove what a test left in its ``tmp_path``, *path*, and keep the directory.

    pytest numbers a test's directory one past the highest of its name that exists
    (``_mk_tmp`` in ``_pytest/tmpdir.py`` keeps the first 30 characters of the test's
    name). Were the directory removed, the next test whose name starts the same, as a
    parametrized test's next case does, would be handed the same path, and a process-wide
    cache keyed by path would carry the last test's state into it:
    ``metabrowser.git.tree_source``'s reader pools handed
    ``test_displayed_missing_blob_repairs_after_record_and_head_advance[True]`` a reader on
    the event loop of its ``[False]`` case, in every unit job of the CI run of a version of
    this cleanup that removed the directory. Like pytest's own removal, this is best
    effort: what cannot be removed stays.
    """

    shutil.rmtree(path, ignore_errors=True)
    with contextlib.suppress(OSError):
        path.mkdir(mode=0o700, exist_ok=True)


def end_session(basetemp: Path, *, passed: bool) -> None:
    """Release the locks of the sessions under *basetemp*'s root whose process has gone,
    and remove *basetemp*, this session's directory, when the session passed.

    Called before pytest's own ``pytest_sessionfinish``, which then prunes the sessions
    older than the newest it keeps, as their locks now let it.
    """

    release_dead_locks(basetemp.parent)
    if passed:
        shutil.rmtree(basetemp, ignore_errors=True)


def release_dead_locks(root: Path) -> list[Path]:
    """Remove the lock of each session directory under *root* whose process has exited.

    *root* is ``pytest-of-<user>``. A lock that cannot be read, or holds no process id
    yet (pytest writes it just after creating it), or a number no process can have, is
    left, as is one whose process is alive or belongs to another user. The look is one
    directory listing and one small read per session kept, and the removal itself is
    pytest's. It raises nothing: it runs as the session ends, where an exception would
    replace the run's report. Returns the directories released.
    """

    if os.name != "posix":
        # Signal 0 tests for a process on POSIX; on Windows os.kill ends it.
        return []
    released: list[Path] = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return released
    for entry in entries:
        if not (_SESSION.fullmatch(entry.name) or entry.name.startswith(_GARBAGE)):
            continue
        if entry.is_symlink():
            continue
        lock = entry / LOCK_NAME
        try:
            owner = int(lock.read_text(encoding="ascii"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if owner <= 0 or _running(owner):
            continue
        try:
            lock.unlink()
        except OSError:
            continue
        released.append(entry)
    return released


def _running(pid: int) -> bool:
    """Whether *pid* may be a running session's: false only when no process has it."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Another user's process holds the number: not this user's session, but alive.
        return True
    except (OverflowError, ValueError):
        # Too large for a process id, so no session wrote it: not pytest's lock to judge.
        return True
    return True
