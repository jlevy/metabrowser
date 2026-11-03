"""Existing dotenv references keep their ordered meaning within startup budgets."""

from __future__ import annotations

import io
import itertools
import json
import logging
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values
from dotenv.variables import parse_variables

from metabrowser import dotenv as dotenv_module
from metabrowser.dotenv import ALLOWED_KEYS, load_dotenv_chain


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "HELPER=DE\nHELPER=${HELPER}BUG\nMETABROWSER_LOG_LEVEL=${HELPER}\nHELPER=ERROR\n",
            "DEBUG",
        ),
        ("METABROWSER_LOG_LEVEL=${SHELL_LEVEL}\n", "WARNING"),
        ("SHELL_LEVEL=DEBUG\nMETABROWSER_LOG_LEVEL=${SHELL_LEVEL}\n", "DEBUG"),
        ("METABROWSER_LOG_LEVEL=${ABSENT:-WARNING}\n", "WARNING"),
        ("HELPER\nMETABROWSER_LOG_LEVEL=${HELPER:-WARNING}\n", ""),
        ("HELPER=\nMETABROWSER_LOG_LEVEL=${HELPER:-WARNING}\n", ""),
        ("METABROWSER_LOG_LEVEL=${ABSENT}\n", ""),
        ("export HELPER='DEBUG'\nMETABROWSER_LOG_LEVEL='${HELPER}'\n", "DEBUG"),
        ('HELPER="DE"\nMETABROWSER_LOG_LEVEL="${HELPER}BUG" # note\n', "DEBUG"),
        ("METABROWSER_LOG_LEVEL=${ABSENT:-${SHELL_LEVEL}}\n", "${SHELL_LEVEL}"),
        ("METABROWSER_LOG_LEVEL=${broken:${SHELL_LEVEL}}\n", "${broken:WARNING}"),
        ("METABROWSER_LOG_LEVEL=$SHELL_LEVEL\n", "$SHELL_LEVEL"),
    ],
)
def test_expansion_matches_existing_ordered_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str, expected: str
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (*ALLOWED_KEYS, "HELPER", "ABSENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SHELL_LEVEL", "WARNING")
    # This is the parser current main uses, plus an explicit expected value.
    assert dotenv_values(stream=io.StringIO(source))["METABROWSER_LOG_LEVEL"] == expected
    (tmp_path / ".env").write_text(source, encoding="utf-8")
    assert load_dotenv_chain() == [tmp_path / ".env"]
    assert os.environ["METABROWSER_LOG_LEVEL"] == expected
    assert "HELPER" not in os.environ
    assert os.environ["SHELL_LEVEL"] == "WARNING"


def test_expansion_preserves_shell_and_file_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    monkeypatch.delenv("METABROWSER_REQUEST_LOG", raising=False)
    monkeypatch.delenv("MODE", raising=False)
    (tmp_path / ".env").write_text(
        "METABROWSER_LOG_LEVEL=DEBUG\nMODE=verbose\nMETABROWSER_REQUEST_LOG=${MODE}\n"
    )
    (tmp_path / ".env.local").write_text(
        "METABROWSER_LOG_LEVEL=WARNING\nMETABROWSER_REQUEST_LOG=quiet\n"
    )
    load_dotenv_chain()
    assert os.environ["METABROWSER_LOG_LEVEL"] == "ERROR"
    assert os.environ["METABROWSER_REQUEST_LOG"] == "verbose"
    assert "MODE" not in os.environ


def test_expansion_reaches_actual_logging_consumers(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "LEVEL=DEBUG\nMETABROWSER_LOG_LEVEL=${LEVEL}\n"
        "MODE=verbose\nMETABROWSER_REQUEST_LOG=${MODE}\n"
    )
    env = {key: value for key, value in os.environ.items() if key not in ALLOWED_KEYS}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, logging; import metabrowser.server as s; "
            "s._setup_perf_logging(); print(json.dumps([logging.getLogger('metabrowser').level, "
            "s._VERBOSE_REQUEST_LOG]))",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout.splitlines()[-1]) == [logging.DEBUG, True]


def test_variable_grammar_matches_the_existing_parser() -> None:
    environment = {"": "empty", "a": "DEBUG", "b": None, "${a": "nested", "a\n": "line"}
    samples = (
        "".join(parts)
        for length in range(7)
        for parts in itertools.product("${}:-a", repeat=length)
    )
    rng = random.Random(0)
    longer = ("".join(rng.choices("${}:-ab\n雪", k=80)) for _ in range(2000))
    for value in itertools.chain(samples, longer):
        expected = "".join(atom.resolve(environment) for atom in parse_variables(value))
        assert "".join(dotenv_module._expanded_parts(value, environment)) == expected, repr(value)


