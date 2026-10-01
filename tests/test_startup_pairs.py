"""The start-up pairs harness measures every build in one bytecode state.

A start that finds no compiled bytecode compiles each module it imports, about three
times the work of a start that loads them compiled. One build with bytecode beside one
without therefore reads as a regression of that size whatever the builds are, so
``startup_pairs.py`` reads each environment's state before it measures, refuses a
series whose builds differ, and records the state.

The environments here are real ones, made with ``venv``, holding a stand-in
``metabrowser`` distribution, one distribution it requires, and one it does not. The
harness reads them through each environment's own interpreter, as it does a build's.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import venv
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "explorations" / "performance-loop" / "startup_pairs.py"

# What the stand-in package and the distribution it requires hold: three sources.
PACKAGE_SOURCES = 3


def _harness() -> Any:
    name = "metabrowser_startup_pairs"
    spec = importlib.util.spec_from_file_location(name, HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pairs = _harness()


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
    metab.write_text("#!/bin/sh\necho 'metab 1.0'\n", encoding="utf-8")
    metab.chmod(0o755)
    return metab


def _compiled(directory: Path) -> Path:
    metab = _build(directory)
    pairs.compile_bytecode(pairs.bytecode_state(metab))
    return metab


def test_an_environment_is_uncached_until_it_is_compiled(tmp_path: Path) -> None:
    metab = _build(tmp_path / "env")

    fresh = pairs.bytecode_state(metab)
    assert (fresh.state, fresh.sources, fresh.compiled) == ("uncached", PACKAGE_SOURCES, 0)

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
    (source,) = (tmp_path / "env" / "lib").glob("python*/site-packages/fake_dep/__init__.py")
    os.utime(source, (1_000_000_000, 1_000_000_000))

    stale = pairs.bytecode_state(metab)

    assert (stale.state, stale.compiled) == ("partial", PACKAGE_SOURCES - 1)


def test_a_source_that_cannot_compile_is_not_counted(tmp_path: Path) -> None:
    """No start imports it and no compile step can give it bytecode."""

    metab = _build(tmp_path / "env", extra={"fake_dep/template.py": "def broken(:\n"})

    assert pairs.bytecode_state(metab).sources == PACKAGE_SOURCES
    assert pairs.settle_bytecode({"control": metab}, compile_missing=True) == "cached"


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
    (source,) = (tmp_path / "env" / "lib").glob("python*/site-packages/metabrowser/cli.py")
    os.utime(source, (1_000_000_000, 1_000_000_000))

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

    state = pairs.settle_bytecode({"control": control, "tip": candidate}, compile_missing=True)

    assert state == "cached"
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

    assert pairs.settle_bytecode(builds, compile_missing=False) == "uncached"
    assert "--compile-bytecode" in capsys.readouterr().out


def test_an_environment_without_installed_sources_is_refused(tmp_path: Path) -> None:
    """An editable install lists no sources, and is not what a user runs."""

    metab = _build(tmp_path / "env")
    (record,) = (tmp_path / "env" / "lib").glob(
        "python*/site-packages/metabrowser-1.0.dist-info/RECORD"
    )
    record.write_text("__editable__.metabrowser-1.0.pth,,\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="editable install"):
        pairs.bytecode_state(metab)


def test_no_measured_process_writes_bytecode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise an uncached series compiles itself as it runs, the control first."""

    monkeypatch.delenv(pairs.DONT_WRITE_BYTECODE, raising=False)

    assert pairs._environment(tmp_path)[pairs.DONT_WRITE_BYTECODE] == "1"


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
    """A second run appended to a file reuses the pair numbers, so every record is read."""

    rows = [
        _record(0, "control", "uncached", 7400e6),
        _record(0, "tip", "uncached", 7690e6),
        _record(0, "control", "cached", 2400e6),
        _record(0, "tip", "cached", 2480e6),
    ]

    with pytest.raises(SystemExit, match=r"more than one bytecode state \(cached, uncached\)"):
        _summarize(tmp_path, rows)
