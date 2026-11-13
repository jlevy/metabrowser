#!/usr/bin/env node

// Startup-script comments: how many of the eager bytes they are, and test builds without
// them or with more of them.
//
// The startup-script gate counts the compressed bytes of the scripts a folder's shell
// requests before DOMContentLoaded, comments included. This counts what share of those
// bytes the comments are, and writes two kinds of variant a tier-probe.mjs comparison can
// serve: the same scripts with every comment removed, and the same scripts with every
// comment followed by another of the same kind, a given fraction of its length, of prose
// drawn in order from a text file. Neither changes a line of code, and that is checked:
// each variant is parsed again and must give the original's tokens, in order. Removal
// keeps every line break, so line numbers stay where they were.
//
//   node explorations/performance-loop/eager-comments.mjs --origin http://127.0.0.1:8411
//   node explorations/performance-loop/eager-comments.mjs --origin http://127.0.0.1:8411 \
//     --strip .bench/eager/stripped --pad .bench/eager/padded --prose .bench/prose.txt
//
// --origin reads the startup set from that server's shell for a folder, as
// devtools/check_startup_scripts.py does; script names after the options are read
// instead. Sizes are gzip level 6, the application's middleware level. Node's gzip
// header differs from Python's by a few bytes a file, so a total here can be a few
// hundred bytes under the check's.
//
// The parser is TypeScript's, from the locked development install, because telling a
// comment from a regular expression or a template string needs a parser.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const STATIC_DIR = path.join(ROOT, "src", "metabrowser", "static");
const ts = createRequire(path.join(ROOT, "package.json"))("typescript");
const GZIP_LEVEL = 6;
const TYPE_ANNOTATION = /^\/\*\*\s*@type\s*\{[^\n]*\}\s*\*\/$/;

function parseArgs(argv) {
  const options = { origin: "", strip: "", pad: "", prose: "", fraction: 1, names: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!flag.startsWith("--")) {
      options.names.push(flag);
      continue;
    }
    const value = argv[index + 1];
    index += 1;
    if (value === undefined) {
      throw new Error(`${flag} needs a value`);
    }
    if (flag === "--origin") {
      options.origin = value;
    } else if (flag === "--strip") {
      options.strip = value;
    } else if (flag === "--pad") {
      options.pad = value;
    } else if (flag === "--prose") {
      options.prose = value;
    } else if (flag === "--fraction") {
      options.fraction = Number(value);
    } else {
      throw new Error(`unknown option ${flag}`);
    }
  }
  if (options.pad && !options.prose) {
    throw new Error("--pad needs --prose, a text file to draw the added comments from");
  }
  return options;
}

// The startup set of a folder's shell: every script tag outside /static/vendor/.
async function startupNames(origin) {
  const html = await (await fetch(`${origin}/view/`)).text();
  const names = [];
  for (const match of html.matchAll(/<script[^>]*\bsrc="([^"]+)"/g)) {
    const pathname = new URL(match[1], origin).pathname;
    if (pathname.startsWith("/static/") && !pathname.startsWith("/static/vendor/")) {
      names.push(pathname.slice("/static/".length));
    }
  }
  return names;
}

function parse(text, name) {
  const source = ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  if (source.parseDiagnostics?.length) {
    throw new Error(`${name} does not parse`);
  }
  const comments = new Map();
  const tokens = [];
  const record = (ranges) => {
    for (const range of ranges ?? []) {
      comments.set(range.pos, range);
    }
  };
  const visit = (node) => {
    // JSDoc is attached to nodes as children of its own; its text is the comment's.
    if (node.kind >= ts.SyntaxKind.FirstJSDocNode && node.kind <= ts.SyntaxKind.LastJSDocNode) {
      return;
    }
    const children = node.getChildren(source);
    if (children.length === 0) {
      tokens.push(`${node.kind}:${node.getText(source)}`);
      record(ts.getLeadingCommentRanges(text, node.pos));
      record(ts.getTrailingCommentRanges(text, node.end));
      return;
    }
    for (const child of children) {
      visit(child);
    }
  };
  visit(source);
  return { comments: [...comments.values()].sort((a, b) => a.pos - b.pos), tokens };
}

function sameTokens(a, b) {
  return a.length === b.length && a.every((token, index) => token === b[index]);
}

function strip(text, comments) {
  let out = "";
  let at = 0;
  for (const comment of comments) {
    out += text.slice(at, comment.pos);
    out += "\n".repeat(text.slice(comment.pos, comment.end).split("\n").length - 1);
    at = comment.end;
  }
  return (out + text.slice(at)).replace(/[ \t]+\n/g, "\n");
}

