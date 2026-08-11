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

PER_FILE_CAP_BYTES = 1_700_000
TOTAL_CAP_BYTES = 3_000_000


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
    if total > TOTAL_CAP_BYTES:
        print(f"vendored total over cap: {total} bytes")
        return 1
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Vendored {len(ENTRIES)} assets ({total} bytes) into {VENDOR_DIR}")
    return 0


def check() -> list[str]:
    """Return problems; empty list means the committed vendor tree is exact."""
    problems: list[str] = []
    if not MANIFEST_PATH.is_file():
        return [f"missing {MANIFEST_PATH}"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pins = _pinned_versions()
    expected_dests = {entry.dest for entry in ENTRIES}
    if set(manifest) != expected_dests:
        problems.append(f"manifest entries {sorted(manifest)} != expected {sorted(expected_dests)}")
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
