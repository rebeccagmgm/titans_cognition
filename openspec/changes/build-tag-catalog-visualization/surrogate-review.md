# Surrogate Review

## Scope

- Input: `20260812T222759+0800` tag snapshot.
- Reader artifact: snapshot-scoped `index.html` and `tag-catalog-projection-manifest.json`.
- Review mode: independent source/reader inspection plus static HTML/JavaScript smoke checks. Browser interaction was attempted but the in-app browser blocked `file://` navigation by policy.

## Representative checks

- Cataloged rows retain multi-segment paths and are projected as directory nodes followed by tag-dimension leaves.
- Rows without a usable `catalogPath` are retained in the explicit uncategorized branch.
- Dimension SQL content is present in the page, with file resolution and SHA-256 verification applied before status assignment.
- The real snapshot has `2,424` dimensions and `2,424` `HASH_MISMATCH` SQL statuses. This is visible evidence of a snapshot/file mismatch, not a `FOUND` result.
- The page keeps task SQL out of scope and distinguishes dimension SQL from scheduling SQL.
- Static checks found the tree, search, detail, selection, filtering, and SQL-rendering hooks; the generated JavaScript passed `node --check`.

## Disposition

`ACCEPT` for this bounded engineering Change with an explicit evidence gap: the current snapshot's SQL hashes do not match the local SQL files. This does not constitute SQL correctness or business acceptance. Browser-level interaction remains unverified because the browser security policy rejected the local `file://` target.

## Smallest next action

If browser-level acceptance is required, serve the artifact through an approved local testing surface or open it manually in a permitted browser context, then verify search, selection, count updates, and SQL display. Do not change the evidence status without reconciling the SQL hashes.
