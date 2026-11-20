"""The shape, size, and claim rules of a repository store's directory key.

``tests/fixtures/repository-cache/source-identity.json`` freezes the keys of sixteen
addresses and the collision answers, and ``test_repository_cache_contract_fixtures.py``
replays them. This file holds what a fixture cannot: the grammar of a key, the base-36
encoding of its suffix, the sizing the constant's comment claims, and the claim rules when
a store holds another's name.
"""

from __future__ import annotations

import hashlib
import math
import re
from itertools import pairwise

import pytest

from metabrowser.cache import identity
from metabrowser.cache.identity import (
    NAME_MAX_BYTES,
    NAME_SEPARATOR,
    NAME_SUFFIX_CHARS,
    SlugCollisionError,
    StoreKeyCollisionError,
    cache_slug,
    cache_store_key,
    identity_digest,
    is_slug,
    is_store_key,
    name_suffixes,
    readable_part,
    slug_candidates,
    slug_matches_identity,
    store_key_candidates,
    store_key_matches_identity,
)
from metabrowser.cache.projection import MAX_DIRECTORY_ENTRIES

ADDRESS = "https://github.com/jlevy/markform"
STORE = "sha256:589d51b16fd8f1a2e54f3b4a7c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f70819"
# Agrees with STORE on its first 64 bits, so on the whole first suffix and no more.
OTHER = "sha256:589d51b16fd8f1a2ffffffffffffffffffffffffffffffffffffffffffffffff"
STORE_SUFFIXES = (
    "cglzx070dcg",
    "cglzx070dcgijlclak1",
    "cglzx070dcgijlclak1zs5no1",
    "cglzx070dcgijlclak1zs5no17qz3ef4nmcawnw6y7cl2knnmr",
)
BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _digits_by_long_multiplication(digest: str, characters: int) -> str:
    """The first base-36 digits of ``digest / 16^len(digest)``, one multiplication each.

    A different route from the one the production code takes, which scales once and
    divides once: this peels one digit at a time, as a person converting a fraction by hand
    would, so the two agreeing says the closed form is the fraction's expansion.
    """

    bits = 4 * len(digest)
    remainder = int(digest, 16)
    digits = []
    for _ in range(characters):
        remainder *= 36
        digits.append(BASE36[remainder >> bits])
        remainder &= (1 << bits) - 1
    return "".join(digits)


def test_a_key_is_the_repository_and_the_start_of_the_identity_in_base_36() -> None:
    assert name_suffixes(STORE) == STORE_SUFFIXES
    assert store_key_candidates("https", ADDRESS, STORE) == tuple(
        f"github-com-jlevy-markform-{suffix}" for suffix in STORE_SUFFIXES
    )


def test_the_suffix_is_the_digest_read_as_a_fraction_in_base_36() -> None:
    """Checked against a long multiplication, and against ``bc``, which gave the literal.

    ``printf 'ibase=16\\nd=<DIGEST>\\nibase=A\\n(d * 36^11) / (2^256)\\n' | bc`` is the
    integer whose 11 base-36 digits the first suffix spells.
    """

    digest = identity_digest(STORE)
    for characters, suffix in zip(NAME_SUFFIX_CHARS, STORE_SUFFIXES, strict=True):
        assert _digits_by_long_multiplication(digest, characters) == suffix
    assert int(STORE_SUFFIXES[0], 36) == (int(digest, 16) * 36**11) >> 256


def _digests(count: int) -> list[str]:
    return [hashlib.sha256(str(index).encode()).hexdigest() for index in range(count)]


def test_every_suffix_is_fixed_width_lowercase_and_starts_the_next() -> None:
    for digest in _digests(300):
        suffixes = name_suffixes(identity.IDENTITY_PREFIX + digest)
        assert tuple(len(suffix) for suffix in suffixes) == NAME_SUFFIX_CHARS
        for shorter, longer in pairwise(suffixes):
            assert longer.startswith(shorter)
        assert all(re.fullmatch(r"[0-9a-z]+", suffix) for suffix in suffixes)


