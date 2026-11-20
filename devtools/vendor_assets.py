"""Vendor browser third-party assets from lockfile-verified npm packages.

Every third-party file the browser loads is copied out of ``node_modules``
(installed by ``npm ci`` under the repository's exact-pin, cool-off, and
``ignore-scripts`` policy) into ``src/metabrowser/static/vendor/`` and
committed, so the served page has no external origins and works offline.

``--write`` refreshes the vendored files, their license texts, and
``manifest.json`` (versions + SHA-256 digests). ``--check`` verifies the
committed files match the manifest byte-for-byte and the manifest versions
match ``package.json``; it needs no ``node_modules`` and runs in the test
suite. Size caps keep an upgraded dependency from silently bloating the
wheel.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO / "src" / "metabrowser" / "static" / "vendor"
MANIFEST_PATH = VENDOR_DIR / "manifest.json"
NODE_MODULES = REPO / "node_modules"

# The largest vendored file is Mermaid 12.3.0's ELK layout chunk, 1,620,399 bytes.
PER_FILE_CAP_BYTES = 1_700_000
# Measured 2026-11-18: the flat entries total 432,092 bytes and Mermaid 12.3.0's ESM
# tree 5,435,568 (a 30,936-byte entry and 105 chunks), 5,867,660 in all. Only the
# Mermaid entry's imports of the chunks a document's diagram types need are ever
# fetched, and only for a document that has a diagram; the cap bounds the wheel.
TOTAL_CAP_BYTES = 6_000_000


@dataclass(frozen=True)
class VendorEntry:
    package: str
    source: str
    dest: str
    license_source: str


ENTRIES: tuple[VendorEntry, ...] = (
    VendorEntry("mustache", "mustache.min.js", "mustache.min.js", "LICENSE"),
    VendorEntry("@highlightjs/cdn-assets", "highlight.min.js", "highlight.min.js", "LICENSE"),
    VendorEntry(
        "@highlightjs/cdn-assets",
        "languages/ini.min.js",
        "highlight-toml.min.js",
        "LICENSE",
    ),
    VendorEntry("chart.js", "dist/chart.umd.min.js", "chart.umd.min.js", "LICENSE.md"),
    VendorEntry(
        "chartjs-plugin-annotation",
        "dist/chartjs-plugin-annotation.min.js",
        "chartjs-plugin-annotation.min.js",
        "LICENSE.md",
    ),
    VendorEntry(
        "chartjs-adapter-date-fns",
        "dist/chartjs-adapter-date-fns.bundle.min.js",
        "chartjs-adapter-date-fns.bundle.min.js",
        "LICENSE.md",
    ),
)


@dataclass(frozen=True)
class VendorTree:
    """A package directory vendored file by file, for a build that loads its own parts.

    Every file matching *include* under *source* is copied to the same relative path
    under *dest*, and each is its own manifest record carrying ``tree``. The tree is
    replaced whole on ``--write``, so a chunk an upgrade dropped does not linger, and
    ``--check`` refuses a file under *dest* the manifest does not list.

    A build that bundles its runtime dependencies ships their code, and a minified chunk
    keeps some of their license comments and drops others (Mermaid's ELK chunk keeps
    none), so ``--write`` also collects the license text of every package in the
    production dependency closure into ``licenses/<package>.bundled.txt``.
    """

    package: str
    source: str
    dest: str
    license_source: str
    include: tuple[str, ...]


TREES: tuple[VendorTree, ...] = (
    # Mermaid's ESM build: an entry that imports per-diagram-type chunks by relative
    # specifiers, so the tree works from any URL prefix with no import map. Source maps
    # are left out. 12.3.0 is the release GitHub's renderer bundle embeds (2026-11-18).
    VendorTree(
        "mermaid",
        "dist",
        "mermaid",
        "LICENSE",
        ("mermaid.esm.min.mjs", "chunks/mermaid.esm.min/*.mjs"),
    ),
)


def _tree_files(tree: VendorTree) -> list[Path]:
    root = NODE_MODULES / tree.package / tree.source
    files: set[Path] = set()
    for pattern in tree.include:
        files.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(files)


_LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING")


def _resolve(name: str, parent: Path) -> Path | None:
    """The directory npm resolves *name* to from the package at *parent*."""
    here = parent
    while True:
        candidate = here / "node_modules" / name
        if (candidate / "package.json").is_file():
            return candidate
        if here == REPO or here == here.parent:
            return None
        here = here.parent


# Mermaid bundles elkjs, dual-licensed "EPL-2.0 OR GPL-3.0-or-later", and NOTICE.md elects
# GPL-3.0-or-later, the one compatible with Metabrowser's AGPL. elkjs ships only the EPL
# text, so the elected text is committed beside the generated ones: the FSF's canonical
# gpl-3.0.txt, by its SHA-256. `--write` leaves it in place.
ELKJS_ELECTED_LICENSE = VENDOR_DIR / "licenses" / "elkjs.GPL-3.0.txt"
ELKJS_ELECTED_LICENSE_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"


def _bundled_licenses(package: str) -> str:
    """Every license text in *package*'s production dependency closure, in name order."""
    seen: dict[str, Path] = {}
    pending = [NODE_MODULES / package]
    while pending:
        directory = pending.pop()
        meta = json.loads((directory / "package.json").read_text(encoding="utf-8"))
        for name in meta.get("dependencies", {}):
            found = _resolve(name, directory)
            if found is None:
                raise SystemExit(f"{package}: dependency {name} is not installed")
            key = f"{name}@{_installed_meta(found)['version']}"
            if key not in seen:
                seen[key] = found
                pending.append(found)
    sections: list[str] = []
    for key in sorted(seen):
        directory = seen[key]
        files = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.name.upper().startswith(_LICENSE_NAMES)
        )
        declared = _installed_meta(directory).get("license", "not declared")
        body = "\n".join(path.read_text(encoding="utf-8").strip() for path in files)
        sections.append(
            f"{key} (license: {declared})\n\n"
            + (body or "The package ships no license file; its declared license applies.")
        )
    separator = "\n\n" + "-" * 72 + "\n\n"
    return separator + separator.join(sections) + "\n"


