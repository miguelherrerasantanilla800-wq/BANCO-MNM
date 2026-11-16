import json
from pathlib import Path

import pytest

from publish_dashboard import build_dashboard


def write_parts(directory: Path, content: str) -> None:
    directory.mkdir(parents=True)
    (directory / "part-00000").write_text(content, encoding="utf-8")


def test_build_dashboard_aggregates_gold_and_checks_record_counts(tmp_path):
    gold_dir = tmp_path / "gold"
    write_parts(gold_dir / "job1_categoria", "mercado\t250.00\t2\nsalud\t50.00\t1\n")
    write_parts(gold_dir / "job2_fraude", "Bogota\t3\nCali\t1\n")
    write_parts(gold_dir / "job3_clientes", "7\t200.00\t2\n3\t100.00\t1\n")
    write_parts(gold_dir / "job4_mensual", "2026-01\tweb\t100.00\t2\n2026-02\tapp\t200.00\t2\n")
    quality_report = tmp_path / "quality_report.json"
    quality_report.write_text(
        json.dumps(
            {"input_records": 4, "valid_records": 4, "rejected_records": 0}
        ),
        encoding="utf-8",
    )

    result = build_dashboard(gold_dir, quality_report)

    assert result["quality"]["valid_records"] == 4
    assert result["approved"] == {"amount_cop": 300.0, "transactions": 3}
    assert result["fraud"]["transactions"] == 4
    assert result["customers"]["with_approved_activity"] == 2
    assert result["customers"]["top"][0]["customer_id"] == 7
    assert sum(row["transactions"] for row in result["monthly_channel"]) == 4


def test_build_dashboard_rejects_incomplete_monthly_gold(tmp_path):
    gold_dir = tmp_path / "gold"
    write_parts(gold_dir / "job1_categoria", "mercado\t250.00\t2\n")
    write_parts(gold_dir / "job2_fraude", "")
    write_parts(gold_dir / "job3_clientes", "7\t250.00\t2\n")
    write_parts(gold_dir / "job4_mensual", "2026-01\tweb\t100.00\t1\n")
    quality_report = tmp_path / "quality_report.json"
    quality_report.write_text(
        json.dumps(
            {"input_records": 2, "valid_records": 2, "rejected_records": 0}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="do not cover all valid Silver records"):
        build_dashboard(gold_dir, quality_report)
