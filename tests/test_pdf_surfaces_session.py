"""What a reader sees of a PDF on every surface, from what the server serves there.

A PDF shows up in four places: a trusted folder's file view, an ``--untrusted`` folder's,
a pinned revision's (every GitHub repository and pull request is one), and a comparison
that changes it (a commit's diff, or a pull request's Changes). Whether the reader sees
the PDF inline, a note, or a binary file's line depends on what the server serves on each:
the trust block in the shell, the page's content policy, the kind and views the file
route answers, the answers at ``/raw`` the view's actions link to, and the PDF plugin's
preview of the file: the first page the file page shows behind its viewer, and the card a
diff shows for a binary PDF, which is drawn only where threat model T7 lets it be.

``tests/dom/pdf-surfaces-session.js`` runs the production PDF view and diff view on those
answers, and ``tests/golden/cli-ui-pdf-surfaces.tryscript.md`` pins what each surface
draws, so a reviewer reads which surfaces show a PDF without opening a browser. Its input
is ``tests/fixtures/pdf-surfaces-responses.json``, which the first test here rebuilds and
fails when the server answers differently; ``make golden-update`` rewrites it and then the
transcript. The second test holds the invariants the transcript shows: a view that draws
the viewer is on a page whose policy admits it, and every action links to an answer that
is the PDF.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser import paths_safe
from metabrowser.builtin_plugins.pdf import preview, preview_isolation
from metabrowser.builtin_plugins.pdf.preview_isolation import Sandbox
from metabrowser.capabilities import UNTRUSTED_CAPABILITIES, set_capabilities
from metabrowser.git.tree_source import GitPath
from metabrowser.paths_safe import _set_root_dir
from metabrowser.server import app
from metabrowser.source import AttachedFilesystemSubject, attach_subject, reset_source_session
from tests.git_pin_harness import git_env, overwrite_tree, pinned_client
from tests.golden_harness import check_recording, run_session
from tests.required_tools import needs_git, require_git

# A PDF as writers emit it, with a binary comment after the header, whose NUL byte is what
# makes Git call it binary, and one page PDFium draws (a filled rectangle, no cross-reference
# table, which PDFium rebuilds as viewers do); one whose bytes are all ASCII, which Git
# diffs as text and a binary sniff does not catch, and which has no page to draw; one with
# no extension; and a `.pdf` that is not one. The view never parses them: the browser's
# viewer does, and the preview's renderer, in a child process.
_PDF = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\x00\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Length 33 >>\nstream\n0.2 0.4 0.8 rg 30 30 240 140 re f\nendstream\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)
PDFS: dict[str, bytes] = {
    "papers/report.pdf": _PDF,
    "papers/ascii.pdf": b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n",
    "scans/untitled": _PDF,
    "notes/not-really.pdf": b"a text file named like a PDF\n",
}
# The file the commit changes beside the PDFs, so its comparison holds a text diff too.
README_BEFORE = b"# Papers\n"
README_AFTER = b"# Papers\n\nThe report is in papers/.\n"
FILES: dict[str, bytes] = {"README.md": README_AFTER, **PDFS}

# The headers that decide what a reader sees: an answer's type, and the policy that
# decides whether a page may embed it or a document may run scripts.
_HEADERS = ("content-type", "content-security-policy", "content-disposition")

posix_only = pytest.mark.skipif(os.name != "posix", reason="folder identities are POSIX bytes")
pytestmark = needs_git


def _store(directory: Path) -> tuple[Path, str]:
    """A bare store whose ``main`` is a README, then a commit adding the PDFs.

    Every identity and date comes from the stream, so each commit ID is the same on every
    machine.
    """

    require_git()
    store = directory / "store.git"
    env = git_env(directory)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", "main", str(store)],
        check=True,
        capture_output=True,
        env=env,
    )

    def blob(name: str, body: bytes) -> bytes:
        return (
            b"M 100644 inline "
            + name.encode()
            + b"\ndata "
            + str(len(body)).encode()
            + b"\n"
            + body
            + b"\n"
        )

    stream = bytearray(
        b"commit refs/heads/main\nmark :1\n"
        b"committer Pin <pin@example.invalid> 1767225600 +0000\n"
        b"data 6\nfirst\n\n"
    )
    stream += blob("README.md", README_BEFORE)
    stream += (
        b"\ncommit refs/heads/main\n"
        b"committer Pin <pin@example.invalid> 1767229200 +0000\n"
        b"data 9\nadd PDFs\nfrom :1\n"
    )
    for name, body in FILES.items():
        stream += blob(name, body)
    stream += b"\ndone\n"
    subprocess.run(
        ["git", "--git-dir", str(store), "fast-import", "--quiet", "--done"],
        check=True,
        capture_output=True,
        input=bytes(stream),
        env=env,
    )
    commit = subprocess.run(
        ["git", "--git-dir", str(store), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    ).stdout.strip()
    return store, commit


@asynccontextmanager
async def _folder_client(root: Path) -> AsyncGenerator[AsyncClient]:
    original = paths_safe.ROOT_DIR
    _set_root_dir(root)
    attach_subject(AttachedFilesystemSubject(root))
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app, raise_app_exceptions=True)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client
    finally:
        reset_source_session()
        _set_root_dir(original)


def _shell_block(html: str, name: str) -> str:
    """The JSON a shell's inline ``window.<name>=...;`` assigns."""

    start = html.index(f"window.{name}=") + len(f"window.{name}=")
    end = html.index(";</script>", start)
    return html[start:end]


