import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from crawl_szdata_downstream import can_expand


def node(name: str, db_name: str = "") -> dict[str, str]:
    return {
        "guid": name,
        "name": name,
        "type_name": "hive_table",
        "db_name": db_name,
    }


def test_unresolved_table_does_not_expand() -> None:
    assert not can_expand(node("unknown_table"), "", "dm_", "dm_otc_n")


def test_resolved_non_dm_table_expands() -> None:
    assert can_expand(node("ods_table", "ods_n"), "", "dm_", "dm_otc_n")


def test_other_dm_stops_but_dm_otc_n_passes_through() -> None:
    assert not can_expand(node("dm_table", "dm_rsk_n"), "", "dm_", "dm_otc_n")
    assert can_expand(node("otc_table", "dm_otc_n"), "", "dm_", "dm_otc_n")
