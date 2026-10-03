"""``devtools/shell_status.py`` says when a command line hides the status under test."""

from __future__ import annotations

import pytest

from devtools import shell_status


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("metab root | grep x", "`metab` is followed by `|`"),
        ("metab root 2>&1 | head -3", "`metab` is followed by `|`"),
        ("metab root |& tee log", "`metab` is followed by `|&`"),
        ("HOME=$PWD/home metab root | grep -c x", "`metab` is followed by `|`"),
        ("metab root > out.txt; grep x out.txt | sort", "`metab` is not the last command"),
        ("metab root || echo failed", "`metab` is followed by `||`"),
        ("metab a && metab b", "`metab` is followed by `&&`"),
        ("metab root &", "`metab` is followed by `&`"),
        ("{ metab root; } | sort", "`metab` is not the last command"),
        ("( metab root ) | sort", "`metab` is not the last command"),
        ("sh -c 'metab root | grep x'", "`metab` is followed by `|`"),
        ('bash -c "metab root; true"', "`metab` is not the last command"),
        ("eval 'metab root | cat'", "`metab` is followed by `|`"),
        ("./node_modules/.bin/metab root | cat", "`metab` is followed by `|`"),
        ("/usr/local/bin/node session.js | sort", "`node` is followed by `|`"),
        ("env -u HOME metab root | cat", "`metab` is followed by `|`"),
        ("time metab root | tail -1", "`metab` is followed by `|`"),
        ("if metab root; then echo ok; fi", "`metab` is not the last command"),
        ("metab root; echo done", "`metab` is not the last command"),
        # Single quotes do not expand, so this prints a dollar sign and a question mark.
        ("metab root; echo '$?'", "`metab` is not the last command"),
        ('echo "$(metab root)"', "the command under test runs inside a command substitution"),
        ("echo `metab root`", "the command under test runs inside a command substitution"),
        ("x=$(node session.js)", "the command under test runs inside a command substitution"),
    ],
)
def test_a_hidden_status_is_named(line: str, reason: str) -> None:
    assert shell_status.hidden_statuses(line) == [reason]


@pytest.mark.parametrize(
    "line",
    [
        "metab root",
        "metab root > out.txt",
        "metab root 2>&1",
        "metab root > out.txt 2>&1",
        "METABROWSER_HOME=$PWD/home metab root --api /api/tree",
        "cd repo && metab root",
        "git init -q repo; metab repo",
        "sh -c 'metab root'",
        "( metab root )",
        # A pipe, an ampersand, and a semicolon inside an argument are the argument.
        "metab root --api '/api/a?b=c|d'",
        'metab root --api "/api/a?b=c|d&e=f;g"',
        "metab root --api /api/a\\|b",
        # The status is printed, directly after the command it belongs to.
        'metab root > out.txt; echo "exit: $?"',
        'metab > a.txt; echo "a: $?"; metab --help > b.txt; echo "b: $?"; diff a.txt b.txt',
        '( metab root ); echo "exit: $?"',
        "node session.js > out.json; echo $?",
        # Filters over a saved file hide nothing: no command under test is in the line.
        "grep -E 'status' out.txt | sort -u",
        "test -e home || echo 'no application home'",
        'printf "%s" "$(cat out.txt)" | wc -c',
    ],
)
def test_a_line_that_records_the_status_is_clean(line: str) -> None:
    assert shell_status.hidden_statuses(line) == []


def test_each_hidden_invocation_is_reported() -> None:
    assert shell_status.hidden_statuses("metab a | cat; metab b | cat") == [
        "`metab` is followed by `|`",
        "`metab` is followed by `|`",
    ]


@pytest.mark.parametrize(
    ("line", "runs"),
    [
        ("metab root", True),
        ("FOO=1 ./bin/metab root", True),
        ('echo "$(node x.js)"', True),
        ("sh -c 'cd x && metab root'", True),
        ("grep metab notes.txt", False),
        ("echo 'metab root | less'", False),
        ("metabrowser root", False),
    ],
)
def test_finding_the_program_under_test(line: str, runs: bool) -> None:
    assert shell_status.runs_program_under_test(line) is runs
