from pathlib import Path

from titans_cognition.scope import load_scope


PROJECT_ROOT = Path(__file__).parents[1]


def test_panorama_scope_contains_only_confirmed_non_prod_titans_schemas():
    scope = load_scope(PROJECT_ROOT / "cases" / "titans-panorama" / "scope.yaml")

    assert scope.scope_id == "titans-panorama-v1"
    assert "TITANS_TRADEFLOW" in scope.schemas
    assert "TITANS_DM" in scope.schemas
    assert all(not schema.endswith("_PROD") for schema in scope.schemas)
    assert scope.object_types == (
        "TABLE",
        "VIEW",
        "MATERIALIZED_VIEW",
        "SYNONYM",
    )


def test_scope_rejects_prod_schema_even_if_provider_returns_it():
    scope = load_scope(PROJECT_ROOT / "cases" / "titans-panorama" / "scope.yaml")

    assert scope.accepts_schema("TITANS_DM")
    assert not scope.accepts_schema("TITANS_DM_PROD")
    assert not scope.accepts_schema("GF_OTC")
