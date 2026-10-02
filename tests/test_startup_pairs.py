"""The start-up pairs harness measures every build in one bytecode state.

A start that finds no compiled bytecode compiles each module it imports, about three
times the work of a start that loads them compiled. One build with bytecode beside one
without therefore reads as a regression of that size whatever the builds are, so
``startup_pairs.py`` reads each environment's state before it measures, refuses a
series whose builds differ, and records the state.

The environments here are real ones, made with ``venv``, holding a stand-in
``metabrowser`` distribution, one distribution it requires, and one it does not. The
harness reads them through each environment's own interpreter, as it does a build's,
and a run starts the stand-in ``metab`` in every mode it measures.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import py_compile
import subprocess
import sys
import venv
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "explorations" / "performance-loop" / "startup_pairs.py"

# What the stand-in package and the distribution it requires hold: three sources.
PACKAGE_SOURCES = 3

# A console script as an installer writes one for a long path: `sh` runs the first lines
# and hands the file to the environment's interpreter, which reads them as a string. It
# imports the package, and through it what the package requires, as every mode of the
# real one does, so a start that may write bytecode leaves some behind. It answers the
# modes the harness measures: one-shot commands, and a server.
_METAB_HEAD = "#!/bin/sh\n'''exec' 'PYTHON' \"$0\" \"$@\"\n' '''\n"
_METAB_BODY = """\
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

import metabrowser.cli

arguments = sys.argv[1:]
if "--version" in arguments:
    print(f"metab 1.{metabrowser.VERSION}")
