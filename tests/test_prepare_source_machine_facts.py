from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "prepare_source_machine_facts.py"
SPEC = importlib.util.spec_from_file_location("prepare_source_machine_facts", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_task_output_tables_uses_table_task_associations() -> None:
    rows = [
        {
            "db_name": "odata_n_tit",
            "table_name": "d_ref_otc_option_deal",
            "task_ids": ["78472", "78472"],
        },
        {
            "db_name": "odata_n_tit",
            "table_name": "d_ref_option_deal_structure",
            "task_ids": ["86840"],
        },
        {
            "db_name": "",
            "table_name": "ignored",
            "task_ids": ["99999"],
        },
    ]

    assert MODULE.task_output_tables(rows) == {
        "78472": ["odata_n_tit.d_ref_otc_option_deal"],
        "86840": ["odata_n_tit.d_ref_option_deal_structure"],
    }
