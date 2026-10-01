// Focused invariants for View file (builtin_plugins/diff/diff-view-file.js): which
// sides of a change are files at a commit, what a path's address is built from, what
// each control is, and what the opener does with every answer of the pin route. The
// session in diff-view-file-session.js covers the same code on a real server's answers.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

// A check that waits on a promise the code under test never settles would end the
// process with nothing printed and status 0. Say so instead.
let finished = false;
process.on("exit", (code) => {
  if (!finished && code === 0) {
    process.stderr.write("diff view file: ended before its last check; a promise never settled\n");
    process.exitCode = 1;
  }
});

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function equal(label, actual, expected) {
  check(
    label,
    JSON.stringify(actual) === JSON.stringify(expected),
    `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
  );
}

const PARENT = "1".repeat(40);
const COMMIT = "2".repeat(40);
const SHA256 = "a".repeat(64);

function side(filePath, extra = {}) {
  return {
    path: filePath,
    entry_type: "file",
    mode: "100644",
    content: { kind: "git_object", oid: "3".repeat(40) },
    ...extra,
  };
}

function resolved(left, right, basePolicy = "first_parent") {
  return { base_policy: basePolicy, left, right };
}

const commits = resolved({ kind: "commit", id: PARENT }, { kind: "commit", id: COMMIT });

async function main() {
  const modulePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view-file.js");
  const { createViewFileOpener, describeViewFile, sidePathForAddress, viewFileSides } =
    await import(pathToFileURL(modulePath).href);

  // ── What an address is built from ───────────────────────────────────────
  equal("a UTF-8 path is itself", sidePathForAddress({ path: "docs/a.md" }), "docs/a.md");
  equal(
    "a name that is not UTF-8 is its bytes, not the replacement characters shown",
    [...sidePathForAddress({ path: "d\ufffd/f", path_b64: "ZOkvZg==" })],
    [0x64, 0xe9, 0x2f, 0x66],
  );
  equal("bytes that are not base64 are no path", sidePathForAddress({ path_b64: "%%%" }), null);
  equal("an entry with no path has none", sidePathForAddress({}), null);

  // ── Which sides are files at a commit ───────────────────────────────────
  const modified = { kind: "modified", old: side("a.txt"), new: side("a.txt") };
  equal(
    "a modified file has both sides, base first",
    viewFileSides(modified, commits).map((entry) => [
      entry.side,
      entry.role,
      entry.commit,
      entry.path,
      entry.address,
    ]),
    [
      ["base", "parent", PARENT, "a.txt", "a.txt"],
      ["head", "head", COMMIT, "a.txt", "a.txt"],
    ],
  );
  equal(
    "an added file has only its head side",
    viewFileSides({ kind: "added", new: side("new.txt") }, commits).map((entry) => entry.side),
    ["head"],
  );
  equal(
    "a deleted file has only its base side",
    viewFileSides({ kind: "deleted", old: side("old.txt") }, commits).map((entry) => entry.side),
    ["base"],
  );
  for (const kind of ["renamed", "copied"]) {
    equal(
      `a ${kind} file's base side is its old path`,
      viewFileSides(
        { kind, similarity: 90, old: side("from.txt"), new: side("to.txt") },
        commits,
      ).map((entry) => [entry.side, entry.path]),
      [
        ["base", "from.txt"],
        ["head", "to.txt"],
      ],
    );
  }
  // A submodule's side is a commit of another repository, and a symbolic link's side
  // would open its target rather than the link text the diff shows.
  const gitlink = { entry_type: "submodule", mode: "160000" };
  const symlink = { entry_type: "symlink", mode: "120000" };
  equal(
    "a submodule has no side to open",
    viewFileSides(
      { kind: "modified", old: side("vendor/lib", gitlink), new: side("vendor/lib", gitlink) },
      commits,
    ),
    [],
  );
  equal(
    "a symbolic link has no side to open",
    viewFileSides(
      { kind: "modified", old: side("link", symlink), new: side("link", symlink) },
      commits,
    ),
    [],
  );
  equal(
    "a file that became a link or a submodule keeps only its file side",
    [symlink, gitlink].map((other) =>
      viewFileSides(
        { kind: "type_changed", old: side("thing"), new: side("thing", other) },
        commits,
      ).map((entry) => entry.side),
    ),
    [["base"], ["base"]],
  );
  equal(
    "an entry of no known type has no side",
    viewFileSides({ kind: "added", new: side("x", { entry_type: undefined }) }, commits),
    [],
  );
  equal(
    "a comparison from a merge base calls its left side the base",
    viewFileSides(
      modified,
      resolved({ kind: "commit", id: PARENT }, { kind: "commit", id: COMMIT }, "merge_base"),
    ).map((entry) => entry.role),
    ["base", "head"],
  );
  equal(
    "a direct comparison's left side is a base too",
    viewFileSides(
      modified,
      resolved({ kind: "commit", id: PARENT }, { kind: "commit", id: COMMIT }, "direct"),
    )[0].role,
    "base",
  );
  equal(
    "a root commit's empty side opens nothing",
    viewFileSides(modified, resolved({ kind: "empty" }, { kind: "commit", id: COMMIT })).map(
      (entry) => entry.side,
    ),
    ["head"],
  );
  equal(
    "a SHA-256 commit ID is a commit ID",
    viewFileSides(
      modified,
      resolved({ kind: "commit", id: SHA256 }, { kind: "commit", id: COMMIT }),
    )[0].commit,
    SHA256,
  );
  for (const [label, snapshot] of [
    ["a patch", { kind: "patch" }],
    ["a working tree", { kind: "worktree", id: COMMIT }],
    ["the index", { kind: "index" }],
    ["a tree", { kind: "tree", id: COMMIT }],
    ["an abbreviated commit ID", { kind: "commit", id: COMMIT.slice(0, 12) }],
    ["revision syntax", { kind: "commit", id: `${COMMIT.slice(0, 38)}^1` }],
    ["a commit with no ID", { kind: "commit" }],
    ["nothing", null],
  ]) {
    equal(
      `${label} is not a commit a file opens at`,
      viewFileSides(modified, resolved(snapshot, snapshot)),
      [],
    );
  }

  // ── What each control is ────────────────────────────────────────────────
  const [base, head] = viewFileSides(modified, commits);
  const address = "/view/g1-YS50eHQ";
  equal("a side at the page's commit is a link", describeViewFile(head, address, { pin: COMMIT }), {
    side: "head",
    commit: COMMIT,
    path: "a.txt",
    href: address,
    mode: "link",
    label: "View file",
    detail: `Open a.txt at ${COMMIT.slice(0, 12)}, the commit this page shows`,
  });
  equal(
    "a side at another commit is a switch, and says so",
    describeViewFile(base, address, { pin: COMMIT }),
    {
      side: "base",
      commit: PARENT,
      path: "a.txt",
      href: address,
      mode: "switch",
      label: "View at parent",
      detail: `Switch to ${PARENT.slice(0, 12)} and open a.txt`,
    },
  );
  equal(
    "on the parent's page the sides swap",
    [
      describeViewFile(base, address, { pin: PARENT }).mode,
      describeViewFile(head, address, { pin: PARENT }).mode,
    ],
    ["link", "switch"],
  );

  // ── The opener ──────────────────────────────────────────────────────────
  function page(answers, extra = {}) {
    const log = { asked: [], navigated: [], listening: 0, released: 0 };
    let restored = () => {};
    const opener = createViewFileOpener(
      {
        pin: COMMIT,
        href: (name) => (name === "" ? null : `/view/<${name}>`),
        async switchPin(body) {
          log.asked.push(body);
          const next = answers.shift();
          if (next instanceof Error) {
            throw next;
          }
          return next;
        },
        navigate: (href) => log.navigated.push(href),
        onRestored(callback) {
          restored = callback;
          log.listening += 1;
          return () => {
            log.listening -= 1;
          };
        },
        ...extra,
      },
      { released: () => (log.released += 1) },
    );
    return { log, opener, restore: () => restored() };
  }

  equal(
    "a side whose path has no address gets no control",
    page([])
      .opener.actions({ kind: "modified", old: side(""), new: side("a.txt") }, commits)
      .map((action) => [action.side, action.href]),
    [["head", "/view/<a.txt>"]],
  );
  const toParent = page([]).opener.actions(modified, commits)[0];
  equal(
    "the old side's control switches",
    [toParent.mode, toParent.href],
    ["switch", "/view/<a.txt>"],
  );

  const followed = page([
    { status: 200, body: { changed: true, view_href: "/view/g1-elsewhere" } },
  ]);
  equal(
    "a switch goes where the server says",
    [await followed.opener.switchTo(toParent), followed.log.asked, followed.log.navigated],
    [
      { kind: "navigated", href: "/view/g1-elsewhere" },
      [{ oid: PARENT, view: "/view/<a.txt>" }],
      ["/view/g1-elsewhere"],
    ],
  );
  for (const [label, body] of [
    ["no address", { changed: true }],
    ["an address off /view/", { changed: true, view_href: "https://example.invalid/" }],
    ["an address that is not a string", { changed: true, view_href: 7 }],
    ["no body", null],
  ]) {
    const asked = page([{ status: 200, body }]);
    equal(
      `an answer with ${label} goes to the address asked for`,
      await asked.opener.switchTo(toParent),
      { kind: "navigated", href: "/view/<a.txt>" },
    );
  }
  const at = PARENT.slice(0, 12);
  for (const [status, body, message] of [
    [
      202,
      { code: "selection_pending" },
      `The mirror is fetching ${at}; try again when the fetch ends.`,
    ],
    [
      404,
      { code: "selection_not_found" },
      `Commit ${at} is not in the mirror, and its origin does not have it.`,
    ],
    [
      502,
      { code: "selection_fetch_failed" },
      `Commit ${at} is not in the mirror, and fetching it failed.`,
    ],
    [
      409,
      { code: "unsupported_for_subject" },
      `Could not switch to ${at} (unsupported_for_subject).`,
    ],
    [415, { code: "invalid_request" }, `Could not switch to ${at} (invalid_request).`],
    [500, null, `Could not switch to ${at} (HTTP 500).`],
    [403, "forbidden", `Could not switch to ${at} (HTTP 403).`],
  ]) {
    const refused = page([
      { status, body },
      { status: 200, body: {} },
    ]);
    equal(
      `HTTP ${status} is refused in words and the page stays`,
      [await refused.opener.switchTo(toParent), refused.log.navigated, refused.opener.switching()],
      [{ kind: "refused", message }, [], false],
    );
    equal(
      `and after HTTP ${status} the next attempt runs`,
      (await refused.opener.switchTo(toParent)).kind,
      "navigated",
    );
  }
  const broken = page([new TypeError("fetch failed"), { status: 200, body: {} }]);
  equal("a request that fails says so", await broken.opener.switchTo(toParent), {
    kind: "refused",
    message: "The switch request failed.",
  });
  equal("and the next attempt runs", (await broken.opener.switchTo(toParent)).kind, "navigated");

  // One switch at a time; the hold outlasts a switch the server made, while the page
  // leaves, and ends when the browser brings the page back.
  let release = () => {};
  const slow = page([], {
    switchPin(body) {
      slow.log.asked.push(body);
      return new Promise((resolve) => {
        release = resolve;
      });
    },
  });
  const first = slow.opener.switchTo(toParent);
  equal("a second switch while one runs is held", await slow.opener.switchTo(toParent), {
    kind: "busy",
  });
  equal("and asks the server nothing", slow.log.asked.length, 1);
  release({ status: 200, body: { view_href: address } });
  equal("the first one finishes", (await first).kind, "navigated");
  equal(
    "the page is leaving: nothing more is asked of it",
    [await slow.opener.switchTo(toParent), slow.log.asked.length, slow.opener.switching()],
    [{ kind: "busy" }, 1, true],
  );
  slow.restore();
  equal("a page brought back lets go", [slow.opener.switching(), slow.log.released], [false, 1]);
  const again = slow.opener.switchTo(toParent);
  equal("and switches again", slow.log.asked.length, 2);
  release({ status: 404, body: { code: "selection_not_found" } });
  equal(
    "a refusal ends its own hold",
    [(await again).kind, slow.opener.switching()],
    ["refused", false],
  );
  slow.restore();
  equal("a restore with nothing held releases nothing", slow.log.released, 1);

  // A diff unmounted while its switch was on the way takes the page nowhere.
  const gone = page([], {
    switchPin(body) {
      gone.log.asked.push(body);
      return new Promise((resolve) => {
        release = resolve;
      });
    },
  });
  const late = gone.opener.switchTo(toParent);
  gone.opener.dispose();
  release({ status: 200, body: { view_href: address } });
  equal(
    "a switch answered after the diff was unmounted does not navigate",
    [await late, gone.log.navigated, gone.log.listening],
    [{ kind: "abandoned" }, [], 0],
  );
  equal(
    "and an unmounted diff asks nothing",
    [await gone.opener.switchTo(toParent), gone.log.asked.length],
    [{ kind: "abandoned" }, 1],
  );
  const failing = page([], {
    switchPin() {
      return new Promise((_resolve, reject) => {
        release = reject;
      });
    },
  });
  const failed = failing.opener.switchTo(toParent);
  failing.opener.dispose();
  release(new TypeError("fetch failed"));
  equal("nor does a failure after unmounting say anything", await failed, { kind: "abandoned" });

  finished = true;
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("diff view file OK\n");
}

main().catch((error) => {
  finished = true;
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
