// Browserless session: a person, as every page draws one (docs/design-system.md, "Actor
// Identity").
//
// One component draws a person wherever a page names one: `actorIdentity` in
// plugin-sdk-views.js, as nodes, and `actorIdentityHtml` beside it, as markup, which the SDK
// exposes as `metabrowser.actorIdentity` and `metabrowser.actorIdentityHtml`. It is an
// avatar's box, then the bold name in `strong.actor-name`. The commit page draws its author
// through the markup form, and the GitHub plugin's `authorLabel` draws every author on a
// pull request's page and in a Pulls row through the nodes form, so the box is the same on
// both pages (mb-nunw). The box holds the avatar where the caller has one, and the shell's
// person glyph, Lucide's `circle-user-round`, where it has none or the image fails (mb-s3g8).
//
// This runs the real plugin SDK against a recording document and prints
// what each case draws. It fails if a name is ever anything but its text, if an image asks
// for anything before its size and privacy attributes are set, if an address that is not
// https is asked for, if a failed image leaves its box anything but the glyph, or if the
// markup form draws anything but what the nodes form draws for the same person.

const assert = require("node:assert/strict");
const { createSdkSandbox } = require("./sdk-sandbox.js");

/** The smallest document the identity needs: elements that record what is set on them. */
const recording = {
  createElement(tag) {
    return {
      tag,
      className: "",
      attributes: new Map(),
      children: [],
      innerHTML: "",
      textContent: "",
      listeners: new Map(),
      setAttribute(name, value) {
        this.attributes.set(name, String(value));
      },
      getAttribute(name) {
        return this.attributes.get(name) ?? null;
      },
      append(...nodes) {
        this.children.push(...nodes);
      },
      replaceChildren(...nodes) {
        this.children = [...nodes];
        this.innerHTML = "";
      },
      addEventListener(name, listener, options) {
        this.listeners.set(name, { listener, once: options?.once === true });
      },
    };
  },
};
const sandbox = createSdkSandbox();
// After the SDK's startup, which touches a document of its own: its nodes come from this one.
sandbox.document = recording;
const mb = sandbox.metabrowser;
// The person glyph, read from the markup form's box: Lucide's `circle-user-round`, in the
// box's ink.
const glyph = mb
  .actorIdentityHtml("")
  .match(/<span class="actor-avatar" aria-hidden="true">(.*?)<\/span>/)[1];
assert.match(
  glyph,
  /^<svg [^>]*stroke="currentColor"[^>]*><path d="M17\.925 20\.056a6 6 0 0 0-11\.851\.001"\/><circle cx="12" cy="11" r="4"\/><circle cx="12" cy="12" r="10"\/><\/svg>$/,
  "the glyph is Lucide's circle-user-round",
);

/** An element as plain data in this realm: its tag, class, attributes in order, and children. */
function shape(node) {
  if (typeof node === "string") {
    return node;
  }
  return {
    tag: node.tag,
    class: node.className,
    ...(node.attributes.size ? { attributes: Object.fromEntries(node.attributes) } : {}),
    ...(node.innerHTML
      ? { inner: node.innerHTML === glyph ? "the person glyph" : node.innerHTML }
      : {}),
    ...(node.textContent ? { text: node.textContent } : {}),
    ...(node.children.length ? { children: node.children.map(shape) } : {}),
  };
}

/** The markup the nodes stand for, as the HTML form writes it, so the two forms compare. */
function markup(node) {
  const attributes = [...node.attributes].map(([name, value]) => ` ${name}="${value}"`).join("");
  const classes = node.className ? ` class="${node.className}"` : "";
  return (
    `<${node.tag}${classes}${attributes}>` +
    `${node.innerHTML}${mb.escapeHtml(node.textContent)}${node.children.map(markup).join("")}` +
    `</${node.tag}>`
  );
}

const AVATAR = "https://avatars.githubusercontent.com/u/1242887?s=40";
const cases = {};

// A person with an avatar: the box holds its image, eager where the caller asks.
{
  const identity = mb.actorIdentity("octo", { avatar: AVATAR, loading: "eager" });
  const image = identity.children[0].children[0];
  assert.equal([...image.attributes.keys()].at(-1), "src", "the request is asked for last");
  cases["an avatar, eager"] = shape(identity);
  // It fails to load: the box keeps its place and holds the glyph.
  const failed = image.listeners.get("error");
  assert.ok(failed.once, "the image gives its box up once");
  failed.listener();
  cases["the avatar fails to load"] = shape(identity);
  assert.equal(identity.children[0].innerHTML, glyph);
}
// The default is lazy: the conversation's avatars are asked for as the reader nears them.
cases["an avatar, by default"] = shape(
  mb.actorIdentity("octo", { avatar: AVATAR }),
).children[0].children[0].attributes;

// A person with no avatar: the box holds the person glyph, and is there all the same.
cases["no avatar"] = shape(mb.actorIdentity("Jane Author"));

// An address that is not https is never asked for: the glyph stands in.
const refused = {};
for (const address of [
  "http://avatars.githubusercontent.com/u/1?s=40",
  "javascript:alert(1)",
  "data:image/svg+xml,<svg/>",
  "//avatars.githubusercontent.com/u/1",
  "",
]) {
  const identity = mb.actorIdentity("ghost", { avatar: address });
  const box = identity.children[0];
  assert.equal(box.children.length, 0, `${address} makes no image`);
  refused[address] = box.innerHTML === glyph ? "the person glyph" : box.innerHTML;
}
cases["an address that is not https"] = refused;

// A dense list row asks for no box where there is no avatar, and keeps it where there is one.
cases["a list row, no avatar"] = shape(
  mb.actorIdentity("ghost", { placeholder: false, nameClass: "github-pulls-author" }),
);
cases["a list row, an avatar"] = shape(
  mb.actorIdentity("octo", { avatar: AVATAR, placeholder: false }),
).children.map((child) => child.class);

// A placement's own classes, on the identity and on the name.
cases["a placement's classes"] = shape(
  mb.actorIdentity("forker", {
    className: "github-pull-identity",
    nameClass: "github-pull-author",
  }),
);

// A name is its text, never markup, in both forms; the markup form is the nodes form's.
const name = 'Ada <b>"Lovelace"</b> & co';
const nodes = mb.actorIdentity(name, { nameClass: "git-commit-author" });
assert.equal(nodes.children[1].textContent, name, "the name is its text");
const html = mb.actorIdentityHtml(name, { nameClass: "git-commit-author" });
assert.equal(html, markup(nodes), "the markup form draws what the nodes form draws");
cases["markup, a name with markup in it"] = html.replace(glyph, "{the person glyph}");

console.log(JSON.stringify(cases, null, 2));
