// Where probe.js puts a region's stand-in, and the height it then reads.
//
// `frame_missing_px` compares a region's settled height with the height of a stand-in
// holding only what the shell ships, laid out by the region's own container. The
// production heightOfStandIn is lifted out of probe.js and run on a document double
// with the one piece of layout the question turns on: a row gives each child its full
// height, and a column divides its height among its children.
//
// In a browser the same question was put to Chrome on both builds; this holds the
// placement rule between captures. Prints the height read for each shape.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const probePath = path.resolve(__dirname, "../../explorations/performance-loop/probe.js");
const source = fs.readFileSync(probePath, "utf-8");
const lifted = source.match(
  / {2}function heightOfStandIn\(reference, standIn\) \{[\s\S]*?\n {2}\}/,
);
if (!lifted) {
  throw new Error("heightOfStandIn not found in probe.js");
}

class Box {
  constructor(name, direction, height = 0) {
    this.name = name;
    this.direction = direction;
    this.ownHeight = height;
    this.children = [];
    this.parentElement = null;
    this.id = name;
  }

  get parentNode() {
    return this.parentElement;
  }

  appendChild(child) {
    child.remove();
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  insertBefore(child, reference) {
    child.remove();
    child.parentElement = this;
    this.children.splice(this.children.indexOf(reference), 0, child);
    return child;
  }

  remove() {
    if (this.parentElement) {
      this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1);
      this.parentElement = null;
    }
  }

  cloneNode() {
    return new Box(`copy of ${this.name}`, this.direction);
  }

  removeAttribute(name) {
    if (name === "id") {
      this.id = "";
    }
  }

  // A row stretches each child to its height; a column shares its height out.
  height() {
    const parent = this.parentElement;
    if (!parent) {
      return this.ownHeight;
    }
    return parent.direction === "row" ? parent.height() : parent.height() / parent.children.length;
  }

  getBoundingClientRect() {
    return { height: this.height() };
  }
}

function page() {
  const body = new Box("body", "row", 900);
  const main = body.appendChild(new Box("main", "row"));
  const nav = main.appendChild(new Box("nav", "column"));
  return { body, main, nav };
}

function measure(build) {
  const { body, main, nav } = page();
  const region = build({ main, nav });
  const sandbox = { document: { body }, Math };
  vm.createContext(sandbox);
  vm.runInContext(`${lifted[0]}\nresult = heightOfStandIn;`, sandbox);
  const standIn = region.cloneNode();
  const before = JSON.stringify(shape(body));
  const settled = region.height();
  const shipped = sandbox.result(region, standIn);
  return { settled, shipped, restored: JSON.stringify(shape(body)) === before };
}

function shape(box) {
  return [box.name, box.children.map(shape)];
}

const output = {
  // v0.11.0: the pane is a child of the row, beside the nav.
  pane_in_the_row: measure(({ main }) => main.appendChild(new Box("pane", "column"))),
  // Since the pane was framed: a column that holds the pane and nothing else.
  pane_alone_in_a_frame: measure(({ main }) =>
    main.appendChild(new Box("frame", "column")).appendChild(new Box("pane", "column")),
  ),
  // Two such wrappers, one inside the other.
  pane_alone_in_two_frames: measure(({ main }) =>
    main
      .appendChild(new Box("outer", "column"))
      .appendChild(new Box("frame", "column"))
      .appendChild(new Box("pane", "column")),
  ),
  // A region with siblings in a column shares the column with them, and with its
  // stand-in: three children become four.
  region_with_siblings: measure(({ nav }) => {
    nav.appendChild(new Box("filter", "row"));
    const files = nav.appendChild(new Box("files", "column"));
    nav.appendChild(new Box("summary", "row"));
    return files;
  }),
};
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