def _embedding_policy(policy: str | None) -> str | None:
    """The directives of a page's policy that decide whether it may embed a PDF.

    The rest name the response's nonce and the build's asset addresses, which differ
    between runs and decide nothing here.
    """

    if policy is None:
        return None
    kept = [
        part.strip()
        for part in policy.split(";")
        if part.strip().split(" ", 1)[0] in ("default-src", "child-src", "frame-src", "object-src")
    ]
    return "; ".join(kept)


async def _observe(client: AsyncClient, address: dict[str, str]) -> dict[str, Any]:
    """The shell's trust facts, and for each PDF its file answer and its ``/raw`` answer.

    *address* maps a file's display path to the path the shell asks the server with: the
    path itself in a folder, its GitPath wire on a pin.
    """

    shell = await client.get("/view/")
    assert shell.status_code == 200, shell.text
    settings = json.loads(_shell_block(shell.text, "METABROWSER_SETTINGS"))
    files: dict[str, Any] = {}
    for display, path in address.items():
        answer = await client.get("/api/file", params={"path": path})
        assert answer.status_code == 200, answer.text
        body = answer.json()
        # What the view reads, without the age, which differs between runs.
        file = {
            "path": body["path"],
            "kind": body["kind"],
            "views": [
                {"id": view["id"], "label": view["label"], "default": view.get("default", False)}
                for view in body["views"]
            ],
        }
        # The address the PDF view's actions link to, as it spells it.
        href = "/raw?path=" + quote(path, safe="")
        raw = await client.get(href)
        # The first page the file page shows behind its viewer.
        shown = await client.get("/api/plugin/pdf/preview", params={"path": path})
        assert shown.status_code == 200, shown.text
        files[display] = {
            "file": file,
            "preview": shown.json(),
            "raw": {
                "href": href,
                "status": raw.status_code,
                **{name: raw.headers.get(name) for name in _HEADERS},
                "head": raw.content[:8].decode("latin-1"),
            },
        }
    return {
        "shell": {
            "source_kind": json.loads(_shell_block(shell.text, "METABROWSER_SOURCE_KIND")),
            "capabilities": settings.get("CAPABILITIES"),
            "content-security-policy": _embedding_policy(
                shell.headers.get("content-security-policy")
            ),
        },
        "files": files,
    }


async def _no_sandbox() -> Sandbox | None:
    return None


# A sandbox that confines nothing: the child runs as it would bare. It stands in for the
# platform's, so the recording holds a drawn card for an untrusted source on every
# platform; that the real one confines the child is tests/test_pdf_preview_sandbox.py's.
_STAND_IN = Sandbox(name="stand-in", prefix=())


async def _stand_in() -> Sandbox | None:
    return _STAND_IN


def _card_sides(comparison: dict[str, Any]) -> dict[str, str]:
    """Each binary change's ``.pdf`` side's blob, as ``diff-view.js`` ``pdfCardSide`` picks it."""

    sides: dict[str, str] = {}
    for change in comparison["manifest"]["files"]:
        side = change.get("old") if change["kind"] == "deleted" else change.get("new")
        content = (side or {}).get("content") or {}
        if (
            change["availability"] == "binary"
            and str(side["path"]).lower().endswith(".pdf")
            and content.get("kind") == "git_object"
        ):
            sides[side["path"]] = content["oid"]
    return sides


