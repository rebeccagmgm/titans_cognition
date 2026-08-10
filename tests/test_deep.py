from titans_cognition.deep import derive_tradeflow_features, select_tradeflow_sample
from titans_cognition.extract import PhysicalFacts


def _facts() -> PhysicalFacts:
    objects = []
    columns = []
    constraints = []
    indexes = []
    for name, stratum, width in (
        ("A_COMPOSITE", "PK_COMPOSITE", 2),
        ("B_SINGLE", "PK_SINGLE", 1),
        ("C_UNIQUE", "UK_ONLY", 1),
        ("D_INDEX", "NO_KEY_WITH_INDEX", 1),
        ("E_NONE", "NO_DECLARED_KEY", 1),
        ("F_PEER", "NO_DECLARED_KEY", 1),
    ):
        asset = f"testdb:TITANS_TRADEFLOW:TABLE:{name}"
        objects.append(
            {
                "run_id": "run-1",
                "asset_id": asset,
                "schema_name": "TITANS_TRADEFLOW",
                "object_name": name,
                "object_type": "TABLE",
                "extraction_status": "SUCCESS",
                "is_boundary": False,
            }
        )
        for ordinal in range(1, width + 1):
            columns.append(
                {
                    "asset_id": asset,
                    "column_id": f"{asset}:COLUMN:ID{ordinal}",
                    "column_name": f"ID{ordinal}",
                    "ordinal_position": ordinal,
                    "data_type": "NUMBER",
                    "nullable_declared": False,
                }
            )
        if stratum == "PK_COMPOSITE":
            constraints.append(
                {
                    "asset_id": asset,
                    "constraint_type": "PRIMARY_KEY",
                    "column_ids": [f"{asset}:COLUMN:ID1", f"{asset}:COLUMN:ID2"],
                }
            )
        elif stratum == "PK_SINGLE":
            constraints.append(
                {
                    "asset_id": asset,
                    "constraint_type": "PRIMARY_KEY",
                    "column_ids": [f"{asset}:COLUMN:ID1"],
                }
            )
        elif stratum == "UK_ONLY":
            constraints.append(
                {
                    "asset_id": asset,
                    "constraint_type": "UNIQUE_KEY",
                    "column_ids": [f"{asset}:COLUMN:ID1"],
                }
            )
        elif stratum == "NO_KEY_WITH_INDEX":
            indexes.append(
                {
                    "asset_id": asset,
                    "index_id": f"{asset}:INDEX:I1",
                    "column_ids": [f"{asset}:COLUMN:ID1"],
                }
            )
    return PhysicalFacts(
        objects=objects,
        columns=columns,
        constraints=constraints,
        indexes=indexes,
    )


def test_tradeflow_sample_is_stratified_and_deterministic():
    first = select_tradeflow_sample(_facts())
    second = select_tradeflow_sample(_facts())
    assert first == second
    assert {row["stratum"] for row in first["selected_objects"]} == {
        "PK_COMPOSITE",
        "PK_SINGLE",
        "UK_ONLY",
        "NO_KEY_WITH_INDEX",
        "NO_DECLARED_KEY",
    }
    composite = next(
        row for row in first["selected_objects"] if row["stratum"] == "PK_COMPOSITE"
    )
    assert composite["object_name"] == "A_COMPOSITE"


def test_tradeflow_features_keep_unknown_business_meaning_out():
    sample = select_tradeflow_sample(_facts())
    derived = derive_tradeflow_features(_facts(), sample)
    assert derived.object_features
    assert derived.column_features
    assert derived.structure_similarity
    assert all("identity" not in row for row in derived.object_features)
    assert all(row["method_id"].startswith("feature.") for row in derived.column_features)
