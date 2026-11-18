"""Structural discipline for durable documents.

Prose drifts silently; these are the parts of `docs/development.md`'s documentation
conventions a machine can hold. Content review stays human: these checks keep a document
findable, the links and paths that name it true, and its status honest.

1. **Links resolve.** Every relative link and image in human-authored Markdown, and every
   `href` and `src` in its raw HTML, names a file or directory in the repository; one with
   a fragment into a Markdown file names a heading that file has. So does every
   `github.com/jlevy/metabrowser/blob/main/` link in that Markdown and in `src/`, `apps/`,
   and `skills/`, and every document path named in source under `src/` and `apps/`
   (:func:`_document_path_findings` says what counts as one). Anchors are github.com's:
   the heading's text with its inline Markdown rendered away, slugged by
   `inert_html.heading_slug`, and repeats numbered `-1`, `-2`. That is what
   `inert_html.harden_document` gives a page's headings, so the anchors are read from it.
2. **Every document is reachable.** Following relative links from `README.md` reaches every
   Markdown file under `docs/` outside `docs/project/` and `docs/tbd/`, without passing
   through a record (`docs/project/`, `explorations/`): a reader does not find a guide by
   way of a plan. Following them from `docs/project/README.md`, within `docs/project/`,
   reaches every Markdown file there.
3. **No tracker IDs in user guides.** `README.md`, the top-level `docs/*.md` guides,
   `skills/metabrowser/SKILL.md`, and `apps/macos/README.md` name no bead, matched as a
   whole token so that `data-mb-copy` is not one. A bead changes state without the guide
   changing. The architecture documents in `docs/` may cite one in their status line, as
   every architecture document may.
4. **Architecture discipline everywhere.** The status, footer, and named-check rules that
   cover `docs/project/architecture/` also cover `docs/architecture.md` and the standards
   in `docs/` (:data:`ARCHITECTURE_IN_DOCS`).

"In the repository" means a file git tracks, or an untracked one it does not ignore: an
ignored file is not on github.com, so a link to one is broken there whatever a checkout
holds, and matching git's paths catches a case mismatch a case-insensitive disk hides.
Each check is proven by a fixture it must fail, as `tests/test_experiment_storage.py`
proves its own.
"""

from __future__ import annotations

import difflib
import posixpath
import re
import subprocess
from collections.abc import Callable, Iterable
from html import unescape
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token

from devtools.changelog import CHANGELOG, is_fragment
from metabrowser.inert_html import ANCHOR_PREFIX, harden_document, heading_slug
from tests.required_tools import require_git

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DIR = REPO_ROOT / "docs/project/architecture"
PROJECT_INDEX = REPO_ROOT / "docs/project/README.md"
FOOTER = "This document follows common-doc-guidelines.md."

# Architecture documents that live in docs/ rather than docs/project/architecture/: the
# entry point and the contributor standards. Check 4 holds them to the same rules.
ARCHITECTURE_IN_DOCS = (
    "docs/architecture.md",
    "docs/large-content-rendering.md",
    "docs/web-performance-framework.md",
    "docs/realtime-debugging.md",
    "docs/engine-performance-model.md",
)

# Markdown this repository does not write by hand, so its links are not checked. Links
# into it are.
NOT_AUTHORED = (
    "docs/tbd/",  # tbd's forked guidelines, which `tbd docs` rewrites
    "tests/golden/",  # CLI captures, which `make golden-update` rewrites
    ".tbd/",  # tbd's own state and document forks
    "tests/fixtures/",  # inputs to renderer tests, whose odd links are the point
    "tests/manual-fixtures/",
    ".agents/skills/",  # installed skills, written upstream
    ".claude/skills/",
)
# Vendored browser bundles, checked byte for byte against static/vendor/manifest.json.
VENDORED = "static/vendor/"

# Records, which a reader does not pass through to find a guide (check 2).
RECORDS = ("docs/project/", "explorations/")

# Example paths that source writes and that name no document, each with why. Nothing joins
# this list to excuse a document that moved: point the source at its current path.
EXAMPLE_PATHS: dict[tuple[str, str], str] = {
    (
        "apps/macos/Tests/ShellCoreTests/OpenTargetTests.swift",
        "docs/plan.md",
    ): "the test builds a page address for an invented file",
    (
        "src/metabrowser/data/file-diff-format/file-diff-conformance.json",
        "docs/new.md",
    ): "a path inside a conformance case's patch",
}

