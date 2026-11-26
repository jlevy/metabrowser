// Lean 4 for Highlight.js: a rule-for-rule port of the official Lean 4 grammar.
//
// Upstream is `vscode-lean4/syntaxes/lean4.json` in github.com/leanprover/vscode-lean4,
// the grammar VS Code, GitHub's linguist ("Lean 4", tm_scope source.lean4), and Shiki
// use. It is Apache-2.0 licensed (lean.license.txt beside this file); the copy this port
// follows is pinned in tests/fixtures/vscode-lean4/, and tests/test_lean_grammar.py
// holds every regex in UPSTREAM below to that copy, so refreshing the fixture fails until
// this file follows it.
//
// Every upstream `match`, `begin`, and `end` is copied verbatim into UPSTREAM. Two
// adaptations, which the test names: definitionName's POSIX `[:space:]`, which a
// JavaScript character class reads as the letters of the word, is `\s` here; and the
// Markdown grammar upstream embeds in comments is not ported, so a comment is one
// comment. TextMate scopes map to the standard Highlight.js scopes; `sorry`, `admit`, and
// `#exit`, which upstream marks invalid.illegal because they leave a proof unfinished,
// keep the `sorry` scope Lean's earlier Highlight.js grammar gave them. Highlight.js
// tries a rule's contents before its `end`, the reverse of TextMate; unlessEnd restores
// TextMate's order where the two can meet.

