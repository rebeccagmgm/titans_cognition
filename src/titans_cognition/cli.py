"""Command-line entry points for the deterministic cognition core."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .baseline import build_independent_baseline
from .classification import (
    import_llm_responses,
    load_classification_config,
    run_classification,
    write_classification_results,
)
from .field_concepts import (
    load_field_concept_config,
    run_field_concepts,
    write_field_concept_results,
)
from .field_semantics import (
    load_field_semantic_config,
    run_field_semantics,
    write_field_semantic_results,
)
from .context_semantics import (
    load_context_map_config,
    run_context_map,
    write_context_map_results,
)
from .indicator_catalog import build_indicator_catalog
from .table_semantics import (
    load_table_semantic_config,
    run_table_semantic_map,
    write_table_semantic_results,
)
from .llm_field_review import (
    import_review_responses,
    load_review_config,
    prepare_review,
    render_review as render_field_concept_llm_review,
)
from .derive import derive_observations
from .deep import (
    derive_tradeflow_features,
    load_sample,
    select_tradeflow_sample,
    write_sample,
)
from .inference import infer_tradeflow
from .evaluation import (
    evaluate_tradeflow,
    load_inference_directory,
    load_yaml_mapping,
    render_review_pack,
)
from .measurements import render_measurement_pack
from .extract import (
    ColumnMetadata,
    ConstraintMetadata,
    DefinitionMetadata,
    DependencyMetadata,
    IndexMetadata,
    ObjectMetadata,
    PhysicalFacts,
    extract_facts,
    iter_fact_batches,
)
from .io import (
    read_json_facts,
    write_json_derived,
    write_json_fact_batches,
    write_json_facts,
    write_parquet_derived,
    write_parquet_facts,
    write_json_tradeflow_derived,
    write_json_tradeflow_inference,
)
from .provider import GfDerivativeDbProvider
from .reconcile import panorama_delivery_ready, reconcile_facts
from .render import render_panorama
from .scope import load_scope
from .semantic_cleaning import import_review_decisions


def _filter_facts_by_schema(facts: PhysicalFacts, schema_name: str) -> PhysicalFacts:
    """Return a bounded schema slice while retaining its declared dependencies."""

    normalized = schema_name.strip().upper()
    objects = [
        row
        for row in facts.objects
        if str(row.get("schema_name", "")).upper() == normalized
    ]
    asset_ids = {str(row["asset_id"]) for row in objects}

    def owned(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        return [row for row in rows if str(row.get("asset_id", "")) in asset_ids]

    return PhysicalFacts(
        objects=objects,
        columns=owned(facts.columns),
        constraints=owned(facts.constraints),
        indexes=owned(facts.indexes),
        object_definitions=owned(facts.object_definitions),
        dependencies=[
            row
            for row in facts.dependencies
            if str(row.get("source_asset_id", "")) in asset_ids
        ],
        failures=[
            row for row in facts.failures if str(row.get("asset_id", "")) in asset_ids
        ],
    )


def _object_metadata_from_mapping(data: dict[str, Any]) -> ObjectMetadata:
    return ObjectMetadata(
        schema_name=data["schema_name"],
        object_name=data["object_name"],
        object_type=data["object_type"],
        object_comment=data.get("object_comment"),
        columns=tuple(ColumnMetadata(**item) for item in data.get("columns", [])),
        constraints=tuple(
            ConstraintMetadata(
                **{
                    **item,
                    "column_names": tuple(item.get("column_names", [])),
                    "referenced_column_names": tuple(
                        item.get("referenced_column_names", [])
                    ),
                }
            )
            for item in data.get("constraints", [])
        ),
        indexes=tuple(
            IndexMetadata(
                **{
                    **item,
                    "column_names": tuple(item.get("column_names", [])),
                    "expressions": tuple(item.get("expressions", [])),
                }
            )
            for item in data.get("indexes", [])
        ),
        definitions=tuple(
            DefinitionMetadata(**item) for item in data.get("definitions", [])
        ),
        dependencies=tuple(
            DependencyMetadata(**item) for item in data.get("dependencies", [])
        ),
        is_boundary=data.get("is_boundary", False),
        boundary_for_case_ids=tuple(data.get("boundary_for_case_ids", [])),
        extraction_status=data.get("extraction_status", "SUCCESS"),
        error_category=data.get("error_category"),
    )


def _load_metadata_json(path: Path) -> list[ObjectMetadata]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("objects", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError(
            "metadata JSON must be a list or an object with an objects list"
        )
    return [_object_metadata_from_mapping(item) for item in records]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="titans-cognition")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-scope")
    validate.add_argument("--scope", required=True, type=Path)

    extract = subparsers.add_parser("extract")
    extract.add_argument("--scope", required=True, type=Path)
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-json", type=Path)
    source.add_argument("--db")
    extract.add_argument("--adapter-python", default="python")
    extract.add_argument("--adapter-script", type=Path)
    extract.add_argument(
        "--definition-mode",
        choices=("record-only", "all"),
        default="record-only",
        help="record capability gaps or retrieve DDL/View SQL",
    )
    extract.add_argument("--output", required=True, type=Path)
    extract.add_argument("--run-id", required=True)
    extract.add_argument(
        "--format",
        choices=("json", "parquet", "both"),
        default="json",
    )
    extract.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="number of objects normalized before a JSON fact batch is flushed",
    )
    derive = subparsers.add_parser("derive")
    derive.add_argument("--input-dir", required=True, type=Path)
    derive.add_argument("--output", required=True, type=Path)
    derive.add_argument(
        "--format",
        choices=("json", "parquet", "both"),
        default="json",
    )
    classify = subparsers.add_parser("classify-panorama")
    classify.add_argument("--facts-dir", required=True, type=Path)
    classify.add_argument("--config", required=True, type=Path)
    classify.add_argument("--wiki-metadata", required=True, type=Path)
    classify.add_argument("--output", required=True, type=Path)
    classify.add_argument("--schema")
    classify.add_argument("--source-panorama-root", type=Path)
    classify.add_argument(
        "--format",
        choices=("json", "parquet", "both"),
        default="both",
    )
    import_llm = subparsers.add_parser("import-classification-llm")
    import_llm.add_argument("--classification-dir", required=True, type=Path)
    import_llm.add_argument("--responses", required=True, type=Path)
    import_llm.add_argument("--model-id", required=True)
    field_concepts = subparsers.add_parser("discover-field-concepts")
    field_concepts.add_argument("--facts-dir", required=True, type=Path)
    field_concepts.add_argument("--config", required=True, type=Path)
    field_concepts.add_argument("--output", required=True, type=Path)
    field_concepts.add_argument(
        "--write-diagnostics",
        action="store_true",
        help="write run-local nearest-neighbor diagnostics",
    )
    field_semantics = subparsers.add_parser("discover-field-semantics")
    field_semantics.add_argument("--facts-dir", required=True, type=Path)
    field_semantics.add_argument("--config", required=True, type=Path)
    field_semantics.add_argument("--output", required=True, type=Path)
    field_semantics.add_argument(
        "--investigation-query",
        action="append",
        default=[],
        help="repeatable acceptance query; does not alter inference",
    )
    context_map = subparsers.add_parser("build-context-semantic-map")
    context_map.add_argument("--config", required=True, type=Path)
    context_map.add_argument("--output", required=True, type=Path)
    indicator_catalog = subparsers.add_parser("build-indicator-catalog-review")
    indicator_catalog.add_argument("--snapshot-dir", required=True, type=Path)
    indicator_catalog.add_argument("--output", required=True, type=Path)
    table_map = subparsers.add_parser("build-table-semantic-map")
    table_map.add_argument("--config", required=True, type=Path)
    table_map.add_argument("--output", required=True, type=Path)
    import_context_review = subparsers.add_parser("import-context-semantic-review")
    import_context_review.add_argument("--review-pack-dir", required=True, type=Path)
    import_context_review.add_argument("--responses", required=True, type=Path)
    import_context_review.add_argument("--output", required=True, type=Path)
    import_context_review.add_argument("--model-id", required=True)
    prepare_field_review = subparsers.add_parser("prepare-field-concept-llm-review")
    prepare_field_review.add_argument("--field-concepts-dir", required=True, type=Path)
    prepare_field_review.add_argument("--config", required=True, type=Path)
    prepare_field_review.add_argument("--output", required=True, type=Path)
    prepare_field_review.add_argument("--max-packs", type=int)
    prepare_field_review.add_argument("--token-budget", type=int)
    import_field_review = subparsers.add_parser("import-field-concept-llm-review")
    import_field_review.add_argument("--review-dir", required=True, type=Path)
    import_field_review.add_argument("--responses", required=True, type=Path)
    import_field_review.add_argument("--model-id", required=True)
    import_field_review.add_argument("--cache-dir", type=Path)
    render_field_review = subparsers.add_parser("render-field-concept-llm-review")
    render_field_review.add_argument("--review-dir", required=True, type=Path)
    render_field_review.add_argument("--source-panorama-root", type=Path)
    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--scope", required=True, type=Path)
    reconcile.add_argument("--facts-dir", required=True, type=Path)
    reconcile.add_argument("--baseline-json", required=True, type=Path)
    reconcile.add_argument("--output", type=Path)
    reconcile.add_argument("--render-dir", type=Path)
    render = subparsers.add_parser("render")
    render.add_argument("--scope", required=True, type=Path)
    render.add_argument("--facts-dir", required=True, type=Path)
    render.add_argument("--output", required=True, type=Path)
    render.add_argument(
        "--code-version",
        default=os.environ.get("TITANS_COGNITION_CODE_VERSION", "working-tree"),
    )
    baseline = subparsers.add_parser("baseline")
    baseline.add_argument("--scope", required=True, type=Path)
    baseline.add_argument("--db", required=True)
    baseline.add_argument("--adapter-python", default="python")
    baseline.add_argument("--adapter-script", required=True, type=Path)
    baseline.add_argument("--output", required=True, type=Path)
    sample = subparsers.add_parser("select-sample")
    sample.add_argument("--facts-dir", required=True, type=Path)
    sample.add_argument("--output", required=True, type=Path)
    sample.add_argument("--max-objects", type=int, default=8)
    sample.add_argument(
        "--include-numeric-suffix",
        action="store_true",
        help="include numeric-suffixed objects in the V1B sample",
    )
    deep_derive = subparsers.add_parser("deep-derive")
    deep_derive.add_argument("--facts-dir", required=True, type=Path)
    deep_derive.add_argument("--sample", required=True, type=Path)
    deep_derive.add_argument("--output", required=True, type=Path)
    deep_infer = subparsers.add_parser("deep-infer")
    deep_infer.add_argument("--facts-dir", required=True, type=Path)
    deep_infer.add_argument("--sample", required=True, type=Path)
    deep_infer.add_argument("--output", required=True, type=Path)
    deep_evaluate = subparsers.add_parser("deep-evaluate")
    deep_evaluate.add_argument("--inference-dir", required=True, type=Path)
    deep_evaluate.add_argument("--gold-set", required=True, type=Path)
    deep_evaluate.add_argument("--reviews", required=True, type=Path)
    deep_evaluate.add_argument("--measurements", type=Path)
    deep_evaluate.add_argument("--output", required=True, type=Path)
    measurement_pack = subparsers.add_parser("deep-measure-pack")
    measurement_pack.add_argument("--measurements", required=True, type=Path)
    measurement_pack.add_argument("--output", required=True, type=Path)
    review_pack = subparsers.add_parser("deep-review-pack")
    review_pack.add_argument("--evaluation-report", required=True, type=Path)
    review_pack.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate-scope":
        scope = load_scope(args.scope)
        print(
            json.dumps(
                {
                    "scope_id": scope.scope_id,
                    "source_label": scope.source_label,
                    "schema_count": len(scope.schemas),
                    "object_types": list(scope.object_types),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "derive":
        facts = read_json_facts(args.input_dir)
        derived = derive_observations(facts)
        written: dict[str, Path] = {}
        if args.format in ("json", "both"):
            written.update(write_json_derived(args.output, derived))
        if args.format in ("parquet", "both"):
            written.update(write_parquet_derived(args.output, derived))
        print(
            json.dumps(
                {
                    "schema_count": len(derived.schema_summary),
                    "object_profile_count": len(derived.object_inventory_profiles),
                    "dependency_summary_count": len(derived.dependency_summary),
                    "failure_count": len(derived.extraction_failures),
                    "outputs": {name: str(path) for name, path in written.items()},
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "classify-panorama":
        facts = read_json_facts(args.facts_dir)
        if args.schema:
            facts = _filter_facts_by_schema(facts, args.schema)
        if not facts.objects:
            raise ValueError("classification scope contains no objects")
        config = load_classification_config(args.config)
        wiki_metadata = json.loads(args.wiki_metadata.read_text(encoding="utf-8"))
        if not isinstance(wiki_metadata, dict):
            raise ValueError("Wiki metadata JSON must be an object")
        result = run_classification(facts, config, wiki_metadata)
        formats = ("json", "parquet") if args.format == "both" else (args.format,)
        paths = write_classification_results(
            args.output,
            result,
            formats=formats,
            source_panorama_root=args.source_panorama_root,
        )
        print(
            json.dumps(
                {
                    "schema": args.schema,
                    **result.stats,
                    "graph_run_id": result.graph_run_id,
                    "review_index": str(paths["review_index"]),
                    "manifest": str(paths["manifest"]),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "import-classification-llm":
        stats = import_llm_responses(
            args.classification_dir,
            args.responses,
            model_id=args.model_id,
        )
        print(json.dumps(stats, ensure_ascii=False))
        return 0

    if args.command == "discover-field-concepts":
        facts = read_json_facts(args.facts_dir)
        config = load_field_concept_config(args.config)
        result = run_field_concepts(facts, config)
        paths = write_field_concept_results(
            args.output,
            result,
            write_diagnostics=args.write_diagnostics,
            source_panorama_root=Path(args.facts_dir) / "panorama",
        )
        print(
            json.dumps(
                {
                    **result.stats,
                    "review_index": str(paths["review_index"]),
                    "manifest": str(paths["manifest"]),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "discover-field-semantics":
        facts = read_json_facts(args.facts_dir)
        config = load_field_semantic_config(args.config)
        result = run_field_semantics(facts, config)
        paths = write_field_semantic_results(
            args.output,
            result,
            facts,
            config=config,
            investigation_queries=tuple(args.investigation_query),
        )
        print(
            json.dumps(
                {
                    **result.stats,
                    "semantic_shape_gate": result.quality_gate["status"],
                    "root": str(paths["manifest"].parent),
                    "manifest": str(paths["manifest"]),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "build-context-semantic-map":
        config = load_context_map_config(args.config)
        result = run_context_map(config)
        paths = write_context_map_results(args.output, result, config)
        print(
            json.dumps(
                {
                    **result.stats,
                    "model_gate": result.quality_gate["status"],
                    "root": str(paths["manifest"].parent),
                    "manifest": str(paths["manifest"]),
                    "investigation_card": str(paths["investigation_card"]),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "build-indicator-catalog-review":
        result = build_indicator_catalog(args.snapshot_dir, args.output)
        print(
            json.dumps(
                {
                    key: str(value) if isinstance(value, Path) else value
                    for key, value in result.items()
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "build-table-semantic-map":
        config = load_table_semantic_config(args.config)
        result = run_table_semantic_map(config)
        paths = write_table_semantic_results(args.output, result, config)
        print(
            json.dumps(
                {
                    **result.stats,
                    "model_gate": result.quality_gate["status"],
                    "root": str(paths["manifest"].parent),
                    "manifest": str(paths["manifest"]),
                    "investigation_cards": str(paths["investigation_cards"]),
                    "review_index": str(paths.get("review_index", "NOT_BUILT")),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "import-context-semantic-review":
        stats = import_review_decisions(
            args.review_pack_dir,
            args.responses,
            args.output,
            model_id=args.model_id,
        )
        print(json.dumps({**stats, "output": str(args.output)}, ensure_ascii=False))
        return 0

    if args.command == "prepare-field-concept-llm-review":
        config = load_review_config(args.config).with_run_limits(
            max_packs=args.max_packs,
            token_budget=args.token_budget,
        )
        paths = prepare_review(args.field_concepts_dir, config, args.output)
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "root": str(paths["root"]),
                    "packs": str(paths["packs"]),
                    "batch": str(paths["batch"]),
                    "manifest": str(paths["manifest"]),
                    **manifest["stats"],
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "import-field-concept-llm-review":
        stats = import_review_responses(
            args.review_dir,
            args.responses,
            model_id=args.model_id,
            cache_dir=args.cache_dir,
        )
        print(json.dumps(stats, ensure_ascii=False))
        return 0

    if args.command == "render-field-concept-llm-review":
        path = render_field_concept_llm_review(
            args.review_dir,
            source_panorama_root=args.source_panorama_root,
        )
        print(json.dumps({"review_index": str(path)}, ensure_ascii=False))
        return 0

    if args.command == "reconcile":
        scope = load_scope(args.scope)
        facts = read_json_facts(args.facts_dir)
        baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
        if not isinstance(baseline, dict):
            raise ValueError("baseline JSON must be an object")
        report = reconcile_facts(
            scope,
            facts,
            baseline,
            delivery_ready=(
                panorama_delivery_ready(args.render_dir) if args.render_dir else False
            ),
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(report, ensure_ascii=False))
        return 0

    if args.command == "render":
        scope = load_scope(args.scope)
        facts = read_json_facts(args.facts_dir)
        derived = derive_observations(facts)
        paths = render_panorama(
            scope,
            facts,
            derived,
            args.output,
            scope_config_sha256=hashlib.sha256(args.scope.read_bytes()).hexdigest(),
            code_version=args.code_version,
        )
        print(
            json.dumps(
                {
                    "schema_page_count": len(paths["schema_pages"]),
                    "object_card_count": len(paths["object_cards"]),
                    "index": str(paths["index"]),
                    "manifest": str(paths["manifest"]),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "baseline":
        scope = load_scope(args.scope)
        baseline = build_independent_baseline(
            scope,
            python_executable=args.adapter_python,
            query_script=args.adapter_script,
            database=args.db,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "baseline_kind": baseline["baseline_kind"],
                    "object_count": len(baseline["objects"]),
                    "schema_count": len(baseline["columns"]),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "select-sample":
        facts = read_json_facts(args.facts_dir)
        sample = select_tradeflow_sample(
            facts,
            max_objects=args.max_objects,
            exclude_numeric_suffix=not args.include_numeric_suffix,
        )
        write_sample(str(args.output), sample)
        print(
            json.dumps(
                {
                    "sample_id": sample["sample_id"],
                    "selected_object_count": len(sample["selected_objects"]),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "deep-derive":
        facts = read_json_facts(args.facts_dir)
        sample = load_sample(str(args.sample))
        derived = derive_tradeflow_features(facts, sample)
        paths = write_json_tradeflow_derived(args.output, derived)
        print(
            json.dumps(
                {
                    "sample_object_count": len(derived.sample_objects),
                    "column_feature_count": len(derived.column_features),
                    "object_feature_count": len(derived.object_features),
                    "similarity_count": len(derived.structure_similarity),
                    "outputs": {name: str(path) for name, path in paths.items()},
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "deep-infer":
        facts = read_json_facts(args.facts_dir)
        sample = load_sample(str(args.sample))
        derived = derive_tradeflow_features(facts, sample)
        inference = infer_tradeflow(
            facts, derived, case_id=str(sample.get("case_id", "tradeflow"))
        )
        paths = write_json_tradeflow_inference(args.output, inference)
        print(
            json.dumps(
                {
                    "identity_candidate_count": len(inference.identity_candidates),
                    "grain_candidate_count": len(inference.grain_candidates),
                    "field_role_candidate_count": len(inference.field_role_candidates),
                    "object_role_candidate_count": len(
                        inference.object_role_candidates
                    ),
                    "relation_candidate_count": len(inference.relation_candidates),
                    "inference_result_count": len(inference.inference_results),
                    "evidence_item_count": len(inference.evidence_items),
                    "candidate_evidence_count": len(inference.candidate_evidence),
                    "outputs": {name: str(path) for name, path in paths.items()},
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "deep-evaluate":
        inference = load_inference_directory(args.inference_dir)
        gold_set = load_yaml_mapping(args.gold_set)
        reviews = load_yaml_mapping(args.reviews)
        measurements = (
            load_yaml_mapping(args.measurements) if args.measurements else None
        )
        report = evaluate_tradeflow(inference, gold_set, reviews, measurements)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "gate_b_status": report["gate_b"]["status"],
                    "gate_b_scope": report["gate_b"]["scope"],
                    "gold_set_status": report["gold_set_status"],
                    "adjudicated_case_count": report["adjudicated_case_count"],
                    "unknown_result_count": report["evidence_quality"][
                        "unknown_result_count"
                    ],
                    "business_acceptance_status": report["business_acceptance"][
                        "status"
                    ],
                    "scale_authorization_status": report["scale_authorization"][
                        "status"
                    ],
                    "v1c_authorized": report["v1c_authorized"],
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "deep-review-pack":
        report = json.loads(args.evaluation_report.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("evaluation report must be a mapping")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_review_pack(report), encoding="utf-8")
        print(
            json.dumps(
                {
                    "gate_b_status": report.get("gate_b", {}).get("status"),
                    "gate_b_scope": report.get("gate_b", {}).get(
                        "scope", "STRUCTURAL_REGRESSION_ONLY"
                    ),
                    "business_acceptance_status": report.get(
                        "business_acceptance", {}
                    ).get("status", "NOT_ACCEPTED"),
                    "scale_authorization_status": report.get(
                        "scale_authorization", {}
                    ).get("status", "PROHIBITED"),
                    "v1c_authorized": False,
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "deep-measure-pack":
        measurements = load_yaml_mapping(args.measurements)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_measurement_pack(measurements), encoding="utf-8")
        print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
        return 0

    scope = load_scope(args.scope)
    if args.input_json:
        metadata = _load_metadata_json(args.input_json)
    else:
        if not args.adapter_script:
            raise ValueError("--adapter-script is required when --db is used")
        provider = GfDerivativeDbProvider(
            python_executable=args.adapter_python,
            query_script=args.adapter_script,
            database=args.db,
            definition_mode=args.definition_mode,
        )
        metadata = provider.iter_objects(scope)
    written: dict[str, Path] = {}
    if args.format == "json":
        counts = {
            "object_count": 0,
            "column_count": 0,
            "constraint_count": 0,
            "index_count": 0,
            "definition_count": 0,
            "dependency_count": 0,
            "failure_count": 0,
        }

        def counted_batches():
            for batch in iter_fact_batches(
                scope,
                metadata,
                run_id=args.run_id,
                batch_size=args.batch_size,
            ):
                counts["object_count"] += len(batch.objects)
                counts["column_count"] += len(batch.columns)
                counts["constraint_count"] += len(batch.constraints)
                counts["index_count"] += len(batch.indexes)
                counts["definition_count"] += len(batch.object_definitions)
                counts["dependency_count"] += len(batch.dependencies)
                counts["failure_count"] += len(batch.failures)
                yield batch

        written.update(write_json_fact_batches(args.output, counted_batches()))
    else:
        facts = extract_facts(
            scope,
            metadata,
            run_id=args.run_id,
        )
        counts = {
            "object_count": len(facts.objects),
            "column_count": len(facts.columns),
            "constraint_count": len(facts.constraints),
            "index_count": len(facts.indexes),
            "definition_count": len(facts.object_definitions),
            "dependency_count": len(facts.dependencies),
            "failure_count": len(facts.failures),
        }
        if args.format == "both":
            written.update(write_json_facts(args.output, facts))
        written.update(write_parquet_facts(args.output, facts))
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                **counts,
                "outputs": {name: str(path) for name, path in written.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