# KPress's MarkdownIt preset, with raw HTML, so links and headings parse as a page has them.
_MARKDOWN = MarkdownIt("js-default", {"html": True})
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_HTML_REFERENCE = re.compile(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_ANCHOR_ID = re.compile(rf'\bid="{re.escape(ANCHOR_PREFIX)}([^"]*)"')
_MAIN_LINK = re.compile(r"github\.com/jlevy/metabrowser/blob/main/([^\s<>()\[\]{}\"'`|*]*)")
# A path ending in `.md`, not inside a URL or an absolute path, then a fragment, or a
# section title in quotes, which may wrap onto two more comment lines.
_DOCUMENT_PATH = re.compile(
    r"(?<![\w./:~@%$\\-])"
    r"(?P<up>(?:\.\./)+|blob/main/)?"
    r"(?P<path>(?:[\w-][\w.-]*/)*[\w-][\w.-]*\.md)"
    r"(?![\w/-]|\.\w)"
    r"(?:#(?P<fragment>[\w-]+)"
    r"|\)?,?[ \t]+(?:section[ \t]+)?[\"“](?P<title>[^\"”\n]+(?:\n[^\"”\n]+){0,2})[\"”])?"
)
_COMMENT_BREAK = re.compile(r"\s*\n\s*(?://+|\*|#+|--)?\s*")
# The naming conventions of docs/project/'s records. A bare name of this shape is a
# document's even when no file has it, which is how a retired name is caught.
_RECORD_NAME = re.compile(r"^(?:arch|plan|research|qa|review)-[\w.-]+\.md$")


class _Finding(NamedTuple):
    where: str
    subject: str
    problem: str

    def __str__(self) -> str:
        return f"{self.where}: {self.subject}: {self.problem}"


def _report(title: str, findings: Iterable[object]) -> str:
    return "\n".join([title, *(f"- {finding}" for finding in findings)])


def _without_front_matter(text: str) -> str:
    """*text* with a leading YAML front matter block blanked, its lines kept for numbering."""

    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() in ("---", "..."):
                return "\n" * (end + 1) + "\n".join(lines[end + 1 :])
    return text


class _Tree:
    """A work tree's files, read through one function so a fixture can stand in for it."""

    def __init__(self, files: Iterable[str], read: Callable[[str], str]) -> None:
        self.files = frozenset(files)
        self.read = read
        self.directories = frozenset(
            parent.as_posix()
            for name in self.files
            for parent in PurePosixPath(name).parents
            if parent.as_posix() != "."
        )
        self.markdown_by_name: dict[str, list[str]] = {}
        for name in sorted(self.files):
            if name.endswith(".md"):
                self.markdown_by_name.setdefault(PurePosixPath(name).name, []).append(name)
        # What each document yields is kept, not its tokens: a parse of every document
        # is millions of objects, and pytest's collection after each test walks them all.
        self._links: dict[str, list[tuple[int, str]]] = {}
        self._anchors: dict[str, frozenset[str]] = {}

    def exists(self, name: str) -> bool:
        return name in (".", "") or name in self.files or name in self.directories

    def text(self, name: str) -> str | None:
        try:
            return self.read(name)
        except UnicodeDecodeError:
            return None

    def _parse(self, name: str) -> tuple[list[Token], dict[str, Any], list[str]]:
        text = _without_front_matter(self.read(name))
        env: dict[str, Any] = {}
        return _MARKDOWN.parse(text, env), env, text.split("\n")

    def links(self, name: str) -> list[tuple[int, str]]:
        """Every reference Markdown file *name* makes, with its line: links and images,
        and the `href` and `src` of raw HTML. Code blocks and code spans make none."""

        if name in self._links:
            return self._links[name]
        tokens, _, lines = self._parse(name)
        found: list[tuple[int, str]] = []

        def line_of(value: str, start: int, end: int) -> int:
            for number in range(start, min(end, len(lines))):
                if value in lines[number] or unquote(value) in lines[number]:
                    return number + 1
            return start + 1

        def walk(children: list[Token], start: int, end: int) -> None:
            for token in children:
                if token.map:
                    start, end = token.map
                if token.type in ("link_open", "image"):
                    value = token.attrGet("href" if token.type == "link_open" else "src")
                    if value is not None:
                        found.append((line_of(str(value), start, end), str(value)))
                elif token.type in ("html_block", "html_inline"):
                    for double, single in _HTML_REFERENCE.findall(token.content):
                        value = unescape(double or single)
                        found.append((line_of(value, start, end), value))
                if token.children:
                    walk(token.children, start, end)

        walk(tokens, 0, 1)
        self._links[name] = found
        return found

    def anchors(self, name: str) -> frozenset[str]:
        """The heading anchors of Markdown file *name*, as a page and github.com give them."""

        if name not in self._anchors:
            tokens, env, _ = self._parse(name)
            html, _ = harden_document(_MARKDOWN.renderer.render(tokens, _MARKDOWN.options, env))
            self._anchors[name] = frozenset(unescape(i) for i in _ANCHOR_ID.findall(html))
        return self._anchors[name]


def _published(root: Path) -> list[str]:
    """What git tracks or would add under *root*, as repository-relative POSIX paths."""

    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    return [name for name in listed.split("\0") if name and (root / name).is_file()]


@pytest.fixture(scope="module")
def repo() -> _Tree:
    require_git()
    return _Tree(_published(REPO_ROOT), lambda name: (REPO_ROOT / name).read_text(encoding="utf-8"))


def _authored_markdown(tree: _Tree) -> list[str]:
    return sorted(
        name for name in tree.files if name.endswith(".md") and not name.startswith(NOT_AUTHORED)
    )


def _source(tree: _Tree, roots: tuple[str, ...]) -> list[str]:
    return sorted(name for name in tree.files if name.startswith(roots) and VENDORED not in name)


# ---- Check 1: links resolve ----


def _resolve(source: str, href: str) -> tuple[str, str] | None:
    """The repository path and fragment that *href*, written in *source*, names, or
    ``None`` for another site. A path that leaves the repository starts with ``..``."""

    if _SCHEME.match(href) or href.startswith("//"):
        return None
    parts = urlsplit(href)
    path, fragment = unquote(parts.path), unquote(parts.fragment)
    if not path:
        return source, fragment
    if path.startswith("/"):
        joined = path.lstrip("/")
    else:
        joined = posixpath.join(posixpath.dirname(source), path)
    return posixpath.normpath(joined), fragment


def _hint(wanted: str, anchors: frozenset[str]) -> str:
    near = difflib.get_close_matches(wanted, sorted(anchors), n=1)
    return f" (closest: #{near[0]})" if near else ""


def _target_problem(tree: _Tree, target: str, fragment: str) -> str | None:
    if target == ".." or target.startswith("../"):
        return "leaves the repository; link a file inside it, or write the full URL"
    if not tree.exists(target):
        return (
            f"{target} is not in the repository; point it at the document's current path, "
            "or remove it"
        )
    fragment = fragment.removeprefix(ANCHOR_PREFIX)
    if fragment and target.endswith(".md") and target in tree.files:
        anchors = tree.anchors(target)
        if fragment not in anchors:
            return (
                f"{target} has no heading with anchor #{fragment}; link a heading it has"
                f"{_hint(fragment, anchors)}"
            )
    return None


def _link_findings(tree: _Tree, sources: Iterable[str]) -> list[_Finding]:
    findings: list[_Finding] = []
    for source in sources:
        # A changelog fragment's bullets land in CHANGELOG.md unchanged, so its links are
        # written from there (devtools/changelog.py).
        written_in = CHANGELOG if is_fragment(source) else source
        for line, href in tree.links(source):
            resolved = _resolve(written_in, href)
            if resolved is None:
                continue
            problem = _target_problem(tree, *resolved)
            if problem:
                findings.append(_Finding(f"{source}:{line}", href, problem))
    return findings


def _main_link_findings(tree: _Tree, sources: Iterable[str]) -> list[_Finding]:
    """`github.com/jlevy/metabrowser/blob/main/` links, wherever they are written: released
    code and installed skills reach the documents through them."""

    findings: list[_Finding] = []
    for source in sources:
        text = tree.text(source)
        if text is None:
            continue
        for match in _MAIN_LINK.finditer(text):
            reference = match.group(1).rstrip(".,;:!?")
            if not reference:
                continue  # the prefix itself, named in prose
            parts = urlsplit(reference)
            target = posixpath.normpath(unquote(parts.path))
            problem = _target_problem(tree, target, unquote(parts.fragment))
            if problem:
                line = text.count("\n", 0, match.start()) + 1
                subject = match.group(0)[: len(match.group(0)) - len(match.group(1))] + reference
                findings.append(_Finding(f"{source}:{line}", subject, problem))
    return findings


def _document_target(tree: _Tree, source: str, up: str | None, path: str) -> str | None:
    """The repository path that *path*, written in *source*, names as a document, or
    ``None`` when it names none of this repository's."""

    if up == "blob/main/":
        return path
    if up:
        return posixpath.normpath(posixpath.join(posixpath.dirname(source), up + path))
    if "/" in path:
        first = path.split("/", 1)[0]
        here = PurePosixPath(source).parent
        for base in (p.as_posix() for p in (here, *here.parents) if p.as_posix() != "."):
            if f"{base}/{first}" in tree.directories:
                return f"{base}/{path}"
        if first in tree.directories:
            return path
        if f"docs/{first}" in tree.directories:
            return f"docs/{path}"
        return None
    named = tree.markdown_by_name.get(path, [])
    if len(named) == 1:
        return named[0]
    if not named and _RECORD_NAME.match(path):
        return path
    return None


def _leads_in_bold(text: str, title: str) -> bool:
    lead = rf"(?im)^[ \t]*(?:[-*+][ \t]+)?\*\*{re.escape(title)}[.:]?\*\*"
    return re.search(lead, text) is not None


def _document_path_findings(
    tree: _Tree,
    sources: Iterable[str],
    examples: dict[tuple[str, str], str] = EXAMPLE_PATHS,
) -> list[_Finding]:
    """Document paths named in source, such as a comment's `See docs/plugins.md`.

    A token ending in `.md` that is not inside a URL or an absolute path counts when it
    names a document of this repository:

    - with a leading `../`, from the source file's directory;
    - with a leading `blob/main/`, from the repository root (a URL built in two parts, as
      `ProjectLinks.swift` builds the installation guide's);
    - with a directory, when its first directory is in the source file's directory or an
      ancestor up to the root, or in `docs/`: `docs/plugins.md` from anywhere,
      `AppIcon/README.md` from `apps/macos/scripts/`;
    - as a bare name, when exactly one Markdown file has it, or none does and it has a
      record's shape (`arch-`, `plan-`, `research-`, `qa-`, `review-`), so that a retired
      architecture document's name is caught.

    Anything else, such as `folder/a.md`, `/view/a.md`, or `README.md`, is an example, a
    URL, or a name too common to place. A fragment (`docs/command-line.md#pull-requests`)
    must name a heading, and so must a quoted section title right after the path
    (`docs/design-system.md, "Keyboard Shortcuts"`), compared by its slug, or else open a
    paragraph in bold, as a run-in heading does (`**What starts a fetch.**`).
    *examples*, :data:`EXAMPLE_PATHS` by default, lists the few examples that look like
    documents.
    """

    findings: list[_Finding] = []
    for source in sources:
        text = tree.text(source)
        if text is None:
            continue
        for match in _DOCUMENT_PATH.finditer(text):
            up, path = match.group("up"), match.group("path")
            written = (up or "") + path
            if (source, written) in examples:
                continue
            target = _document_target(tree, source, up, path)
            if target is None:
                continue
            line = f"{source}:{text.count(chr(10), 0, match.start()) + 1}"
            fragment, title = match.group("fragment"), match.group("title")
            if title is not None:
                title = _COMMENT_BREAK.sub(" ", title).strip()
            problem = _target_problem(tree, target, fragment or "")
            if problem is None and title is not None and target in tree.files:
                anchors = tree.anchors(target)
                slug = heading_slug(title)
                if slug not in anchors and not _leads_in_bold(tree.read(target), title):
                    problem = (
                        f"{target} has no heading titled “{title}”; cite a heading it has"
                        f"{_hint(slug, anchors)}"
                    )
            if problem:
                subject = written + (f"#{fragment}" if fragment else "")
                subject += f", “{title}”" if title else ""
                findings.append(_Finding(line, subject, problem))
    return findings


def _stale_example_paths(tree: _Tree) -> list[str]:
    stale: list[str] = []
    for (source, written), _ in EXAMPLE_PATHS.items():
        text = tree.text(source) if source in tree.files else None
        if text is None or written not in text:
            stale.append(f"{source} no longer writes {written}; remove it from EXAMPLE_PATHS")
    return stale


def test_relative_links_resolve(repo: _Tree) -> None:
    findings = _link_findings(repo, _authored_markdown(repo))
    assert not findings, _report("Relative links that name nothing:", findings)


def test_main_branch_links_resolve(repo: _Tree) -> None:
    sources = sorted(
        set(_authored_markdown(repo)) | set(_source(repo, ("src/", "apps/", "skills/")))
    )
    findings = _main_link_findings(repo, sources)
    assert not findings, _report("github.com/jlevy/metabrowser/blob/main/ links:", findings)


def test_document_paths_in_source_resolve(repo: _Tree) -> None:
    sources = [name for name in _source(repo, ("src/", "apps/")) if not name.endswith(".md")]
    findings = _document_path_findings(repo, sources)
    assert not findings, _report("Document paths named in source:", findings)


def test_example_paths_are_still_written(repo: _Tree) -> None:
    stale = _stale_example_paths(repo)
    assert not stale, "\n".join(stale)


# ---- Check 2: every document is reachable ----


def _reached(tree: _Tree, start: str, enters: Callable[[str], bool]) -> set[str]:
    """The Markdown files reached by following relative links from *start*, entering only
    the files *enters* admits. A link to a directory reaches its README."""

    reached = {start}
    queue = [start]
    while queue:
        source = queue.pop()
        for _, href in tree.links(source):
            resolved = _resolve(source, href)
            if resolved is None:
                continue
            target = resolved[0]
            if target in tree.directories:
                target = f"{target}/README.md"
            known = target.endswith(".md") and target in tree.files
            if known and target not in reached and enters(target):
                reached.add(target)
                queue.append(target)
    return reached


def _unreachable_from_readme(tree: _Tree) -> list[str]:
    reached = _reached(tree, "README.md", lambda name: not name.startswith(RECORDS))
    required = (
        name
        for name in tree.files
        if name.startswith("docs/")
        and name.endswith(".md")
        and not name.startswith(("docs/project/", "docs/tbd/"))
    )
    return sorted(set(required) - reached)


def _unreachable_from_project_index(tree: _Tree) -> list[str]:
    index = "docs/project/README.md"
    reached = _reached(tree, index, lambda name: name.startswith("docs/project/"))
    required = (n for n in tree.files if n.startswith("docs/project/") and n.endswith(".md"))
    return sorted(set(required) - reached)


def test_readme_reaches_every_guide(repo: _Tree) -> None:
    missing = _unreachable_from_readme(repo)
    assert not missing, _report(
        "Not reachable by links from README.md; link each from README.md's Documentation "
        "section, or from a guide README.md reaches:",
        missing,
    )


def test_project_index_reaches_every_record(repo: _Tree) -> None:
    missing = _unreachable_from_project_index(repo)
    assert not missing, _report(
        "Not reachable by links from docs/project/README.md; add each to that index:",
        missing,
    )


# ---- Check 3: no tracker IDs in user guides ----


def _tracker_id_pattern() -> re.Pattern[str]:
    """A bead's short ID (`mb-5lxr`, prefixed as `.tbd/config.yml` says) or its internal
    one, each a whole token: `data-mb-copy`, `.mb-icon`, and `--mb-tone` name no bead."""

    config = yaml.safe_load((REPO_ROOT / ".tbd/config.yml").read_text(encoding="utf-8"))
    prefix = re.escape(str(config["display"]["id_prefix"]))
    return re.compile(rf"(?<![\w.-])(?:{prefix}-[a-z0-9]{{4}}|is-[0-9a-z]{{26}})(?![\w-])")


def _tracker_id_findings(
    name: str, text: str, pattern: re.Pattern[str], *, status_may_cite: bool
) -> list[_Finding]:
    findings: list[_Finding] = []
    for match in pattern.finditer(text):
        start = text.rfind("\n\n", 0, match.start())
        block = text[start + 2 :] if start >= 0 else text
        if status_may_cite and block.startswith("**Status:**"):
            continue
        findings.append(
            _Finding(
                f"{name}:{text.count(chr(10), 0, match.start()) + 1}",
                match.group(0),
                "a tracker ID in a user guide; describe what ships, and leave the bead to "
                "the spec, record, or TODO.md that tracks it",
            )
        )
    return findings


def _user_guides(tree: _Tree) -> list[str]:
    guides = {"README.md", "skills/metabrowser/SKILL.md", "apps/macos/README.md"}
    guides |= {n for n in tree.files if n.startswith("docs/") and n.count("/") == 1}
    return sorted(name for name in guides if name in tree.files and name.endswith(".md"))


def test_user_guides_name_no_tracker_ids(repo: _Tree) -> None:
    pattern = _tracker_id_pattern()
    findings = [
        finding
        for name in _user_guides(repo)
        for finding in _tracker_id_findings(
            name, repo.read(name), pattern, status_may_cite=name in ARCHITECTURE_IN_DOCS
        )
    ]
    assert not findings, _report("Tracker IDs in user guides:", findings)


# ---- Check 4: architecture discipline, wherever an architecture document lives ----


def _architecture_docs() -> list[Path]:
    return sorted(ARCHITECTURE_DIR.rglob("*.md"))


def _disciplined_docs() -> list[Path]:
    in_docs = (REPO_ROOT / name for name in ARCHITECTURE_IN_DOCS)
    return [*_architecture_docs(), *(doc for doc in in_docs if doc.is_file())]


def _status_problem(text: str) -> str | None:
    """Whether a document describes built or planned work is the first thing a reader
    needs, and the thing that goes stale first."""

    head = text.split("\n\n", 3)
    if any(part.startswith("**Status:**") for part in head[:3]):
        return None
    return "needs a **Status:** line near the top, saying what is built and what is planned"


def _footer_problem(text: str) -> str | None:
    return None if FOOTER in text else f"lost the footer that begins “{FOOTER}”; restore it"


def _named_check_problem(text: str) -> str | None:
    """A table of what the code registers must name its executable maintainer."""

    if ("| Route |" in text or "| Kind |" in text) and "tests/test_" not in text:
        return (
            "tabulates registered surfaces but names no test that checks it; name the "
            "tests/test_*.py that compares the table to the code"
        )
    if "| Contract ID |" in text and "devtools/check_artifact_contracts.py" not in text:
        return (
            "tabulates installed formats but names no inventory checker; name "
            "devtools/check_artifact_contracts.py"
        )
    return None


def _discipline_findings(rule: Callable[[str], str | None]) -> list[str]:
    findings: list[str] = []
    for doc in _disciplined_docs():
        problem = rule(doc.read_text(encoding="utf-8"))
        if problem:
            findings.append(f"{doc.relative_to(REPO_ROOT).as_posix()} {problem}")
    return findings


def test_architecture_documents_in_docs_exist() -> None:
    missing = [name for name in ARCHITECTURE_IN_DOCS if not (REPO_ROOT / name).is_file()]
    assert not missing, f"{missing} moved or were removed; update ARCHITECTURE_IN_DOCS"


def test_every_architecture_doc_is_linked_from_the_project_index() -> None:
    """A reader must reach every document from an obvious root."""
    index = PROJECT_INDEX.read_text(encoding="utf-8")
    for doc in _architecture_docs():
        relative = doc.relative_to(PROJECT_INDEX.parent).as_posix()
        assert relative in index, f"{relative} is not linked from docs/project/README.md"


def test_every_architecture_doc_states_its_status() -> None:
    findings = _discipline_findings(_status_problem)
    assert not findings, _report("Architecture documents without a status:", findings)


def test_every_architecture_doc_carries_the_shared_footer() -> None:
    findings = _discipline_findings(_footer_problem)
    assert not findings, _report("Architecture documents without the footer:", findings)


def test_documents_that_tabulate_registered_surfaces_name_their_check() -> None:
    findings = _discipline_findings(_named_check_problem)
    assert not findings, _report("Tables of registered surfaces with no check:", findings)


# ---- Each check fails on a fixture ----


def _sample(files: dict[str, str], *others: str) -> _Tree:
    return _Tree([*files, *others], files.__getitem__)


GUIDE = "\n\n".join(
    [
        "# Guide",
        "## Usage",
        "### Usage",
        "## The `--api` Flag",
        "<h2>Raw heading</h2>",
        "**Run-in rule.** A paragraph that leads in bold.",
    ]
)


def test_the_link_check_sees_what_it_must() -> None:
    readme = "\n".join(
        [
            "# Metabrowser",
            "",
            "[guide](docs/guide.md) [moved](docs/old.md) [case](docs/Guide.md)",
            "[usage](docs/guide.md#usage) [again](docs/guide.md#usage-1)",
            "[flag](docs/guide.md#the---api-flag) [raw](docs/guide.md#raw-heading)",
            "[prefixed](docs/guide.md#user-content-usage) [gone](docs/guide.md#usages)",
            "[folder](docs/) [code](src/app.py#L3) [here](#metabrowser) [nowhere](#nowhere)",
            "[out](../elsewhere.md) [site](https://example.com/x.md) [mail](mailto:a@b.c)",
            '<img src="images/missing.png" alt="">',
            "`[span](docs/span.md)`",
            "```",
            "[fenced](docs/fenced.md)",
            "```",
            "[ref][r]",
            "",
            "[r]: docs/ref.md",
        ]
    )
    tree = _sample({"README.md": readme, "docs/guide.md": GUIDE}, "src/app.py")
    findings = _link_findings(tree, ["README.md"])
    assert [(f.where, f.subject) for f in findings] == [
        ("README.md:3", "docs/old.md"),
        ("README.md:3", "docs/Guide.md"),
        ("README.md:6", "docs/guide.md#usages"),
        ("README.md:7", "#nowhere"),
        ("README.md:8", "../elsewhere.md"),
        ("README.md:9", "images/missing.png"),
        ("README.md:14", "docs/ref.md"),
    ]
    assert "closest: #usage" in findings[2].problem


def test_a_changelog_fragment_links_from_the_changelog() -> None:
    fragment = "- [usage](docs/guide.md#usage) [up](../docs/guide.md) [own](#changelog)\n"
    tree = _sample(
        {"CHANGELOG.md": "# Changelog\n", "docs/guide.md": GUIDE, "changelog.d/a.md": fragment},
        "changelog.d/README.md",
    )
    assert [(f.where, f.subject) for f in _link_findings(tree, ["changelog.d/a.md"])] == [
        ("changelog.d/a.md:1", "../docs/guide.md"),
    ]


def test_front_matter_is_not_a_heading() -> None:
    tree = _sample({"a.md": "---\ntitle: x\n---\n\n# A\n\n[t](#title-x) [b](b.md)\n"})
    assert [(f.where, f.subject) for f in _link_findings(tree, ["a.md"])] == [
        ("a.md:7", "#title-x"),
        ("a.md:7", "b.md"),
    ]


def test_the_main_branch_link_check_sees_what_it_must() -> None:
    prefix = "https://github.com/jlevy/metabrowser/blob/main/"
    text = "\n".join(
        [
            f"[guide]({prefix}docs/guide.md#usage), {prefix}docs/gone.md.",
            f'"{prefix}docs/guide.md#nope" and the prefix `{prefix}` alone',
            "https://github.com/jlevy/metabrowser-extra/blob/main/docs/gone.md",
        ]
    )
    tree = _sample({"skills/s/SKILL.md": text, "docs/guide.md": GUIDE})
    findings = _main_link_findings(tree, ["skills/s/SKILL.md"])
    assert [(f.where, f.subject) for f in findings] == [
        ("skills/s/SKILL.md:1", "github.com/jlevy/metabrowser/blob/main/docs/gone.md"),
        ("skills/s/SKILL.md:2", "github.com/jlevy/metabrowser/blob/main/docs/guide.md#nope"),
    ]


def test_the_document_path_check_sees_what_it_must() -> None:
    source = "\n".join(
        [
            "// See docs/guide.md and docs/moved.md.",
            "// Anchors: docs/guide.md#usage, docs/guide.md#gone.",
            '// (docs/guide.md, "Usage"; docs/guide.md, "Gone Section"; guide.md, "Run-in rule").',
            '// The rule is in guide.md, "The --api',
            '// Flag", and project/specs/plan.md.',
            "// Retired: arch-retired.md; kept: arch-kept.md.",
            "// Beside it: ../../docs/guide.md, ../../docs/lost.md",
            '    url.appending(path: "blob/main/docs/guide.md")',
            '    url.appending(path: "blob/main/docs/absent.md")',
            "// Not documents: /view/docs/moved.md, https://github.com/o/r/blob/main/README.md,",
            "// folder/a.md, notes.md, README.md, a.md.bak, docs/plan.md",
            "// Icon notes: AppIcon/README.md and AppIcon/MISSING.md",
        ]
    )
    tree = _sample(
        {"apps/x/main.swift": source, "docs/guide.md": GUIDE},
        "docs/project/architecture/arch-kept.md",
        "docs/project/specs/plan.md",
        "apps/x/AppIcon/README.md",
        "README.md",
    )
    examples = {("apps/x/main.swift", "docs/plan.md"): "an example in this fixture"}
    findings = _document_path_findings(tree, ["apps/x/main.swift"], examples)
    assert [(f.where, f.subject) for f in findings] == [
        ("apps/x/main.swift:1", "docs/moved.md"),
        ("apps/x/main.swift:2", "docs/guide.md#gone"),
        ("apps/x/main.swift:3", "docs/guide.md, “Gone Section”"),
        ("apps/x/main.swift:6", "arch-retired.md"),
        ("apps/x/main.swift:7", "../../docs/lost.md"),
        ("apps/x/main.swift:9", "blob/main/docs/absent.md"),
        ("apps/x/main.swift:12", "AppIcon/MISSING.md"),
    ]


def test_the_reachability_check_sees_what_it_must() -> None:
    tree = _sample(
        {
            "README.md": "[a](docs/a.md) [p](docs/project/README.md) [s](docs/sub/) [e](explorations/e.md)",
            "docs/a.md": "[b](b.md)",
            "docs/b.md": "",
            "docs/sub/README.md": "",
            "docs/orphan.md": "",
            "docs/via-project.md": "",
            "docs/via-exploration.md": "",
            "docs/tbd/generated.md": "",
            "explorations/e.md": "[v](../docs/via-exploration.md)",
            "docs/project/README.md": "[r](specs/r.md) [v](../via-project.md)",
            "docs/project/specs/r.md": "[s](s.md)",
            "docs/project/specs/s.md": "",
            "docs/project/lost.md": "",
        }
    )
    assert _unreachable_from_readme(tree) == [
        "docs/orphan.md",
        "docs/via-exploration.md",
        "docs/via-project.md",
    ]
    assert _unreachable_from_project_index(tree) == ["docs/project/lost.md"]


def test_the_tracker_id_check_sees_what_it_must() -> None:
    text = "\n".join(
        [
            "Fixed in `mb-e9fm`, and (mb-3h2m).",
            "Styled by data-mb-copy and .mb-icon, with --mb-tone and mb-copy-button.",
            "Tracked as is-01m7dqr8dg594qf7mjq3hdr9xd.",
            "",
            "**Status:** built; the rest is mb-5lxr.",
        ]
    )
    pattern = _tracker_id_pattern()
    guide = _tracker_id_findings("g.md", text, pattern, status_may_cite=False)
    assert [f.subject for f in guide] == [
        "mb-e9fm",
        "mb-3h2m",
        "is-01m7dqr8dg594qf7mjq3hdr9xd",
        "mb-5lxr",
    ]
    assert [f.where for f in guide] == ["g.md:1", "g.md:1", "g.md:3", "g.md:5"]
    architecture = _tracker_id_findings("a.md", text, pattern, status_may_cite=True)
    assert [f.subject for f in architecture] == [
        "mb-e9fm",
        "mb-3h2m",
        "is-01m7dqr8dg594qf7mjq3hdr9xd",
    ]


def test_the_architecture_rules_see_what_they_must() -> None:
    bare = "# Title\n\nIntro.\n\n| Route | View |\n| --- | --- |\n| `/` | home |\n"
    assert _status_problem(bare) is not None
    assert _footer_problem(bare) is not None
    assert _named_check_problem(bare) is not None
    kept = "# Title\n\n**Status:** Built.\n\n" + bare.split("\n\n", 2)[2]
    kept += "\n`tests/test_routes.py` checks the table.\n\n<!-- " + FOOTER + "\n-->\n"
    assert _status_problem(kept) is None
    assert _footer_problem(kept) is None
    assert _named_check_problem(kept) is None
    assert _named_check_problem("| Contract ID |\n") is not None