(() => {
  /** @typedef {Record<string, unknown>} HljsMode */

  const UPSTREAM = Object.freeze({
    dashCommentBegin: String.raw`--`,
    dashCommentEnd: String.raw`$`,
    docCommentBegin: String.raw`/--`,
    modDocCommentBegin: String.raw`/-!`,
    blockCommentBegin: String.raw`/-`,
    commentEnd: String.raw`-/`,
    sortKeywords: String.raw`\b(Prop|Type|Sort)\b`,
    attributeCommand: String.raw`\b(attribute\b\s*)(?:(\[[^\]\s]*\])|\[([^\]\s]*))`,
    attributeAt: String.raw`(@)(?:(\[[^\]\s]*\])|\[([^\]\s]*))`,
    modifiers: String.raw`\b(?<!\.)(local|scoped|partial|unsafe|nonrec|public|private|protected|noncomputable|meta)(?!\.)\b`,
    unfinished: String.raw`\b(sorry|admit|#exit)\b`,
    hashCommands: String.raw`#(print|eval|eval!|reduce|synth|widget|where|version|with_exporting|check|check_tactic|check_tactic_failure|check_failure|check_simp|discr_tree_key|discr_tree_simp_key|guard|guard_expr|guard_msgs)\b`,
    derivingInstance: String.raw`\bderiving\s+instance\b`,
    definitionBegin: String.raw`\b(?<!\.)(inductive|coinductive|structure|theorem|axiom|abbrev|lemma|def|instance|class)\b\s+(\{[^}]*\})?`,
    definitionEnd: String.raw`(?=\bwith\b|\bextends\b|\bwhere\b|[:\|\(\[\{⦃<>])`,
    definitionName: String.raw`\b[^:«»\(\)\{\}\s=→λ∀?][^:«»\(\)\{\}\s]*`,
    definitionComma: String.raw`,`,
    keywords: String.raw`\b(?<!\.)(theorem|show|have|using|haveI|from|suffices|nomatch|nofun|no_index|def|class|structure|instance|elab|set_option|initialize|builtin_initialize|example|inductive_fixpoint|inductive|coinductive_fixpoint|coinductive|termination_by\?|termination_by|decreasing_by|partial_fixpoint|axiom|universe|variable|module|import all|import|open|export|prelude|renaming|hiding|do|by\?|by|let|letI|let_expr|extends|mutual|mut|where|rec|declare_syntax_cat|syntax|macro_rules|macro|binop_lazy%|binop%|unop%|binrel_no_prop%|binrel%|leftact%|rightact%|max_prec|leading_parser|elab_rules|deriving|fun|section|namespace|end|prefix|postfix|infixl|infixr|infix|notation|abbrev|if|bif|then|else|calc|matches|match_expr|match|with|forall|for|while|repeat|unless|until|panic!|unreachable!|assert!|try|catch|finally|return|continue|break|exists|mod_cast|exact\?%|include_str|include|in|trailing_parser|tactic_tag|tactic_alt|tactic_extension|register_tactic_tag|type_of%|binder_predicate|grind_propagator|builtin_grind_propagator|grind_pattern|simproc|builtin_simproc|simproc_pattern%|builtin_simproc_pattern%|simproc_decl|builtin_simproc_decl|dsimproc|builtin_dsimproc|dsimproc_decl|builtin_dsimproc_decl|show_panel_widgets|show_term|seal|unseal|nat_lit|norm_cast_add_elim|println!|private_decl%|declare_config_elab|decl_name%|register_error_explanation|register_builtin_option|register_option|register_parser_alias|register_simp_attr|register_linter_set|register_label_attr|recommended_spelling|reportIssue!|reprove|run_elab|run_cmd|run_meta|value_of%|add_decl_doc|omit|opaque|json%|dbg_trace|trace_goal\[[^\]\s]*\]|trace\[[^\]\s]*\]|throwErrorAt|throwError|throwNamedErrorAt|throwNamedError|logNamedWarningAt|logNamedWarning|logNamedErrorAt|logNamedError)(?!\.)\b`,
    guillemetBegin: String.raw`«`,
    guillemetEnd: String.raw`»`,
    interpolatedBegin: String.raw`(s!|m!|throwError|dbg_trace|panic!|reportIssue!|(?:trace_goal|trace)\[[^\]\s]*\])\s*"`,
    interpolationBegin: String.raw`(\{)`,
    interpolationEnd: String.raw`(\})`,
    stringQuote: String.raw`"`,
    escapeSimple: String.raw`\\[\\"ntr']`,
    escapeHex: String.raw`\\x[0-9A-Fa-f][0-9A-Fa-f]`,
    escapeUnicode: String.raw`\\u[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]`,
    booleans: String.raw`\b(true|false)\b`,
    character: String.raw`(?<!\]|\w)'[^\\']'`,
    characterEscape: String.raw`(?<!\]|\w)'(\\(x[0-9A-Fa-f][0-9A-Fa-f]|u[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]|.))'`,
    numbers: String.raw`\b([0-9]+|0([xX][0-9a-fA-F]+)|[-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?)\b`,
  });

  /** @param {string} source */
  const re = (source) => new RegExp(source);

  /**
   * TextMate tries a rule's `end` before its patterns at a position; Highlight.js tries
   * the patterns first. Guarding a contained pattern with a lookahead of *end* restores
   * TextMate's order, so `structure Point where` ends at `where` as it does upstream.
   * @param {string} end
   * @param {string} pattern
   */
  const unlessEnd = (end, pattern) => new RegExp(`(?!${end})${pattern}`);

  /** @returns {HljsMode} */
  function lean4() {
    /** @type {HljsMode} */
    const blockComment = {
      scope: "comment",
      begin: re(UPSTREAM.blockCommentBegin),
      end: re(UPSTREAM.commentEnd),
      contains: ["self"],
    };
    const comments = [
      { scope: "comment", begin: re(UPSTREAM.dashCommentBegin), end: re(UPSTREAM.dashCommentEnd) },
      {
        scope: "comment",
        begin: re(UPSTREAM.docCommentBegin),
        end: re(UPSTREAM.commentEnd),
        contains: [blockComment],
      },
      {
        scope: "comment",
        begin: re(UPSTREAM.modDocCommentBegin),
        end: re(UPSTREAM.commentEnd),
        contains: [blockComment],
      },
      blockComment,
    ];
    const escapes = [UPSTREAM.escapeSimple, UPSTREAM.escapeHex, UPSTREAM.escapeUnicode].map(
      (source) => ({ scope: "char.escape", match: re(source) }),
    );
    /** @type {HljsMode[]} */
    const top = [];
    /** @type {HljsMode} */
    const interpolation = {
      begin: re(UPSTREAM.interpolationBegin),
      end: re(UPSTREAM.interpolationEnd),
      beginScope: "keyword",
      endScope: "keyword",
      contains: top,
    };
    top.push(
      ...comments,
      { scope: "type", match: re(UPSTREAM.sortKeywords) },
      { scope: "meta", match: re(UPSTREAM.attributeCommand) },
      { scope: "meta", match: re(UPSTREAM.attributeAt) },
      { scope: "keyword", match: re(UPSTREAM.modifiers) },
      { scope: "sorry", match: re(UPSTREAM.unfinished) },
      { scope: "keyword", match: re(UPSTREAM.hashCommands) },
      { scope: "keyword", match: re(UPSTREAM.derivingInstance) },
      {
        begin: re(UPSTREAM.definitionBegin),
        beginScope: "keyword",
        end: re(UPSTREAM.definitionEnd),
        contains: [
          ...comments,
          {
            scope: "title.function",
            match: unlessEnd(UPSTREAM.definitionEnd, UPSTREAM.definitionName),
          },
          {
            scope: "title.function",
            begin: re(UPSTREAM.guillemetBegin),
            end: re(UPSTREAM.guillemetEnd),
          },
          { match: re(UPSTREAM.definitionComma) },
        ],
      },
      { scope: "keyword", match: re(UPSTREAM.keywords) },
      { begin: re(UPSTREAM.guillemetBegin), end: re(UPSTREAM.guillemetEnd) },
      {
        scope: "string",
        begin: re(UPSTREAM.interpolatedBegin),
        end: re(UPSTREAM.stringQuote),
        contains: [interpolation, ...escapes],
      },
      {
        scope: "string",
        begin: re(UPSTREAM.stringQuote),
        end: re(UPSTREAM.stringQuote),
        contains: escapes,
      },
      { scope: "literal", match: re(UPSTREAM.booleans) },
      { scope: "string", match: re(UPSTREAM.character) },
      { scope: "string", match: re(UPSTREAM.characterEscape) },
      { scope: "number", match: re(UPSTREAM.numbers) },
    );
    return { name: "Lean 4", aliases: ["lean4"], contains: top };
  }

  if (typeof hljs !== "undefined") {
    hljs.registerLanguage("lean", lean4);
  }
})();