elif "--port" in arguments:

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"{}" if self.path == "/api/routes" else b"<!doctype html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_arguments):
            pass

    port = int(arguments[arguments.index("--port") + 1])
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def _harness() -> Any:
    name = "metabrowser_startup_pairs"
    spec = importlib.util.spec_from_file_location(name, HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pairs = _harness()


@pytest.fixture(autouse=True)
def _environment_package_only(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """The stand-in ``metab`` imports the package its own environment holds.

    A ``PYTHONPATH`` in the shell that runs the tests would put another ``metabrowser``
    ahead of it, as it would for a real build under the harness.
    """

    monkeypatch.delenv("PYTHONPATH", raising=False)


def _distribution(
    site: Path, name: str, files: dict[str, str], *, requires: tuple[str, ...] = ()
) -> None:
    """An installed distribution: its sources, and the metadata that lists them."""

    for relative, body in files.items():
        target = site / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    # An installer spells the directory with underscores, which is how a name is found.
    info = site / f"{name.replace('-', '_')}-1.0.dist-info"
    info.mkdir()
    metadata = [f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n"]
    metadata += [f"Requires-Dist: {requirement}\n" for requirement in requires]
    (info / "METADATA").write_text("".join(metadata), encoding="utf-8")
    (info / "RECORD").write_text("".join(f"{relative},,\n" for relative in files), encoding="utf-8")


def _build(directory: Path, *, extra: dict[str, str] | None = None) -> Path:
    """An environment with the stand-in package installed; returns its ``metab`` script."""

    venv.EnvBuilder(with_pip=False, symlinks=True).create(directory)
    (site,) = (directory / "lib").glob("python*/site-packages")
    _distribution(
        site,
        "metabrowser",
        {"metabrowser/__init__.py": "VERSION = 1\n", "metabrowser/cli.py": "import fake_dep\n"},
        # A marker, an extra, and a requirement nothing installed: none stops the walk.
        requires=("fake-dep>=1", 'absent-dep; extra == "more"'),
    )
    _distribution(site, "fake-dep", {"fake_dep/__init__.py": "VALUE = 2\n", **(extra or {})})
    # Installed, and nothing the package requires: its bytecode is no part of the state.
    _distribution(site, "unrelated", {"unrelated/__init__.py": "VALUE = 3\n"})
    metab = directory / "bin" / "metab"
    interpreter = str(directory / "bin" / "python")
    metab.write_text(_METAB_HEAD.replace("PYTHON", interpreter) + _METAB_BODY, encoding="utf-8")
    metab.chmod(0o755)
    return metab


def _compiled(directory: Path) -> Path:
    metab = _build(directory)
    pairs.compile_bytecode(pairs.bytecode_state(metab))
    return metab


def _source(directory: Path, relative: str) -> Path:
    (source,) = (directory / "lib").glob(f"python*/site-packages/{relative}")
    return source


# ── Reading a state ────────────────────────────────────────────────────────────────


def test_an_environment_is_uncached_until_it_is_compiled(tmp_path: Path) -> None:
    metab = _build(tmp_path / "env")

    fresh = pairs.bytecode_state(metab)
    assert (fresh.state, fresh.sources, fresh.compiled) == ("uncached", PACKAGE_SOURCES, 0)
    assert (fresh.python, fresh.python_base) == (sys.version, sys.base_prefix)

    pairs.compile_bytecode(fresh)
    compiled = pairs.bytecode_state(metab)
    assert (compiled.state, compiled.sources, compiled.compiled) == (
        "cached",
        PACKAGE_SOURCES,
        PACKAGE_SOURCES,
    )


def test_bytecode_the_interpreter_would_not_load_does_not_count(tmp_path: Path) -> None:
    """A bytecode file older than its source is recompiled at import, so it is not cached."""

    metab = _compiled(tmp_path / "env")
    source = _source(tmp_path / "env", "fake_dep/__init__.py")
    os.utime(source, (1_000_000_000, 1_000_000_000))

    stale = pairs.bytecode_state(metab)

    assert (stale.state, stale.compiled) == ("partial", PACKAGE_SOURCES - 1)


def test_a_timestamp_file_must_match_the_source_size_as_well_as_its_time(tmp_path: Path) -> None:
    """The import system checks both, so a rewrite within the same second is not cached."""

    metab = _compiled(tmp_path / "env")
    source = _source(tmp_path / "env", "fake_dep/__init__.py")
    stamp = source.stat().st_mtime_ns
    source.write_text("VALUE = 2  # and a comment that makes the file longer\n", encoding="utf-8")
    os.utime(source, ns=(stamp, stamp))

    assert pairs.bytecode_state(metab).compiled == PACKAGE_SOURCES - 1


def test_a_hash_based_file_counts_when_the_interpreter_would_load_it(tmp_path: Path) -> None:
    """Unchecked: always. Checked: while the source's bytes hash to what it records."""

    metab = _build(tmp_path / "env")
    checked = _source(tmp_path / "env", "fake_dep/__init__.py")
    unchecked = _source(tmp_path / "env", "metabrowser/cli.py")
    modes = py_compile.PycInvalidationMode
    py_compile.compile(str(checked), invalidation_mode=modes.CHECKED_HASH, doraise=True)
    py_compile.compile(str(unchecked), invalidation_mode=modes.UNCHECKED_HASH, doraise=True)
    assert pairs.bytecode_state(metab).compiled == 2

    # Both sources change. Only the checked file is tied to its source's bytes.
    checked.write_text("VALUE = 7\n", encoding="utf-8")
    unchecked.write_text("import fake_dep  # changed\n", encoding="utf-8")

    assert pairs.bytecode_state(metab).compiled == 1


def test_a_source_that_cannot_compile_is_not_counted(tmp_path: Path) -> None:
    """No start imports it and no compile step can give it bytecode."""

    metab = _build(tmp_path / "env", extra={"fake_dep/template.py": "def broken(:\n"})

    assert pairs.bytecode_state(metab).sources == PACKAGE_SOURCES
    assert pairs.settle_bytecode({"control": metab}, compile_missing=True)[0] == "cached"


def test_an_environment_without_installed_sources_is_refused(tmp_path: Path) -> None:
    """An editable install lists no sources, and is not what a user runs."""

    metab = _build(tmp_path / "env")
    record = _source(tmp_path / "env", "metabrowser-1.0.dist-info/RECORD")
    record.write_text("__editable__.metabrowser-1.0.pth,,\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="editable install"):
        pairs.bytecode_state(metab)


# ── One state for every build ──────────────────────────────────────────────────────


def test_builds_in_different_states_are_refused_with_the_command_that_fixes_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    control = _compiled(tmp_path / "release")
    candidate = _build(tmp_path / "candidate")

    with pytest.raises(SystemExit) as refusal:
        pairs.settle_bytecode({"control": control, "tip": candidate}, compile_missing=False)

    message = str(refusal.value)
    assert "  control: cached (3 of 3 source files have bytecode)" in message
    assert "  tip: uncached (0 of 3 source files have bytecode)" in message
    (site,) = (tmp_path / "candidate" / "lib").glob("python*/site-packages")
    assert f"  {tmp_path / 'candidate' / 'bin' / 'python'} -m compileall -q {site}" in message
    assert str(tmp_path / "release") not in message.split("run again:")[1]
    assert "--compile-bytecode" in message
    # A refusal changes nothing, and says nothing as if the series had started.
    assert pairs.bytecode_state(candidate).state == "uncached"
    assert capsys.readouterr().out == ""


def test_a_partly_compiled_environment_is_refused_even_when_every_build_is(
    tmp_path: Path,
) -> None:
    """What one earlier run leaves behind depends on which modes it imported."""

    metab = _compiled(tmp_path / "env")
    os.utime(_source(tmp_path / "env", "metabrowser/cli.py"), (1_000_000_000, 1_000_000_000))

    with pytest.raises(SystemExit) as refusal:
        pairs.settle_bytecode({"control": metab, "tip": metab}, compile_missing=False)

    message = str(refusal.value)
    assert message.count("partial (2 of 3 source files have bytecode)") == 2
    assert message.count("-m compileall -q") == 1


def test_compiling_first_puts_every_build_in_the_cached_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    control = _compiled(tmp_path / "release")
    candidate = _build(tmp_path / "candidate")

    state, read = pairs.settle_bytecode(
        {"control": control, "tip": candidate}, compile_missing=True
    )

    assert state == "cached"
    assert {name: found.state for name, found in read.items()} == {
        "control": "cached",
        "tip": "cached",
    }
    assert pairs.bytecode_state(candidate).state == "cached"
    assert capsys.readouterr().out.splitlines() == [
        "tip: compiling 3 source files",
        "control: bytecode cached (3 of 3 source files have bytecode)",
        "tip: bytecode cached (3 of 3 source files have bytecode)",
    ]


def test_builds_that_all_lack_bytecode_are_measured_as_uncached(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    builds = {"control": _build(tmp_path / "release"), "tip": _build(tmp_path / "candidate")}

    assert pairs.settle_bytecode(builds, compile_missing=False)[0] == "uncached"
    assert "--compile-bytecode" in capsys.readouterr().out


def test_builds_on_different_python_versions_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second interpreter is stood in for: what is read of one build names another version."""

    builds = {"control": _compiled(tmp_path / "release"), "tip": _compiled(tmp_path / "candidate")}
    read = pairs.bytecode_state

    def other_python(metab: Path) -> Any:
        state = read(metab)
        return replace(state, python="3.99.0 (other)") if metab == builds["tip"] else state

    monkeypatch.setattr(pairs, "bytecode_state", other_python)

    with pytest.raises(SystemExit) as refusal:
        pairs.settle_bytecode(builds, compile_missing=False)

    message = str(refusal.value)
    assert f"  control: {sys.version}" in message
    assert "  tip: 3.99.0 (other)" in message


# ── A run ──────────────────────────────────────────────────────────────────────────


def _run(tmp_path: Path, builds: dict[str, Path], *, rounds: int = 1) -> list[dict[str, Any]]:
    tree = tmp_path / "tree"
    tree.mkdir(exist_ok=True)
    (tree / "README.md").write_text("# tree\n", encoding="utf-8")
    out = tmp_path / "pairs.jsonl"
    arguments = argparse.Namespace(
        tree=str(tree),
        out=str(out),
        control=str(builds["control"]),
        candidate=[f"{name}={path}" for name, path in builds.items() if name != "control"],
        pairs=rounds,
        compile_bytecode=False,
    )
    assert pairs.cmd_run(arguments) == 0
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


def test_a_run_records_each_build_with_its_state_and_its_interpreter(tmp_path: Path) -> None:
    builds = {"control": _compiled(tmp_path / "release"), "tip": _compiled(tmp_path / "candidate")}

    records = _run(tmp_path, builds, rounds=2)

    assert [(row["pair"], row["candidate"], row["build"]) for row in records] == [
        (0, "tip", "control"),
        (0, "tip", "tip"),
        (1, "tip", "control"),
        (1, "tip", "tip"),
    ]
    for row in records:
        assert row["version"] == "metab 1.1"
        assert row["bytecode"] == "cached"
        assert (row["python"], row["python_base"]) == (sys.version, sys.base_prefix)
        # Each mode was really started, and the server really answered.
        for metric in ("cli_show_ms", "cli_api_tree_ms", "cli_version_ms", "cli_doctor_ms"):
            assert row[metric] > 0, metric
        assert row["serve_first_api_ms"] > 0 and row["shell_ms"] > 0


def test_a_run_writes_no_bytecode_and_lets_no_process_it_starts_write_any(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uncached series stays uncached, though the caller's shell would let Python write.

    Otherwise the first round compiles what it imports and every later one runs cached,
    the control first. Asking a build its version and reading its state are starts too.
    """

    monkeypatch.delenv(pairs.DONT_WRITE_BYTECODE, raising=False)
    builds = {"control": _build(tmp_path / "release"), "tip": _build(tmp_path / "candidate")}
    started: list[tuple[str, dict[str, str] | None]] = []
    real_popen = subprocess.Popen

    # Every process the harness starts is a Popen, those `subprocess.run` starts included.
    def popen(command: list[str], **options: Any) -> Any:
        started.append((" ".join(command), options.get("env")))
        return real_popen(command, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pairs.subprocess, "Popen", popen)
        records = _run(tmp_path, builds)

    assert [row["bytecode"] for row in records] == ["uncached", "uncached"]
    # Each start imported the package and what it requires, and left nothing behind.
    for metab in builds.values():
        state = pairs.bytecode_state(metab)
        assert (state.state, state.compiled) == ("uncached", 0)
    # Per build: its version, its state, four commands and a server.
    assert len(started) == 2 * 7
    for command, environment in started:
        assert environment is not None, command
        assert environment.get(pairs.DONT_WRITE_BYTECODE) == "1", command


def test_a_run_refuses_a_file_that_already_holds_records(tmp_path: Path) -> None:
    """Pair numbers start at zero in every run, so a second run's records share the first's keys."""

    builds = {"control": _compiled(tmp_path / "release"), "tip": _compiled(tmp_path / "candidate")}
    out = tmp_path / "pairs.jsonl"
    earlier = json.dumps(_record(0, "control", "cached", 1.0)) + "\n"
    out.write_text(earlier, encoding="utf-8")

    with pytest.raises(SystemExit, match="already holds records"):
        _run(tmp_path, builds)
    assert out.read_text(encoding="utf-8") == earlier

    # An empty file is one a caller made to claim the name.
    out.write_text("", encoding="utf-8")
    assert len(_run(tmp_path, builds)) == 2


# ── Summarizing ────────────────────────────────────────────────────────────────────


def _record(pair: int, build: str, bytecode: str | None, work: float) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pair": pair,
        "candidate": "tip",
        "build": build,
        "version": f"metab {build}",
        "load1": 1.0,
        "recorded_at": 0.0,
        "cli_show_instr": work,
    }
    if bytecode is not None:
        row["bytecode"] = bytecode
    return row


def _summarize(tmp_path: Path, rows: list[dict[str, Any]]) -> None:
    out = tmp_path / "pairs.jsonl"
    out.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    pairs.cmd_summarize(
        argparse.Namespace(file=str(out), candidate="tip", suffix="_instr", ratios=False)
    )


def test_summarize_names_the_state_the_records_were_taken_in(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _summarize(
        tmp_path, [_record(0, "control", "cached", 2400e6), _record(0, "tip", "cached", 2480e6)]
    )
    header, _columns, metric = capsys.readouterr().out.splitlines()
    assert header.startswith("candidate=tip pairs=1 bytecode=cached load1 ")
    assert metric.split()[:4] == ["cli_show_instr", "2400.0", "2480.0", "1.033"]

    # A file written before the state was recorded says so, and claims neither.
    _summarize(tmp_path, [_record(0, "control", None, 2400e6), _record(0, "tip", None, 2480e6)])
    assert " bytecode=unrecorded " in capsys.readouterr().out.splitlines()[0]


def test_summarize_refuses_records_from_more_than_one_state(tmp_path: Path) -> None:
    """Every record is read, a half-finished last pair included."""

    rows = [
        _record(0, "control", "uncached", 7400e6),
        _record(0, "tip", "uncached", 7690e6),
        _record(1, "control", "cached", 2400e6),
    ]

    with pytest.raises(SystemExit, match=r"more than one bytecode state \(cached, uncached\)"):
        _summarize(tmp_path, rows)


def test_summarize_refuses_a_file_that_holds_more_than_one_run(tmp_path: Path) -> None:
    """A second run written after a first, even one interrupted in its first pair.

    Keeping the last record for each pair and build paired the second run's control
    with the first run's candidate and summarized that with exit status 0.
    """

    first = [
        _record(0, "control", "cached", 2400e6),
        _record(0, "tip", "cached", 2480e6),
        _record(1, "control", "cached", 2400e6),
        _record(1, "tip", "cached", 2480e6),
    ]
    interrupted = [_record(0, "control", "cached", 9999e6)]

    with pytest.raises(SystemExit, match="more than one record for pair 0 of 'control'"):
        _summarize(tmp_path, [*first, *interrupted])


def test_summarize_refuses_a_build_recorded_under_two_versions(tmp_path: Path) -> None:
    rows = [
        _record(0, "control", "cached", 2400e6),
        _record(0, "tip", "cached", 2480e6),
        _record(1, "control", "cached", 2400e6),
        {**_record(1, "tip", "cached", 2480e6), "version": "metab another"},
    ]

    with pytest.raises(SystemExit, match="tip: metab another, metab tip"):
        _summarize(tmp_path, rows)
