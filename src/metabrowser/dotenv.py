"""``.env`` / ``.env.local`` loader for the `metab` CLI.

Thin wrapper over ``python-dotenv`` that follows a conventional lookup:
walk up from the current working directory looking for both ``.env`` and
``.env.local``, and apply each with ``setdefault`` so a shell-exported
value always wins over a file value.

Trust model: a dotenv file may contribute only the names in
``ALLOWED_KEYS``. The chain walks up from the working directory, so
``cd cloned-repo && metab .`` reaches that repository's own ``.env``, and
the loader cannot tell that file apart from one the operator wrote. An
allowlist is therefore the only shape that holds: a denylist secures the
names somebody thought of, and the environment is full of names that
decide which program runs — ``BROWSER``, which the standard library's
browser launcher honors, the ``GIT_*`` variables that select an external
diff or ssh command, and ``PATH``.

The file is parsed rather than loaded: the parser reads it without
touching ``os.environ``, so a value outside the allowlist is never
written to the process environment even transiently.

The same reach means the file must not be able to stop the command, so
only a regular file under ``MAX_DOTENV_BYTES`` is parsed. Ordered variable
expansion uses layered lookups and explicit output budgets, without copying
the whole environment for each binding or repeatedly scanning malformed references.
"""

from __future__ import annotations

import logging
import os
import re
import stat
from collections import ChainMap
from collections.abc import Iterator, Mapping
from pathlib import Path

from dotenv import find_dotenv
from dotenv.main import DotEnv

from metabrowser.capabilities import CAPABILITY_ENV_VARS

# `metab` already imports this at startup (`cli/serve.py`), and it imports no other Git
# module, so a folder's start pays nothing for it here.
from metabrowser.git.process import loggable

log = logging.getLogger(__name__)

# python-dotenv's own logger, which warns once per statement it cannot parse.
_parser_log = logging.getLogger("dotenv.main")

DOTENV_NAMES: tuple[str, ...] = (".env", ".env.local")
"""Files searched, in load order. ``.env.local`` is conventionally
gitignored for per-developer overrides; loaded after ``.env``, and
``setdefault`` means it only fills gaps ``.env`` left."""

MAX_DOTENV_BYTES = 64 * 1024
"""The largest dotenv file parsed; a larger one is skipped with a warning.

python-dotenv reads the whole file. With its interpolation off, measured 2026-11-02
with python-dotenv 1.2.2 on Python 3.14 (Apple silicon, machine under load, median of 3):
the slowest shape found, a file of ``=`` lines, took 257 ms at 64 KB, and the slow shapes took 3.5 s at 1 MB; plain
``NAME=value`` lines took 38 ms at 64 KB and 2 ms at 4 KB. ``metab . --api`` parses each
of the two files three times, and a pair of the slowest shape at the cap took it from
1.15 s to 2.73 s, against about 25 s at 1 MB by the same arithmetic. An honest dotenv
file is kilobytes, and what this skips is at worst two log settings, which the warning
names the file for."""

MAX_EXPANDED_VALUE_CHARS = 1024 * 1024
MAX_EXPANDED_FILE_CHARS = 4 * MAX_EXPANDED_VALUE_CHARS
"""Bound each expanded value and the sum of values, including overwritten helpers.

The input cap cannot bound repeated doubling through references. Check lengths before
joining, and refuse the whole file before applying settings. These are character limits,
so four-byte Unicode produces at most 16 MiB of text, excluding object overhead.
Measured 2026-11-03 with Python 3.14 / python-dotenv 1.2.2 on Apple silicon (median
of nine local runs): 4,193,280 aggregate characters took 0.330 ms; doubling past the
value cap was refused in 0.265 ms. A 54,930-byte file of 7,000 bindings took 64.8 ms,
versus 602.9 ms through stock interpolation (nine alternating pairs).
"""

