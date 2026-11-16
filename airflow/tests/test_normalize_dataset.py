import importlib.util
import io
import json
from pathlib import Path

import pytest


NORMALIZER_PATH = Path(__file__).parents[1] / "dags" / "utils" / "normalize_dataset.py"
SPEC = importlib.util.spec_from_file_location("normalize_dataset", NORMALIZER_PATH)
NORMALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NORMALIZER)


def transaction(transaction_id, **overrides):
    record = {
        "transaction_id": transaction_id,
        "fecha_hora": "2026-05-31 04:42:20",
        "customer_id": 42,
        "merchant": "Market",
        "categoria": "Alimentos",
        "monto_cop": 1250,
        "metodo_pago": "PSE",
        "ciudad": "Bogota",
        "canal": "Web",
        "estado": "Aprobada",
        "fraude": 0,
    }
    record.update(overrides)
    return record


def test_normalizes_array_and_handles_records_across_buffer_chunks(tmp_path):
    source = tmp_path / "source.json"
    output = tmp_path / "dataset.jsonl"
    records = [
        transaction(1, merchant=" " + "A" * 70_000 + " "),
        transaction(2, estado=" aprobada ", fraude="1"),
    ]
    source.write_text(json.dumps(records), encoding="utf-8")

    count = NORMALIZER.normalize_dataset(source, output, expected_count=2)

    normalized = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert count == 2
    assert normalized[0]["merchant"] == "A" * 70_000
    assert normalized[1]["estado"] == "Aprobada"
    assert normalized[1]["fraude"] == 1


def test_removes_partial_output_when_record_count_does_not_match(tmp_path):
    source = tmp_path / "source.json"
    output = tmp_path / "dataset.jsonl"
    source.write_text(json.dumps([transaction(1)]), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected 2 records, found 1"):
        NORMALIZER.normalize_dataset(source, output, expected_count=2)

    assert not output.exists()


def test_normalizes_json_array_from_standard_input(tmp_path):
    output = tmp_path / "dataset.jsonl"

    count = NORMALIZER.normalize_dataset(
        io.StringIO(json.dumps([transaction(1)])),
        output,
        expected_count=1,
    )

    assert count == 1
    assert json.loads(output.read_text(encoding="utf-8"))["transaction_id"] == 1


def test_quarantines_invalid_and_duplicate_rows_and_writes_quality_report(tmp_path):
    source = tmp_path / "source.json"
    output = tmp_path / "dataset.jsonl"
    quarantine = tmp_path / "quarantine.jsonl"
    report = tmp_path / "quality_report.json"
    records = [
        transaction(1),
        transaction(1, ciudad="Medellin"),
        transaction(2, fecha_hora="not-a-date"),
    ]
    source.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="Rejected 2 of 3 records"):
        NORMALIZER.normalize_dataset(
            source,
            output,
            expected_count=3,
            quarantine_path=quarantine,
            quality_report_path=report,
        )

    quality = json.loads(report.read_text(encoding="utf-8"))
    rejected = [json.loads(line) for line in quarantine.read_text(encoding="utf-8").splitlines()]
    assert quality["input_records"] == 3
    assert quality["valid_records"] == 1
    assert quality["rejected_records"] == 2
    assert quality["rejection_reasons"] == {
        "duplicate transaction_id": 1,
        "fecha_hora must use YYYY-MM-DD HH:MM:SS": 1,
    }
    assert [row["row_number"] for row in rejected] == [2, 3]
    assert not output.exists()
