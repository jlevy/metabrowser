"""Unified-patch source: File Diff Format from a ``.patch`` or ``.diff``.

The source that proves the format is standalone — no repository, no
subprocess, no network. It parses git's extended headers (rename, copy,
mode, similarity, binary) and plain unified diffs alike, byte-exactly:
paths and line content that are not valid UTF-8 keep their bytes in
``*_b64`` beside a replacement-decoded display projection.

Malformed input is a value, not an exception: the parser returns a
document whose files (or whole manifest) carry ``unsupported``
availability, because a browsable explanation beats a stack trace for a
file a user just clicked.
"""

from __future__ import annotations

from base64 import b64encode
from hashlib import sha256

from metabrowser.diff.format import (
    Availability,
    BasePolicy,
    ChangeKind,
    ChangeSetDocument,
    ChangeSetManifest,
    ContentRef,
    ContentRefKind,
    DiffOptions,
    EntrySide,
    EntryType,
    FileChange,
    FileMode,
    FilePatch,
    Hunk,
    LineOp,
    LineRecord,
    ResolvedComparison,
    SnapshotKind,
    SnapshotRef,
    SourceInfo,
    Totals,
)

MAX_PATCH_BYTES = 8 * 1024 * 1024
"""Refusal cap for one pasted-in patch document. A bound on parse cost:
8 MiB of unified diff is ~100k lines, which parses in well under a second
and renders through the manifest-first path; anything larger is almost
certainly generated output that belongs in git, and the CLI/route report
it as `truncated` rather than stalling."""

MAX_FILE_SECTIONS = 2000
"""Manifest cap mirroring the route-level manifest bound."""

_HUNK_RE_PREFIX = b"@@ -"


def _display(raw: bytes) -> tuple[str, str | None]:
    """UTF-8 projection plus b64 of the exact bytes when they differ."""
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace"), b64encode(raw).decode("ascii")


