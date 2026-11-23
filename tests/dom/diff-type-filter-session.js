// Browserless session: a multi-file diff's File type filter, through the production browser
// code.
//
// builtin_plugins/diff/diff-type-filter.js loads whole, as the diff plugin loads it, with
// static/filter-controls.js, whose File type menu rows and markup the control draws. The
// comparison route is a stand-in that records each request and answers when the session
// says, so an answer a later choice overtook can arrive late; what `types=` keeps and what
// `view=types` counts are the route's, pinned by cli-api-diff-type-filter.tryscript.md. A
// mount is a stand-in that records what it was given. Events reach the control as
// filter-controls.js's `bind` delivers them: the session calls the handlers it bound.
//
// Each step prints the requests made, what is mounted, and what the toolbar control draws:
// its trigger's words, the menu's rows with their counts, the note, and whether it is busy.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// static/filter-controls.js, as the shell installs it before plugins load.
const sandbox = {
  console: { warn() {}, error() {} },
  JSON,
  String,
  Array,
  Object,
  MetabrowserIcons: {
    toggle: "",
    withClass: (name, cls) => `<i class="${cls}" data-icon="${name}"></i>`,
  },
  MetabrowserFileTypes: { iconFor: () => null },
  MetabrowserFileTypeTaxonomy: {
    displayGroups: [
      { id: "documentation", label: "Documentation", icon: "doc" },
      { id: "code", label: "Code", icon: "code" },
    ],
    families: [
      { id: "markdown", label: "Markdown", groupId: "documentation", extensions: [".md"] },
      { id: "python", label: "Python", groupId: "code", extensions: [".py"] },
      { id: "javascript", label: "JavaScript", groupId: "code", extensions: [".js"] },
    ],
  },
  METABROWSER_SETTINGS: {
    FILTER_TYPE_PRESETS: [
      { id: "docs", label: "Documentation", values: [".md", "readme"] },
      { id: "code", label: "Code", values: [".py", ".js"] },
    ],
  },
  metabrowser: {},
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/filter-controls.js"), "utf-8"),
  sandbox,
  { filename: "filter-controls.js" },
);
const real = sandbox.metabrowser.filterControls;
// The plugin module reads its globals from the page.
Object.assign(globalThis, {
  MetabrowserFileTypeTaxonomy: sandbox.MetabrowserFileTypeTaxonomy,
  METABROWSER_SETTINGS: sandbox.METABROWSER_SETTINGS,
});

/** The handlers the control bound, which a click or a key would reach through `bind`. */
let bound = null;
let focusedMenu = null;
const fc = {
  ...real,
  bind(_root, handlers) {
    bound = handlers;
    return () => {
      bound = null;
    };
  },
  keepFocus: () => () => {},
  focusMenu(_root, key) {
    focusedMenu = key;
    return null;
  },
};

/** The toolbar element: what its markup says, read back as the reader would see it. */
class ControlElement {
  constructor() {
    this.className = "";
    this.html = "";
    this.attributes = new Map();
    this.trigger = { focused: false, focus: () => (this.trigger.focused = true) };
  }

  set innerHTML(value) {
    this.html = value;
  }

  get innerHTML() {
    return this.html;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  querySelector(selector) {
    return selector === "[data-chip-menu-toggle]" && this.html.includes("data-chip-menu-toggle")
      ? this.trigger
      : null;
  }

  replaceChildren() {
    this.html = "";
  }

  /** The trigger's words, the rows of an open menu, the note, Clear, and busy. */
  read() {
    const text = (html) =>
      html
        .replace(/<svg[\s\S]*?<\/svg>/g, "")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    const trigger = /data-chip-menu-toggle[^>]*>([\s\S]*?)<\/button>/.exec(this.html);
    const rows = [
      ...this.html.matchAll(
        /<(button|div) [^>]*class="(?:menu-item chip-menu-item[^"]*|group-heading)"([^>]*)>([\s\S]*?)<\/\1>/g,
      ),
    ].map((match) =>
      match[0].includes("group-heading")
        ? `— ${text(match[3])}`
        : `${match[2].includes('aria-checked="true"') ? "[x]" : "[ ]"} ${text(match[3]).replace(/^✓ /, "")}`,
    );
    const note = /class="(notice )?diff-type-note"[^>]*>([^<]*)</.exec(this.html);
    return {
      trigger: trigger ? text(trigger[1]) : null,
      ...(this.html.includes('aria-expanded="true"') ? { rows } : {}),
      note: note ? (note[1] ? `alert: ${note[2]}` : note[2]) : null,
      clear: this.html.includes("data-chip-clear"),
      busy: this.attributes.get("aria-busy") === "true",
    };
  }
}

/** A diff document of these paths, as the comparison route answers with its totals. */
function documentOf(paths) {
  return {
    manifest: {
      files: paths.map((p, index) => ({ id: `f${index}`, new: { path: p } })),
      totals: { files: paths.length },
      truncated: false,
    },
    patches: {},
  };
}

