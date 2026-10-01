// Focused invariants for View file (builtin_plugins/diff/diff-view-file.js): which
// sides of a change are files at a commit, how a path becomes its GitPath wire, what
// each control is, and what the opener does with every answer of the pin route. The
// session in diff-view-file-session.js covers the same code on a real server's answers.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

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
  const { createViewFileOpener, describeViewFile, sidePathWire, viewFileSides } = await import(
    pathToFileURL(modulePath).href
  );

  // ── The wire of a path ──────────────────────────────────────────────────
  equal(
    "a path's wire is one token per segment",
    sidePathWire({ path: "src/app.py" }),
    "g1-c3Jj/g1-YXBwLnB5",
  );
  equal(
    "a name outside ASCII is its UTF-8 bytes",
    sidePathWire({ path: "docs/雪.md" }),
    "g1-ZG9jcw/g1-6ZuqLm1k",
  );
  equal("base64url, unpadded: + and / never appear", sidePathWire({ path: "a?>" }), "g1-YT8-");
  equal(
    "a name that is not UTF-8 uses its bytes, not the replacement characters shown",
    sidePathWire({ path: "latin1-\ufffd.txt", path_b64: "bGF0aW4xLekudHh0" }),
    "g1-bGF0aW4xLekudHh0",
  );
  equal(
    "bytes split at the slash byte only",
    sidePathWire({
      path: "d\ufffd/f",
      path_b64: Buffer.from([0x64, 0xe9, 0x2f, 0x66]).toString("base64"),
    }),
    "g1-ZOk/g1-Zg",
  );
  for (const [label, bad] of [
    ["an empty path", { path: "" }],
    ["a leading slash", { path: "/a" }],
    ["a trailing slash", { path: "a/" }],
    ["an empty segment", { path: "a//b" }],
    ["bytes that are not base64", { path: "x", path_b64: "%%%" }],
    ["no path at all", {}],
  ]) {
    equal(`${label} has no wire`, sidePathWire(bad), null);
  }

  // ── Which sides are files at a commit ───────────────────────────────────
  const modified = { kind: "modified", old: side("a.txt"), new: side("a.txt") };
  equal(
    "a modified file has both sides, base first",
    viewFileSides(modified, commits).map((entry) => [
      entry.side,
      entry.role,
      entry.commit,
      entry.path,
    ]),
    [
      ["base", "parent", PARENT, "a.txt"],
      ["head", "head", COMMIT, "a.txt"],
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
  equal(
    "a side whose path has no wire is left out",
    viewFileSides({ kind: "modified", old: side(""), new: side("a.txt") }, commits).map(
      (entry) => entry.side,
    ),
    ["head"],
  );

  // ── What each control is ────────────────────────────────────────────────
  const [base, head] = viewFileSides(modified, commits);
  equal("a side at the page's commit is a link", describeViewFile(head, { pin: COMMIT }), {
    side: "head",
    commit: COMMIT,
    path: "a.txt",
    wire: "g1-YS50eHQ",
    mode: "link",
    label: "View file",
    detail: `Open a.txt at ${COMMIT.slice(0, 12)}, the commit this page shows`,
  });
  equal(
    "a side at another commit is a switch, and says so",
    describeViewFile(base, { pin: COMMIT }),
    {
      side: "base",
      commit: PARENT,
      path: "a.txt",
      wire: "g1-YS50eHQ",
      mode: "switch",
      label: "View at parent",
      detail: `Switch to ${PARENT.slice(0, 12)} and open a.txt`,
    },
  );
  equal(
    "on the parent's page the sides swap",
    [describeViewFile(base, { pin: PARENT }).mode, describeViewFile(head, { pin: PARENT }).mode],
    ["link", "switch"],
  );

  // ── The opener ──────────────────────────────────────────────────────────
  function host(answers) {
    const log = { asked: [], navigated: [] };
    return {
      log,
      opener: createViewFileOpener({
        pin: COMMIT,
        href: (wire) => `/view/${wire}`,
        async switchPin(body) {
          log.asked.push(body);
          const next = answers.shift();
          if (next instanceof Error) {
            throw next;
          }
          return next;
        },
        navigate: (href) => log.navigated.push(href),
      }),
    };
  }
  const toParent = describeViewFile(base, { pin: COMMIT });
  const address = "/view/g1-YS50eHQ";

  const followed = host([
    { status: 200, body: { changed: true, view_href: "/view/g1-elsewhere" } },
  ]);
  equal(
    "a switch goes where the server says",
    [await followed.opener.switchTo(toParent), followed.log],
    [
      { kind: "navigated", href: "/view/g1-elsewhere" },
      { asked: [{ oid: PARENT, view: address }], navigated: ["/view/g1-elsewhere"] },
    ],
  );
  for (const [label, body] of [
    ["no address", { changed: true }],
    ["an address off /view/", { changed: true, view_href: "https://example.invalid/" }],
    ["an address that is not a string", { changed: true, view_href: 7 }],
    ["no body", null],
  ]) {
    const asked = host([{ status: 200, body }]);
    equal(
      `an answer with ${label} goes to the address asked for`,
      await asked.opener.switchTo(toParent),
      {
        kind: "navigated",
        href: address,
      },
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
    [500, null, `Could not switch to ${at} (HTTP 500).`],
    [403, "forbidden", `Could not switch to ${at} (HTTP 403).`],
  ]) {
    const refused = host([{ status, body }]);
    equal(
      `HTTP ${status} is refused in words and the page stays`,
      [await refused.opener.switchTo(toParent), refused.log.navigated],
      [{ kind: "refused", message }, []],
    );
  }
  const broken = host([
    new TypeError("fetch failed"),
    { status: 200, body: { view_href: address } },
  ]);
  equal("a request that fails says so", await broken.opener.switchTo(toParent), {
    kind: "refused",
    message: "The switch request failed.",
  });
  equal("and the next attempt runs", (await broken.opener.switchTo(toParent)).kind, "navigated");

  // One switch at a time, and the hold ends with the switch whether or not it worked.
  let release;
  const slow = { asked: 0 };
  const held = createViewFileOpener({
    pin: COMMIT,
    href: (wire) => `/view/${wire}`,
    switchPin() {
      slow.asked += 1;
      return new Promise((resolve) => {
        release = resolve;
      });
    },
    navigate() {},
  });
  const first = held.switchTo(toParent);
  equal("a second switch while one runs is held", await held.switchTo(toParent), { kind: "busy" });
  equal("and asks the server nothing", slow.asked, 1);
  release({ status: 200, body: { view_href: address } });
  equal("the first one finishes", (await first).kind, "navigated");
  const again = held.switchTo(toParent);
  equal("a page restored from history can switch again", slow.asked, 2);
  release({ status: 404, body: { code: "selection_not_found" } });
  equal("and a refusal releases the hold too", (await again).kind, "refused");
  const third = held.switchTo(toParent);
  equal("so the next attempt asks", slow.asked, 3);
  release({ status: 200, body: {} });
  await third;

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("diff view file OK\n");
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
