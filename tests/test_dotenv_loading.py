"""``.env`` / ``.env.local`` files are honored by the `metab` CLI bootstrap.

Plugin discovery is operator-opt-in at the trust boundary.
Operators name plugin parents via ``--plugins-dir`` flags or set
``METABROWSER_PLUGINS_DIRS`` in the process environment; a dotenv file
cannot supply it.

These tests exercise the dotenv loader and the CLI's interaction with
it. We use python-dotenv under the hood; the wrapper in
``metabrowser.dotenv`` adds the .env-then-.env.local search order,
``setdefault`` semantics (shell-set values win over file values), and
the allowlist that keeps a browsed repository's file from contributing
anything but the two log names.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import metabrowser
from metabrowser import dotenv as dotenv_module
from metabrowser.dotenv import ALLOWED_KEYS, MAX_DOTENV_BYTES, load_dotenv_chain


def test_load_dotenv_chain_picks_up_env_var(tmp_path: Path, monkeypatch) -> None:
    """An allowlisted key in a `.env` above cwd is loaded into os.environ."""
    (tmp_path / ".env").write_text("METABROWSER_LOG_LEVEL=DEBUG\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)

    applied = load_dotenv_chain()
    assert any(p.name == ".env" for p in applied)
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"


def test_dotenv_local_overlays_dotenv(tmp_path: Path, monkeypatch) -> None:
    """`.env.local` runs after `.env`; both contribute via setdefault, so
    the first non-empty value wins. Local fills gaps left by `.env`."""
    (tmp_path / ".env").write_text("METABROWSER_LOG_LEVEL=DEBUG\n")
    (tmp_path / ".env.local").write_text("METABROWSER_REQUEST_LOG=verbose\n")

    monkeypatch.chdir(tmp_path)
    for k in ("METABROWSER_LOG_LEVEL", "METABROWSER_REQUEST_LOG"):
        monkeypatch.delenv(k, raising=False)

    load_dotenv_chain()
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"
    assert os.environ.get("METABROWSER_REQUEST_LOG") == "verbose"


def test_shell_export_wins_over_dotenv(tmp_path: Path, monkeypatch) -> None:
    """`override=False`: a value already in os.environ beats both .env
    and .env.local."""
    (tmp_path / ".env").write_text("METABROWSER_LOG_LEVEL=DEBUG\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "WARNING")

    load_dotenv_chain()
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "WARNING"


# Names a browsed repository could set to choose which program runs.
# BROWSER is honored by the standard library's browser launcher, which
# `metab` calls by default. GIT_EXTERNAL_DIFF is executed by the
# patch-producing `git diff` the diff views spawn, which carries no
# --no-ext-diff; GIT_TRACE makes git write a file anywhere the value
# names, under every vector this package uses.
EXECUTION_SELECTING_KEYS = (
    "BROWSER",
    "GIT_EXTERNAL_DIFF",
    "GIT_TRACE",
    "GIT_CONFIG_COUNT",
    "GIT_SSH_COMMAND",
    "PATH",
)


def test_dotenv_contributes_nothing_outside_the_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anything not allowlisted comes from the real environment or not at all.

    The chain walks up from the working directory, so browsing a cloned
    repository from inside it reaches that repository's `.env`. A
    denylist would secure only the names somebody thought of, and the
    ones that matter most decide which program runs.
    """
    outside = (*EXECUTION_SELECTING_KEYS, "METAB_UNTRUSTED", "METABROWSER_PLUGINS_DIRS")
    lines = "".join(f"{key}=/tmp/attacker\n" for key in outside)
    (tmp_path / ".env").write_text(f"{lines}METABROWSER_LOG_LEVEL=DEBUG\n")

    monkeypatch.chdir(tmp_path)
    for key in (*outside, "METABROWSER_LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)

    applied = load_dotenv_chain()

    assert any(p.name == ".env" for p in applied)
    assert not [key for key in outside if key in os.environ]
    # The allowlisted key still loads: this is a filter, not a refusal
    # of the file.
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"


def test_a_refused_name_cannot_act_on_the_terminal_it_is_reported_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The names and the directory are the browsed repository's, and a log goes to a terminal.

    Raw, the escape sequences colour or erase the one line that reports the names were
    ignored, a bidirectional override reorders it, and a quoted key's line break prints a
    line of the file's choosing. The warning shows each as a visible escape.
    """

    root = tmp_path / "repo\x1b[2J"
    root.mkdir()
    (root / ".env").write_text(
        "METABROWSER_\x1b[31mRED\x1b[0m=1\n"
        "'METABROWSER_A\nFORGED: a line of its own'=1\n"
        "METABROWSER_B\x08ERASED=1\n"
        "METABROWSER_\u202eBIDI=1\n"
        "METABROWSER_雪=1\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(root)

    with caplog.at_level(logging.WARNING, logger="metabrowser.dotenv"):
        load_dotenv_chain()

    message = next(
        record.getMessage() for record in caplog.records if "ignored" in record.getMessage()
    )
    assert not {"\x1b", "\n", "\x08", "\u202e"} & set(message)
    assert "repo\\x1b[2J/.env: ignored " in message
    assert "METABROWSER_\\x1b[31mRED\\x1b[0m" in message
    assert "METABROWSER_A\\nFORGED: a line of its own" in message
    assert "METABROWSER_B\\x08ERASED" in message
    assert "METABROWSER_\\u202eBIDI" in message
    # A name a terminal only prints is left readable.
    assert "METABROWSER_雪" in message


def test_a_file_that_is_not_text_does_not_stop_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A browsed repository could otherwise keep the browser from opening it at all."""

    root = tmp_path / "repo\x1b[2J"
    root.mkdir()
    env = root / ".env"
    env.write_bytes(b"METABROWSER_LOG_LEVEL=DEBUG\n\xff\xfe\n")
    (root / ".env.local").write_text("METABROWSER_REQUEST_LOG=1\n", encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    monkeypatch.delenv("METABROWSER_REQUEST_LOG", raising=False)

    with caplog.at_level(logging.WARNING, logger="metabrowser.dotenv"):
        parsed = load_dotenv_chain()

    # The other file still loads, and the bad one is not claimed as parsed.
    assert parsed == [root / ".env.local"]
    assert os.environ.get("METABROWSER_REQUEST_LOG") == "1"
    assert "METABROWSER_LOG_LEVEL" not in os.environ
    message = next(
        record.getMessage() for record in caplog.records if "skipped" in record.getMessage()
    )
    assert "\x1b" not in message
    assert "repo\\x1b[2J/.env: skipped" in message
    assert "UnicodeDecodeError" in message


# Prints what the chain parsed and every warning, in a process of its own: a file that
# blocks would otherwise hang the test run, and it is the block being tested.
_LOAD_THE_CHAIN = (
    "import logging, sys\n"
    "from metabrowser.dotenv import load_dotenv_chain\n"
    "logging.basicConfig(stream=sys.stdout, format='warning: %(message)s')\n"
    "print('parsed:', [p.name for p in load_dotenv_chain()])\n"
)


def _load_in_a_process(root: Path, stdin: int | None = subprocess.DEVNULL) -> str:
    """The chain's report from *root*; a chain that blocks raises ``TimeoutExpired``.

    A *stdin* of ``subprocess.PIPE`` is left open and unwritten for as long as it runs.
    """

    with subprocess.Popen(
        [sys.executable, "-c", _LOAD_THE_CHAIN],
        cwd=root,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as process:
        try:
            assert process.stdout is not None
            # A generous limit on a loaded machine: the import is what takes the time.
            process.wait(timeout=30)
            return process.stdout.read()
        finally:
            process.kill()


def _a_fifo(root: Path) -> None:
    os.mkfifo(root / ".env")


def _a_link_to_a_fifo(root: Path) -> None:
    os.mkfifo(root / "elsewhere")
    (root / ".env").symlink_to(root / "elsewhere")


@pytest.mark.parametrize("make", [_a_fifo, _a_link_to_a_fifo])
def test_a_fifo_does_not_block_the_command(tmp_path: Path, make) -> None:
    """A clone can carry a link, and opening a FIFO waits for a writer that never comes."""

    make(tmp_path)
    (tmp_path / ".env.local").write_text("METABROWSER_REQUEST_LOG=1\n", encoding="utf-8")

    report = _load_in_a_process(tmp_path)

    assert "/.env: skipped, because it is not a regular file." in report
    assert "parsed: ['.env.local']" in report


def test_a_link_to_a_pipe_on_stdin_does_not_block_the_command(tmp_path: Path) -> None:
    """The link a clone can carry and a harness can complete, by piping `metab` its stdin."""

    (tmp_path / ".env").symlink_to("/dev/stdin")

    report = _load_in_a_process(tmp_path, stdin=subprocess.PIPE)

    assert "/.env: skipped, because it is not a regular file." in report
    assert "parsed: []" in report


@pytest.mark.parametrize("make", ["directory", "link to a directory", "link to a device"])
def test_what_is_not_a_file_is_passed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, make: str
) -> None:
    """A dotenv file further up still counts, and nothing is said about the one that is not.

    This holds without the regular-file check too: ``find_dotenv`` refuses these itself, so
    the check is the second line for them. It pins the first, which a python-dotenv upgrade
    could move.
    """

    below = tmp_path / "repo"
    below.mkdir()
    (tmp_path / ".env").write_text("METABROWSER_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    (tmp_path / "a-directory").mkdir()
    if make == "directory":
        (below / ".env").mkdir()
    else:
        target = tmp_path / "a-directory" if make == "link to a directory" else "/dev/zero"
        (below / ".env").symlink_to(target)
    monkeypatch.chdir(below)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)

    with caplog.at_level(logging.WARNING, logger="metabrowser.dotenv"):
        parsed = load_dotenv_chain()

    assert parsed == [tmp_path / ".env"]
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"
    assert not caplog.records


def test_a_file_over_the_cap_is_skipped_with_one_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Parsing it could hold the command for minutes, and an honest dotenv file is kilobytes."""

    binding = "METABROWSER_LOG_LEVEL=DEBUG\n"
    (tmp_path / ".env").write_text(binding + "#" * MAX_DOTENV_BYTES, encoding="utf-8")
    (tmp_path / ".env.local").write_text("METABROWSER_REQUEST_LOG=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    monkeypatch.delenv("METABROWSER_REQUEST_LOG", raising=False)

    with caplog.at_level(logging.WARNING, logger="metabrowser.dotenv"):
        parsed = load_dotenv_chain()
        again = load_dotenv_chain()

    assert parsed == again == [tmp_path / ".env.local"]
    assert "METABROWSER_LOG_LEVEL" not in os.environ
    assert os.environ.get("METABROWSER_REQUEST_LOG") == "1"
    skipped = [record.getMessage() for record in caplog.records]
    assert skipped == [f"{tmp_path}/.env: skipped, because it is larger than 64 KB."]


def test_a_file_at_the_cap_is_parsed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = "METABROWSER_LOG_LEVEL=DEBUG\n"
    env = tmp_path / ".env"
    env.write_text(binding + "#" * (MAX_DOTENV_BYTES - len(binding)), encoding="utf-8")
    assert env.stat().st_size == MAX_DOTENV_BYTES
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)

    assert load_dotenv_chain() == [env]
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"


def test_ordered_values_are_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing dotenv files may compose either allowlisted logging setting."""

    (tmp_path / ".env").write_text(
        "LEVEL=DE\nLEVEL=${LEVEL}BUG\nMETABROWSER_LOG_LEVEL=${LEVEL}\n"
        "MODE=verbose\nMETABROWSER_REQUEST_LOG=${MODE}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    for key in (*ALLOWED_KEYS, "LEVEL", "MODE"):
        monkeypatch.delenv(key, raising=False)

    load_dotenv_chain()

    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"
    assert os.environ.get("METABROWSER_REQUEST_LOG") == "verbose"
    assert "LEVEL" not in os.environ and "MODE" not in os.environ


def test_a_file_of_bad_statements_warns_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """python-dotenv warns per statement, which the file could make a screenful of screens."""

    (tmp_path / ".env").write_text("=\n" * 100 + "METABROWSER_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)

    with caplog.at_level(logging.WARNING, logger="dotenv.main"):
        load_dotenv_chain()
        load_dotenv_chain()

    assert len(caplog.records) == 1
    assert "starting at line 1" in caplog.records[0].getMessage()
    # The filter was for that parse, and a good binding in the file still counts.
    assert not logging.getLogger("dotenv.main").filters
    assert os.environ.get("METABROWSER_LOG_LEVEL") == "DEBUG"


def test_the_skip_warning_is_said_once_for_each_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Each of the chain's bootstrap points would otherwise repeat it."""

    first = tmp_path / "first"
    first.mkdir()
    (first / ".env").write_bytes(b"\xff")
    second = tmp_path / "second"
    second.mkdir()
    (second / ".env").write_bytes(b"\xff")
    monkeypatch.setattr(dotenv_module, "_reported", set())

    with caplog.at_level(logging.WARNING, logger="metabrowser.dotenv"):
        monkeypatch.chdir(first)
        load_dotenv_chain()
        load_dotenv_chain()
        monkeypatch.chdir(second)
        load_dotenv_chain()

    assert [record.getMessage().split(":")[0] for record in caplog.records] == [
        str(first / ".env"),
        str(second / ".env"),
    ]


def test_every_allowlisted_key_is_one_the_package_reads() -> None:
    """The allowlist does not drift into names nothing consults.

    A name here is a standing decision that a hostile repository may set
    it, so one that no longer means anything is a decision nobody is
    making on purpose.
    """
    package_dir = Path(metabrowser.__file__).parent
    # The defining module is excluded on purpose. Every allowlisted name
    # appears there as the literal inside ``ALLOWED_KEYS``, so including it
    # would make the corpus match any name at all and this gate could never
    # fail -- which is what it did until a review caught it.
    sources = [p for p in package_dir.rglob("*.py") if p.name != "dotenv.py"]
    assert sources, f"no package sources under {package_dir}"
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    # Match a read, not a mention: a name in a docstring is not a consumer.
    unread = sorted(
        key
        for key in ALLOWED_KEYS
        if not re.search(
            rf"""os\.environ(?:\.get)?\(\s*["']{re.escape(key)}["']"""
            rf"""|os\.environ\[\s*["']{re.escape(key)}["']\]""",
            corpus,
        )
    )
    assert not unread, f"allowlisted but never read: {unread}"


def test_the_drift_gate_can_actually_fail() -> None:
    """The gate above must reject a name nothing reads.

    Without this, the gate is unfalsifiable and silently stops testing
    anything -- the exact failure it was introduced with.
    """
    package_dir = Path(metabrowser.__file__).parent
    sources = [p for p in package_dir.rglob("*.py") if p.name != "dotenv.py"]
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    planted = "METABROWSER_NOBODY_READS_THIS"
    assert not re.search(rf"""os\.environ(?:\.get)?\(\s*["']{re.escape(planted)}["']""", corpus)


def test_dotenv_leaves_a_shell_set_trust_variable_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusing the file's value never disturbs the process environment's."""
    (tmp_path / ".env").write_text("METAB_ALLOW_EDITS=1\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("METAB_ALLOW_EDITS", "0")

    load_dotenv_chain()
    assert os.environ["METAB_ALLOW_EDITS"] == "0"


def test_dotenv_never_drives_plugin_discovery(tmp_path: Path) -> None:
    """End-to-end: a `.env` setting METABROWSER_PLUGINS_DIRS loads nothing.

    Directory plugins are JavaScript that runs in the application page. A
    repository browsed from inside itself reaches its own `.env` through the
    chain, so honoring the name there would make the served root an automatic
    plugin source, which docs/plugins.md names as a security boundary. The
    real environment still works; `--plugins-dir` is untouched.

    Uses subprocess so the python-dotenv side effects don't leak into
    other tests in the suite.
    """
    plugins_parent = tmp_path / "plugins"
    plugins_parent.mkdir()
    plugin = plugins_parent / "envloaded"
    plugin.mkdir()
    (plugin / "manifest.toml").write_text(
        '[plugin]\nname = "envloaded"\nsdk_version = "0.7"\n'
        '[[kind]]\nid = "envk"\nmatch = { ext = ".envk" }\n'
    )
    (plugin / "index.js").write_text("// stub\n")

    cwd = tmp_path / "workdir"
    cwd.mkdir()
    (cwd / ".env").write_text(f"METABROWSER_PLUGINS_DIRS={plugins_parent}\n")

    env = os.environ.copy()
    env.pop("METABROWSER_PLUGINS_DIRS", None)

    code = (
        "import metabrowser.server as s; "
        "import json; print(json.dumps([p.name for p in s._LOADED_PLUGINS]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    last_line = result.stdout.strip().splitlines()[-1]
    names = json.loads(last_line)
    assert "envloaded" not in names, (
        f"a `.env` must not drive plugin discovery; loaded plugins: {names}"
    )

    result_env = subprocess.run(
        [sys.executable, "-c", code],
        env={**env, "METABROWSER_PLUGINS_DIRS": str(plugins_parent)},
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result_env.returncode == 0, (
        f"subprocess failed: stdout={result_env.stdout!r} stderr={result_env.stderr!r}"
    )
    names_env = json.loads(result_env.stdout.strip().splitlines()[-1])
    assert "envloaded" in names_env, (
        f"the real environment should still drive discovery; loaded plugins: {names_env}"
    )


def test_walk_loads_dotenv_before_configuring_logging(tmp_path: Path) -> None:
    """The non-server walk command honors the same dotenv chain as other commands."""
    root = tmp_path / "runs"
    root.mkdir()
    cwd = tmp_path / "workdir"
    cwd.mkdir()
    (cwd / ".env").write_text("METABROWSER_LOG_LEVEL=DEBUG\n")

    code = (
        "import logging\n"
        "from pathlib import Path\n"
        "from unittest.mock import patch\n"
        "from metabrowser.cli.walk_cli import run_walk\n"
        f"root = Path({str(root)!r})\n"
        "levels = []\n"
        "with patch('metabrowser.cli.walk_cli._run_walk', "
        "side_effect=lambda *args: levels.append(logging.getLogger('metabrowser').level)):\n"
        "    run_walk(root, fmt='text', stream=False, subpath='', detail='summary', "
        "log_level='', max_depth=20, max_files=100)\n"
        "print(levels[0])\n"
    )
    env = os.environ.copy()
    env.pop("METABROWSER_LOG_LEVEL", None)
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip().splitlines()[-1] == str(logging.DEBUG)
