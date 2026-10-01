"""Whether a transcript's command line records the exit status of the command under test.

A tryscript block has one command line and one ``? N``, which is the status of whatever
ran last. So the status belongs to ``metab`` or ``node`` only when that invocation is
the last command of the line. Otherwise the line has to print it: ``; echo "exit: $?"``
directly after the invocation. Everything else hides it, and these all hide it the same
way:

    metab root | grep x                 the pipeline's status is grep's
    metab root > out; grep x out        the line's status is grep's
    metab root || echo failed           a failure reads as 0
    { metab root; } | sort              the group is piped
    sh -c 'metab root | grep x'         the same pipeline, one level down
    echo "$(metab root)"                a substitution discards the status
    metab root &                        a background job reports 0

This is a lexer for the part of shell syntax that decides that, not a shell. It knows
quoting, so a ``|`` inside ``--api '/api/a?b=c|d'`` is an argument and not a pipe; the
operators that separate commands; grouping; ``sh -c`` and ``eval``, whose argument is
read as a command line in place; and command substitution. It does not expand
anything, and a construct it does not know (a here-document, a function) is read as
plain words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

# The programs a transcript exists to record.
UNDER_TEST: Final = frozenset({"metab", "node"})

_SHELLS: Final = frozenset({"sh", "bash", "dash", "zsh", "ksh"})
# Words that come before a command and are not it.
_PREFIXES: Final = frozenset(
    {"env", "command", "exec", "time", "nohup", "!", "if", "then", "else", "elif", "do", "while"}
    | {"until"}
)
_ASSIGNMENT: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# Operators after which the line carries on with another command.
_CLOSERS: Final = frozenset({";", "\n", "}", ")"})
_SEQUENCE: Final = frozenset({";", "\n"})


@dataclass(frozen=True, slots=True)
class Token:
    """A simple command, or the operator between two of them."""

    operator: str | None
    words: tuple[str, ...] = ()
    reads_status: bool = False

    @property
    def program(self) -> str | None:
        """The basename of the program a simple command runs."""

        words = list(self.words)
        while words:
            word = words[0]
            if _ASSIGNMENT.match(word) is not None or word in _PREFIXES:
                was_env = word == "env"
                words.pop(0)
                while was_env and words and words[0].startswith("-"):
                    option = words.pop(0)
                    if option in {"-u", "-C", "-S"} and words:
                        words.pop(0)
                continue
            return PurePosixPath(word).name
        return None

    @property
    def under_test(self) -> bool:
        return self.operator is None and self.program in UNDER_TEST


@dataclass(slots=True)
class _Lexer:
    text: str
    position: int = 0

    def _closing(self, start: int, opener: str, closer: str) -> int:
        """The index of the *closer* matching the *opener* at ``start - 1``."""

        depth = 1
        index = start
        while index < len(self.text):
            char = self.text[index]
            if char == "\\":
                index += 2
                continue
            if char == "'":
                end = self.text.find("'", index + 1)
                index = len(self.text) if end < 0 else end + 1
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return len(self.text)

    def tokens(self) -> tuple[list[Token], list[str]]:
        """The simple commands and operators of the text, and its command substitutions."""

        text = self.text
        tokens: list[Token] = []
        substitutions: list[str] = []
        words: list[str] = []
        word: list[str] | None = None
        reads_status = False

        def end_word() -> None:
            nonlocal word
            if word is not None:
                words.append("".join(word))
                word = None

        def end_command() -> None:
            nonlocal reads_status
            end_word()
            # `{` and `}` are words to the lexer and grouping to the shell.
            while words and words[0] in {"{", "}"}:
                tokens.append(Token(words.pop(0)))
            if words:
                tokens.append(Token(None, tuple(words), reads_status))
            words.clear()
            reads_status = False

        def substitution(start: int) -> int:
            """Record the substitution opening at *start*; return the index after it."""

            if text[start] == "`":
                end = text.find("`", start + 1)
                end = len(text) if end < 0 else end
                substitutions.append(text[start + 1 : end])
                return end + 1
            end = self._closing(start + 2, "(", ")")
            substitutions.append(text[start + 2 : end])
            return end + 1

        index = 0
        while index < len(text):
            char = text[index]
            following = text[index + 1] if index + 1 < len(text) else ""
            if char == "\\" and following:
                word = (word or []) + [following]
                index += 2
            elif char == "'":
                end = text.find("'", index + 1)
                end = len(text) if end < 0 else end
                word = (word or []) + [text[index + 1 : end]]
                index = end + 1
            elif char == '"':
                word = word or []
                index += 1
                while index < len(text) and text[index] != '"':
                    inner = text[index]
                    if inner == "\\" and index + 1 < len(text):
                        word.append(text[index + 1])
                        index += 2
                    elif inner == "`" or text.startswith("$(", index):
                        after = substitution(index)
                        word.append(text[index:after])
                        index = after
                    else:
                        reads_status = reads_status or text.startswith("$?", index)
                        word.append(inner)
                        index += 1
                index += 1
            elif char == "`" or (char == "$" and following == "("):
                after = substitution(index)
                word = (word or []) + [text[index:after]]
                index = after
            elif char in " \t":
                end_word()
                index += 1
            elif char == "#" and word is None:
                newline = text.find("\n", index)
                index = len(text) if newline < 0 else newline
            elif char in ";\n()":
                end_command()
                tokens.append(Token(char))
                index += 1
            elif char == "|":
                end_command()
                operator = "||" if following == "|" else "|&" if following == "&" else "|"
                tokens.append(Token(operator))
                index += len(operator)
            elif char == "&" and following == "&":
                end_command()
                tokens.append(Token("&&"))
                index += 2
            elif char == "&" and following != ">" and (index == 0 or text[index - 1] not in "<>"):
                end_command()
                tokens.append(Token("&"))
                index += 1
            else:
                reads_status = reads_status or (char == "$" and following == "?")
                word = (word or []) + [char]
                index += 1
        end_command()
        return tokens, substitutions


def _expand(tokens: list[Token]) -> list[Token]:
    """Read the argument of ``sh -c`` and ``eval`` as the command line it is."""

    expanded: list[Token] = []
    for token in tokens:
        inner: str | None = None
        if token.operator is None and token.program in _SHELLS and "-c" in token.words:
            after = token.words.index("-c") + 1
            inner = token.words[after] if after < len(token.words) else None
        elif token.operator is None and token.program == "eval":
            inner = " ".join(token.words[token.words.index("eval") + 1 :])
        if inner is None:
            expanded.append(token)
            continue
        nested, _substitutions = _Lexer(inner).tokens()
        expanded += [Token("("), *_expand(nested), Token(")")]
    return expanded


def commands(line: str) -> tuple[list[Token], list[str]]:
    """The tokens of *line*, with wrapped command lines read in place, and its substitutions."""

    tokens, substitutions = _Lexer(line).tokens()
    return _expand(tokens), substitutions


def runs_program_under_test(line: str) -> bool:
    """Whether *line* invokes ``metab`` or ``node`` anywhere, substitutions included."""

    tokens, substitutions = commands(line)
    return any(token.under_test for token in tokens) or any(
        runs_program_under_test(inner) for inner in substitutions
    )


def hidden_statuses(line: str) -> list[str]:
    """Why each invocation under test in *line* does not decide the line's exit status."""

    tokens, substitutions = commands(line)
    reasons: list[str] = []
    for index, token in enumerate(tokens):
        if not token.under_test:
            continue
        rest = tokens[index + 1 :]
        if all(later.operator in _CLOSERS for later in rest):
            continue
        skipped = 0
        while skipped < len(rest) and rest[skipped].operator in _CLOSERS:
            skipped += 1
        sequenced = any(later.operator in _SEQUENCE for later in rest[:skipped])
        if sequenced and skipped < len(rest) and rest[skipped].reads_status:
            continue
        following = rest[0].operator
        reasons.append(
            f"`{token.program}` is not the last command"
            if following is None or following in _CLOSERS
            else f"`{token.program}` is followed by `{following}`"
        )
    for inner in substitutions:
        if runs_program_under_test(inner):
            reasons.append("the command under test runs inside a command substitution")
    return reasons
