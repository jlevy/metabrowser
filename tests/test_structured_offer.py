"""The structured kind offers its Table view on a file that starts as a list of records.

``offers_table`` decides from a file's leading bytes what the record-list source
(records.py) would decide from its whole parse, as far as those bytes settle it. Where
they settle it, the two agree: each case here also asks the source, through
``build_records``, over the whole parse.
"""

from __future__ import annotations

import pytest

from metabrowser.builtin_plugins.structured import offer, records
from metabrowser.builtin_plugins.structured.offer import OFFER_YAML_PREFIX_BYTES, offers_table
from metabrowser.builtin_plugins.structured.parser import parse_structured_bytes
from metabrowser.plugin_api import SourceUnreadableError

_OFFERED = [
    (".json", b'[{"name": "Ada"}, {"name": "Grace"}]'),
    (".json", b'\xef\xbb\xbf \n [ \n {"name": "Ada"}]'),
    (".json", b'// people\n[ /* first */ {"name": "Ada"},]'),
    (".yaml", b"- name: Ada\n- name: Grace\n"),
    (".yml", b"# people\n%YAML 1.1\n---\n- name: Ada\n  role: analyst\n"),
    (".yaml", b"-\n  name: Ada\n-\n  name: Grace\n"),
    (".yaml", b"- {name: Ada}\n- {name: Grace}\n"),
    (".yaml", b"[{name: Ada}, {name: Grace}]\n"),
    (".yaml", b"- &ada\n  name: Ada\n- *ada\n"),
    (".yaml", b"- !!omap\n  - name: Ada\n  - role: analyst\n"),
    (".yaml", b"---\nkind: Service\n---\nkind: Deployment\n"),
    (".yaml", b"---\n# nothing\n---\nkind: Service\n---\n\n---\nkind: Deployment\n"),
    (".yaml", b"---\n# nothing\n---\n- name: Ada\n"),
]

_NOT_OFFERED = [
    (".json", b'{"name": "metabrowser", "version": 1}'),
    (".json", b"[1, 2, 3]"),
    (".json", b"[[1], [2]]"),
    (".json", b'"text"'),
    (".json", b"null"),
    (".json", b""),
    (".yaml", b"name: metabrowser\nversion: 1\n"),
    (".yaml", b"- 1\n- 2\n"),
    (".yaml", b"- - 1\n"),
    (".yaml", b"just text\n"),
    (".yaml", b""),
    (".yaml", b"---\nkind: Service\n---\n# only a comment\n"),
    (".yaml", b"---\nkind: Service\n---\n- 1\n"),
    (".yaml", b"---\nkind: Service\n---\ntext\n"),
    (".yaml", b"--- !!set\n? a\n? b\n"),
    (".yaml", b"- !!pairs\n  - a: 1\n"),
    (".yaml", b"key: [unclosed\n"),
]


def _source_reads_records(ext: str, data: bytes) -> bool:
    payload = parse_structured_bytes(data, ext, serialize=False)
    try:
        records.build_records(payload, "g")
    except SourceUnreadableError:
        return False
    return True


@pytest.mark.parametrize(("ext", "data"), _OFFERED)
def test_a_file_that_starts_as_a_list_of_records_is_offered(ext: str, data: bytes) -> None:
    assert offers_table(data, ext) is True
    assert _source_reads_records(ext, data) is True


@pytest.mark.parametrize(("ext", "data"), _NOT_OFFERED)
def test_any_other_file_is_not_offered(ext: str, data: bytes) -> None:
    assert offers_table(data, ext) is False
    assert _source_reads_records(ext, data) is False


def test_an_empty_list_holds_no_records_to_show() -> None:
    """The source reads `[]` as a table of no rows and no fields, nothing to offer."""
    assert offers_table(b"[]", ".json") is False
    assert _source_reads_records(".json", b"[]") is True


def test_a_list_that_turns_out_not_to_be_records_is_still_offered() -> None:
    """Its Table view says why the source refused it; only a whole parse could tell."""
    data = b'[{"name": "Ada"}, "Grace"]'
    assert offers_table(data, ".json") is True
    assert _source_reads_records(".json", data) is False


def test_a_long_list_is_decided_by_its_first_item() -> None:
    data = b"- name: Ada\n" + b"- name: someone\n" * 100_000
    assert offers_table(data, ".yaml") is True


def test_a_mapping_longer_than_the_yaml_prefix_is_the_only_document() -> None:
    first = b"---\n" + b"".join(b"key_%d: value\n" % i for i in range(5_000))
    assert len(first) > OFFER_YAML_PREFIX_BYTES
    assert offers_table(first + b"---\nkey: value\n", ".yaml") is False
    short = b"---\n" + b"".join(b"key_%d: value\n" % i for i in range(50))
    assert offers_table(short + b"---\nkey: value\n", ".yaml") is True


def test_a_prefix_cut_inside_a_character_or_a_token_is_still_read() -> None:
    data = "- name: Adá\n".encode() * 2_000
    cut = OFFER_YAML_PREFIX_BYTES - 1
    assert data[cut - 1 : cut + 1].decode("utf-8", errors="replace") != "á"
    assert offers_table(data[: cut + 1], ".yaml") is True


@pytest.mark.parametrize("loader", ["CSafeLoader", "SafeLoader"])
def test_libyaml_and_the_python_parser_agree(loader: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml

    if not hasattr(yaml, loader):
        pytest.skip(f"PyYAML has no {loader} here")
    monkeypatch.setattr(offer, "_LOADER", getattr(yaml, loader))
    for ext, data in _OFFERED:
        assert offers_table(data, ext) is True, data
    for ext, data in _NOT_OFFERED:
        assert offers_table(data, ext) is False, data


def test_another_extension_is_never_offered() -> None:
    assert offers_table(b'[{"name": "Ada"}]', ".toml") is False
