const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.hidden = false;
    this.attributes = {};
    this.listeners = {};
    this._innerHTML = "";
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = [...children];
    this._innerHTML = "";
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }
  removeEventListener(type, listener) {
    if (this.listeners[type] === listener) {
      delete this.listeners[type];
    }
  }
  set innerHTML(value) {
    this._innerHTML = value;
  }
  get innerHTML() {
    return this._innerHTML;
  }
}

global.document = { createElement: (tag) => new Element(tag) };

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/overview.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  let contextListener = null;
  let activeListener = null;
  let updateCount = 0;
  let updateShouldFail = false;
  let disposeCount = 0;
  let summaryMountSignal = null;
  const printStates = [];
  const envelope = { kind: "folder", path: "src", readme_path: "src/README.md" };
  const mb = {
    errors: {
      isAbortError: (error) => error?.name === "AbortError",
      classifyRequestError: () => ({ message: "Panel failed.", retryable: true }),
    },
    folderContext: {
      subscribe(_path, listener) {
        contextListener = listener;
        listener(envelope);
        return () => {
          contextListener = null;
        };
      },
    },
    viewState: {
      isActive: () => true,
      subscribeActive(_container, listener) {
        activeListener = listener;
        listener(true);
        return () => {
          activeListener = null;
        };
      },
    },
    setViewPrintState(_container, state) {
      printStates.push(state);
    },
  };
  const descriptors = [
    {
      id: "folder.file-types",
      label: "File types",
      placement: "summary",
      presentation: "surface",
      required: true,
      printable: false,
      resolve: (context) => ({ key: context.path, data: "summary" }),
      mount(container, _context, _data, options) {
        container.innerHTML = "summary";
        summaryMountSignal = options.signal;
        return {
          dispose: () => (disposeCount += 1),
          update() {
            updateCount += 1;
            if (updateShouldFail) {
              throw new Error("update failed");
            }
          },
        };
      },
    },
    {
      id: "folder.readme",
      label: "README",
      placement: "content",
      presentation: "document",
      printable: true,
      resolve: () => null,
      mount() {
        throw new Error("optional null panel must not mount");
      },
    },
    {
      id: "example.license",
      label: "License",
      placement: "supplemental",
      presentation: "surface",
      printable: true,
      resolve: () => Promise.resolve({ key: "license", data: "MIT" }),
      mount(container, _context, data) {
        container.innerHTML = data;
        return { dispose: () => (disposeCount += 1) };
      },
    },
  ];
  const container = new Element("div");
  const handle = module.mountOverview(container, { path: "src", raw: envelope }, mb, {
    listPanels: () => descriptors,
  });
  await new Promise((resolve) => setImmediate(resolve));
  const stack = container.children[0];
  check(
    "deterministic slots",
    stack.children.map((slot) => slot.dataset.panelId).join(",") ===
      "folder.file-types,folder.readme,example.license",
  );
  check(
    "panels receive visible headings",
    stack.children.map((slot) => slot.children[0].textContent).join(",") ===
      "File types,README,License",
  );
  check(
    "panel headings use a shared semantic level",
    stack.children.every((slot) => slot.children[0].tagName === "H2"),
  );
  check("optional panel hidden", stack.children[1].hidden === true);
  check("synthetic panel mounted", stack.children[2].children[1].innerHTML === "MIT");
  check(
    "print aggregation",
    printStates.some((state) => state.printable === true),
  );

  contextListener({ ...envelope, readme_search_truncated: true });
  await new Promise((resolve) => setImmediate(resolve));
  check("same-key update", updateCount === 1, String(updateCount));
  check("same-key update keeps the mounted panel active", summaryMountSignal.aborted === false);
  activeListener(false);
  contextListener({ ...envelope, readme_search_truncated: false });
  await new Promise((resolve) => setImmediate(resolve));
  check("inactive context gated", updateCount === 1, String(updateCount));
  activeListener(true);
  await new Promise((resolve) => setImmediate(resolve));
  check("stale context reconciled", updateCount === 2, String(updateCount));

  updateShouldFail = true;
  contextListener({ ...envelope, readme_search_truncated: true });
  await new Promise((resolve) => setImmediate(resolve));
  check("failed update disposes old mount", disposeCount === 1, String(disposeCount));
  check("failed update aborts the mounted panel", summaryMountSignal.aborted === true);
  check(
    "failed update renders panel error",
    stack.children[0].children[1].children[0].attributes.role === "alert",
  );

  handle.dispose();
  handle.dispose();
  check("handles disposed exactly once", disposeCount === 2, String(disposeCount));
  check("subscriptions disposed", contextListener === null && activeListener === null);

  if (failures.length) {
    console.error(`folder overview FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder overview OK");
})();