def test_a_leading_zero_is_kept_and_a_digit_is_never_leaned_on() -> None:
    """Spelling the digest itself in base 36 would drop leading zeros and vary in length."""

    zero = identity.IDENTITY_PREFIX + "0" * 64
    assert name_suffixes(zero) == tuple("0" * width for width in NAME_SUFFIX_CHARS)
    top = identity.IDENTITY_PREFIX + "f" * 64
    assert name_suffixes(top)[0] == "z" * 11


def test_the_first_character_takes_every_value() -> None:
    """The first base-36 digit of the number itself is 1 to 6 for 84% of digests; a fraction's is not."""

    firsts = {name_suffixes(identity.IDENTITY_PREFIX + digest)[0][0] for digest in _digests(2000)}
    assert firsts == set(BASE36)


def test_the_last_width_spells_the_whole_digest_so_no_two_identities_share_it() -> None:
    """50 characters hold 258.5 bits and 49 hold 253.3, so only 50 can tell any 256-bit digests apart."""

    assert NAME_SUFFIX_CHARS[-1] == 50
    assert 36**50 >= 2**256 > 36**49
    base = int(identity_digest(STORE), 16)
    seen = {
        name_suffixes(identity.IDENTITY_PREFIX + f"{base ^ flipped:064x}")[-1]
        for flipped in [0, *(1 << bit for bit in range(256))]
    }
    assert len(seen) == 257


@pytest.mark.parametrize(
    "value",
    [
        "github-com-jlevy-markform-cglzx070dcg",
        "local-origin-cglzx070dcgijlclak1",
        "source-" + "a" * 25,
        "a-" + "0" * 50,
        # An all-letter suffix, as about one key in thirty-five has, and an all-digit one.
        "github-com-jlevy-markform-abcdefghijk",
        "github-com-jlevy-markform-01234567890",
    ],
)
def test_the_keys_of_this_format_are_keys(value: str) -> None:
    assert is_store_key(value)


@pytest.mark.parametrize(
    "value",
    [
        # What an f01 home called a store: the whole digest and nothing else.
        "589d51b16fd8f1a2e54f3b4a7c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f70819",
        # What an f02 home called one: words joined by `--` and a hexadecimal prefix.
        "github-com--jlevy--markform--589d51b16fd8f1a2",
        "unattached--589d51b16fd8f1a2",
        # No readable part, no suffix, or a suffix of a width no key has.
        "github-com-jlevy-markform",
        "-cglzx070dcg",
        "cglzx070dcg",
        "github-com-jlevy-markform-cglzx070dc",
        "github-com-jlevy-markform-cglzx070dcgi",
        "github-com-jlevy-markform-cglzx070dcgijlclak",
        "github-com-jlevy-markform-cglzx070dcg-",
        "github-com-jlevy-markform--cglzx070dcg",
        "github-com-jlevy-markform-CGLZX070DCG",
        "GitHub-com-jlevy-markform-cglzx070dcg",
        "github-com-jlevy-markform-cglzx070dc_",
        "github.com/jlevy/markform-cglzx070dcg",
        "../github-com-jlevy-markform-cglzx070dcg",
        "github-com-jlevy-markform-cglzx070dcg ",
        "x" * 200 + "-cglzx070dcg",
        "",
    ],
)
def test_other_names_are_not_keys(value: str) -> None:
    assert not is_store_key(value)


def test_a_readable_word_that_looks_like_a_suffix_does_not_move_the_suffix() -> None:
    """The suffix is the last token, so a repository named like one cannot be taken for it.

    ``abcdefghijk`` is 11 lowercase letters, a suffix's shape, and it is the last word of
    this address's readable part. The key is that readable part and then the real suffix.
    """

    address = "https://github.com/jlevy/abcdefghijk"
    key = store_key_candidates("https", address, STORE)[0]
    assert key == "github-com-jlevy-abcdefghijk-cglzx070dcg"
    assert is_store_key(key)
    assert key.rpartition(NAME_SEPARATOR)[2] == STORE_SUFFIXES[0]
    assert store_key_matches_identity(key, STORE)
    # The same words with no suffix have a key's shape, which is why the shape is never
    # taken for the identity: only a suffix of the recorded identity ties a name to a store.
    bare = "github-com-jlevy-abcdefghijk"
    assert is_store_key(bare)
    assert not store_key_matches_identity(bare, STORE)
    assert not store_key_matches_identity(bare, OTHER)


