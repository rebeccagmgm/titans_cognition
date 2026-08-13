## Parallel-work boundary

Recorded on 2026-08-12 before implementation.

- Existing field-side work is present in `src/titans_cognition/cli.py`, the field/context semantic modules, their tests, configs, schemas, scripts, project status documents, and the active field-semantic OpenSpec Changes.
- This Change owns only `src/titans_cognition/table_semantics.py`, `src/titans_cognition/table_review.py`, `tests/test_table_semantics.py`, `tests/test_table_review.py`, `cases/tradeflow/table-semantic-map.yaml`, and this Change directory.
- `src/titans_cognition/cli.py` is the only intentional overlap. Changes there must be additive and must preserve the existing field/context commands.
- Fixed `output/` runs and the Wiki cache are read-only inputs. Generated table-semantic runs remain ignored build artifacts.
- No reset, checkout, rewrite, or cleanup of parallel field-side files is authorized.

## Fixed input decision

The first table-semantic run is pinned by `cases/tradeflow/table-semantic-map.yaml` to:

- the TRADEFLOW slice of the 2026-08-11 Panorama physical-facts run;
- the replayed 2026-08-11 table-classification run;
- the 2026-08-12 business-review field-semantic run;
- the 2026-08-12 context-enriched field-semantic run;
- the 2026-08-11 Wiki Tree snapshot.

No Wiki body page is approved in the initial config. Body evidence support is implemented and tested, but the real run must report it as unavailable rather than crawl or select pages implicitly.