@pytest.mark.parametrize("limit", ["value", "total"])
def test_expansion_budget_refuses_whole_file_once_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, limit: str
) -> None:
    monkeypatch.setattr(dotenv_module, "_reported", set())
    root = tmp_path / "repo\x1b[2J"
    root.mkdir()
    monkeypatch.chdir(root)
    for key in (*ALLOWED_KEYS, "HELPER"):
        monkeypatch.delenv(key, raising=False)
    source = "METABROWSER_LOG_LEVEL=DEBUG\nHELPER=" + "x" * 1024 + "\n"
    source += "HELPER=${HELPER}${HELPER}\n" * 10
    # Both attacks stay small even under an accidentally unbounded resolver.
    source += "HELPER=${HELPER}${HELPER}\n" if limit == "value" else "HELPER=${HELPER}\n" * 3
    (root / ".env").write_text(source)
    (root / ".env.local").write_text(
        "METABROWSER_LOG_LEVEL=${ABSENT:-WARNING}\nMETABROWSER_REQUEST_LOG=verbose\n"
    )
    monkeypatch.delenv("ABSENT", raising=False)
    with caplog.at_level(logging.WARNING, logger="metabrowser.dotenv"):
        assert load_dotenv_chain() == [root / ".env.local"]
        assert load_dotenv_chain() == [root / ".env.local"]
    assert os.environ["METABROWSER_LOG_LEVEL"] == "WARNING"
    assert os.environ["METABROWSER_REQUEST_LOG"] == "verbose"
    warnings = [
        record.getMessage() for record in caplog.records if "skipped" in record.getMessage()
    ]
    assert len(warnings) == 1
    assert "repo\\x1b[2J/.env: skipped" in warnings[0]
    assert ("1,048,576" if limit == "value" else "4,194,304") in warnings[0]
    assert "characters" in warnings[0]
    assert "xxxxxxxx" not in warnings[0] and "\x1b" not in warnings[0]
    assert "HELPER" not in os.environ
    assert not logging.getLogger("dotenv.main").filters


def test_expansion_character_budgets_accept_the_exact_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    # Referencing one existing string avoids a large on-disk input and verifies that
    # characters, not encoded bytes, govern both the value and aggregate bounds.
    monkeypatch.setenv("EXPANSION_SOURCE", "雪" * dotenv_module.MAX_EXPANDED_VALUE_CHARS)
    source = "".join(f"HELPER_{n}=${{EXPANSION_SOURCE}}\n" for n in range(4))
    (tmp_path / ".env").write_text(source)
    assert load_dotenv_chain() == [tmp_path / ".env"]
    (tmp_path / ".env").write_text(source + "OVER=x\n")
    assert load_dotenv_chain() == []


@pytest.mark.parametrize("shape", ["malformed", "bindings"])
def test_adversarial_expansion_does_not_stall_startup(tmp_path: Path, shape: str) -> None:
    if shape == "malformed":
        source = "HELPER=" + "${" * 30000 + "\n"
    else:
        source = "".join(f"K{n}=x\n" for n in range(7000))
    source += "METABROWSER_LOG_LEVEL=${ABSENT:-DEBUG}\n"
    assert len(source.encode()) < dotenv_module.MAX_DOTENV_BYTES
    (tmp_path / ".env").write_text(source)
    env = {key: value for key, value in os.environ.items() if key not in {*ALLOWED_KEYS, "ABSENT"}}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from metabrowser.dotenv import load_dotenv_chain; "
            "print([p.name for p in load_dotenv_chain()]); print(os.environ['METABROWSER_LOG_LEVEL'])",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    # The former tokenizer took 9.4 seconds on only 32,768 malformed characters.
    # This shape is almost twice as large; allow ample time for the new process to start.
    assert result.stdout.splitlines() == ["['.env']", "DEBUG"]


def test_dotenv_remains_utf8_under_an_ascii_locale(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# 雪\nHELPER=DEBUG\nMETABROWSER_LOG_LEVEL=${HELPER}\n", encoding="utf-8"
    )
    env = {key: value for key, value in os.environ.items() if key not in ALLOWED_KEYS}
    env.update(PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", LC_ALL="C", LANG="C")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, os; "
            "from metabrowser.dotenv import load_dotenv_chain; load_dotenv_chain(); "
            "print(json.dumps(os.environ['METABROWSER_LOG_LEVEL']))",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert json.loads(result.stdout) == "DEBUG"