_VARIABLE_END = re.compile(r"[}:]")


ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # Log verbosity. Read once through ``VALID_LOG_LEVELS``, so an
        # unknown value falls back to INFO rather than raising.
        "METABROWSER_LOG_LEVEL",
        # Verbose request log. Read as an equality test against one
        # literal, so no value can fail to parse.
        "METABROWSER_REQUEST_LOG",
    }
)
"""The only keys a dotenv file may contribute.

Membership has one test, and it is narrower than it looks: the name must
be consumed by a *total* parser, so that no value a hostile repository
writes can change what the program does beyond the knob's own meaning.
Both names here are read that way — one through ``VALID_LOG_LEVELS``,
one as an equality test — so the worst a browsed repository buys by
setting them is a noisier terminal.

The rendering budgets (``METABROWSER_*_MAX_BYTES``, ``STRUCTURED_*``, and
``METABROWSER_SLOW_SERVER_MS``) are deliberately **not** here. Each is
parsed with ``int()`` at import and is the upper bound on a request-path
read, so a file value could crash the process before anything renders or
lift a cap that exists to keep a large document from exhausting memory.
They are operator knobs: export them.

Also outside, for the reason each name carries: what executes
(``BROWSER``, ``GIT_EXTERNAL_DIFF``, ``PATH``), how far content is
trusted (``METAB_UNTRUSTED`` and its siblings), which JavaScript loads
into the application page (``METABROWSER_PLUGINS_DIRS``), which origins
may read responses (``METABROWSER_ALLOWED_HOSTS``), where a remote
session connects (``METABROWSER_GCP_PROJECT``), which routes exist
(``METABROWSER_DEBUG``), which engine walks the tree
(``METABROWSER_INVENTORY_PROVIDER``), and where the toolchain looks for
configuration and credentials (``HOME``).

Adding a name here is a trust decision. Ask what a hostile repository
gains by setting it, and check its parser is total, before adding one."""

# Names whose refusal is worth reporting: a dotenv file carrying one was
# almost certainly written by the operator, so silence would look like a
# bug. An unrelated project's own variables are not reported, because
# every repository has those and the noise would train the warning away.
_REPORTED_PREFIXES: tuple[str, ...] = ("METABROWSER_", "METAB_", "STRUCTURED_")

# The chain is loaded at several bootstrap points in one process -- the CLI
# mode, the server module, one-shot plugin discovery -- and each would
# otherwise repeat the same warning. Report each file once per process, so
# the message stays a signal.
_reported: set[Path] = set()
_parse_warned: set[Path] = set()

# The capability variables decide how far content is trusted, so a file
# the content controls must never supply them. Checked at import rather
# than asserted: ``python -O`` strips ``assert``, and this invariant
# should hold in an optimized process too.
if ALLOWED_KEYS & set(CAPABILITY_ENV_VARS):
    raise RuntimeError("capability variables must never be loadable from a dotenv file")


def _one_line(text: str) -> str:
    """*text* as part of a one-line warning, with nothing in it acting on a terminal.

    The file's names and the directory it is in are the browsed repository's, so they
    could colour or erase the line that reports them. A quoted key may also hold a line
    break, which :func:`~metabrowser.git.process.loggable` keeps and which would start a
    line the file wrote.
    """

    return loggable(text).replace("\n", "\\n")


def _report_skipped(path: Path, reason: str) -> None:
    """Say once per process that *path* was skipped, and why."""

    if path not in _reported:
        _reported.add(path)
        log.warning("%s: skipped, because %s.", _one_line(str(path)), reason)


def _unfit_to_parse(found: str) -> str | None:
    """Why the dotenv file at *found* is not to be parsed, or ``None`` if it can be.

    ``find_dotenv`` admits a FIFO, and through a symlink a pipe on stdin, whose ``open``
    blocks until a writer appears. Following the link is the point: a link to a regular
    file is an ordinary way to share a dotenv file.
    """

    status = os.stat(found)
    if not stat.S_ISREG(status.st_mode):
        return "it is not a regular file"
    if status.st_size > MAX_DOTENV_BYTES:
        return f"it is larger than {MAX_DOTENV_BYTES // 1024} KB"
    return None


