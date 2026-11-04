"""Optional avatar normalization does not admit arbitrary browser image origins."""

from typing import Any

import pytest

from metabrowser.builtin_plugins.github.avatars import avatar_url
from metabrowser.builtin_plugins.github.pull_list import PullListRow
from metabrowser.builtin_plugins.github.pull_list_refresh import _row
from tests.github_pull_fixture import generated_item


@pytest.mark.parametrize("kind", ["u", "in"])
def test_provider_avatar_size_is_canonical_and_cached_values_are_checked(kind: str) -> None:
    raw = f"https://avatars.githubusercontent.com/{kind}/123?v=4&size=900&other=discarded"
    canonical = f"https://avatars.githubusercontent.com/{kind}/123?s=40"
    assert avatar_url(raw) == canonical
    item = generated_item(7)
    item["user"]["avatar_url"] = raw
    row, cut = _row(item)
    assert not cut and row.author_avatar_url == canonical
    cached = row.model_dump() | {"author_avatar_url": "https://elsewhere.invalid/image.png"}
    assert PullListRow.model_validate(cached).author_avatar_url is None
    del cached["author_avatar_url"]
    assert PullListRow.model_validate(cached).author_avatar_url is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        7,
        {},
        "",
        "http://avatars.githubusercontent.com/u/1",
        "https://avatars.githubusercontent.com.evil.invalid/u/1",
        "https://user@avatars.githubusercontent.com/u/1",
        "https://avatars.githubusercontent.com:443/u/1",
        "//avatars.githubusercontent.com/u/1",
        "https://avatars.githubusercontent.com/u/1#fragment",
        "https://avatars.githubusercontent.com/u/1\n",
        "https://avatars.githubusercontent.com/u/1\\x",
        "https://avatars.githubusercontent.com/%75/1",
        "https://avatars.githubusercontent.com/u/../1",
        "https://avatars.githubusercontent.com/user-name",
        "https://avatars.githubusercontent.com/u/" + "1" * 21,
        "https://avatars.githubusercontent.com/u/1?" + "x" * 512,
        "https://[invalid/u/1",
    ],
)
def test_invalid_optional_avatar_is_absent_without_losing_the_row(value: Any) -> None:
    item = generated_item(7)
    item["user"]["avatar_url"] = value
    row, cut = _row(item)
    assert row.number == 7 and row.author_avatar_url is None and not cut


def test_deleted_actor_keeps_the_record_without_an_avatar() -> None:
    item = generated_item(7)
    item["user"] = None
    row, cut = _row(item)
    assert row.author is None and row.author_avatar_url is None and not cut