@pytest.mark.parametrize(
    ("address", "readable"),
    [
        ("https://github.com/jlevy/markform", "github-com-jlevy-markform"),
        ("https://github.com/jlevy/my-repo", "github-com-jlevy-my-repo"),
        ("https://github.com/jlevy/my/repo", "github-com-jlevy-my-repo"),
        ("https://gitlab.example.com:8443/a/b.git", "gitlab-example-com-8443-a-b"),
    ],
)
def test_the_readable_part_is_the_words_of_the_address_joined_by_single_dashes(
    address: str, readable: str
) -> None:
    assert readable_part("https", address) == readable
    # Two repositories may read alike; the suffix is what tells them apart.
    assert "-".join(identity.slug_tokens("https", address)) == readable


def test_a_readable_part_is_bounded_and_never_ends_in_a_dash() -> None:
    address = "https://example.com/" + "/".join(["segment"] * 40)
    readable = readable_part("https", address)
    assert len(readable) <= identity.READABLE_MAX_BYTES
    assert not readable.endswith("-")
    assert is_store_key(f"{readable}-{STORE_SUFFIXES[0]}")


def test_the_longest_key_and_its_lock_files_fit_a_file_name() -> None:
    longest = "a" * identity.READABLE_MAX_BYTES + "-" + "0" * NAME_SUFFIX_CHARS[-1]
    assert is_store_key(longest) and len(longest) == NAME_MAX_BYTES
    # `locks/stores/<key>.fetch.lock` is the longest name a key makes; NAME_MAX is 255.
    assert NAME_MAX_BYTES + len(".fetch.lock") <= 255


def test_a_key_matches_the_store_it_starts_with() -> None:
    first, wider, *_ = store_key_candidates("https", ADDRESS, STORE)
    assert store_key_matches_identity(first, STORE)
    assert store_key_matches_identity(wider, STORE)
    assert not store_key_matches_identity(first, "sha256:" + "0" * 64)
    assert not store_key_matches_identity(identity_digest(STORE), STORE)
    assert not store_key_matches_identity(first, identity_digest(STORE))
    # The widths agree on a shared start and part at the second one.
    assert store_key_matches_identity(first, OTHER)
    assert not store_key_matches_identity(wider, OTHER)


def test_the_widths_end_with_the_whole_digest_and_only_grow() -> None:
    widths = NAME_SUFFIX_CHARS
    assert list(widths) == sorted(set(widths))
    assert math.ceil(256 / math.log2(36)) == widths[-1]


def _collision_probability(stores: int, characters: int) -> float:
    """The birthday bound ``n(n - 1) / 2^(b + 1)`` the constant's comment states."""

    bits = characters * math.log2(36)
    return stores * (stores - 1) / 2 ** (bits + 1)


def test_the_first_width_is_the_shortest_that_meets_the_stated_collision_target() -> None:
    """The comment beside ``NAME_SUFFIX_CHARS`` states a target, and this is it.

    Under 1e-9 at 10,000 stores, the most the cache routes list, with every readable part
    taken to be the same, and no shorter width does: 10 characters is 1.4e-8.
    """

    first = NAME_SUFFIX_CHARS[0]
    assert first * math.log2(36) == pytest.approx(56.9, abs=0.05)
    assert _collision_probability(10_000, first) < 1e-9
    assert _collision_probability(10_000, first - 1) >= 1e-9
    for characters, at_10k, at_100k in [
        (13, 2.9e-13, 2.9e-11),
        (12, 1.1e-11, 1.1e-9),
        (11, 3.8e-10, 3.8e-8),
        (10, 1.4e-8, 1.4e-6),
    ]:
        assert _collision_probability(10_000, characters) == pytest.approx(at_10k, rel=0.05)
        assert _collision_probability(100_000, characters) == pytest.approx(at_100k, rel=0.05)


def test_the_target_stores_are_the_most_the_cache_lists() -> None:
    assert MAX_DIRECTORY_ENTRIES == 10_000


