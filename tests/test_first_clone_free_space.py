"""The free space a first clone leaves on the cache's volume, which core checks for every
source before any provider is asked (``cache/free_space.py``, ``cache/providers.py``).

``shutil.disk_usage`` is replaced, so the volume these tests run on decides nothing.
"""

from __future__ import annotations

import asyncio
import errno
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from metabrowser.builtin_plugins.github.gh import gh_executable
from metabrowser.cache import providers
from metabrowser.cache.acquire import RepositoryTooLargeError
from metabrowser.cache.free_space import (
    FREE_SPACE_RESERVE_ENV,
    FREE_SPACE_RESERVE_MB,
    size_text,
)
from metabrowser.cache.urls import GitSource

RESERVE: int = FREE_SPACE_RESERVE_MB * 1_000_000
GITHUB = GitSource(transport="https", form="url", normalized="https://github.com/octo/demo")
OTHER_HOST = GitSource(transport="https", form="url", normalized="https://gitlab.com/o/r.git")


def _volume_with(monkeypatch: pytest.MonkeyPatch, free: int) -> list[Path]:
    """Make every volume report *free* bytes free; the paths asked are recorded."""

    asked: list[Path] = []

    def disk_usage(path: str | Path) -> SimpleNamespace:
        asked.append(Path(path))
        return SimpleNamespace(total=free, used=0, free=free)

    monkeypatch.setattr(shutil, "disk_usage", disk_usage)
    return asked


def test_a_first_clone_is_checked_against_the_volume_that_will_hold_the_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The home need not exist yet: its nearest existing parent's volume is read, and
    every provider is handed that free space, or ``None`` when it cannot be read."""

    handed: list[int | None] = []

    class Recorder:
        async def check_first_clone(self, source: GitSource, *, free_bytes: int | None) -> None:
            handed.append(free_bytes)

    monkeypatch.setattr(providers, "installed_providers", lambda: (Recorder(),))
    asked = _volume_with(monkeypatch, 7 * 10**9 + 3)
    asyncio.run(providers.check_first_clone(GITHUB, home=tmp_path / "not" / "yet"))
    assert asked == [tmp_path]
    assert handed == [7 * 10**9 + 3]

    def unreadable(_path: str | Path) -> SimpleNamespace:
        raise OSError(errno.EIO, "unreadable")

    monkeypatch.setattr(shutil, "disk_usage", unreadable)
    asyncio.run(providers.check_first_clone(GITHUB, home=tmp_path))
    assert handed[-1] is None, "an unreadable volume refuses nothing"


@pytest.mark.parametrize("source", [GITHUB, OTHER_HOST], ids=["github-without-gh", "other-host"])
def test_a_volume_below_the_reserve_refuses_every_first_clone(
    source: GitSource, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Whatever the source, and whether or not its host can size it: no clone can leave
    the reserve free on a volume that already has less."""

    monkeypatch.delenv(FREE_SPACE_RESERVE_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert gh_executable() is None
    _volume_with(monkeypatch, 400_000_000)
    with pytest.raises(RepositoryTooLargeError) as refused:
        asyncio.run(providers.check_first_clone(source, home=tmp_path / "cache"))
    assert refused.value.state == "too_large"
    assert str(refused.value) == (
        f"{source.normalized} does not fit on the cache's volume for a first clone "
        "(too_large); the cache's volume has 400 MB free, less than the 1.0 GB metab "
        "leaves free; free space on the volume, set METABROWSER_CACHE_DIR to one with "
        f"more, or lower {FREE_SPACE_RESERVE_ENV}; nothing was published"
    )
    # At the reserve itself the floor refuses nothing, and neither source can be sized.
    _volume_with(monkeypatch, RESERVE)
    asyncio.run(providers.check_first_clone(source, home=tmp_path / "cache"))


def test_no_reserve_refuses_nothing_on_a_full_volume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(FREE_SPACE_RESERVE_ENV, "0")
    _volume_with(monkeypatch, 0)
    asyncio.run(providers.check_first_clone(OTHER_HOST, home=tmp_path))


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (0, "0 MB"),
        (1, "under 1 MB"),
        (13_516, "under 1 MB"),
        (1_000_000, "1 MB"),
        (337_920_000, "338 MB"),
        (999_400_000, "999 MB"),
        (10**9, "1.0 GB"),
        (1_808_724_096, "1.8 GB"),
        (62_307_266_560, "62.3 GB"),
    ],
)
def test_a_size_is_named_in_a_unit_that_shows_it(count: int, text: str) -> None:
    assert size_text(count) == text
