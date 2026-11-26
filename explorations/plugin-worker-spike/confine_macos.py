"""Spike: confine a child process on macOS with a ``sandbox-exec`` profile.

The macOS counterpart of ``confine_linux.py``, taking the same policy. Where the Linux
launcher is an interpreter that confines itself and then execs the child, macOS's is the
system's: the prefix is ``/usr/bin/sandbox-exec -p PROFILE``, and this module only
renders ``PROFILE`` from the policy. The profile denies everything it does not allow, as
``macos_profile`` in ``src/metabrowser/builtin_plugins/pdf/preview_isolation.py`` does
for the PDF render child, and starts from that profile's grants:

- metadata of any path, which an interpreter's path searches need and which says only
  whether a name exists;
- reading the policy's ``read`` roots and the system's libraries, and mapping code from
  them;
- reading the machine's settings through ``sysctl``;
- exec of the programs under the read roots, and fork, unless ``processes`` is ``none``,
  in which case only the interpreter named by ``exec`` may be exec'd, once, by
  ``sandbox-exec`` itself;
- writing the policy's ``write`` roots, and ``/dev/null``;
- signals and process information for the child itself and the processes it starts.

``network`` set to ``internet`` adds outbound IP and the system resolver's socket; a
Unix socket elsewhere stays refused. ``mach`` names Mach services the child may look up,
which ``getpwuid`` and the resolver need on macOS and Linux has no counterpart for.
The profile only renders named grants. The probe reports denials for inspection.


Usage:
    confine_macos.py probe
    confine_macos.py profile POLICY_JSON
    confine_macos.py run POLICY_JSON -- ARGV...

``POLICY_JSON`` is ``{"read": [paths], "write": [paths], "network": "none" | "internet",
"processes": "confined" | "none", "exec": [paths], "mach": [names]}``. As on Linux, ``network`` defaults to ``none`` and ``processes`` to
``confined``; ``exec`` defaults to ``ARGV[0]`` under ``run``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable
from typing import Any

SANDBOX_EXEC = "/usr/bin/sandbox-exec"

# The system's read-only locations every child reads: its libraries, the dyld shared
# cache, the time zone database `time.localtime` opens, and the shells and tools a
# confined child may start. The PDF profile's set, less the fonts, plus the last three.
SYSTEM_READ_ROOTS = (
    "/System",
    "/usr/lib",
    "/private/var/db/dyld",
    "/private/var/db/timezone",
    "/usr/share/zoneinfo",
    "/bin",
    "/usr/bin",
)
SYSTEM_CODE_ROOTS = ("/System", "/usr/lib")
SYSTEM_READ_FILES = ("/", "/dev/null", "/dev/random", "/dev/urandom", "/private/etc/localtime")
# The system resolver's socket, which `getaddrinfo` connects to for every name.
RESOLVER_SOCKET = "/private/var/run/mDNSResponder"


def sbpl_string(text: str) -> str:
    """*text* as a sandbox profile string literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _paths(kind: str, paths: Iterable[str]) -> str:
    return " ".join(f"({kind} {sbpl_string(path)})" for path in paths)


def _with_real_paths(paths: Iterable[str]) -> list[str]:
    """Each path as given and as the kernel resolves it, since the profile matches the
    resolved path and ``/tmp``, ``/var``, and ``/etc`` are links into ``/private``."""
    found = {str(path) for path in paths}
    return sorted(found | {os.path.realpath(path) for path in found})


def profile(policy: dict[str, Any]) -> str:
    """The ``sandbox-exec`` profile for *policy*."""
    reads = _with_real_paths(policy.get("read", []))
    writes = _with_real_paths(policy.get("write", []))
    processes = str(policy.get("processes", "confined"))
    network = str(policy.get("network", "none"))
    rules = ["(version 1)", "(deny default)"]
    read_rule = _paths("subpath", [*reads, *SYSTEM_READ_ROOTS])
    rules += [
        "(allow file-read-metadata)",
        f"(allow file-read* {read_rule} {_paths('literal', SYSTEM_READ_FILES)})",
        f"(allow file-map-executable {_paths('subpath', [*reads, *SYSTEM_CODE_ROOTS])})",
        "(allow sysctl-read)",
        '(allow file-write* (literal "/dev/null"))',
        "(allow signal (target self))",
        "(allow process-info* (target self))",
    ]
    if writes:
        rules.append(f"(allow file-write* {_paths('subpath', writes)})")
    executables = _with_real_paths(policy.get("exec", []))
    if executables:
        rules.append(f"(allow process-exec {_paths('literal', executables)})")
    if processes == "confined":
        rules += [
            "(allow process-fork)",
            f"(allow process-exec {_paths('subpath', [*reads, *SYSTEM_READ_ROOTS])})",
            "(allow signal (target same-sandbox))",
            "(allow process-info* (target same-sandbox))",
        ]
    if network == "internet":
        rules += [
            '(allow network-outbound (remote ip "*:*") (remote ip "localhost:*"))',
            f"(allow network-outbound (literal {sbpl_string(RESOLVER_SOCKET)}))",
            "(allow system-socket)",
        ]
    mach = sorted(set(policy.get("mach", [])))
    if mach:
        rules.append(f"(allow mach-lookup {_paths('global-name', mach)})")
    return "\n".join(rules)


def prefix(policy: dict[str, Any]) -> list[str]:
    """The command prefix that runs what follows it under *policy*."""
    return [SANDBOX_EXEC, "-p", profile(policy)]


def probe() -> dict[str, Any]:
    """Whether ``sandbox-exec`` is here and applies a deny-default profile, which a
    process that is itself sandboxed may not be allowed to do."""
    report: dict[str, Any] = {
        "macos": _macos_version(),
        "sandbox_exec": os.access(SANDBOX_EXEC, os.X_OK),
    }
    if not report["sandbox_exec"]:
        return {**report, "applies": False}
    command = [*prefix({"exec": ["/usr/bin/true"], "processes": "none"}), "/usr/bin/true"]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    report["applies"] = done.returncode == 0
    if done.returncode != 0:
        report["refusal"] = (done.stderr.strip().splitlines() or ["no output"])[-1]
    return report


def _macos_version() -> str:
    try:
        done = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True)
    except OSError:
        return "unknown"
    return done.stdout.strip() or "unknown"


def main() -> None:
    if sys.argv[1:2] == ["probe"]:
        print(json.dumps(probe()))
        return
    if sys.argv[1:2] == ["profile"] and len(sys.argv) == 3:
        print(profile(json.loads(sys.argv[2])))
        return
    if sys.argv[1:2] != ["run"] or "--" not in sys.argv:
        raise SystemExit(__doc__)
    policy: dict[str, Any] = json.loads(sys.argv[2])
    command = sys.argv[sys.argv.index("--") + 1 :]
    policy.setdefault("exec", [command[0]])
    os.execv(SANDBOX_EXEC, [*prefix(policy), *command])


if __name__ == "__main__":
    main()
