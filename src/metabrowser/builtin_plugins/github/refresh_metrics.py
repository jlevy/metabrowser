"""Measured GitHub CLI answers for the operation that owns the reads."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class RefreshTiming(TypedDict):
    finished_at: str
    duration_ms: int
    provider: NotRequired[Literal["github_cli"]]
    request_count: NotRequired[int]
    response_body_bytes: NotRequired[int]


class GitHubAnswers(BaseModel):
    """HTTP answers delivered by gh, including unchanged answers with no body."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_count: int = Field(gt=0)
    response_body_bytes: int = Field(ge=0)

    def add_to(self, timing: RefreshTiming) -> None:
        timing["provider"] = "github_cli"
        timing["request_count"] = self.request_count
        timing["response_body_bytes"] = self.response_body_bytes


@dataclass
class AnswerCounter:
    request_count: int = 0
    response_body_bytes: int = 0

    def snapshot(self) -> GitHubAnswers | None:
        if not self.request_count:
            return None
        return GitHubAnswers(
            request_count=self.request_count, response_body_bytes=self.response_body_bytes
        )


_COUNTERS: ContextVar[tuple[AnswerCounter, ...]] = ContextVar("github_answer_counters", default=())


def begin_counting() -> tuple[AnswerCounter, Token[tuple[AnswerCounter, ...]]]:
    """A child task inherits the enclosing operation's counters, not other jobs'."""

    counter = AnswerCounter()
    return counter, _COUNTERS.set((*_COUNTERS.get(), counter))


def finish_counting(token: Token[tuple[AnswerCounter, ...]]) -> None:
    _COUNTERS.reset(token)


@contextmanager
def count_answers() -> Generator[AnswerCounter]:
    counter, token = begin_counting()
    try:
        yield counter
    finally:
        finish_counting(token)


def record_answer(body_bytes: int) -> None:
    for counter in _COUNTERS.get():
        counter.request_count += 1
        counter.response_body_bytes += body_bytes