def _installed_meta(directory: Path) -> dict[str, object]:
    return dict(json.loads((directory / "package.json").read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned_versions() -> dict[str, str]:
    package_json = json.loads((REPO / "package.json").read_text(encoding="utf-8"))
    return dict(package_json.get("devDependencies", {}))


def _installed_version(package: str) -> str:
    meta = json.loads((NODE_MODULES / package / "package.json").read_text(encoding="utf-8"))
    return str(meta["version"])


def write() -> int:
    pins = _pinned_versions()
    licenses_dir = VENDOR_DIR / "licenses"
    licenses_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, str | int]] = {}
    total = 0
    for entry in ENTRIES:
        src = NODE_MODULES / entry.package / entry.source
        dest = VENDOR_DIR / entry.dest
        shutil.copyfile(src, dest)
        size = dest.stat().st_size
        total += size
        if size > PER_FILE_CAP_BYTES:
            print(f"vendored file over per-file cap: {entry.dest} ({size} bytes)")
            return 1
        version = _installed_version(entry.package)
        if pins.get(entry.package) != version:
            print(f"{entry.package}: installed {version} != pinned {pins.get(entry.package)}")
            return 1
        license_dest = licenses_dir / f"{entry.package.replace('/', '__')}.txt"
        shutil.copyfile(NODE_MODULES / entry.package / entry.license_source, license_dest)
        manifest[entry.dest] = {
            "package": entry.package,
            "version": version,
            "source": entry.source,
            "sha256": _sha256(dest),
            "bytes": size,
        }
    for tree in TREES:
        version = _installed_version(tree.package)
        if pins.get(tree.package) != version:
            print(f"{tree.package}: installed {version} != pinned {pins.get(tree.package)}")
            return 1
        root = NODE_MODULES / tree.package / tree.source
        dest_root = VENDOR_DIR / tree.dest
        if dest_root.exists():
            shutil.rmtree(dest_root)
        for src in _tree_files(tree):
            relative = src.relative_to(root).as_posix()
            dest = dest_root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            size = dest.stat().st_size
            total += size
            if size > PER_FILE_CAP_BYTES:
                print(f"vendored file over per-file cap: {tree.dest}/{relative} ({size} bytes)")
                return 1
            manifest[f"{tree.dest}/{relative}"] = {
                "package": tree.package,
                "version": version,
                "source": f"{tree.source}/{relative}",
                "sha256": _sha256(dest),
                "bytes": size,
                "tree": tree.dest,
            }
        license_dest = licenses_dir / f"{tree.package.replace('/', '__')}.txt"
        shutil.copyfile(NODE_MODULES / tree.package / tree.license_source, license_dest)
        bundled = licenses_dir / f"{tree.package.replace('/', '__')}.bundled.txt"
        bundled.write_text(
            f"Licenses of the production dependencies of {tree.package} {version}, whose build"
            " bundles their code; type-only packages among them ship no code."
            + _bundled_licenses(tree.package),
            encoding="utf-8",
        )
    if total > TOTAL_CAP_BYTES:
        print(f"vendored total over cap: {total} bytes")
        return 1
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Vendored {len(manifest)} assets ({total} bytes) into {VENDOR_DIR}")
    return 0