def _named_keys(recording: Any) -> Any:
    """*recording* with each preview key named by its order of first appearance.

    A key is a hash of the renderer's version among other things, so it changes with every
    PDFium release; which answers share a key is what a reader checks.
    """

    names: dict[str, str] = {}

    def name(key: str) -> str:
        return names.setdefault(key, f"preview-{len(names) + 1}")

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("status") == "ready" and isinstance(value.get("key"), str):
                key = name(value["key"])
                return {
                    **{field: walk(item) for field, item in value.items()},
                    "key": key,
                    "image": f"/api/plugin/pdf/preview-image?key={key}",
                }
            return {field: walk(item) for field, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return walk(recording)


def _served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    # Previews are kept in this run's own cache, and drawn as on a platform without a
    # sandbox until the comparison asks again with a stand-in, so the recording is the
    # same on every machine.
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "cache"))
    preview.reset_for_tests()
    preview_isolation.set_sandbox_probe(_no_sandbox)
    folder = tmp_path / "folder"
    for name, body in FILES.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (tmp_path / "git").mkdir()
    store, commit = _store(tmp_path / "git")
    in_folder = {name: name for name in PDFS}
    on_pin = {name: GitPath.from_display(name).to_wire() for name in PDFS}

    async def run() -> dict[str, Any]:
        async with _folder_client(folder) as client:
            trusted = await _observe(client, in_folder)
        set_capabilities(UNTRUSTED_CAPABILITIES)
        async with _folder_client(folder) as client:
            untrusted = await _observe(client, in_folder)
        # A pin answered from the folder's bytes could not match the recording by accident.
        overwrite_tree(folder)
        async with pinned_client(store, commit, ref="refs/heads/main") as (client, _subject):
            pin = await _observe(client, on_pin)
            comparison = await client.get(
                "/api/plugin/diff/comparison", params={"revision": "HEAD"}
            )
            assert comparison.status_code == 200, comparison.text
            # Each card the diff draws asks for its side's blob, never trusted: once as
            # on a platform without a sandbox, and once with one.
            cards: dict[str, dict[str, Any]] = {}
            for label, probe in (("noSandbox", _no_sandbox), ("sandbox", _stand_in)):
                preview_isolation.set_sandbox_probe(probe)
                answers: dict[str, Any] = {}
                for oid in _card_sides(comparison.json()).values():
                    address = f"/api/plugin/pdf/preview?oid={oid}"
                    answer = await client.get(address)
                    assert answer.status_code == 200, answer.text
                    answers[address] = answer.json()
                cards[label] = answers
        return {
            "folder": trusted,
            "folderUntrusted": untrusted,
            "pin": pin,
            "pinComparison": comparison.json(),
            "pinComparisonPreviews": cards,
        }

    try:
        return _named_keys(asyncio.run(run()))
    finally:
        preview_isolation.set_sandbox_probe(None)
        preview.reset_for_tests()


@posix_only
def test_fixture_is_what_the_server_serves_on_each_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served = _served(tmp_path, monkeypatch)
    assert served["folder"]["shell"]["capabilities"]["active_content"] is True
    assert served["folderUntrusted"]["shell"]["capabilities"]["active_content"] is False
    assert served["pin"]["shell"]["capabilities"]["active_content"] is False
    check_recording(
        "pdf-surfaces-responses.json", served, transcript="cli-ui-pdf-surfaces.tryscript.md"
    )


