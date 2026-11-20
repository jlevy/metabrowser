"""The shape, size, and claim rules of a repository store's directory key.

``tests/fixtures/repository-cache/source-identity.json`` freezes the keys of sixteen
addresses and the collision answers, and ``test_repository_cache_contract_fixtures.py``
replays them. This file holds what a fixture cannot: the grammar of a key, the sizing the
constant's comment claims, and the claim rules when a store holds another's name.
"""

from __future__ import annotations

import pytest

from metabrowser.cache import identity
from metabrowser.cache.identity import (
    SLUG_MAX_BYTES,
    STORE_KEY_MAX_BYTES,
    STORE_KEY_SUFFIX_HEX_DIGITS,
    StoreKeyCollisionError,
    cache_store_key,
    identity_digest,
    is_store_key,
    store_key,
    store_key_candidates,
    store_key_matches_identity,
)

ADDRESS = "https://github.com/jlevy/markform"
STORE = "sha256:589d51b16fd8f1a2e54f3b4a7c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f70819"
OTHER = "sha256:589d51b16fd8f1a2ffffffffffffffffffffffffffffffffffffffffffffffff"


def test_a_key_is_the_repository_and_a_prefix_of_the_identity() -> None:
    assert store_key("https", ADDRESS, STORE) == "github-com--jlevy--markform--589d51b16fd8f1a2"
    assert store_key_candidates("https", ADDRESS, STORE) == (
        "github-com--jlevy--markform--589d51b16fd8f1a2",
        "github-com--jlevy--markform--589d51b16fd8f1a2e54f3b4a",
        "github-com--jlevy--markform--589d51b16fd8f1a2e54f3b4a7c9d0e1f",
        "github-com--jlevy--markform--" + identity_digest(STORE),
    )


@pytest.mark.parametrize(
    "value",
    [
        "github-com--jlevy--markform--589d51b16fd8f1a2",
        "local--origin--589d51b16fd8f1a2e54f3b4a",
        "source--" + "a" * 64,
        "a--" + "0" * 32,
    ],
)
def test_the_keys_of_this_format_are_keys(value: str) -> None:
    assert is_store_key(value)


@pytest.mark.parametrize(
    "value",
    [
        # What an f01 home called a store: the whole digest and nothing else.
        "589d51b16fd8f1a2e54f3b4a7c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f70819",
        "github-com--jlevy--markform",
        "--589d51b16fd8f1a2",
        "github-com--jlevy--markform--589d51b16fd8",
        "github-com--jlevy--markform--589d51b16fd8f1a2e",
        "github-com--jlevy--markform--589D51B16FD8F1A2",
        "github-com--jlevy--markform--589d51b16fd8f1ag",
        "GitHub-com--jlevy--markform--589d51b16fd8f1a2",
        "github.com/jlevy/markform--589d51b16fd8f1a2",
        "../github-com--jlevy--markform--589d51b16fd8f1a2",
        "github-com--jlevy--markform--589d51b16fd8f1a2 ",
        "x" * 200 + "--589d51b16fd8f1a2",
        "",
    ],
)
def test_other_names_are_not_keys(value: str) -> None:
    assert not is_store_key(value)


def test_the_longest_key_and_its_lock_files_fit_a_file_name() -> None:
    assert STORE_KEY_MAX_BYTES == SLUG_MAX_BYTES
    longest = "a" * identity.SLUG_READABLE_MAX_BYTES + "--" + "0" * STORE_KEY_SUFFIX_HEX_DIGITS[-1]
    assert is_store_key(longest) and len(longest) == STORE_KEY_MAX_BYTES
    # `locks/stores/<key>.fetch.lock` is the longest name a key makes; NAME_MAX is 255.
    assert STORE_KEY_MAX_BYTES + len(".fetch.lock") <= 255


def test_a_key_matches_the_store_it_is_a_prefix_of() -> None:
    first, wider, *_ = store_key_candidates("https", ADDRESS, STORE)
    assert store_key_matches_identity(first, STORE)
    assert store_key_matches_identity(wider, STORE)
    assert not store_key_matches_identity(first, "sha256:" + "0" * 64)
    assert not store_key_matches_identity(identity_digest(STORE), STORE)
    assert not store_key_matches_identity(first, identity_digest(STORE))


def test_the_widths_end_with_the_whole_digest_and_only_grow() -> None:
    widths = STORE_KEY_SUFFIX_HEX_DIGITS
    assert list(widths) == sorted(set(widths))
    assert widths[-1] == 64


def _collision_probability(stores: int, hex_digits: int) -> float:
    """The birthday bound ``n(n - 1) / 2^(b + 1)`` the constant's comment states."""

    bits = 4 * hex_digits
    return stores * (stores - 1) / 2 ** (bits + 1)


def test_the_first_width_is_the_shortest_that_meets_the_stated_collision_target() -> None:
    """The comment beside ``STORE_KEY_SUFFIX_HEX_DIGITS`` states a target, and this is it.

    Under 1e-9 at 100,000 stores with every readable part taken to be the same, and no
    shorter width does: 12 digits is 1.8e-5 and 14 is 6.9e-8.
    """

    first = STORE_KEY_SUFFIX_HEX_DIGITS[0]
    assert _collision_probability(100_000, first) < 1e-9
    assert _collision_probability(100_000, first - 1) >= 1e-9
    assert _collision_probability(100_000, 12) == pytest.approx(1.8e-5, rel=0.05)
    assert _collision_probability(100_000, 14) == pytest.approx(6.9e-8, rel=0.05)
    assert _collision_probability(100_000, first) == pytest.approx(2.7e-10, rel=0.05)
    assert _collision_probability(10_000, first) == pytest.approx(2.7e-12, rel=0.05)


def test_an_unclaimed_store_takes_its_first_key() -> None:
    assert cache_store_key("https", ADDRESS, STORE, store_owner=lambda _key: None) == store_key(
        "https", ADDRESS, STORE
    )


def test_a_name_held_by_another_store_is_skipped_and_never_shared() -> None:
    first, second, third, _whole = store_key_candidates("https", ADDRESS, STORE)
    held = {first: OTHER}
    assert cache_store_key("https", ADDRESS, STORE, store_owner=held.get) == second
    held[second] = OTHER
    assert cache_store_key("https", ADDRESS, STORE, store_owner=held.get) == third


def test_a_store_is_found_at_the_name_it_took_even_when_a_shorter_one_is_free() -> None:
    first, second, *_ = store_key_candidates("https", ADDRESS, STORE)
    assert cache_store_key("https", ADDRESS, STORE, store_owner={second: STORE}.get) == second
    assert first != second


def test_a_store_holding_every_name_of_another_is_a_typed_collision() -> None:
    held = dict.fromkeys(store_key_candidates("https", ADDRESS, STORE), OTHER)
    with pytest.raises(StoreKeyCollisionError):
        cache_store_key("https", ADDRESS, STORE, store_owner=held.get)
