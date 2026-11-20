"""How a request's time filter decides which age group a file is in (`_GitTimes`).

One bucketing of every file serves every group of a grouped answer, so it has to say what
the band definition says (`tree_groups.age_band`): a file is in the group of the first
window it is no older than, the windows cut it at a recency filter, and a file with no
time is in Undated alone. No Git here: the answer is built by hand.
"""

from __future__ import annotations

import random
from array import array

import pytest

from metabrowser.git import content_routes
from metabrowser.git.file_ages import UNDATED, RevisionAges
from metabrowser.git.tree_source import GitBlobIndex
from metabrowser.settings import RECENT_WINDOW_SECONDS
from metabrowser.tree_filter import TreeFilter
from metabrowser.tree_groups import UNDATED_GROUP, age_band, age_windows, groups_for

AS_OF = 1_800_000_000.0
WINDOWS = tuple(seconds for seconds in RECENT_WINDOW_SECONDS.values() if seconds)


def _answer(stamps: list[int], prefix: str = "") -> tuple[GitBlobIndex, RevisionAges]:
    names = tuple(sorted(f"{prefix}f{at:05d}".encode() for at in range(len(stamps))))
    index = GitBlobIndex(tuple((name, f"{at:040x}") for at, name in enumerate(names)), {})
    ages = RevisionAges(
        commit="a" * 40,
        commit_time=int(AS_OF),
        names=names,
        times=array("q", stamps),
        older_than=None,
        stop="complete",
        seconds=0.0,
    )
    return index, ages


def _stamps(seed: int, count: int) -> list[int]:
    """Times at, one second either side of, and far from every window's edge, in the future,
    and absent."""

    rng = random.Random(seed)
    edges = [int(AS_OF - window) for window in WINDOWS]
    out: list[int] = []
    for _ in range(count):
        kind = rng.randrange(6)
        if kind == 0:
            out.append(UNDATED)
        elif kind == 1:
            out.append(rng.choice(edges) + rng.choice((-1, 0, 1)))
        elif kind == 2:
            out.append(int(AS_OF) + rng.randrange(1, 10_000))
        else:
            out.append(int(AS_OF) - rng.randrange(0, 3 * 31 * 86_400))
    return out


def _reference(stamp: int, group_id: str, recency: int) -> bool:
    """The membership the band definition gives, written out for one file."""

    if group_id == UNDATED_GROUP.id:
        return stamp == UNDATED and not recency
    if stamp == UNDATED:
        return False
    group = next(member for member in groups_for("age") if member.id == group_id)
    band = age_band(group, recency)
    age = AS_OF - stamp
    if recency and age > recency:
        return False
    if band.within_seconds is not None and age > band.within_seconds:
        return False
    return not (band.older_than_seconds is not None and age <= band.older_than_seconds)


@pytest.mark.parametrize("recency", [0, 3_600, 86_400, 7 * 86_400, 12_345])
def test_every_group_keeps_the_files_the_band_definition_keeps(recency: int) -> None:
    index, ages = _answer(_stamps(recency, 600))
    for group in (*groups_for("age"), UNDATED_GROUP):
        times = content_routes._git_times(  # pyright: ignore[reportPrivateUsage]
            ages, TreeFilter(group=group, recency_seconds=recency), AS_OF
        )
        mask = times.mask(index)
        for at, stamp in enumerate(ages.times):
            assert bool(mask[at]) == _reference(stamp, group.id, recency), (group.id, stamp)
            # The bucketing of one file and of every file are one definition.
            name = ages.names[at]
            assert times.keeps(name) == bool(mask[at])


@pytest.mark.parametrize("recency", [0, 3_600, 7 * 86_400])
def test_the_groups_partition_the_files(recency: int) -> None:
    """Each file is in exactly one group, or in none when a window leaves it out."""

    index, ages = _answer(_stamps(99, 500))
    masks = [
        content_routes._git_times(  # pyright: ignore[reportPrivateUsage]
            ages, TreeFilter(group=group, recency_seconds=recency), AS_OF
        ).mask(index)
        for group in (*groups_for("age"), UNDATED_GROUP)
    ]
    for at, stamp in enumerate(ages.times):
        members = sum(mask[at] for mask in masks)
        outside = recency and (stamp == UNDATED or AS_OF - stamp > recency)
        assert members == (0 if outside else 1), (stamp, recency)


def test_the_windows_the_groups_cut_at_are_the_menus() -> None:
    assert age_windows() == tuple(sorted(WINDOWS))


def test_a_recency_window_alone_keeps_every_dated_file_inside_it() -> None:
    index, ages = _answer(_stamps(5, 400))
    times = content_routes._git_times(  # pyright: ignore[reportPrivateUsage]
        ages, TreeFilter(recency_seconds=86_400), AS_OF
    )
    mask = times.mask(index)
    for at, stamp in enumerate(ages.times):
        assert bool(mask[at]) == (stamp != UNDATED and AS_OF - stamp <= 86_400)


def test_no_answer_puts_every_file_in_undated_and_no_window_holds_one() -> None:
    index, _ages = _answer([UNDATED] * 4)
    for recency, expect in ((0, 1), (3_600, 0)):
        times = content_routes._git_times(  # pyright: ignore[reportPrivateUsage]
            None, TreeFilter(group=UNDATED_GROUP, recency_seconds=recency), AS_OF
        )
        assert list(times.mask(index)) == [expect] * 4
    band = content_routes._git_times(  # pyright: ignore[reportPrivateUsage]
        None, TreeFilter(group=groups_for("age")[0]), AS_OF
    )
    assert list(band.mask(index)) == [0] * 4


def test_the_stamps_of_a_folders_index_are_a_slice_of_the_answers() -> None:
    """A folder's blobs are the run of the answer's names under it, so its times are that run;
    names that do not line up are looked up one by one."""

    index, ages = _answer([100 + at for at in range(6)], prefix="d/")
    inner = GitBlobIndex(tuple((name[2:], oid) for name, oid in index.blobs), {})
    aligned = content_routes._blob_stamps(inner, ages, b"d")  # pyright: ignore[reportPrivateUsage]
    assert list(aligned) == [100 + at for at in range(6)]
    # An index with one name the answer does not have is read name by name.
    odd = GitBlobIndex(((b"f00000", "0" * 40), (b"zzz", "1" * 40)), {})
    mixed = content_routes._blob_stamps(odd, ages, b"d")  # pyright: ignore[reportPrivateUsage]
    assert list(mixed) == [100, UNDATED]
    nothing = content_routes._blob_stamps(odd, None, b"d")  # pyright: ignore[reportPrivateUsage]
    assert list(nothing) == [UNDATED, UNDATED]