class _FirstParseWarning(logging.Filter):
    """Let python-dotenv's first warning about *path* in this process through, and no other.

    It warns per statement, so 64 KB of ``=`` lines would otherwise print 32,768 lines,
    from each of the two files and each time the chain loads, to the reader's terminal.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        first = self._path not in _parse_warned
        _parse_warned.add(self._path)
        return first


class _ExpansionLimit(ValueError):
    """A file exceeds the startup budget before any of its settings are applied."""


def _expanded_parts(value: str, environment: Mapping[str, str | None]) -> Iterator[str]:
    """Match python-dotenv's variable grammar with a forward-only scan.

    Its variable regex retries every nested `${` when a closing brace is absent,
    taking quadratic time. A colon that is not `:-` invalidates every opening before
    it; resume after that colon. Defaults are literal, and expansion is not recursive.
    """
    literal_start = cursor = 0
    while (start := value.find("${", cursor)) != -1:
        boundary = _VARIABLE_END.search(value, start + 2)
        if boundary is None:
            break
        end = boundary.start()
        default = ""
        if value[end] == ":":
            if not value.startswith(":-", end):
                cursor = end + 1
                continue
            close = value.find("}", end + 2)
            if close == -1:
                break
            default = value[end + 2 : close]
        else:
            close = end
        yield value[literal_start:start]
        yield environment.get(value[start + 2 : end], default) or ""
        literal_start = cursor = close + 1
    yield value[literal_start:]


def _expanded_values(found: str) -> dict[str, str | None]:
    """Resolve in file order; duplicates and bare bindings must retain their position."""
    values: dict[str, str | None] = {}
    shell: dict[str, str | None] = dict(os.environ)
    environment: Mapping[str, str | None] = ChainMap(values, shell)
    total_chars = 0
    # DotEnv.parse preserves duplicate bindings and the library's quote/escape/warning
    # behavior. dotenv_values would collapse duplicates before we could expand them.
    for key, value in DotEnv(found, interpolate=False, encoding="utf-8").parse():
        if value is None:
            values[key] = None
            continue
        parts: list[str] = []
        value_chars = 0
        for part in _expanded_parts(value, environment):
            value_chars += len(part)
            total_chars += len(part)
            if value_chars > MAX_EXPANDED_VALUE_CHARS:
                raise _ExpansionLimit(
                    f"an expanded value exceeds {MAX_EXPANDED_VALUE_CHARS:,} characters"
                )
            if total_chars > MAX_EXPANDED_FILE_CHARS:
                raise _ExpansionLimit(
                    f"expanded values exceed {MAX_EXPANDED_FILE_CHARS:,} characters in total"
                )
            parts.append(part)
        values[key] = "".join(parts)
    return values


def load_dotenv_chain() -> list[Path]:
    """Apply the allowlisted names from ``.env`` then ``.env.local``.

    Uses ``python-dotenv``'s ``find_dotenv`` to walk up from cwd to the
    nearest ancestor containing each filename, and its ordered parser to
    parse it without touching ``os.environ``. Allowlisted names are
    applied with ``setdefault``, so a shell-set value beats both files
    and ``.env`` beats ``.env.local``. Every other name is ignored, and
    those carrying one of this package's prefixes are reported at
    WARNING so an operator is not left guessing.

    A file that is not regular, is over ``MAX_DOTENV_BYTES``, cannot be read as text,
    or exceeds the expansion budgets is skipped with a warning. It is the browsed
    repository's to write, and it must not stop the command that browses it.

    Returns the files found and parsed, in load order, for callers that
    want to surface which files were consulted. A file every one of
    whose names was ignored still appears.
    """

    parsed: list[Path] = []
    for name in DOTENV_NAMES:
        found = find_dotenv(filename=name, usecwd=True)
        if not found:
            continue
        path = Path(found)
        first_warning = _FirstParseWarning(path)
        _parser_log.addFilter(first_warning)
        try:
            unfit = _unfit_to_parse(found)
            if unfit is not None:
                _report_skipped(path, unfit)
                continue
            values = _expanded_values(found)
        except _ExpansionLimit as exc:
            _report_skipped(path, str(exc))
            continue
        except (UnicodeDecodeError, OSError) as exc:
            _report_skipped(path, f"it could not be read as text ({type(exc).__name__})")
            continue
        finally:
            _parser_log.removeFilter(first_warning)
        parsed.append(path)
        ignored: list[str] = []
        for key, value in values.items():
            if value is None:
                continue
            if key in ALLOWED_KEYS:
                os.environ.setdefault(key, value)
            elif key.startswith(_REPORTED_PREFIXES):
                ignored.append(key)
        if ignored and path not in _reported:
            _reported.add(path)
            # Names only, never values: a refused name is often a secret's.
            log.warning(
                "%s: ignored %s — a dotenv file may only set %s. "
                "Export the others in the environment instead; see SECURITY.md.",
                _one_line(str(path)),
                _one_line(", ".join(sorted(ignored))),
                ", ".join(sorted(ALLOWED_KEYS)),
            )
    return parsed


__all__ = ["ALLOWED_KEYS", "DOTENV_NAMES", "MAX_DOTENV_BYTES", "load_dotenv_chain"]
