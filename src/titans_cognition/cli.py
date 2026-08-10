"""Command-line entry points for the deterministic cognition core."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .baseline import build_independent_baseline
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
from .extract import (
    ColumnMetadata,
    ConstraintMetadata,
    DefinitionMetadata,
    DependencyMetadata,
    IndexMetadata,
    ObjectMetadata,
    extract_facts,
)
from .io import (
    read_json_facts,
    write_json_derived,
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
        raise ValueError("metadata JSON must be a list or an object with an objects list")
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
    derive = subparsers.add_parser("derive")
    derive.add_argument("--input-dir", required=True, type=Path)
    derive.add_argument("--output", required=True, type=Path)
    derive.add_argument(
        "--format",
        choices=("json", "parquet", "both"),
        default="json",
    )
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
    deep_evaluate.add_argument("--output", required=True, type=Path)
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
                panorama_delivery_ready(args.render_dir)
                if args.render_dir
                else False
            ),
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
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
            json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
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
        inference = infer_tradeflow(facts, derived, case_id=str(sample.get("case_id", "tradeflow")))
        paths = write_json_tradeflow_inference(args.output, inference)
        print(
            json.dumps(
                {
                    "identity_candidate_count": len(inference.identity_candidates),
                    "grain_candidate_count": len(inference.grain_candidates),
                    "field_role_candidate_count": len(inference.field_role_candidates),
                    "object_role_candidate_count": len(inference.object_role_candidates),
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
        report = evaluate_tradeflow(inference, gold_set, reviews)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "gate_b_status": report["gate_b"]["status"],
                    "gold_set_status": report["gold_set_status"],
                    "adjudicated_case_count": report["adjudicated_case_count"],
                    "unknown_result_count": report["evidence_quality"]["unknown_result_count"],
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
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
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
    facts = extract_facts(
        scope,
        metadata,
        run_id=args.run_id,
    )
    written: dict[str, Path] = {}
    if args.format in ("json", "both"):
        written.update(write_json_facts(args.output, facts))
    if args.format in ("parquet", "both"):
        written.update(write_parquet_facts(args.output, facts))
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "object_count": len(facts.objects),
                "column_count": len(facts.columns),
                "constraint_count": len(facts.constraints),
                "index_count": len(facts.indexes),
                "dependency_count": len(facts.dependencies),
                "failure_count": len(facts.failures),
                "outputs": {name: str(path) for name, path in written.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