def _unquote_c_style(raw: bytes) -> bytes:
    """Git quotes non-ASCII paths C-style: ``"calf\\351.txt"``."""
    if not (raw.startswith(b'"') and raw.endswith(b'"') and len(raw) >= 2):
        return raw
    body = raw[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        byte = body[i]
        if byte != 0x5C:  # backslash
            out.append(byte)
            i += 1
            continue
        i += 1
        if i >= len(body):
            break
        escape = body[i : i + 1]
        if escape.isdigit():
            # A malformed octal escape is somebody's literal backslash:
            # keep the bytes verbatim rather than crashing on int().
            octal = body[i : i + 3]
            try:
                value = int(octal, 8)
            except ValueError:
                out.append(0x5C)
                out.append(body[i])
                i += 1
                continue
            if value > 0xFF:
                out.append(0x5C)
                out.extend(octal)
                i += 3
                continue
            out.append(value)
            i += 3
        else:
            out.append({b"n": 10, b"t": 9, b'"': 34, b"\\": 92}.get(escape, escape[0]))
            i += 1
    return bytes(out)


def _strip_prefix(raw: bytes) -> bytes:
    """Drop git's ``a/`` / ``b/`` prefix; keep ``/dev/null`` recognizable."""
    if raw == b"/dev/null":
        return raw
    if len(raw) > 2 and raw[1:2] == b"/" and raw[0:1] in (b"a", b"b"):
        return raw[2:]
    return raw


class _Section:
    """One ``diff --git`` (or bare unified) section, before interpretation."""

    def __init__(self) -> None:
        self.old_path: bytes | None = None
        self.new_path: bytes | None = None
        self.old_mode: str | None = None
        self.new_mode: str | None = None
        self.kind_hint: ChangeKind | None = None
        self.similarity: int | None = None
        self.binary = False
        self.malformed: str | None = None
        self.hunk_lines: list[bytes] = []
        # True while the paths are only the `diff --git` header's guess;
        # the authoritative ---/+++ lines override a guess (a filename
        # containing " b/" defeats the header split), but never a path
        # set by rename/copy headers.
        self.old_guessed = False
        self.new_guessed = False


def _hunk_line_budget(raw_line: bytes) -> tuple[int, int]:
    """Old/new line counts a hunk header declares, or a permissive fallback.

    Used only to know where a hunk body ends; the real count validation
    happens in _parse_hunks. A header these ints cannot be read from
    keeps the permissive legacy behavior (body runs until the next
    marker), which _parse_hunks will then reject with a precise reason.
    """
    try:
        marker_end = raw_line.index(b" @@", 3)
        spans = raw_line[4:marker_end].split(b" +")
        if len(spans) != 2:
            raise ValueError(raw_line.decode("ascii", "replace"))

        def count(text: bytes) -> int:
            if b"," in text:
                _, count_raw = text.split(b",", 1)
            else:
                count_raw = b"1"
            if not count_raw.isdigit():
                raise ValueError(text.decode("ascii", "replace"))
            return int(count_raw)

        return count(spans[0]), count(spans[1])
    except ValueError:
        return (1 << 60), (1 << 60)


def _split_sections(data: bytes) -> list[_Section]:
    sections: list[_Section] = []
    current: _Section | None = None
    in_hunks = False
    hunk_old_left = hunk_new_left = 0
    # After the counted lines run out, a `\ No newline at end of file`
    # marker may still belong to the hunk's final line.
    hunk_tail_ok = False
    raw_lines = data.split(b"\n")
    if raw_lines and raw_lines[-1] == b"":
        # split() artifact after the final newline, not an empty diff line —
        # a genuinely empty context line arrives as a single space.
        raw_lines.pop()
    for raw_line in raw_lines:
        if raw_line.startswith(b"diff --cc ") or raw_line.startswith(b"diff --combined "):
            # Combined (merge) diffs carry N+1-column hunks this parser
            # cannot represent; surface the section as unsupported rather
            # than silently parsing zero hunks out of it.
            current = _Section()
            current.malformed = "combined (merge) diff is not supported"
            sections.append(current)
            in_hunks = False
            continue
        if raw_line.startswith(b"diff --git "):
            current = _Section()
            sections.append(current)
            in_hunks = False
            rest = raw_line[len(b"diff --git ") :]
            halves = rest.split(b" b/", 1)
            if len(halves) == 2 and not rest.startswith(b'"'):
                current.old_path = _strip_prefix(halves[0])
                current.new_path = halves[1]
                current.old_guessed = True
                current.new_guessed = True
            continue
        if current is None:
            if raw_line.startswith(b"--- "):
                current = _Section()
                sections.append(current)
                in_hunks = False
            else:
                continue
        if raw_line.startswith(_HUNK_RE_PREFIX):
            in_hunks = True
            hunk_old_left, hunk_new_left = _hunk_line_budget(raw_line)
            current.hunk_lines.append(raw_line)
            continue
        if in_hunks:
            if raw_line[:1] in (b" ", b"+", b"-", b"\\") or raw_line == b"":
                current.hunk_lines.append(raw_line)
                # Count the declared lines down so the splitter knows where
                # a hunk body ends: `diff -ru` output has no `diff --git`
                # separators, and consuming the next file's `---` header as
                # a deletion line collapsed multi-file plain diffs into one
                # malformed section. The no-newline marker costs nothing.
                marker = raw_line[:1]
                if marker in (b" ", b"", b"-"):
                    hunk_old_left -= 1
                if marker in (b" ", b"", b"+"):
                    hunk_new_left -= 1
                if hunk_old_left <= 0 and hunk_new_left <= 0:
                    in_hunks = False
                    hunk_tail_ok = True
            continue
        if hunk_tail_ok:
            hunk_tail_ok = False
            if raw_line.startswith(b"\\"):
                # The final line's no-newline marker arrives after the
                # counted lines ran out; it still belongs to the hunk.
                current.hunk_lines.append(raw_line)
                continue
        if raw_line.startswith(b"old mode "):
            current.old_mode = raw_line[9:].decode("ascii", "replace")
        elif raw_line.startswith(b"new mode "):
            current.new_mode = raw_line[9:].decode("ascii", "replace")
        elif raw_line.startswith(b"new file mode "):
            current.kind_hint = ChangeKind.added
            current.new_mode = raw_line[14:].decode("ascii", "replace")
        elif raw_line.startswith(b"deleted file mode "):
            current.kind_hint = ChangeKind.deleted
            current.old_mode = raw_line[18:].decode("ascii", "replace")
        elif raw_line.startswith(b"similarity index "):
            # A junk or out-of-range similarity is a malformed header,
            # not a crash; recording the reason routes the section
            # through the malformed net below.
            raw_value = raw_line[17:].rstrip(b"%") or b"0"
            if raw_value.isdigit() and len(raw_value) <= 3 and int(raw_value) <= 100:
                current.similarity = int(raw_value)
            else:
                current.malformed = current.malformed or "unparseable similarity index"
        elif raw_line.startswith(b"rename from "):
            current.kind_hint = ChangeKind.renamed
            current.old_path = _unquote_c_style(raw_line[12:])
        elif raw_line.startswith(b"rename to "):
            current.new_path = _unquote_c_style(raw_line[10:])
        elif raw_line.startswith(b"copy from "):
            current.kind_hint = ChangeKind.copied
            current.old_path = _unquote_c_style(raw_line[10:])
        elif raw_line.startswith(b"copy to "):
            current.new_path = _unquote_c_style(raw_line[8:])
        elif raw_line.startswith(b"Binary files ") or raw_line == b"GIT binary patch":
            current.binary = True
        elif raw_line.startswith(b"@@@"):
            current.malformed = current.malformed or "combined (merge) diff is not supported"
        elif raw_line.startswith(b"--- "):
            if current.hunk_lines:
                # A `---` after a finished hunk body is the next file of a
                # plain multi-file diff (diff -ru): open its section.
                current = _Section()
                sections.append(current)
            path = _unquote_c_style(raw_line[4:].split(b"\t", 1)[0])
            if current.old_path is None or current.old_guessed or path == b"/dev/null":
                current.old_path = _strip_prefix(path)
                current.old_guessed = False
        elif raw_line.startswith(b"+++ "):
            path = _unquote_c_style(raw_line[4:].split(b"\t", 1)[0])
            if current.new_path is None or current.new_guessed or path == b"/dev/null":
                current.new_path = _strip_prefix(path)
                current.new_guessed = False
    return sections


def _parse_hunks(section: _Section) -> tuple[list[Hunk], int, int] | str:
    """Hunks plus (additions, deletions), or a malformed-reason string."""
    hunks: list[Hunk] = []
    additions = deletions = 0
    header: tuple[int, int, int, int, str | None] | None = None
    lines: list[LineRecord] = []

    def close() -> str | None:
        nonlocal header, lines
        if header is None:
            return None
        old_start, old_count, new_start, new_count, heading = header
        hunk = Hunk.model_construct(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            heading=heading,
            lines=tuple(lines),
        )
        got_old = sum(1 for line in lines if line.op is not LineOp.add)
        got_new = sum(1 for line in lines if line.op is not LineOp.delete)
        if got_old != old_count or got_new != new_count:
            return f"hunk counts disagree with body (-{old_count}/+{new_count})"
        hunks.append(hunk)
        header, lines = None, []
        return None

    for raw in section.hunk_lines:
        if raw.startswith(_HUNK_RE_PREFIX):
            problem = close()
            if problem:
                return problem
            try:
                marker_end = raw.index(b" @@", 3)
            except ValueError:
                return "unterminated hunk header"
            spans = raw[4:marker_end].split(b" +")
            if len(spans) != 2:
                return "unparseable hunk header"

            def span(text: bytes) -> tuple[int, int]:
                if b"," in text:
                    start_raw, count_raw = text.split(b",", 1)
                else:
                    start_raw, count_raw = text, b"1"
                # isdigit() refuses signs, so `--1` and `+2` fail here
                # instead of passing int() and crashing final validation.
                if not (start_raw.isdigit() and count_raw.isdigit()):
                    raise ValueError(text.decode("ascii", "replace"))
                return int(start_raw), int(count_raw)

            try:
                (old_start, old_count), (new_start, new_count) = span(spans[0]), span(spans[1])
            except ValueError:
                return "non-numeric hunk header"
            heading_raw = raw[marker_end + 3 :].strip()
            heading, _ = _display(heading_raw)
            header = (old_start, old_count, new_start, new_count, heading or None)
            continue
        if header is None:
            continue
        if raw.startswith(b"\\"):
            if lines:
                last = lines[-1]
                lines[-1] = LineRecord.model_construct(
                    op=last.op, text=last.text, text_b64=last.text_b64, no_newline=True
                )
            continue
        marker, body = (raw[:1], raw[1:]) if raw else (b" ", b"")
        op = {b" ": LineOp.context, b"+": LineOp.add, b"-": LineOp.delete}.get(marker)
        if op is None:
            return "unknown line marker in hunk"
        text, text_b64 = _display(body)
        lines.append(
            LineRecord.model_construct(op=op, text=text, text_b64=text_b64, no_newline=False)
        )
        if op is LineOp.add:
            additions += 1
        elif op is LineOp.delete:
            deletions += 1
    problem = close()
    if problem:
        return problem
    return hunks, additions, deletions


def _mode(value: str | None, fallback: FileMode = FileMode.regular) -> FileMode:
    try:
        return FileMode(value) if value else fallback
    except ValueError:
        return fallback


def _entry_type(mode: FileMode) -> EntryType:
    if mode is FileMode.symlink:
        return EntryType.symlink
    if mode is FileMode.gitlink:
        return EntryType.submodule
    return EntryType.file


def _side(path_raw: bytes, mode: FileMode) -> EntrySide:
    path, path_b64 = _display(path_raw)
    return EntrySide.model_construct(
        path=path,
        path_b64=path_b64,
        entry_type=_entry_type(mode),
        mode=mode,
        content=ContentRef.model_construct(
            kind=ContentRefKind.empty, oid=None, inline_b64=None, generation=None
        ),
        size=None,
    )


def _degraded_document(
    digest: str, truncated: bool, warnings: tuple[str, ...]
) -> ChangeSetDocument:
    """An empty, valid document that states why the input was refused."""
    return ChangeSetDocument.model_construct(
        schema_="file-diff-v1",
        schema_version=1,
        resolved=ResolvedComparison.model_construct(
            comparison_id=f"patch:{digest}",
            source=SourceInfo.model_construct(name="patch", version=None),
            kind="content",
            base_policy=BasePolicy.direct,
            left=SnapshotRef.model_construct(
                kind=SnapshotKind.patch, id=None, symbolic=None, generation=None
            ),
            right=SnapshotRef.model_construct(
                kind=SnapshotKind.patch, id=None, symbolic=None, generation=None
            ),
            options=DiffOptions.model_construct(
                context=3, rename_detection=True, rename_similarity=None, algorithm=None
            ),
            warnings=warnings,
        ),
        manifest=ChangeSetManifest.model_construct(
            files=(),
            totals=Totals.model_construct(files=0, additions=0, deletions=0, exact=False),
            truncated=truncated,
            cursor="parser-bounds" if truncated else None,
        ),
        patches={},
    )


def parse_unified_patch(data: bytes) -> ChangeSetDocument:
    """Whole-document parse; bounded, and total on malformed input."""
    truncated_input = len(data) > MAX_PATCH_BYTES
    if truncated_input:
        data = data[:MAX_PATCH_BYTES]
    digest = sha256(data).hexdigest()[:16]
    # Context-format (diff -c) hunks always open with a 15-asterisk line;
    # inside unified hunk bodies that byte sequence only occurs behind a
    # +/-/space prefix. Refuse the whole input as a value, not a crash.
    context_format = b"\n***************" in b"\n" + data
    sections = [] if context_format else _split_sections(data)
    section_truncated = len(sections) > MAX_FILE_SECTIONS
    sections = sections[:MAX_FILE_SECTIONS]

    files: list[FileChange] = []
    patches: dict[str, FilePatch] = {}
    total_add = total_del = 0
    exact = True
    dropped_sections = 0
    for index, section in enumerate(sections, start=1):
        file_id = f"f{index}"
        old_mode = _mode(section.old_mode)
        new_mode = _mode(section.new_mode, _mode(section.old_mode))
        kind = section.kind_hint or ChangeKind.modified
        if (
            kind is ChangeKind.modified
            and section.old_mode
            and section.new_mode
            and _entry_type(old_mode) is not _entry_type(new_mode)
        ):
            kind = ChangeKind.type_changed
        old_path = section.old_path
        new_path = section.new_path
        if old_path == b"/dev/null":
            kind, old_path = ChangeKind.added, None
        if new_path == b"/dev/null":
            kind, new_path = ChangeKind.deleted, None
        malformed = section.malformed
        hunks: list[Hunk] = []
        additions = deletions = 0
        if not section.binary and not malformed:
            parsed = _parse_hunks(section)
            if isinstance(parsed, str):
                malformed = parsed
            else:
                hunks, additions, deletions = parsed
        if kind is ChangeKind.added and old_path is not None:
            # `new file mode` beats the header guess: an added file has no
            # old side, whatever `diff --git a/x b/x` implied.
            old_path = None
        if kind is not ChangeKind.added and old_path is None:
            malformed = malformed or "missing old path"
        if kind is not ChangeKind.deleted and new_path is None:
            malformed = malformed or "missing new path"
        if kind in (ChangeKind.renamed, ChangeKind.copied) and section.similarity is None:
            # Degrading here keeps the section's neighbors intact; the
            # final-validation net would refuse the whole document.
            malformed = malformed or "rename or copy without a similarity index"

        if malformed:
            availability = Availability.unsupported
            exact = False
            hunks, additions, deletions = [], 0, 0
            # The document must stay format-valid even for junk sections:
            # coerce to modified with the known path mirrored to both
            # sides, or drop a section with no usable path at all.
            known = new_path if new_path is not None else old_path
            if known is None:
                dropped_sections += 1
                continue
            kind = ChangeKind.modified
            old_path = old_path if old_path is not None else known
            new_path = new_path if new_path is not None else known
        elif section.binary:
            # Line totals count text lines; a binary change contributes
            # none and does not make them estimates — git's shortstat
            # reports such totals plainly.
            availability = Availability.binary
        else:
            availability = Availability.ready
            total_add += additions
            total_del += deletions

        change = FileChange.model_construct(
            id=file_id,
            kind=kind,
            old=_side(old_path, old_mode) if old_path is not None else None,
            new=_side(new_path, new_mode) if new_path is not None else None,
            similarity=section.similarity
            if kind in (ChangeKind.renamed, ChangeKind.copied)
            else None,
            binary=section.binary,
            availability=availability,
            additions=additions if availability is Availability.ready else None,
            deletions=deletions if availability is Availability.ready else None,
        )
        files.append(change)
        if availability is Availability.ready:
            patches[file_id] = FilePatch.model_construct(
                file_id=file_id, hunks=tuple(hunks), truncated=False
            )

    truncated = truncated_input or section_truncated
    warnings: list[str] = []
    if truncated:
        warnings.append("input truncated at parser bounds")
    if context_format:
        warnings.append("context-format diff is not supported; regenerate with unified output")
    elif not sections and data.strip():
        # Nonempty input with no recognizable diff section: an empty manifest
        # alone would read as "no changes", which is not what happened.
        warnings.append("no diff sections recognized in this input")
    if dropped_sections:
        warnings.append(f"{dropped_sections} unparseable section(s) skipped")
    document = ChangeSetDocument.model_construct(
        schema_="file-diff-v1",
        schema_version=1,
        resolved=ResolvedComparison.model_construct(
            comparison_id=f"patch:{digest}",
            source=SourceInfo.model_construct(name="patch", version=None),
            kind="content",
            base_policy=BasePolicy.direct,
            left=SnapshotRef.model_construct(
                kind=SnapshotKind.patch, id=None, symbolic=None, generation=None
            ),
            right=SnapshotRef.model_construct(
                kind=SnapshotKind.patch, id=None, symbolic=None, generation=None
            ),
            options=DiffOptions.model_construct(
                context=3, rename_detection=True, rename_similarity=None, algorithm=None
            ),
            warnings=tuple(warnings),
        ),
        manifest=ChangeSetManifest.model_construct(
            files=tuple(files),
            totals=Totals.model_construct(
                files=len(files),
                additions=total_add if exact else None,
                deletions=total_del if exact else None,
                exact=exact,
            ),
            truncated=truncated,
            cursor="parser-bounds" if truncated else None,
        ),
        patches=patches,
    )
    # model_construct skipped validation for speed while assembling; the
    # emitted document must still be format-valid, so validate once here.
    # Totality is structural, not per-probe: an input this parser mapped
    # to an invalid document is by definition malformed input, so it
    # degrades to a warning-bearing empty document instead of raising on
    # the file-open path.
    from pydantic import ValidationError

    from metabrowser.diff.format import dump_document, validate_document

    try:
        return validate_document(dump_document(document))
    except (ValidationError, ValueError) as exc:
        reason = str(exc).splitlines()[0][:200]
        document = _degraded_document(
            digest, truncated, (*warnings, f"input could not be modeled: {reason}")
        )
        return validate_document(dump_document(document))