def test_every_surface_shows_what_its_policy_admits_and_links_to_the_pdf() -> None:
    observed = run_session("pdf-surfaces-session.js")
    surfaces = observed["surfaces"]
    for surface in surfaces:
        for name, seen in surface["files"].items():
            label = f"{surface['surface']}, {surface['host']}: {name}"
            # A view never draws a viewer its page's policy would leave blank.
            if seen["shows"] == "viewer":
                assert seen["policyAdmitsViewer"] is True, label
            # A text file named like a PDF is text, not a viewer showing an error.
            if name == "notes/not-really.pdf":
                assert seen["kind"] == "text", label
                assert seen["shows"] == "another view", label
                continue
            # Every other file is a PDF, and every action reaches the PDF.
            assert seen["kind"] == "pdf", label
            for action in seen["actions"]:
                assert action["answer"]["status"] == 200, label
                assert action["answer"]["type"] == "application/pdf", label
                assert action["answer"]["head"].startswith("%PDF-"), label
    shows = {
        (surface["surface"], surface["host"]): surface["files"]["papers/report.pdf"]["shows"]
        for surface in surfaces
    }
    # Every file page shows the viewer: the untrusted page admits an object from /raw.
    assert set(shows.values()) == {"viewer"}, shows
    policies = {surface["surface"]: surface["served"]["embedPolicy"] for surface in surfaces}
    assert policies == {
        "folder": "admits this origin",
        "folderUntrusted": "admits /raw only",
        "pin": "admits /raw only",
    }
    # A comparison shows a PDF as Git diffs it: a binary one, as real writers' are, by
    # saying so, and one whose bytes are all text as text. Its own view is a click away
    # (the file bar's View file, pinned in cli-ui-diff-view-file.tryscript.md).
    changes = {change["path"]: change for change in observed["pinComparison"]["changes"]}
    for name in ("papers/report.pdf", "scans/untitled"):
        assert changes[name]["availability"] == "binary", name
        assert changes[name]["body"] == "Binary file; no textual diff.", name
    assert changes["papers/ascii.pdf"]["body"] == "text diff"
    # A binary change to a `.pdf` holds a card; one named without the extension, or a PDF
    # Git diffs as text, holds none. The diff loads only the pdf plugin for it.
    assert {name for name, change in changes.items() if change["card"]} == {"papers/report.pdf"}
    assert observed["pinComparison"]["loads"] == ["pdf"]


def test_a_preview_is_drawn_only_where_threat_model_t7_admits_it() -> None:
    """A trusted folder's PDF is drawn, and drawn once for its bytes; an untrusted source's
    is drawn only in a sandbox; a file that is no PDF, or one PDFium cannot read, says so.
    The file page puts a drawn first page behind its viewer, and a diff's card shows it,
    with no viewer of its own."""

    recorded = json.loads(
        (Path(__file__).parent / "fixtures/pdf-surfaces-responses.json").read_text()
    )
    folder = {name: file["preview"] for name, file in recorded["folder"]["files"].items()}
    assert folder["papers/report.pdf"]["status"] == "ready"
    assert folder["papers/report.pdf"]["rendered"] is True
    # The same bytes under another name are the same preview, from the cache.
    assert folder["scans/untitled"]["key"] == folder["papers/report.pdf"]["key"]
    assert folder["scans/untitled"]["rendered"] is False
    assert folder["papers/ascii.pdf"]["reason"] == "unreadable"
    assert folder["notes/not-really.pdf"]["reason"] == "not_a_pdf"
    for surface in ("folderUntrusted", "pin"):
        reasons = {file["preview"].get("reason") for file in recorded[surface]["files"].values()}
        assert reasons == {"no_sandbox"}, surface
    cards = recorded["pinComparisonPreviews"]
    assert {answer["reason"] for answer in cards["noSandbox"].values()} == {"no_sandbox"}
    drawn = list(cards["sandbox"].values())
    assert [answer["status"] for answer in drawn] == ["ready"]
    # A blob is keyed by its object ID, not by the folder's content hash.
    assert drawn[0]["key"] != folder["papers/report.pdf"]["key"]

    observed = run_session("pdf-surfaces-session.js")
    for surface in observed["surfaces"]:
        for name, seen in surface["files"].items():
            if seen["shows"] != "viewer":
                continue
            answer = recorded[surface["surface"]]["files"][name]["preview"]
            if answer["status"] == "ready":
                backdrop = seen["firstPage"]["behindViewer"]
                assert backdrop["src"] == answer["image"], name
                assert backdrop["aria-hidden"] == "true", name
                assert backdrop["loading"] == "lazy", name
            else:
                assert seen["firstPage"] == {"none": answer["reason"]}, name
    by_label = observed["pinComparison"]["cards"]
    assert [card["state"] for card in by_label["noSandbox"]["cards"]] == ["unavailable"]
    assert by_label["noSandbox"]["cards"][0]["image"] is None
    [card] = by_label["sandbox"]["cards"]
    assert card["state"] == "ready"
    assert card["image"]["src"] == drawn[0]["image"]
    assert card["image"]["loading"] == "lazy"
    assert card["caption"] == ["report.pdf", "1 page", "View on branch"]
    # The way to the PDF's page is its file bar's own control, a press nearer.
    assert [control["label"] for control in card["controls"]] == ["View on branch"]
    # Each card asked once, for its side's blob.
    assert by_label["sandbox"]["requests"] == list(cards["sandbox"])