const WHOLE = ["README.md", "docs/guide.md", "src/app.py", "src/util.py", "web/app.js", "logo.png"];
const COUNTS = {
  comparison_id: "c1",
  files: 6,
  truncated: false,
  extensions: [
    [".md", 2, 0],
    [".py", 2, 0],
    [".js", 1, 0],
    [".png", 1, 0],
  ],
  canonical_extensions: [
    [".md", 2, 0],
    [".py", 2, 0],
    [".js", 1, 0],
    [".png", 1, 0],
  ],
  type_families: [
    ["markdown", 2, 0],
    ["python", 2, 0],
    ["javascript", 1, 0],
  ],
  type_presets: [
    ["docs", 2, 0],
    ["code", 3, 0],
  ],
};

async function main() {
  const filterModule = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-type-filter.js"))
      .href
  );
  const { createTypeFilter, createTypeFilterControl, typesParam, narrowedNote, NONE_KEPT } =
    filterModule;

  /** Requests the route was asked, each waiting for the session to answer it. */
  const requests = [];
  const ask = (what, signal) =>
    new Promise((resolve, reject) => {
      const request = { what, resolve, reject, signal, aborted: false };
      signal.addEventListener("abort", () => {
        request.aborted = true;
      });
      requests.push(request);
    });
  const mounts = [];
  const listenerCalls = [];
  const element = new ControlElement();
  const reports = [];
  /** @type {{key: string, id: string, activate: () => void} | null} */
  let attached = null;
  let filter = null;
  const control = createTypeFilterControl(element, fc, {
    select: (types) => filter.select(types),
    formatInteger: (value) => value.toLocaleString("en-US"),
    shortcuts: {
      attach(target, spec) {
        attached = { target, ...spec, retargets: 0 };
        return {
          detach: () => {
            attached.detached = true;
          },
          retarget: () => {
            attached.retargets += 1;
          },
        };
      },
    },
  });
  /** A stand-in mount into *list*, recording the files it was given. */
  const mounter = (list) => (document_, narrowed) => {
    const files = document_.manifest.files.map((file) => file.new.path);
    const entry = {
      files,
      narrowed,
      disposed: false,
      listeners: new Set(),
    };
    list.push(entry);
    return {
      scrollToFile: (p) => (files.includes(p) ? "jumped" : "absent"),
      fileForPath: (p) => (files.includes(p) ? { kind: "file", path: p } : { kind: "absent" }),
      sectionForPath: (p) => (files.includes(p) ? { path: p, entry } : null),
      pathForSection: (section) => (section?.entry === entry ? section.path : null),
      currentFile: () => ({ path: files[0] ?? null }),
      firstScreen: () => Promise.resolve(),
      onCurrentFile(listener) {
        entry.listeners.add(listener);
        listener({ path: files[0] ?? null });
        return () => entry.listeners.delete(listener);
      },
      cancelPending() {},
      dispose() {
        entry.disposed = true;
      },
    };
  };
  const changes = [];
  filter = createTypeFilter({
    whole: documentOf(WHOLE),
    load: (types, signal) => ask(`types=${types}`, signal),
    counts: (signal) => ask("view=types", signal),
    mount: mounter(mounts),
    paint: (state) => control.paint(state),
    swap: (change) => control.swap(change),
    changed: (types) => changes.push(types),
    report: (what) => reports.push(what),
  });
  control.attachKey();
  const facade = filter.facade;
  facade.onCurrentFile((file) => listenerCalls.push(file.path));

  const settle = () => new Promise((resolve) => setImmediate(resolve));
  const steps = [];
  let seen = 0;
  const step = (label) => {
    const live = mounts.filter((mount) => !mount.disposed);
    assert(live.length === 1, `${label}: ${live.length} diffs mounted`);
    steps.push({
      step: label,
      requests: requests.slice(seen).map((r) => r.what + (r.aborted ? " (dropped)" : "")),
      mounted: live[0].files,
      ...(live[0].narrowed ? { narrowed: live[0].narrowed } : {}),
      control: element.read(),
    });
    seen = requests.length;
  };
  const answer = async (what, value) => {
    const request = requests.find((r) => r.what === what && !r.answered);
    assert(request, `no request for ${what}`);
    request.answered = true;
    request.resolve(value);
    await settle();
  };
  const kept = (types) => WHOLE.filter((p) => types.some((t) => p.endsWith(t)));

  step("mounted: the whole comparison, counts asked for");
  await answer("view=types", COUNTS);
  step("the counts arrive");
  bound.onMenuToggle("types", true);
  step("the menu opens");
  bound.onMenuPick("types", ".md");
  step("Markdown chosen: asked for, the menu shows the choice while it loads");
  await answer("types=.md", documentOf(kept([".md"])));
  step("its answer mounts in place of the whole");
  bound.onMenuPick("types", ".py");
  step("Python added: one address for the set, sorted");
  await answer("types=.md,.py", documentOf(kept([".md", ".py"])));
  step("the two types' files");
  bound.onMenuPick("types", ".md");
  bound.onMenuPick("types", ".js");
  step("Markdown off, then JavaScript on before the first answer");
  await answer("types=.js,.py", documentOf(kept([".js", ".py"])));
  await answer("types=.py", documentOf(kept([".py"])));
  step("the overtaken answer arrives last and is dropped");
  bound.onMenuPreset("types", "code", true);
  bound.onMenuPreset("types", "docs", false);
  step("Code turned off, Documentation turned on");
  await answer("types=.md,readme", documentOf(kept([".md"])));
  step("Documentation's files");
  bound.onMenuPick("types", null);
  step("Any type: the whole comparison again, nothing asked");
  bound.onMenuPick("types", ".rs");
  await answer("types=.rs", documentOf([]));
  step("a type with no changed file");
  bound.onMenuPick("types", ".png");
  const failing = requests.find((r) => r.what === "types=.png,.rs");
  failing.reject(Object.assign(new Error("503"), { status: 503 }));
  await settle();
  step("a choice whose files do not load keeps the diff it had");
  filter.select([".rs", ".png"]);
  step("the same choice again asks again");
  await answer("types=.png,.rs", documentOf(kept([".png"])));
  step("its files");
  element.trigger.focused = false;
  bound.onClear();
  step("Clear");
  assert(element.trigger.focused, "Clear left focus nowhere: it goes to the menu's trigger");
  bound.onMenuToggle("types", false);
  attached.activate();
  step("Y opens the menu");
  assert(focusedMenu === "types", "Y focused no row of the menu");
  bound.onMenuPick("types", ".py");
  await answer("types=.py", documentOf(kept([".py"])));
  // A lookup answers for the whole comparison, and a jump to a file the choice hides goes
  // back to every type first, asking nothing.
  const lookups = ["README.md", "src/app.py", "absent.txt"].map(
    (p) => `${p}: ${facade.fileForPath(p).kind}`,
  );
  const jumps = [`src/app.py: ${facade.scrollToFile("src/app.py")}`];
  step("Python chosen, then a jump to a file it shows");
  jumps.push(`absent.txt: ${facade.scrollToFile("absent.txt")}`);
  step("a jump to a file no type shows changes nothing");
  jumps.push(`README.md: ${facade.scrollToFile("README.md")}`);
  step("a jump to a file the choice hides goes back to every type");

  // The handle a host holds goes to whichever diff is mounted, and its file listener is
  // carried from each diff to the next.
  const live = () => mounts.find((mount) => !mount.disposed);
  assert(live().listeners.size === 1, "the host's file listener was not carried over");
  assert(
    mounts.filter((mount) => mount.disposed).every((mount) => mount.listeners.size === 0),
    "a replaced diff kept the host's file listener",
  );
  // A host's place is kept in its file (mb-owwk): its section lookups go to the diff mounted
  // now, and a section of a replaced diff is no file's.
  const section = facade.sectionForPath("README.md");
  assert(
    section?.entry === live() && facade.pathForSection(section) === "README.md",
    "the host's section lookups did not reach the diff mounted now",
  );
  assert(
    facade.pathForSection({ path: "README.md", entry: mounts[0] }) === null,
    "a replaced diff's section still named its file",
  );

  bound.onMenuPick("types", ".py");
  facade.dispose();
  control.dispose();
  await settle();
  const pending = requests.at(-1);
  assert(pending.aborted, "dispose left a request running");
  assert(
    mounts.every((mount) => mount.disposed),
    "dispose left a diff mounted",
  );
  assert(attached.detached, "dispose left Y attached");
  assert(bound === null, "dispose left the control bound");

  // A choice the host kept, as a pull request's page keeps it while the reader is on
  // another tab, mounts its answer first, never the whole comparison.
  const keptMounts = [];
  const keptPaints = [];
  const again = createTypeFilter({
    whole: documentOf(WHOLE),
    initial: { types: [".py", ".md"], document: documentOf(kept([".md", ".py"])) },
    load: () => new Promise(() => {}),
    counts: () => new Promise(() => {}),
    mount: mounter(keptMounts),
    paint: (state) => keptPaints.push({ types: state.types, kept: state.kept, whole: state.whole }),
  });
  const keptChoice = {
    mounts: keptMounts.map((mount) => ({ files: mount.files, narrowed: mount.narrowed })),
    painted: keptPaints[0],
    types: again.types(),
  };
  again.facade.dispose();

  console.log(
    JSON.stringify(
      {
        steps,
        hostListener: listenerCalls,
        toldTheHost: changes.map((types) => (types === null ? "every type" : types.join(","))),
        lookups,
        jumps,
        keptChoice,
        reports,
        key: {
          id: attached.id,
          key: attached.key,
          group: attached.group,
          copy: attached.copy,
          retargetedOnRepaint: attached.retargets > 0,
        },
        disposed: { pendingRequest: "aborted", diffs: "disposed", key: "detached" },
        params: [[".py", ".md", ".md"], [], null].map((types) => typesParam(types)),
        notes: [
          [4, 35],
          [0, 1],
          [1234, 5678],
        ].map(([k, w]) => narrowedNote(k, w, (v) => v.toLocaleString("en-US"))),
        none: NONE_KEPT,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
