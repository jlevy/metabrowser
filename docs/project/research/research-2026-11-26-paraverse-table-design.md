# Research: Paraverse and Metabrowser Tables

**Date:** 2026-11-26

The comparison covers Paraverse’s live Person table, Columns menu, record detail, and
overview on Patch the Conference.
The Metabrowser examples use a synthetic SQLite database with foreign keys and the
existing CSV fixture.
Astra independently reviewed both implementations and the proposed SoftSchema collection
view.

## How the Views Fit

| Surface | Paraverse pattern | Metabrowser decision |
| --- | --- | --- |
| Collection navigation | Entity families with counts, a dataset chooser, and a quality entry point | Use the folder’s existing Table offer and panel stack. List its contracts and Problems with counts and index state. The directory tree remains the navigation for files. |
| Table identity | Short type name, row count, and schema description above the grid | Use the standard page header and shared toolbar. Show a schema description when it explains a contract that the title alone cannot identify. |
| Responsive grid | The default grid keeps the name when the ID repeats it. Explicit choices scroll horizontally. | Keep Metabrowser’s width calculation and fixed row heights. Use a source-declared label when choosing which default identity column to preserve. Retain the stable key in details and when explicitly selected. |
| Columns and filters | Grouped columns include field descriptions. Enum and boolean cells add filters. A relationship filter names the record it references. | Use the current Fields and References groups, header dialogs, and removable filters. Accept field help from schemas and resolve the related record’s label through the existing card route. |
| Values | Compact tags for enum values and small previews of related records | Apply Metabrowser’s distinct literal, filter, and reference roles. Preserve empty, missing, null, invalid, and truncated values. A future multi-reference cell needs one keyboard-reachable disclosure or record link within the fixed row height. |
| Record detail | A name and source path, nested object lists as sub-tables, inbound and outbound relationships, expandable raw data | Add a source-provided title to the shared record panel. Let the SoftSchema adapter supply schema-ordered fields, source path, nested structure, validation messages, and the Markdown body. Use the shared data-grid styles for bounded sub-tables and the inline tree for general JSON. |
| Relationship drill-down | The related table carries the relationship’s direction and type | Carry the referencing and referenced field lists in the shared filter. A record with separate buyer and seller counts opens the rows for the chosen relationship. |
| Freshness | The app offers named dataset views and presents import identity and source coverage | Retain the table plugin’s live refresh, keyboard place, and selection. The collection overview reports build progress and whether counts are complete. Keep graph composition and domain-specific provenance in their adapters. |

## Design Ownership

Use the existing `TableSource` protocol and table plugin for the grid, navigation,
filters, pagination, printing, keyboard behavior, and live updates.
SQLite and fSQLite already share the adapter for reading a database.
CSV and structured record lists already mount the same view.
SoftSchema collections can join that renderer through a folder source.

Shared behavior belongs in the table plugin.
Collection discovery, path identity, read-only repair reports, nested field
descriptions, and contracts belong to the SoftSchema adapter.
Paraverse’s entity family colors, source-merging rules, and graph edge data belong to
Paraverse. Extract a cross-repository UI package once a second production integration
demonstrates a stable mounting, navigation, and style contract.

## Checks

- A record with two foreign keys from the same table exposes two drill-downs whose row
  counts match their destinations, including composite keys and an incomplete count.
- A friendly label can repeat.
  Links still carry their exact key and restore keyboard focus when returning.
  Tables that have only position keys retain a row number.
- A narrow layout preserves a useful identity.
  Explicit column selections remain visible by scrolling, and a bounded preview never
  introduces unreachable links.
- A shaped nested list fits a sub-table.
  Wide or irregular objects remain inspectable in a definition list or tree.
- A cold collection reports its progress separately from an empty finished result.
  Existing live-table selection and position rules still apply.

## Sources

- [Paraverse browser architecture](https://github.com/jlevy/paraverse/blob/main/docs/project/architecture/arch-2026-10-24-kb-browser.md)
- [Paraverse table](https://github.com/jlevy/paraverse/blob/main/db/src/paraverse_graph/web/js/table.js)
  and
  [record view](https://github.com/jlevy/paraverse/blob/main/db/src/paraverse_graph/web/js/record.js)
- [Metabrowser data tables](../../design-system.md#data-tables) and
  [table sources](../../plugins.md#table-sources)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