function padder(prose, fraction) {
  const body = prose.replaceAll("*/", "* /");
  let at = 0;
  const take = (length, oneLine) => {
    let out = "";
    while (out.length < length) {
      const chunk = body.slice(at, at + length - out.length);
      at = (at + chunk.length) % body.length;
      out += chunk;
    }
    return oneLine ? out.replace(/[\r\n]/g, " ") : out;
  };
  return (text, comments) => {
    let out = "";
    let at_ = 0;
    for (const comment of comments) {
      out += text.slice(at_, comment.end);
      const length = Math.round((comment.end - comment.pos) * fraction);
      out +=
        comment.kind === ts.SyntaxKind.SingleLineCommentTrivia
          ? `\n// ${take(Math.max(0, length - 3), true)}`
          : `/* ${take(Math.max(0, length - 6), false)} */`;
      at_ = comment.end;
    }
    return out + text.slice(at_);
  };
}

const gzipped = (text) => zlib.gzipSync(Buffer.from(text), { level: GZIP_LEVEL }).length;

const options = parseArgs(process.argv.slice(2));
const names = options.origin ? await startupNames(options.origin) : options.names;
if (names.length === 0) {
  throw new Error("name the scripts, or give --origin to read them from a shell");
}
const pad = options.pad ? padder(readFileSync(options.prose, "utf8"), options.fraction) : null;
for (const directory of [options.strip, options.pad].filter(Boolean)) {
  mkdirSync(directory, { recursive: true });
}
const rows = [];
for (const name of names) {
  const text = readFileSync(path.join(STATIC_DIR, name), "utf8");
  const { comments, tokens } = parse(text, name);
  const commentText = comments.map((comment) => text.slice(comment.pos, comment.end));
  const row = {
    name,
    bytes: Buffer.byteLength(text),
    gzip: gzipped(text),
    comments: comments.length,
    commentBytes: commentText.reduce((total, body) => total + Buffer.byteLength(body), 0),
    jsdocBytes: commentText
      .filter((body) => body.startsWith("/**"))
      .reduce((total, body) => total + Buffer.byteLength(body), 0),
    // An inline type, such as `/** @type {HTMLElement | null} */` before a declaration.
    typeAnnotations: commentText.filter((body) => TYPE_ANNOTATION.test(body)).length,
    typeAnnotationBytes: commentText
      .filter((body) => TYPE_ANNOTATION.test(body))
      .reduce((total, body) => total + Buffer.byteLength(body), 0),
  };
  const stripped = strip(text, comments);
  const again = parse(stripped, name);
  if (again.comments.length || !sameTokens(again.tokens, tokens)) {
    throw new Error(`${name}: removing its comments changed its code`);
  }
  row.strippedGzip = gzipped(stripped);
  if (options.strip) {
    writeFileSync(path.join(options.strip, name), stripped);
  }
  if (pad) {
    const padded = pad(text, comments);
    if (!sameTokens(parse(padded, name).tokens, tokens)) {
      throw new Error(`${name}: padding its comments changed its code`);
    }
    row.paddedGzip = gzipped(padded);
    writeFileSync(path.join(options.pad, name), padded);
  }
  rows.push(row);
}
const total = (field) => rows.reduce((sum, row) => sum + (row[field] ?? 0), 0);
for (const row of rows) {
  console.log(
    `${String(row.bytes).padStart(8)} B ${String(row.gzip).padStart(7)} gz  comments ` +
      `${String(row.commentBytes).padStart(7)} B (${((100 * row.commentBytes) / row.bytes).toFixed(0)}%)` +
      `  without ${String(row.strippedGzip).padStart(7)} gz  ${row.name}`,
  );
}
const headers = 300 * rows.length;
console.log(
  `${rows.length} scripts: ${total("bytes")} bytes, ${total("commentBytes")} of them comments ` +
    `(${((100 * total("commentBytes")) / total("bytes")).toFixed(1)}%, ${total("jsdocBytes")} JSDoc, ` +
    `${total("typeAnnotationBytes")} in ${total("typeAnnotations")} one-line @type annotations); ` +
    `transferred with 300 header bytes each ${total("gzip") + headers}, without comments ` +
    `${total("strippedGzip") + headers}` +
    (pad ? `, padded ${total("paddedGzip") + headers}` : ""),
);
