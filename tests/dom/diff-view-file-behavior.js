// Focused invariants for View file and View on branch
// (builtin_plugins/diff/diff-view-file.js): which side of a change a control opens, what a
// path's address is built from, what each control is, and what the page's one pin switch
// and a diff's opener do with every answer of the pin route. The session in
// diff-view-file-session.js covers the same code on a real server's answers.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

// The SDK the page gives the module, of which it calls only `shortCommit`: the shell's own.
const { shortCommit } = require("./changed-files-tree-fixture.js").shellFormatters();
globalThis.window = { metabrowser: { shortCommit } };

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
const PULL_HEAD = "refs/pull/7/head";

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
  const {
    createPinSwitch,
    createViewFileOpener,
    describeViewFile,
    sidePathForAddress,
    switchRefusal,
    viewFileSide,
  } = await import(pathToFileURL(modulePath).href);

  // ── What an address is built from ───────────────────────────────────────
  equal("a UTF-8 path is itself", sidePathForAddress({ path: "docs/a.md" }), "docs/a.md");
  equal(
    "a name that is not UTF-8 is its bytes, not the replacement characters shown",
    [...sidePathForAddress({ path: "d�/f", path_b64: "ZOkvZg==" })],
    [0x64, 0xe9, 0x2f, 0x66],
  );
  equal("bytes that are not base64 are no path", sidePathForAddress({ path_b64: "%%%" }), null);
  equal("an entry with no path has none", sidePathForAddress({}), null);

  // ── Which side a control opens ──────────────────────────────────────────
  const modified = { kind: "modified", old: side("a.txt"), new: side("a.txt") };
  equal("a modified file opens its new side", viewFileSide(modified, commits), {
    commit: COMMIT,
    path: "a.txt",
    address: "a.txt",
  });
  equal(
    "an added file opens its new side",
    viewFileSide({ kind: "added", new: side("new.txt") }, commits)?.path,
    "new.txt",
  );
  equal(
    "a deleted file has nothing to open",
    viewFileSide({ kind: "deleted", old: side("old.txt") }, commits),
    null,
  );
  for (const kind of ["renamed", "copied"]) {
    equal(
      `a ${kind} file opens at its new path`,
      viewFileSide({ kind, similarity: 90, old: side("from.txt"), new: side("to.txt") }, commits)
        ?.path,
      "to.txt",
    );
  }
  // A submodule's side is a commit of another repository, and a symbolic link's side
  // would open its target rather than the link text the diff shows.
  const gitlink = { entry_type: "submodule", mode: "160000" };
  const symlink = { entry_type: "symlink", mode: "120000" };
  for (const [label, other] of [
    ["a submodule", gitlink],
    ["a symbolic link", symlink],
  ]) {
    equal(
      `${label} has nothing to open`,
      viewFileSide({ kind: "modified", old: side("x", other), new: side("x", other) }, commits),
      null,
    );
    equal(
      `a file that became ${label} has nothing to open`,
      viewFileSide({ kind: "type_changed", old: side("x"), new: side("x", other) }, commits),
      null,
    );
  }
  equal(
    "an entry of no known type has nothing to open",
    viewFileSide({ kind: "added", new: side("x", { entry_type: undefined }) }, commits),
    null,
  );
  equal(
    "a root commit's new side opens, whatever its empty base",
    viewFileSide(modified, resolved({ kind: "empty" }, { kind: "commit", id: COMMIT }))?.commit,
    COMMIT,
  );
  equal(
    "a SHA-256 commit ID is a commit ID",
    viewFileSide(modified, resolved({ kind: "commit", id: PARENT }, { kind: "commit", id: SHA256 }))
      ?.commit,
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
      viewFileSide(modified, resolved(snapshot, snapshot)),
      null,
    );
  }

  // ── What each control is ────────────────────────────────────────────────
  const head = viewFileSide(modified, commits);
  const address = "/view/g1-YS50eHQ";
  const at = shortCommit(COMMIT);
  const commitPage = { kind: "pin", pin: COMMIT, branch: null };
  equal(
    "a commit's diff at the page's commit is a link",
    describeViewFile(head, address, commitPage),
    {
      commit: COMMIT,
      path: "a.txt",
      href: address,
      mode: "link",
      label: "View file",
      detail: `Open a.txt at ${at}, the commit this page shows`,
    },
  );
  equal(
    "a commit's diff elsewhere switches, and says so",
    describeViewFile(head, address, { ...commitPage, pin: PARENT }),
    {
      commit: COMMIT,
      path: "a.txt",
      href: address,
      mode: "switch",
      label: "View file",
      detail: `Switch to ${at} and open a.txt`,
    },
  );
  const pullPage = { kind: "pin", pin: COMMIT, branch: PULL_HEAD };
  equal(
    "a pull request's diff at its head is View on branch, a link",
    [
      describeViewFile(head, address, pullPage).label,
      describeViewFile(head, address, pullPage).mode,
    ],
    ["View on branch", "link"],
  );
  equal(
    "elsewhere it switches to the pull request's head",
    describeViewFile(head, address, { ...pullPage, pin: PARENT }).detail,
    `Switch to ${at}, this pull request's head, and open a.txt`,
  );
  equal(
    "a page that learned another pin is served switches back",
    describeViewFile(head, address, { ...pullPage, pinChanged: true }).mode,
    "switch",
  );
  equal(
    "beside a checkout at the head it opens the working tree",
    describeViewFile(head, "/view/a.txt", { kind: "checkout", pin: COMMIT, branch: PULL_HEAD }),
    {
      commit: COMMIT,
      path: "a.txt",
      href: "/view/a.txt",
      mode: "link",
      label: "View on branch",
      detail:
        "Open your working-tree copy of a.txt, in this checkout whose HEAD is this pull request's head",
    },
  );

  // ── The page's one switch ───────────────────────────────────────────────
  function switcher(answers) {
    const log = { asked: [], released: 0 };
    let restored = () => {};
    const pinSwitch = createPinSwitch({
      async post(selection) {
        log.asked.push(selection);
        const next = answers.shift();
        if (next instanceof Error) {
          throw next;
        }
        if (typeof next === "function") {
          return next();
        }
        return next;
      },
      onRestored(callback) {
        restored = callback;
        return () => {};
      },
    });
    pinSwitch.onReleased(() => {
      log.released += 1;
    });
    return { log, pinSwitch, restore: () => restored() };
  }
  const selection = { oid: COMMIT, under: PULL_HEAD, view: address };
  const said = switcher([{ status: 200, body: { changed: true, view_href: "/view/g1-there" } }]);
  equal(
    "a switch says where the server says the page goes",
    [await said.pinSwitch.switchTo(selection), said.log.asked],
    [{ kind: "switched", href: "/view/g1-there" }, [selection]],
  );
  for (const [label, body] of [
    ["no address", { changed: true }],
    ["an address off /view/", { changed: true, view_href: "https://example.invalid/" }],
    ["an address that is not a string", { changed: true, view_href: 7 }],
    ["no body", null],
  ]) {
    equal(
      `an answer with ${label} names no address`,
      await switcher([{ status: 200, body }]).pinSwitch.switchTo(selection),
      { kind: "switched", href: null },
    );
  }
  for (const [status, body, message] of [
    [202, { code: "selection_pending" }, "This commit is still being fetched. Try again shortly."],
    [404, { code: "selection_not_found" }, "This commit is not on the origin."],
    [502, { code: "selection_fetch_failed" }, "This commit could not be fetched. Try again."],
    [
      409,
      { code: "ref_moved" },
      "This pull request's head has moved; reload to see the newer changes.",
    ],
    [409, { code: "unsupported_for_subject" }, "Could not open this commit. Try again."],
    [415, { code: "invalid_request" }, "Could not open this commit. Try again."],
    [500, null, "Could not open this commit. Try again."],
    [403, "forbidden", "Could not open this commit. Try again."],
  ]) {
    equal(`HTTP ${status} is said in words`, switchRefusal(body), message);
    const refused = switcher([
      { status, body },
      { status: 200, body: {} },
    ]);
    equal(
      `HTTP ${status} is refused and the page stays`,
      [await refused.pinSwitch.switchTo(selection), refused.pinSwitch.switching()],
      [{ kind: "refused", message }, false],
    );
    equal(
      `and after HTTP ${status} the next switch runs`,
      (await refused.pinSwitch.switchTo(selection)).kind,
      "switched",
    );
  }
  const broken = switcher([new TypeError("fetch failed"), { status: 200, body: {} }]);
  equal("a request that fails says so", await broken.pinSwitch.switchTo(selection), {
    kind: "refused",
    message: "The switch request failed.",
  });
  equal("and the next one runs", (await broken.pinSwitch.switchTo(selection)).kind, "switched");

  // One switch at a time, whoever asks; the hold outlasts a switch the server made, while
  // the page leaves, and ends when the browser brings the page back.
  let release = () => {};
  const slow = switcher([
    () =>
      new Promise((resolve) => {
        release = resolve;
      }),
  ]);
  const first = slow.pinSwitch.switchTo(selection);
  equal("a second switch while one runs is held", await slow.pinSwitch.switchTo(selection), {
    kind: "busy",
  });
  equal("and asks the server nothing", slow.log.asked.length, 1);
  release({ status: 200, body: { view_href: address } });
  equal("the first one finishes", (await first).kind, "switched");
  equal(
    "the page is leaving: nothing more is asked of it",
    [await slow.pinSwitch.switchTo(selection), slow.pinSwitch.switching()],
    [{ kind: "busy" }, true],
  );
  slow.restore();
  equal(
    "a page brought back lets go, and says so",
    [slow.pinSwitch.switching(), slow.log.released],
    [false, 1],
  );
  slow.restore();
  equal("a restore with nothing held says nothing", slow.log.released, 1);
  const unwanted = switcher([
    () =>
      new Promise((resolve) => {
        release = resolve;
      }),
  ]);
  let wanted = true;
  const late = unwanted.pinSwitch.switchTo(selection, () => wanted);
  wanted = false;
  release({ status: 200, body: { view_href: address } });
  equal(
    "an answer its caller no longer wants is abandoned, and lets go",
    [await late, unwanted.pinSwitch.switching()],
    [{ kind: "abandoned" }, false],
  );

  // ── A diff's opener ─────────────────────────────────────────────────────
  function page(answers, extra = {}) {
    const shared = switcher(answers);
    const log = { navigated: [], released: 0, changed: 0, listening: 0 };
    let pinChanged = () => {};
    const opener = createViewFileOpener(
      {
        kind: "pin",
        pin: COMMIT,
        branch: null,
        href: (name) => (name === "" ? null : `/view/<${name}>`),
        pinSwitch: shared.pinSwitch,
        navigate: (href) => log.navigated.push(href),
        onPinChanged(callback) {
          pinChanged = callback;
          log.listening += 1;
          return () => {
            log.listening -= 1;
          };
        },
        ...extra,
      },
      { released: () => (log.released += 1), changed: () => (log.changed += 1) },
    );
    return { log, opener, shared, changePin: () => pinChanged() };
  }

  equal(
    "a side whose path has no address gets no control",
    page([]).opener.actions({ kind: "modified", old: side("a.txt"), new: side("") }, commits),
    [],
  );
  const onParent = page([], { pin: PARENT });
  const [toCommit] = onParent.opener.actions(modified, commits);
  equal(
    "on another commit's page the control switches",
    [toCommit.mode, toCommit.href],
    ["switch", "/view/<a.txt>"],
  );
  const followed = page(
    [{ status: 200, body: { changed: true, view_href: "/view/g1-elsewhere" } }],
    {
      pin: PARENT,
    },
  );
  equal(
    "a switch goes where the server says, naming no ref for a commit's diff",
    [await followed.opener.switchTo(toCommit), followed.shared.log.asked, followed.log.navigated],
    [
      { kind: "navigated", href: "/view/g1-elsewhere" },
      [{ oid: COMMIT, view: "/view/<a.txt>" }],
      ["/view/g1-elsewhere"],
    ],
  );
  const unsaid = page([{ status: 200, body: { changed: true } }], { pin: PARENT });
  equal(
    "an answer with no address goes to the address asked for",
    await unsaid.opener.switchTo(toCommit),
    { kind: "navigated", href: "/view/<a.txt>" },
  );
  const pull = page([{ status: 200, body: {} }], { pin: PARENT, branch: PULL_HEAD });
  const [onBranch] = pull.opener.actions(modified, commits);
  await pull.opener.switchTo(onBranch);
  equal(
    "a pull request's switch names its head ref",
    [onBranch.label, pull.shared.log.asked],
    ["View on branch", [{ oid: COMMIT, under: PULL_HEAD, view: "/view/<a.txt>" }]],
  );
  const refused = page([{ status: 404, body: { code: "selection_not_found" } }], { pin: PARENT });
  equal("a refusal reaches the control in words", await refused.opener.switchTo(toCommit), {
    kind: "refused",
    message: "This commit is not on the origin.",
  });

  // The release is the diff's to show only when the switch was its own.
  const mine = page([{ status: 200, body: {} }], { pin: PARENT });
  await mine.opener.switchTo(toCommit);
  equal("a page leaving keeps the control busy", mine.opener.switching(), true);
  mine.shared.restore();
  equal("a page brought back releases the diff whose switch it was", mine.log.released, 1);
  const other = page([{ status: 200, body: {} }], { pin: PARENT });
  await other.shared.pinSwitch.switchTo(selection);
  other.shared.restore();
  equal("and not a diff that did not switch", other.log.released, 0);

  // Another tab switched the server's pin: each link becomes the switch back, once.
  const shown = page([]);
  equal(
    "at the page's commit the control is a link",
    shown.opener.actions(modified, commits)[0].mode,
    "link",
  );
  shown.changePin();
  shown.changePin();
  equal(
    "after the pin changed it switches, and the view is told once",
    [shown.opener.actions(modified, commits)[0].mode, shown.log.changed],
    ["switch", 1],
  );

  // Beside a checkout: only at its HEAD, never switching, never told of a pin.
  const checkout = page([], { kind: "checkout", pin: COMMIT, branch: PULL_HEAD });
  equal(
    "a checkout at the diff's head opens the working-tree file",
    checkout.opener.actions(modified, commits).map((action) => [action.mode, action.href]),
    [["link", "/view/<a.txt>"]],
  );
  equal("a checkout listens for no pin", checkout.log.listening, 0);
  equal(
    "a checkout elsewhere has no control",
    page([], { kind: "checkout", pin: PARENT, branch: PULL_HEAD }).opener.actions(
      modified,
      commits,
    ),
    [],
  );

  // A diff unmounted while its switch was on the way takes the page nowhere.
  const gone = page(
    [
      () =>
        new Promise((resolve) => {
          release = resolve;
        }),
    ],
    { pin: PARENT },
  );
  const going = gone.opener.switchTo(toCommit);
  gone.opener.dispose();
  release({ status: 200, body: { view_href: address } });
  equal(
    "a switch answered after the diff was unmounted does not navigate",
    [await going, gone.log.navigated, gone.log.listening, gone.shared.pinSwitch.switching()],
    [{ kind: "abandoned" }, [], 0, false],
  );
  equal(
    "and an unmounted diff asks nothing",
    [await gone.opener.switchTo(toCommit), gone.shared.log.asked.length],
    [{ kind: "abandoned" }, 1],
  );
  const failing = page(
    [
      () =>
        new Promise((_resolve, reject) => {
          release = reject;
        }),
    ],
    { pin: PARENT },
  );
  const failed = failing.opener.switchTo(toCommit);
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