def check() -> list[str]:
    """Return problems; empty list means the committed vendor tree is exact."""
    problems: list[str] = []
    if not MANIFEST_PATH.is_file():
        return [f"missing {MANIFEST_PATH}"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pins = _pinned_versions()
    tree_dests = {tree.dest for tree in TREES}
    expected_dests = {entry.dest for entry in ENTRIES}
    flat = {dest for dest, record in manifest.items() if record.get("tree") is None}
    if flat != expected_dests:
        problems.append(f"manifest entries {sorted(flat)} != expected {sorted(expected_dests)}")
    for tree in TREES:
        listed = {dest for dest, record in manifest.items() if record.get("tree") == tree.dest}
        if not listed:
            problems.append(f"manifest lists no files for vendored tree {tree.dest}")
        tree_root = VENDOR_DIR / tree.dest
        on_disk = {
            path.relative_to(VENDOR_DIR).as_posix()
            for path in tree_root.rglob("*")
            if path.is_file()
        }
        for extra in sorted(on_disk - listed):
            problems.append(f"vendored file not in manifest: {extra}")
    for dest, record in manifest.items():
        tree = record.get("tree")
        if tree is not None and tree not in tree_dests:
            problems.append(f"{dest}: unknown vendored tree {tree}")
    total = 0
    for dest, record in manifest.items():
        path = VENDOR_DIR / dest
        if not path.is_file():
            problems.append(f"vendored file missing: {dest}")
            continue
        digest = _sha256(path)
        total += path.stat().st_size
        if digest != record.get("sha256"):
            problems.append(f"hash mismatch for {dest}: run `make vendor-assets`")
        pinned = pins.get(str(record.get("package")))
        if pinned != record.get("version"):
            problems.append(
                f"{dest}: manifest version {record.get('version')} != package.json pin {pinned}"
            )
        license_path = (
            VENDOR_DIR / "licenses" / f"{str(record.get('package')).replace('/', '__')}.txt"
        )
        if not license_path.is_file():
            problems.append(f"missing license text for {record.get('package')}")
    for tree in TREES:
        bundled = VENDOR_DIR / "licenses" / f"{tree.package.replace('/', '__')}.bundled.txt"
        if not bundled.is_file():
            problems.append(f"missing bundled license texts for {tree.package}")
    elected = ELKJS_ELECTED_LICENSE
    if not elected.is_file() or _sha256(elected) != ELKJS_ELECTED_LICENSE_SHA256:
        problems.append(f"{ELKJS_ELECTED_LICENSE.name}: not the GPL-3.0 text NOTICE.md elects")
    if total > TOTAL_CAP_BYTES:
        problems.append(f"vendored total over cap: {total} bytes")
    return problems


def main() -> int:
    if "--write" in sys.argv:
        return write()
    problems = check()
    for problem in problems:
        print(problem)
    if not problems:
        print("Vendored-asset checks passed.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