def test_with_the_readable_part_counted_the_chance_is_far_lower() -> None:
    """Stores share a readable part only as spellings of one repository: groups of a handful."""

    first = NAME_SUFFIX_CHARS[0]
    for stores, expected in [(10_000, 2.7e-13), (100_000, 2.7e-12)]:
        pairs_in_groups_of_8 = stores * 7 / 2
        assert pairs_in_groups_of_8 / 36**first == pytest.approx(expected, rel=0.05)


def test_an_unclaimed_store_takes_its_first_key() -> None:
    assert (
        cache_store_key("https", ADDRESS, STORE, store_owner=lambda _key: None)
        == store_key_candidates("https", ADDRESS, STORE)[0]
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


# A source's slug has the grammar of a store key, and its suffix is its source identity's.

FLASK_ADDRESS = "https://github.com/pallets/flask"
FLASK_SOURCE = "sha256:e7b7fe0ffe8a446772b8a863f51222c90d256e511e1a4da3daec599735962fa9"
FLASK_SLUGS = (
    "github-com-pallets-flask-wl2qiw4376x",
    "github-com-pallets-flask-wl2qiw4376x48g9dx1k",
)


def test_a_slug_is_the_words_of_the_address_and_the_start_of_the_source_identity() -> None:
    candidates = slug_candidates("https", FLASK_ADDRESS, FLASK_SOURCE)
    assert candidates[:2] == FLASK_SLUGS
    assert name_suffixes(FLASK_SOURCE)[0] == "wl2qiw4376x"
    assert [len(slug.rpartition("-")[2]) for slug in candidates] == list(NAME_SUFFIX_CHARS)
    assert all(is_slug(slug) and slug_matches_identity(slug, FLASK_SOURCE) for slug in candidates)
    # The same words and the same digits of another identity: a key, not this source's slug.
    assert not slug_matches_identity(FLASK_SLUGS[0], STORE)


def test_a_slug_and_a_store_key_have_one_shape_and_are_told_apart_by_their_identity() -> None:
    for name in (FLASK_SLUGS[0], "github-com-jlevy-markform-cglzx070dcg"):
        assert is_slug(name) == is_store_key(name) is True
    for name in (
        "github-com--pallets--flask--e7b7fe0ffe8a",
        "github-com--pallets--flask--e7b7fe0ffe8a4467",
        "github-com-pallets-flask-wl2qiw4376",
        "wl2qiw4376x",
        "GitHub-com-pallets-flask-wl2qiw4376x",
    ):
        assert not is_slug(name) and not is_store_key(name), name
    assert not slug_matches_identity("github-com-pallets-flask-wl2qiw4376x", STORE)
    assert not slug_matches_identity("github-com--pallets--flask--e7b7fe0ffe8a", FLASK_SOURCE)


def test_an_unclaimed_source_takes_its_first_slug() -> None:
    assert (
        cache_slug("https", FLASK_ADDRESS, FLASK_SOURCE, slug_owner=lambda _slug: None)
        == FLASK_SLUGS[0]
    )


def test_a_slug_held_by_another_source_is_skipped_and_one_held_by_this_one_is_reused() -> None:
    other = "sha256:" + "f" * 64
    held = {FLASK_SLUGS[0]: other}
    assert cache_slug("https", FLASK_ADDRESS, FLASK_SOURCE, slug_owner=held.get) == FLASK_SLUGS[1]
    held = {FLASK_SLUGS[0]: FLASK_SOURCE}
    assert cache_slug("https", FLASK_ADDRESS, FLASK_SOURCE, slug_owner=held.get) == FLASK_SLUGS[0]


def test_a_source_holding_every_slug_of_another_is_a_typed_collision() -> None:
    held = dict.fromkeys(
        slug_candidates("https", FLASK_ADDRESS, FLASK_SOURCE), "sha256:" + "f" * 64
    )
    with pytest.raises(SlugCollisionError):
        cache_slug("https", FLASK_ADDRESS, FLASK_SOURCE, slug_owner=held.get)


def test_a_slug_for_another_identity_than_its_address_is_refused() -> None:
    with pytest.raises(ValueError, match="does not match"):
        cache_slug("https", FLASK_ADDRESS, STORE, slug_owner=lambda _slug: None)
